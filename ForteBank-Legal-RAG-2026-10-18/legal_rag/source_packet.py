"""Normative packet from retrieved children: whole parent norms plus their dependencies.

A retrieved child is only a pointer. The packet carries the complete parent unit
(clause or article, exact source text), then explicit links: resolved references,
definitions of terms the norm uses, and sibling provisions with exception markers.
The budget is counted in tokens of the generator's tokenizer. Parents are never cut;
dependencies that do not fit are listed as omitted and make the context incomplete.
"""
from __future__ import annotations

import hashlib
import re

from .text import stem_tokens
from .tokens import default_counter

PACKET_VERSION = 'source-packet-v1'
ITEM_OVERHEAD_TOKENS = 24          # per-item header (id, label, title) in the generator prompt
EXCEPTION_MARKERS = ('за исключением', 'не распространяется', 'кроме случаев', 'не применяется')
MAX_SIBLINGS = 3
BLOCKING_REASONS = {'internal_part_not_found', 'not_found_in_container', 'law_article_part_not_found',
                    'article_not_found', 'clause_not_found', 'applicable_clause_of_cited_act_not_specified'}


class PacketOverflow(ValueError):
    pass


def _sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _contains(stems, key):
    width = len(key)
    return width > 0 and any(tuple(stems[i:i + width]) == key for i in range(len(stems) - width + 1))


