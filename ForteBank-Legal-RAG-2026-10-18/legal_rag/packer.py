"""Tiered normative packet for a verifier or reviewer, assembled BEFORE any decision.

Tier order is the drop order under a character budget, lowest first:
  T0 primary clauses of the cards and explicitly requested clauses  (never dropped)
  T1 related/exception clauses and the reference closure            (whole clauses)
  T2 definitions of terms used by T0/T1, only the needed items
  T3 scope clause (п. 1) of every act involved
  T4 search-ranked alternatives (queries, cross-act document links)
  T5 preambles with temporal notes
Every dropped unit is listed in `omitted`; the packet never claims completeness it lacks.
"""
from __future__ import annotations

from dataclasses import asdict
import json

from .bm25 import normative_text
from .corpus import sha256
from .text import stem_tokens
from .types import PacketItem, RetrievalPacket


class PacketOverflow(ValueError):
    pass


def compact_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def _amendments(clause):
    return [{k: v for k, v in asdict(a).items() if k != 'raw' and v is not None} for a in clause.amendments]


def _clause_item(corpus, clause_id, tier, reason, depth=0, score=None, kind='clause'):
    clause = corpus.clause(clause_id)
    act = corpus.acts[clause.source_id]
    return PacketItem(tier=tier, kind=kind, clause_id=clause_id, source_id=clause.source_id, reason=reason,
                      text=clause.text, text_sha256=clause.text_sha256, lines=clause.lines,
                      source_url=act.official_url, revision_instant=act.revision_instant, status=clause.status,
                      depth=depth, score=score, amendments=_amendments(clause),
                      notes=[text for _, text in clause.notes])


def _contains(stems, key):
    width = len(key)
    return any(tuple(stems[i:i + width]) == key for i in range(len(stems) - width + 1))


