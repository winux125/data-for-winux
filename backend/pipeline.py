"""Transport around the supplied JEPA and RAG public APIs; no decision overrides."""
import hashlib
import dataclasses
import json
import logging
import sys
import time

from .settings import ROOT
from .video import metadata, sample
from .vision import VisualObserver
from .legal import assess, publishable_assessments, publishable_review_findings
from .detector import load_detector
from .contracts import append_citation
from .events import select_observations, action_type

sys.path.insert(0, str(ROOT / 'ForteBank-Legal-RAG-2026-10-18'))
if (ROOT / 'releases/legal-rag-mvp-v1/legal_rag').is_dir():
    sys.path.insert(0, str(ROOT / 'releases/legal-rag-mvp-v1'))
log = logging.getLogger(__name__)


class AnalysisUnavailable(ValueError):
    """A processing failure, never a third or a clean verdict."""
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def observation_bundle(events):
    actors, facts = [], []
    for index, event in enumerate(events):
        point = round(event['time'], 4)
        actor = f'actor{index}'
        refs = [f'frame:{f.timestamp:.4f}' for f in event['frames']]
        rows = [{'t_start': point, 't_end': point, 'anchor_sec': point, 'evidence_refs': refs,
                 **fact, 'fact_id': f'e{index}_f{i}', 'actor_id': actor, 'operation_id': f'event{index}'}
                for i, fact in enumerate(event['facts'])]
        facts.extend(rows)
        # IDs express scope within this observation, never biometric identity.
        role = event.get('actor_role', 'unknown')
        actors.append({'actor_id': actor, 'role': role,
                       'role_status': 'confirmed' if event['role_visible'] and role != 'unknown' else 'unknown',
                       'fact_ids': [f['fact_id'] for f in rows]})
    return {'schema': 'legal_rag.input.v1', 'bundle_id': 'video_observations',
            'context': {'organization_type': 'bank', 'event_date': None},
            'actors': actors, 'facts': facts,
            'provenance': {'source': 'local_visual_observer'}}


def event_for_assessment(assessment, events):
    operation = assessment.get('validation', {}).get('scope', {}).get('operation_id')
    if operation is not None:
        return next((e for i, e in enumerate(events) if operation == f'event{i}'), None)
    # General readings may omit scope. Map only unambiguous cited fact IDs.
    cited = {row['fact_id'].split('_')[0] for row in assessment.get('evidence', [])}
    matches = [e for i, e in enumerate(events) if f'e{i}' in cited]
    return matches[0] if len(matches) == 1 else None


def observation_windows(duration, peak):
    """Bounded sampling over the whole timeline plus one JEPA focus interval.

    Coverage is temporal sampling, not proof that every action was observed.
    """
    end = max(0., duration - .05)
    count = 12 if duration <= 24 else 24
    overview = [end * i / (count - 1) for i in range(count)]
    # Keep the whole overview in one model context: splitting at the midpoint
    # hides the beginning of service from a later departure.
    windows = [overview]
    if peak is not None:
        focus = sorted({max(0., min(end, peak + offset)) for offset in (-5, -3, -1, 0, 1, 3, 5)})
        windows.append(focus)
    return windows


def refinement_request(result, events, rag):
    """One unresolved card with an observed trigger; no legal verdict prompt."""
    for assessment in result.get('assessments', []):
        if assessment.get('decision') != 'insufficient' or not assessment.get('context_completeness', {}).get('complete'):
            continue
        card = rag.cards.get(assessment.get('rule_id'))
        if card is None:
            continue
        event = event_for_assessment(assessment, events)
        if event is None:
            continue
        if not any(f['predicate'] in card.trigger_predicates and f['status'] == 'confirmed' for f in event['facts']):
            continue
        if card.kind == 'omission':
            # Another sparse pass cannot prove continuous absence over an operation.
            continue
        questions = [{'id': i.id, 'question': i.question_ru} for i in card.conditions + card.exceptions]
        return events.index(event), {'anchor_sec': event['time'], 'questions': questions}
    return None