class SourcePacketBuilder:
    def __init__(self, library, corpus=None, refs=None, counter=None):
        self.library, self.corpus, self.refs = library, corpus, refs
        self.counter = counter or default_counter()

    # Node access -------------------------------------------------------------
    def _part(self, node_id):
        """'<unit_id>/partN' -> (unit, part_number, first, last); plain unit ids -> (unit, None, ...)."""
        unit_id, _, part = node_id.partition('/part')
        unit = self.library.units[unit_id]
        if not part:
            return unit, None, unit.lines[0], unit.lines[1]
        first, last = unit.parts[part]
        return unit, part, first, last

    def _node_text(self, unit, first, last):
        return '\n'.join(self.library.lines[unit.source_id][first - 1:last]) + '\n'

    def _item(self, node_id, kind, reason, depth=0):
        unit, part, first, last = self._part(node_id)
        source = self.library.sources[unit.source_id]
        text = self._node_text(unit, first, last)
        label = unit.label if part is None else f'{unit.label}, п. {part}'
        return dict(kind=kind, node_id=node_id, unit_id=unit.unit_id, source_id=unit.source_id, label=label,
                    title=source['title'], official_url=source['official_url'], role=source['role'],
                    citation_level=unit.citation_level, structure=unit.structure, container=unit.container,
                    headings=list(unit.headings), lines=[first, last], text=text, text_sha256=_sha(text),
                    status=unit.status, numbering_anomaly=unit.numbering_anomaly, depth=depth, reason=reason,
                    tokens=self.counter.count(text) + ITEM_OVERHEAD_TOKENS)

    # Links -------------------------------------------------------------------
    def _corpus_clause(self, unit):
        if self.corpus is not None and unit.source_id in self.corpus.acts and unit.container == 'rules1' and unit.number:
            return f'{unit.source_id}:{unit.number}'
        return None

    def _references(self, unit):
        """Resolved targets and unresolved phrases; the five core acts also use the cross-act resolver."""
        targets, unresolved = [], []
        for ref in unit.references:
            target = ref['target_unit_id']
            if target and target.partition('/part')[0] == unit.unit_id:
                continue  # resolved inside the parent itself, which is already in the packet whole
            if target:
                targets.append((ref['target_unit_id'], f"reference '{ref['phrase'][:60]}'"))
            elif not ref['target_unit_id']:
                unresolved.append(dict(unit_id=unit.unit_id, phrase=ref['phrase'], reason=ref['unresolved_reason']))
        clause = self._corpus_clause(unit)
        if clause and self.refs is not None:
            closure, cross_unresolved = self.refs.closure([clause], depth=2)
            for clause_id, depth, via in closure:
                source_id, number = clause_id.split(':')
                target = f'{source_id}:rules1:p{number}'
                if target in self.library.units:
                    targets.append((target, f'referenced by {via} (depth {depth})'))
            for ref in cross_unresolved:
                if ref.resolution == 'external' or ref.unresolved_reason:
                    unresolved.append(dict(unit_id=unit.unit_id, phrase=ref.phrase, reason=ref.unresolved_reason))
        seen, unique = set(), []
        for target, reason in targets:
            if target not in seen:
                seen.add(target)
                unique.append((target, reason))
        for item in unresolved:
            # An in-document target that cannot be located blocks completeness; a citation of another
            # act outside the corpus (e.g. the legal basis) is recorded but does not block.
            item['blocking'] = item['reason'] in BLOCKING_REASONS
        return unique, unresolved

    def _definitions(self, unit):
        """Definition items of the same document whose term occurs in the norm's own text."""
        body = stem_tokens(unit.search_text)
        result = []
        for other in self.library.structures[unit.source_id].units:
            if not other.definitions or other.unit_id == unit.unit_id or other.container != unit.container:
                continue
            for definition in other.definitions:
                if _contains(body, tuple(stem_tokens(definition['term']))):
                    result.append((other, definition))
        return result

    def _definition_item(self, other, definition):
        lines = self.library.lines[other.source_id]
        start = next(i for i in range(other.body_start, other.lines[1] + 1)
                     if re.match(rf"^{re.escape(definition['item'])}\)\s", lines[i - 1]))
        end = start
        while end + 1 <= other.lines[1] and not re.match(r'^\d+(?:-\d+)?\)\s', lines[end]) \
                and not lines[end].startswith('Сноска.'):
            end += 1
        item = self._item(other.unit_id, 'definition', f"definition of '{definition['term']}'", depth=1)
        text = '\n'.join(lines[start - 1:end]) + '\n'
        item.update(node_id=f"{other.unit_id}#def{definition['item']}", lines=[start, end], text=text,
                    text_sha256=_sha(text), tokens=self.counter.count(text) + ITEM_OVERHEAD_TOKENS,
                    label=f"{other.label}, подп. {definition['item']}" if other.label else None)
        return item

    def _siblings_with_exceptions(self, unit):
        units = self.library.structures[unit.source_id].units
        siblings = [u for u in units if u.unit_id != unit.unit_id and u.container == unit.container
                    and u.headings == unit.headings and u.indexed and u.kind == unit.kind
                    and any(m in u.search_text.lower() for m in EXCEPTION_MARKERS)]
        return siblings[:MAX_SIBLINGS], max(0, len(siblings) - MAX_SIBLINGS)

    def _scope(self, unit):
        # Approved rules usually declare their scope in clause 1. Do not use
        # a law's definitions article as if it established applicability.
        return next((u for u in self.library.structures[unit.source_id].units
                     if u.container == unit.container and u.kind == 'clause' and u.number == '1'
                     and u.unit_id != unit.unit_id and u.indexed), None)

    # Assembly ----------------------------------------------------------------
    def build(self, ids, budget_tokens=4000):
        """ids: chunk IDs or unit IDs. Returns the packet dict; raises PacketOverflow if parents alone exceed."""
        if not ids:
            raise ValueError('Empty packet request')
        primaries = []
        for node in ids:
            unit_id = self.library.chunks[node]['unit_id'] if node in self.library.chunks else node
            if unit_id not in self.library.units:
                raise KeyError('Unknown chunk or unit: ' + node)
            if unit_id not in primaries:
                primaries.append(unit_id)
        items = [self._item(u, 'parent', 'retrieved norm (whole parent unit)') for u in primaries]
        used = sum(i['tokens'] for i in items)
        if used > budget_tokens:
            raise PacketOverflow(f'Parent norms alone need {used} tokens > budget {budget_tokens}')
        candidates, unresolved, per_norm = [], [], {}
        for unit_id in primaries:
            unit = self.library.units[unit_id]
            refs, open_refs = self._references(unit)
            definitions = self._definitions(unit)
            siblings, siblings_beyond = self._siblings_with_exceptions(unit)
            scope = self._scope(unit)
            per_norm[unit_id] = dict(references=[t for t, _ in refs], definitions=[d['term'] for _, d in definitions],
                                     definition_nodes=[f"{o.unit_id}#def{d['item']}" for o, d in definitions],
                                     exception_siblings=[s.unit_id for s in siblings],
                                     exception_siblings_not_checked=siblings_beyond,
                                     unresolved_references=sum(1 for r in open_refs if r['blocking']),
                                     external_references=sum(1 for r in open_refs if not r['blocking']),
                                     status=unit.status,
                                     structure=unit.structure)
            per_norm[unit_id]['scope_nodes'] = [scope.unit_id] if scope else []
            unresolved += open_refs
            candidates += [(1, lambda t=t, r=r: self._item(t, 'reference', r, depth=1), t) for t, r in refs]
            candidates += [(2, lambda o=o, d=d: self._definition_item(o, d), f"{o.unit_id}#def{d['item']}")
                           for o, d in definitions]
            candidates += [(3, lambda s=s: self._item(s.unit_id, 'exception_context',
                                                      'same-paragraph provision with exception markers', depth=1),
                            s.unit_id) for s in siblings]
            if scope:
                candidates.append((1, lambda s=scope: self._item(s.unit_id, 'scope', 'act scope', depth=1), scope.unit_id))
        present = {i['node_id'] for i in items}
        omitted = []
        for priority, make, node_id in sorted(candidates, key=lambda c: c[0]):
            if node_id in present:
                continue
            item = make()
            if used + item['tokens'] > budget_tokens:
                omitted.append(dict(node_id=node_id, kind=item['kind'], tokens=item['tokens'], reason='token_budget'))
                continue
            items.append(item)
            present.add(node_id)
            used += item['tokens']
        completeness = {}
        omitted_ids = {o['node_id'] for o in omitted}
        for unit_id, info in per_norm.items():
            dependencies = info['references'] + info['exception_siblings'] + info['definition_nodes'] + info['scope_nodes']
            missing = [d for d in dependencies if d in omitted_ids]
            complete = (not missing and info['unresolved_references'] == 0 and info['exception_siblings_not_checked'] == 0
                        and info['status'] == 'in_force_at_snapshot' and info['structure'] == 'structured')
            reasons = []
            if missing:
                reasons.append('dependencies_omitted_by_budget')
            if info['unresolved_references']:
                reasons.append('unresolved_references')
            if info['exception_siblings_not_checked']:
                reasons.append('more_exception_siblings_than_packed')
            if info['status'] != 'in_force_at_snapshot':
                reasons.append('status_' + info['status'])
            if info['structure'] != 'structured':
                reasons.append('unstructured_source_span')
            completeness[unit_id] = dict(info, complete=complete, incomplete_reasons=reasons, omitted=missing)
        return dict(version=PACKET_VERSION, items=items, omitted=omitted, unresolved=unresolved,
                    completeness=completeness, budget_tokens=budget_tokens, used_tokens=used,
                    token_counter=self.counter.describe(), applicability_verified=False,
                    note='Whole parent norms with explicit links; context completeness is per norm.')