def build_packet(corpus, refs, index, cards, *, rule_ids=(), clause_ids=(), query_texts=(), predicates=(),
                 budget_chars=24000, alternatives_k=5, closure_depth=2):
    unknown = [r for r in rule_ids if r not in cards]
    if unknown:
        raise KeyError('Unknown rule cards: ' + ', '.join(unknown))
    candidates, seen = [], set()

    def add(item, key):
        if key not in seen:
            seen.add(key)
            candidates.append(item)

    # T0 ---------------------------------------------------------------
    primary = [cid for rid in rule_ids for cid in cards[rid].clause_ids] + list(clause_ids)
    for cid in primary:
        add(_clause_item(corpus, cid, 0, 'primary clause of ' + (
            ', '.join(r for r in rule_ids if cid in cards[r].clause_ids) or 'explicit request')), cid)
    # T1 ---------------------------------------------------------------
    related = []
    for rid in rule_ids:
        card = cards[rid]
        related += [(cid, f'related clause of {rid}') for cid in card.related_clause_ids]
        related += [(e.source_clause_id, f'exception {e.id} of {rid}') for e in card.exceptions]
    for cid, reason in related:
        add(_clause_item(corpus, cid, 1, reason, depth=1), cid)
    seeds = [i.clause_id for i in candidates]
    closure, unresolved_refs = refs.closure(seeds, depth=closure_depth)
    for cid, depth, via in closure:
        add(_clause_item(corpus, cid, 1, f'referenced by {via}', depth=depth), cid)
    # T2: definitions of terms used in T0/T1, per act ----------------------
    used, whole = {}, {i.clause_id for i in candidates}
    definition_clauses = {d.clause_id for d in corpus.definitions}
    for item in candidates:
        if item.clause_id not in definition_clauses:  # a definitions list would 'use' all its own terms
            used.setdefault(item.source_id, []).append(stem_tokens(normative_text(corpus.clause(item.clause_id))))
    for definition in corpus.definitions:
        act = definition.clause_id.split(':')[0]
        if definition.clause_id in whole:
            continue  # already present as the whole exact clause
        if act in used and definition.key and any(_contains(stems, definition.key) for stems in used[act]):
            end = definition.line + definition.text.count('\n')
            act_meta = corpus.acts[act]
            add(PacketItem(tier=2, kind='definition', clause_id=definition.clause_id, source_id=act,
                           reason=f'definition of "{definition.term}" (item {definition.item})',
                           text=definition.text + '\n', text_sha256=sha256(definition.text + '\n'),
                           lines=(definition.line, end),
                           source_url=act_meta.official_url, revision_instant=act_meta.revision_instant),
                f'def:{definition.clause_id}:{definition.item}')
    # T3: scope of every involved act --------------------------------------
    involved = sorted({i.source_id for i in candidates})
    for sid in involved:
        scope = corpus.scope_clause(sid)
        if scope:
            add(_clause_item(corpus, scope.clause_id, 3, 'scope of the act', kind='scope'), scope.clause_id)
    # T4: alternatives -----------------------------------------------------
    for text in query_texts:
        for hit in index.search(text, k=alternatives_k, predicates=predicates):
            add(_clause_item(corpus, hit.clause_id, 4, f'search rank {hit.rank} for observation',
                             score=hit.score, kind='alternative'), hit.clause_id)
    for ref in unresolved_refs:
        if ref.resolution == 'cross_act_document' and ref.target_source_id:
            query = normative_text(corpus.clause(ref.clause_id))
            for hit in index.search(query, k=2, source_ids={ref.target_source_id}):
                add(_clause_item(corpus, hit.clause_id, 4, f'cited act of {ref.clause_id}, search rank {hit.rank}',
                                 score=hit.score, kind='alternative'), hit.clause_id)
    # T5: preambles --------------------------------------------------------
    for sid in sorted({i.source_id for i in candidates}):
        (a, z), text = corpus.preambles[sid]
        act = corpus.acts[sid]
        add(PacketItem(tier=5, kind='preamble', clause_id=None, source_id=sid, reason='preamble and temporal notes',
                       text=text, text_sha256=sha256(text), lines=(a, z), source_url=act.official_url,
                       revision_instant=act.revision_instant), f'pre:{sid}')
    candidates.sort(key=lambda i: (i.tier, i.depth, -(i.score or 0)))

    primary_ids = set(primary)
    related_ids = {cid for cid, _ in related}
    unresolved = []
    for ref in unresolved_refs:
        origin = 'primary' if ref.clause_id in primary_ids else 'related' if ref.clause_id in related_ids else 'closure'
        # Only a dependency of the rule itself outside the corpus blocks; a cited corpus act or
        # a remote legal-basis reference in the closure is reported without blocking.
        blocking = origin != 'closure' and ref.resolution != 'cross_act_document'
        unresolved.append(dict(clause_id=ref.clause_id, phrase=ref.phrase, resolution=ref.resolution,
                               reason=ref.unresolved_reason, origin=origin, blocking=blocking))
    packet = RetrievalPacket(items=[i for i in candidates if i.tier == 0], omitted=[], unresolved=unresolved,
                             coverage={}, needs_review=True, budget_chars=budget_chars)
    if _size(packet) > budget_chars:
        raise PacketOverflow(f'Primary clauses alone need {_size(packet)} > {budget_chars} characters')
    for item in candidates:
        if item.tier == 0:
            continue
        packet.items.append(item)
        if _size(packet) > budget_chars:
            packet.items.pop()
            packet.omitted.append(dict(tier=item.tier, kind=item.kind, clause_id=item.clause_id,
                                       source_id=item.source_id, reason='budget'))
    while _size(packet) > budget_chars:  # omitted list itself grew; drop lowest remaining unit
        item = max((i for i in packet.items if i.tier), key=lambda i: (i.tier, i.depth))
        packet.items.remove(item)
        packet.omitted.append(dict(tier=item.tier, kind=item.kind, clause_id=item.clause_id,
                                   source_id=item.source_id, reason='budget'))
    _finalize(packet)
    return packet


def _size(packet):
    return len(compact_json(asdict(packet))) + 600  # reserve for coverage flags written afterwards


def _finalize(packet):
    dropped = {o['tier'] for o in packet.omitted}
    statuses = sorted({(i.clause_id, i.status) for i in packet.items
                       if i.clause_id and i.tier <= 1 and i.status != 'in_force_at_snapshot'})
    packet.coverage = dict(
        primary_complete=True, related_complete=1 not in dropped, definitions_complete=2 not in dropped,
        scope_complete=3 not in dropped, alternatives_complete=4 not in dropped, preambles_complete=5 not in dropped,
        unresolved_references=len(packet.unresolved),
        blocking_unresolved=sum(1 for u in packet.unresolved if u['blocking']),
        non_in_force_clauses=[dict(clause_id=c, status=s) for c, s in statuses],
        scope_note='corpus of five verified acts; other legislation is not searched')
    packet.needs_review = bool(1 in dropped or 2 in dropped or statuses or any(u['blocking'] for u in packet.unresolved))
    for _ in range(3):  # the count is part of the serialized packet itself
        packet.serialized_chars = len(compact_json(asdict(packet)))