class Pipeline:
    def __init__(self):
        import torch
        from legal_rag import shared
        from legal_rag.config import load_config, ModelConfig
        from legal_rag.generate import QwenTextGenerator
        from legal_rag.pipeline import LegalRAGRuntime
        from legal_rag.embed import BgeM3Embedder, build_index
        if not torch.cuda.is_available():
            raise RuntimeError('CUDA GPU required for the five minute service')
        digest = hashlib.sha256()
        for file in sorted((ROOT / 'backend').glob('*.py')):
            digest.update(file.name.encode())
            digest.update(file.read_bytes())
        detector_settings = json.loads((ROOT / 'config/detector.json').read_text(encoding='utf-8'))
        for file in [ROOT / 'config/detector.json', ROOT / detector_settings['package_dir'] / 'model.json']:
            digest.update(file.relative_to(ROOT).as_posix().encode())
            digest.update(file.read_bytes())
        self.build_id = digest.hexdigest()[:16]
        torch.set_num_threads(8)
        self.jepa = load_detector()
        self.detector_version = self.jepa.spec['model_id']
        # Versioned, explicit policy; original incoming package remains archived intact.
        config = load_config(ROOT / 'config/rag-mvp.json')
        # Resolve the SAME pinned revisions to disk. Transformers 4.57 otherwise
        # tries a model-info request from AutoTokenizer despite local_files_only.
        from huggingface_hub import snapshot_download
        def on_disk(model):
            path = snapshot_download(model.model_id, revision=model.revision, local_files_only=True)
            return dataclasses.replace(model, model_id=path)
        config = dataclasses.replace(config, embedder=on_disk(config.embedder), generator=on_disk(config.generator))
        self.rag = shared()
        index = ROOT / 'data' / 'legal_index_stock'
        embedder = BgeM3Embedder(config.embedder)
        if not (index / 'manifest.json').exists():
            build_index(self.rag.source_library(), embedder, index)
        self.legal = LegalRAGRuntime(self.rag, config, embedder=embedder, index_dir=index).warm()
        # Separate visual observation adapter: RAG accepts structured facts, not video.
        observer_config = json.loads((ROOT / 'config/observer.json').read_text())
        observer_config['model_id'] = str(ROOT / observer_config['model_id'])
        generator = QwenTextGenerator(ModelConfig(**observer_config))
        from .optimizations import optimize_visual_patch_embedding
        optimize_visual_patch_embedding(generator.model)
        vocabulary = self.rag.cards_meta['predicate_vocabulary']['canonical']
        self.observer = VisualObserver(generator, vocabulary + ['other_observed_action'])
        policy = json.loads((ROOT / 'config/analysis-policy.json').read_text(encoding='utf-8'))
        if policy.get('mode') != 'possible_indications':
            raise ValueError('Unknown service analysis policy')
        self.review_mode = True
        log.info('Models ready; JEPA public interface; RAG evidence-assisted release v1')

    def analyze(self, path, stage):
        started = time.monotonic()
        duration = metadata(path)
        stage('detecting')
        binary = self.jepa.predict(path)
        log.info('JEPA duration=%.2f inference=%.2f label=%s', duration, binary['latency_sec'], binary['label'])
        if binary['label'] == 0:
            # Requested classifier gate: no expensive observation or legal calls for a negative.
            return {'verdict': 'no_violation', 'violations': [], 'build_id': self.build_id,
                'processing_sec': round(time.monotonic() - started, 3), 'duration_sec': duration,
                'limitations': ['Отрицательный результат видеоклассификатора; правовая проверка не запускалась.'],
                'model_versions': {'detector': self.detector_version, 'observer': 'not_run', 'legal': 'not_run'}}
        stage('observing')
        windows = observation_windows(duration, binary.get('timecode_sec'))
        frames = sample(path, [t for window in windows for t in window])
        candidates = []
        for window in windows:
            selected = list({f.timestamp: f for f in
                (min(frames, key=lambda f: abs(f.timestamp - t)) for t in window)}.values())
            candidates.extend(self.observer.observe(selected))
        if getattr(self, 'review_mode', False):
            return self.review_result(path, candidates, binary, duration, started, stage)
        stage('checking_rules')
        # Persist the exact local RAG response for diagnosis, outside public routes.
        # Nothing in this record is sent to an external model or to the browser.
        from pathlib import Path
        from .settings import DATA
        audit = DATA / 'legal-audit'
        audit.mkdir(mode=0o700, exist_ok=True)
        # Save observations before the expensive call, so a timeout is diagnosable locally.
        (audit / (Path(path).stem + '.input.json')).write_text(json.dumps(
            {'bundle': observation_bundle(candidates), 'technical': {'windows': len(windows),
             'frames': len(frames), 'candidates': len(candidates)}}, ensure_ascii=False), encoding='utf-8')
        result = assess(self.legal, observation_bundle(candidates)) if candidates else {'assessments': []}
        request = refinement_request(result, candidates, self.rag)
        refined, refinement_attempted = False, False
        if request is not None and time.monotonic() - started < 175:
            index, focus = request
            anchor = candidates[index]['time']
            first, last = max(0., anchor - 5.), min(duration - .05, anchor + 5.)
            verification_frames = sample(path, [first + (last - first) * i / 11 for i in range(12)])
            stage('verifying_evidence')
            refinement_attempted = True
            try:
                verified = self.observer.observe(verification_frames, focus=focus)
            except ValueError:
                # Reject malformed evidence; never remap invented indices to a nearby frame.
                # The initial honest assessment remains usable for diagnosis.
                log.warning('Refinement validation rejected; initial observations preserved')
                verified = []
            if verified:
                candidates[index:index + 1] = verified
                stage('checking_rules')
                result = assess(self.legal, observation_bundle(candidates))
                refined = True
        (audit / (Path(path).stem + '.json')).write_text(json.dumps({
            'bundle': observation_bundle(candidates), 'result': result,
            'technical': {'candidates': len(candidates),
                'refinement_performed': refinement_attempted, 'refinement_replaced_candidate': refined,
                'assessments': len(result['assessments']),
                'decisions': {d: sum(a.get('decision') == d for a in result['assessments'])
                    for d in sorted({a.get('decision', 'unknown') for a in result['assessments']})}}},
            ensure_ascii=False), encoding='utf-8')
        violations = []
        for assessment in publishable_assessments(result):
            event = event_for_assessment(assessment, candidates)
            if event is None:
                raise AnalysisUnavailable('evidence_scope_unresolved')
            rule_id, norm = assessment.get('rule_id'), assessment['norm']
            if any(v.get('rule_id') == rule_id and abs(v['timecode_sec'] - event['time']) < 7 for v in violations):
                continue
            rule = {'title': norm['title'], 'quote': norm['quote']}
            if norm.get('unit_label'):
                rule['section'] = norm['unit_label']
            if norm.get('official_url'):
                rule['url'] = norm['official_url']
            cited = {ref for row in assessment.get('evidence', []) for ref in row.get('evidence_refs', [])}
            support = [f for f in event.get('support_frames', event['frames']) if f'frame:{f.timestamp:.4f}' in cited]
            evidence = list({f.timestamp: f for f in [event['frames'][0], *support, *event['frames']]}.values())[:3]
            violations.append({'type': self.rag.cards[rule_id].type_label_ru if rule_id else norm['title'],
                'timecode_sec': round(event['time'], 4), 'description': assessment['explanation_text'],
                'evidence_frames': [f.evidence() for f in evidence],
                'rule_id': rule_id, 'rule': rule, 'legal_decision': assessment['decision'],
                'human_review_required': True})
        blocked = [a for a in result['assessments'] if a.get('decision') == 'violation_supported'
                   and a.get('publishable', {}).get('allowed') is not True]
        if blocked and not violations:
            raise AnalysisUnavailable('publication_not_allowed')
        if not violations and (binary['violation_detected'] or any(
                a.get('decision') in ('insufficient', 'no_norm')
                and event_for_assessment(a, candidates) is not None
                for a in result['assessments'])
                or (candidates and not result['assessments'])):
            raise AnalysisUnavailable('evidence_insufficient')
        violations.sort(key=lambda v: v['timecode_sec'])
        return {'verdict': 'violation' if violations else 'no_violation', 'violations': violations,
                'build_id': self.build_id, 'processing_sec': round(time.monotonic() - started, 3),
                'duration_sec': duration,
                'limitations': ['Результат требует проверки человеком.',
                    'Разреженная выборка кадров может пропускать короткие действия.'],
                'model_versions': {'detector': self.detector_version, 'observer': 'Qwen3-VL-8B-Instruct',
                    'legal': 'legal-rag-mvp-v1: Qwen3-VL-4B + BGE-M3/BM25; evidence_assisted'}}

    def review_result(self, path, candidates, binary, duration, started, stage):
        """Render review indications from the dedicated RAG contract, not a formal override."""
        from pathlib import Path
        from .settings import DATA
        # Preserve classifier-led review; no unvalidated second binary gate.
        chosen = select_observations(candidates, binary.get('timecode_sec'))
        if not chosen:
            raise AnalysisUnavailable('visual_observation_unavailable')
        stage('checking_rules')
        bundle = observation_bundle(chosen)
        audit = DATA / 'legal-audit'
        audit.mkdir(mode=0o700, exist_ok=True)
        stem = Path(path).stem
        (audit / (stem + '.input.json')).write_text(json.dumps({'bundle': bundle,
            'technical': {'policy': 'possible_indications', 'candidates': len(chosen)}}, ensure_ascii=False), encoding='utf-8')
        result = self.legal.review(bundle)
        (audit / (stem + '.json')).write_text(json.dumps({'bundle': bundle, 'result': result,
            'technical': {'policy': 'possible_indications', 'candidates': len(chosen)}}, ensure_ascii=False), encoding='utf-8')
        violations = []
        for row in publishable_review_findings(result):
            event = event_for_assessment(row, chosen)
            if event is None:
                raise AnalysisUnavailable('evidence_scope_unresolved')
            norm = row['norm']
            if any(v['rule'].get('unit_id') == norm.get('norm_id')
                   and abs(v['timecode_sec'] - event['time']) < 7 for v in violations):
                continue
            rule = {'title': norm['title'], 'quote': norm['quote'], 'url': norm['official_url'],
                'unit_id': norm.get('norm_id'), 'source_relation': row['source_relation'],
                'path': list(dict.fromkeys([*norm.get('headings', []),
                                           norm.get('unit_label') or '']))}
            rule['path'] = [part for part in rule['path'] if part]
            if row.get('supporting_norms'):
                rule['context'] = [dict(title=n['title'], quote=n['quote'], url=n['official_url'],
                    **({'section': n['unit_label']} if n.get('unit_label') else {}),
                    path=list(n.get('headings', []))) for n in row['supporting_norms']]
            if norm.get('unit_label') and row['source_relation'] == 'candidate_clause':
                rule['section'] = norm['unit_label']
            refs = {ref for fact in row['evidence'] for ref in fact['evidence_refs']}
            evidence = [f for f in event.get('support_frames', event['frames']) if f'frame:{f.timestamp:.4f}' in refs]
            evidence = list({f.timestamp: f for f in [*event['frames'], *evidence]}.values())[:3]
            violations.append({'type': action_type(event), 'timecode_sec': round(event['time'], 4),
                'description': append_citation(row['explanation_text'], rule), 'evidence_frames': [f.evidence() for f in evidence],
                'rule': rule, 'rule_id': row.get('rule_id'), 'legal_decision': row['decision'],
                'source_relation': row['source_relation'], 'unknown_conditions': row['unknown_conditions'],
                'human_review_required': True})
        if not violations:
            raise AnalysisUnavailable('review_generation_unavailable')
        violations.sort(key=lambda v: v['timecode_sec'])
        return {'verdict': 'violation', 'violations': violations, 'build_id': self.build_id,
            'processing_sec': round(time.monotonic() - started, 3), 'duration_sec': duration,
            'limitations': ['Результат показывает признаки для проверки человеком, а не окончательное правовое заключение.',
                'Ссылка с source_relation=context_only даёт контекст и не устанавливает нарушенный пункт.',
                'Разреженная выборка кадров может пропускать короткие действия.'],
            'model_versions': {'detector': self.detector_version, 'observer': 'Qwen3-VL-8B-Instruct',
                    'legal': 'legal-rag-mvp-v1: Qwen3-VL-4B + BGE-M3/BM25; qwen_prompt-v3.2'}}
