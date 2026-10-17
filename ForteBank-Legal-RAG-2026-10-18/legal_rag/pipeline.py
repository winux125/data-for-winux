"""One serialized worker: structured facts -> retrieval -> norms -> decision -> explanation.

No video, classifier outputs or external model APIs are accepted here. Models are
resident within this worker; FakeGenerator is dependency injection for tests only.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
from pathlib import Path
import threading
import time

from .apply import (Scope, apply_card, basis_allowed, card_scopes, decide, reading_states,
                    validate_reading)
from .config import load_config
from .contracts import (LegalAssessment, NormAssessment, NormRef, ObservationBundle,
                        parse_input, validate_output)
from .describe import _clock
from .generate import generation_record, make_generator, parse_json_object
from .prompts import explanation_prompt, reading_prompt
from .retrieve import Retriever
from .source_packet import PacketOverflow, SourcePacketBuilder
from .tokens import TokenCounter, default_counter
from .validate import render, template_sentences, validate_explanation


class GeneratorCounter(TokenCounter):
    def __init__(self, generator):
        self.generator = generator
        self.name = generator.name
        self.exact = generator.is_real_model

    def count(self, text):
        return self.generator.count_tokens(text)


class LegalRAGRuntime:
    def __init__(self, rag, config=None, *, generator=None, embedder=None, dense=None,
                 index_dir=None, template_only=False):
        self.rag, self.config = rag, (config or load_config()).validate()
        self.generator, self.embedder, self.dense = generator, embedder, dense
        self.index_dir, self.template_only = index_dir, template_only
        self._lock = threading.RLock()
        self._ready = False
        self.load_ms = 0.0
        self.memory_start = None
        self._packet_ms = 0.0

    def warm(self):
        with self._lock:
            if self._ready:
                return self
            started = time.perf_counter()
            self.rag.warm()
            config = self.config
            need_dense = config.retrieval.mode != 'bm25'
            if config.reranker is not None and config.reranker.enabled:
                raise ValueError('Reranker is an optional experiment and is not implemented; disable it')
            neural_cuda = ((need_dense and self.embedder is None and config.embedder.device.startswith('cuda')) or
                           (not self.template_only and self.generator is None and config.generator.device.startswith('cuda')))
            if neural_cuda:
                from .resources import cuda_preflight
                self.memory_start = cuda_preflight(config)
            if need_dense and self.dense is None:
                from .embed import DEFAULT_INDEX_DIR, expected_descriptor, load_index, make_embedder
                from .dense import DenseIndex
                flat, ids, self.index_manifest = load_index(
                    self.rag.source_library(), self.index_dir or DEFAULT_INDEX_DIR,
                    expected_descriptor(config.embedder))
                self.embedder = self.embedder or make_embedder(config.embedder)
                self.dense = DenseIndex(flat, ids, self.index_manifest['dims'],
                                        config.embedder.device, config.embedder.dtype)
            if need_dense and self.embedder is None:
                raise ValueError('Dense retrieval needs a query embedder')
            if not self.template_only and self.generator is None:
                self.generator = make_generator(config.generator)
            self.counter = GeneratorCounter(self.generator) if self.generator else default_counter()
            self.retriever = Retriever(self.rag, self.dense, self.embedder, config.retrieval.rrf_k,
                                       config.retrieval.candidates_per_retriever)
            self.packer = SourcePacketBuilder(self.rag.source_library(), self.rag.corpus,
                                              self.rag.refs, self.counter)
            self.load_ms = (time.perf_counter() - started) * 1000
            self._ready = True
            return self

    def _call(self, builder, validator, max_tokens):
        errors, records = [], []
        for attempt in range(2):
            system, user = builder(errors)
            try:
                generation = self.generator.chat(system, user, max_tokens)
                record = generation_record(generation)
                record['attempt'] = attempt + 1
                records.append(record)
                if hasattr(self, '_call_records'):
                    self._call_records.append(record)
                if generation.finish == 'length':
                    raise ValueError('Model answer reached the output limit; incomplete answers are rejected')
                raw = parse_json_object(generation.text)
                value, errors = validator(raw)
                if not errors:
                    return value, dict(valid=True, attempts=records, errors=[])
            except (ValueError, TypeError, KeyError, IndexError) as exc:
                errors = [f'{type(exc).__name__}: {exc}']
        return None, dict(valid=False, attempts=records, errors=errors)

    def _packet(self, ids):
        started = time.perf_counter()
        try:
            return self.packer.build(ids, self.config.packet.budget_tokens)
        finally:
            self._packet_ms += (time.perf_counter() - started) * 1000

    def _assess(self, bundle, unit_id, card=None, scope=None):
        validation = {}
        nodes = [unit_id]
        if card:
            for cid in card.clause_ids + card.related_clause_ids:
                sid, number = cid.split(':')
                node = f'{sid}:rules1:p{number}'
                if node not in nodes:
                    nodes.append(node)
        try:
            packet = self._packet(nodes)
            parent = next(i for i in packet['items'] if i['node_id'] == unit_id)
            completeness = dict(packet['completeness'][unit_id])
            if card and any(not c['complete'] for c in packet['completeness'].values()):
                completeness['complete'] = False
                completeness['incomplete_reasons'] = list(completeness['incomplete_reasons']) + ['card_context_incomplete']
        except PacketOverflow as exc:
            parent = self.packer._item(unit_id, 'parent', 'parent exceeds budget; not sent to the model')
            packet = dict(items=[parent], omitted=[], used_tokens=0, token_counter=self.counter.describe())
            completeness = dict(complete=False, incomplete_reasons=['parent_exceeds_token_budget'])
            validation['packet'] = str(exc)
        if bundle.context.organization_type == 'unknown':
            completeness['complete'] = False
            completeness['incomplete_reasons'] = list(completeness.get('incomplete_reasons', [])) + ['organization_unknown']
        context = [i for i in packet['items'] if i['node_id'] != unit_id]
        reading = None
        if card:
            items, mapping, modality = apply_card(card, bundle, scope)
            requirement = parent['text'].strip()
            requirement_source = 'card'
            validation['call_a'] = dict(skipped=True, reason='explicit_card_mapping')
        elif self.generator is not None and 'packet' not in validation:
            def check(raw):
                result = validate_reading(raw, parent, context, bundle)
                return result, result.errors
            reading, validation['call_a'] = self._call(
                lambda e: reading_prompt(parent, context, bundle, e), check,
                self.config.generator.max_new_tokens)
            if reading is not None and not reading.relevant:
                return None, validation
            items = reading.items if reading else []
            mapping = reading_states(reading, bundle) if reading else []
            modality = reading.modality if reading else 'obligation'
            requirement = reading.requirement if reading else parent['text'].strip()
            requirement_source = 'llm_reading_validated' if reading else 'reading_failed'
        else:
            items, mapping, modality = [], [], 'obligation'
            requirement, requirement_source = parent['text'].strip(), 'unread'
            validation['call_a'] = dict(skipped=True, reason='template_only_or_packet_overflow')
        # Conditions must describe one operation. Equal truth values across different
        # operations do not establish a single breach.
        cited = [bundle.fact(fid) for m in mapping for fid in m.fact_ids]
        operations = {f.operation_id for f in cited if f and f.operation_id is not None}
        if len(operations) > 1:
            completeness['complete'] = False
            completeness['incomplete_reasons'] = list(completeness.get('incomplete_reasons', [])) + ['mixed_operation_scopes']
        decision, reasons = decide(items, mapping, completeness, basis_allowed(parent), modality)
        if card and bundle.context.organization_type not in ('bank', 'postal_operator', 'unknown'):
            decision, reasons = 'not_applicable_scope', ['bank_cashier_card_organization_mismatch']
        source = self.rag.source_library().sources[parent['source_id']]
        norm = NormRef(unit_id, parent['source_id'], parent['title'], parent['official_url'],
                       parent['citation_level'], parent['label'], parent['text'], parent['text_sha256'],
                       tuple(parent['lines']), parent['status'], source.get('raw_revision_value'))
        result = NormAssessment(norm, modality, items, mapping, decision,
                                [m.item_id for m in mapping if m.state == 'unknown'],
                                requirement_source, completeness, rule_id=card.rule_id if card else None,
                                decision_reasons=reasons, validation=validation)
        result.validation['packet'] = dict(used_tokens=packet['used_tokens'],
                                          token_counter=packet['token_counter'], omitted=packet['omitted'])
        result.supporting_norms = [{k: v for k, v in item.items() if k != 'tokens'}
                                   for item in packet['items'] if item['node_id'] != unit_id]
        ctx = self._explanation_context(result, requirement, reading, packet, bundle)
        if self.generator is not None:
            sentences, record = self._call(lambda e: explanation_prompt(ctx, e),
                                           lambda raw: validate_explanation(raw, ctx, bundle),
                                           min(self.config.generator.max_new_tokens,
                                               self.config.packet.answer_reserve_tokens))
            result.validation['call_b'] = record
        else:
            sentences = None
            result.validation['call_b'] = dict(skipped=True, reason='template_only')
        if sentences is None:
            # The fallback quotes the actual norm, never the failed/free-form reading.
            fallback = dict(ctx, requirement='«' + parent['text'].strip() + '»')
            sentences = template_sentences(fallback, bundle)
            result.generator = 'template_fallback'
        else:
            result.generator = self.generator.name
        result.sentences = sentences
        result.evidence = [dict(fact_id=f['fact_id'], status=f['status'], clock=f['clock'],
                                evidence_refs=list(bundle.fact(f['fact_id']).evidence_refs)) for f in ctx['facts']]
        citation_items = [parent]
        if reading:
            cited_nodes = {node for node, _, _ in reading.exception_sources.values()}
            citation_items += [i for i in context if i['node_id'] in cited_nodes]
        elif card:
            cited_nodes = {f'{e.source_clause_id.split(":")[0]}:rules1:p{e.source_clause_id.split(":")[1]}'
                           for e in card.exceptions}
            citation_items += [i for i in context if i['node_id'] in cited_nodes]
        citation = '; '.join(f'{i["title"]}' + (f', {i["label"]}' if i['label'] else '') + f' — {i["official_url"]}'
                             for i in citation_items)
        retrieved = source.get('retrieved_utc') or source.get('retrieved_at')
        dates = [retrieved[:10]] if retrieved else []
        result.explanation_text = render(sentences, citation, result.evidence, dates)
        if card:
            allowed = (decision == 'violation_supported' and card.review.human_reviewed and card.review.production_active)
            reason = None if allowed else ('rule_not_production_active' if decision == 'violation_supported' else 'decision_' + decision)
        else:
            allowed, reason = False, 'general_norm_reading_requires_review'
        if self.template_only or (self.generator and not self.generator.is_real_model):
            allowed, reason = False, 'test_or_template_backend'
        result.publishable = dict(allowed=allowed, reason=reason, analysis_only=not allowed)
        if card:
            result.publishable['review'] = asdict(card.review)
        return result, validation

    def _explanation_context(self, assessment, requirement, reading, packet, bundle):
        states = {m.item_id: m for m in assessment.mapping}
        facts = {fid for m in assessment.mapping for fid in m.fact_ids}
        # An unread norm still needs an honest observation in its explanation.
        if not facts:
            facts = {f.fact_id for f in bundle.facts if f.status != 'unknown'}
        rows = [dict(fact_id=f.fact_id, statement=f.statement, status=f.status,
                     clock=_clock(f.anchor_sec if f.anchor_sec is not None else f.t_start)
                     if f.anchor_sec is not None or f.t_start is not None else None)
                for f in bundle.facts if f.fact_id in facts]
        spans = {'norm': assessment.norm.quote}
        by_node = {i['node_id']: i for i in packet['items']}
        if reading:
            spans.update({key: by_node[node]['text'][start:end]
                          for key, (node, start, end) in reading.exception_sources.items()})
        items = [dict(asdict(i), state=states[i.item_id].state, fact_ids=list(states[i.item_id].fact_ids))
                 for i in assessment.items]
        return dict(decision=assessment.decision, modality=assessment.modality, requirement=requirement,
                    spans=spans, items=items, facts=rows,
                    decided_fact_ids=[f['fact_id'] for f in rows if f['status'] != 'unknown'])

    def analyze(self, raw):
        # Re-parse even a dataclass: callers cannot bypass input validation by constructing one.
        bundle = parse_input(raw.to_dict() if isinstance(raw, ObservationBundle) else raw)
        with self._lock:
            self.warm()
            self._call_records = []
            self._packet_ms = 0.0
            started = time.perf_counter()
            rc = self.config.retrieval
            retrieval = self.retriever.retrieve(bundle, rc.mode, rc.use_lexicon, rc.top_k, rc.tiers)
            assessments, skipped, seen = [], [], set()
            for hit in retrieval['card_candidates']:
                card = self.rag.cards[hit['rule_id']]
                # All primary clauses of a multi-clause card are one analysis, not duplicates.
                key = (card.rule_id, hit['unit_id'])
                if key in seen:
                    continue
                seen.add(key)
                for scope in card_scopes(card, bundle):
                    result, record = self._assess(bundle, hit['unit_id'], card, scope)
                    result.validation['scope'] = asdict(scope)
                    assessments.append(result)
            card_units = {hit['unit_id'] for hit in retrieval['card_candidates']}
            for hits in retrieval['tiers'].values():
                for hit in hits:
                    uid = hit['unit_id']
                    if uid in card_units or uid in seen:
                        continue
                    seen.add(uid)
                    # An existing draft card must not be bypassed by re-reading its norm.
                    has_card = any(uid == f'{cid.split(":")[0]}:rules1:p{cid.split(":")[1]}'
                                   for card in self.rag.cards.values() for cid in card.clause_ids)
                    if has_card:
                        skipped.append(dict(unit_id=uid, reason='card_not_triggered'))
                        continue
                    result, record = self._assess(bundle, uid)
                    if result:
                        assessments.append(result)
                    else:
                        skipped.append(dict(unit_id=uid, reason='call_a_not_relevant', validation=record))
            result = LegalAssessment(bundle.bundle_id, assessments)
            if not assessments:
                result.no_norm = dict(decision='no_norm', reason='No applicable norm among the checked candidates',
                                      exhaustive=False, skipped=skipped)
            result.versions = dict(config=self.config.to_dict(), parser=self.rag.source_library().summary()['parser_version'],
                                   retrieval=retrieval, generator=self.generator.describe() if self.generator else
                                   dict(name='template_only', is_real_model=False),
                                   index={k: v for k, v in self.index_manifest.items()
                                          if k not in ('chunk_ids', 'text_sha256')}
                                   if hasattr(self, 'index_manifest') else None,
                                   cards_sha256=self.rag.manifest()['cards_sha256'],
                                   lexicon_sha256=self.rag.manifest()['lexicon_sha256'],
                                   library_manifest_sha256=hashlib.sha256(self.rag.source_library().path.read_bytes()).hexdigest(),
                                   code_sha256=self.rag.manifest()['code_sha256'])
            result.timings_ms = dict(load=round(self.load_ms, 2), retrieval=retrieval['timing_ms'],
                                     retrieval_stages={k: round(v, 3) for k, v in self.retriever.timings.items()},
                                     packet=round(self._packet_ms, 2),
                                     total=round((time.perf_counter() - started) * 1000, 2))
            calls = self._call_records
            result.tokens = dict(input=sum(g['input_tokens'] for g in calls), output=sum(g['output_tokens'] for g in calls),
                                 model_calls=len(calls), template_fallbacks=sum(a.generator == 'template_fallback' for a in assessments))
            from .resources import memory_snapshot
            result.versions['memory'] = dict(before_models=self.memory_start, after_request=memory_snapshot())
            return validate_output(result, bundle)
