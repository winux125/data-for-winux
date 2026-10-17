"""Tiered retrieval over structural units: BM25, dense, or hybrid via RRF inside one tier.

Tiers are separate candidate lists and are never merged by raw score:
  core         the five core acts (+ cards selected by fact predicates, as their own route)
  operational  other operational documents of the library
  background   legal-basis documents, searched only inside sources linked from tier 1/2 hits
Within a tier, BM25 ranks and dense ranks are fused with Reciprocal Rank Fusion; BM25 scores
and cosine similarities are never compared directly. A rank is retrieval order only.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import time

from .contracts import ObservationBundle
from .text import stem_tokens

TIER_NAMES = ('core', 'operational', 'background')
MODES = ('bm25', 'dense', 'hybrid')


@dataclass
class Candidate:
    unit_id: str
    tier: str
    rank: int
    rrf_score: float
    routes: list = field(default_factory=list)       # bm25 / dense / card_predicate
    ranks: dict = field(default_factory=dict)        # per query part and retriever
    matched_chunks: list = field(default_factory=list)
    query_origins: list = field(default_factory=list)


class Retriever:
    def __init__(self, rag, dense=None, embedder=None, rrf_k=60, per_retriever=50):
        self.rag, self.library = rag, rag.source_library()
        self.dense, self.embedder = dense, embedder
        self.rrf_k, self.per_retriever = rrf_k, per_retriever
        core = set(rag.corpus.acts)
        self.tier_sources = dict(
            core=core,
            operational={s for s, v in self.library.sources.items() if v['role'] == 'operational' and s not in core},
            background={s for s, v in self.library.sources.items() if v['role'] == 'background'})
        self.tier_chunks = {t: {c for c, ch in self.library.chunks.items() if ch['source_id'] in sources}
                            for t, sources in self.tier_sources.items()}
        self.timings = {}
        self._query_vectors = {}

    # Single-retriever rankings (unit level) ---------------------------------
    def bm25_units(self, text, sources, predicates=(), lexicon=True, k=None):
        hits = self.library.search(text, k=min(50, k or self.per_retriever), predicates=predicates,
                                   source_ids=sources, lexicon=lexicon)
        return [(h['unit_id'], h['chunk_id']) for h in hits]

    def dense_units(self, vector, tier, k=None, sources=None):
        if self.dense is None:
            raise RuntimeError('Dense retrieval requested but no embedding index is loaded')
        allowed = self.tier_chunks[tier]
        if sources is not None:
            allowed = {c for c in allowed if self.library.chunks[c]['source_id'] in sources}
        result, seen = [], set()
        for chunk_id, _ in self.dense.search(vector, k=(k or self.per_retriever) * 4, allowed=allowed):
            unit_id = self.library.chunks[chunk_id]['unit_id']
            if unit_id not in seen:
                seen.add(unit_id)
                result.append((unit_id, chunk_id))
            if len(result) == (k or self.per_retriever):
                break
        return result

    def _fuse(self, tier, lists):
        """lists: [(route, origin, [(unit_id, chunk_id), ...])] -> RRF-ordered candidates of one tier."""
        table = {}
        for route, origin, ranking in lists:
            for rank, (unit_id, chunk_id) in enumerate(ranking, 1):
                c = table.setdefault(unit_id, Candidate(unit_id, tier, 0, 0.0))
                c.rrf_score += 1.0 / (self.rrf_k + rank)
                if route not in c.routes:
                    c.routes.append(route)
                c.ranks[f'{route}:{origin}'] = rank
                if chunk_id not in c.matched_chunks:
                    c.matched_chunks.append(chunk_id)
                if origin not in c.query_origins:
                    c.query_origins.append(origin)
        ordered = sorted(table.values(), key=lambda c: (-c.rrf_score, c.unit_id))
        for rank, c in enumerate(ordered, 1):
            c.rank = rank
        return ordered

    def rank_tier(self, tier, queries, mode='hybrid', lexicon=True, sources=None):
        """queries: [(origin, text, predicates)]."""
        if mode not in MODES:
            raise ValueError('mode must be bm25, dense or hybrid')
        sources = sources if sources is not None else self.tier_sources[tier]
        if not sources:
            return []
        lists = []
        texts = [text for _, text, _ in queries]
        if mode != 'bm25':
            if self.embedder is None:
                raise RuntimeError('Dense retrieval needs a query embedder')
            if lexicon:
                texts = [text + ''.join('\nТермины для поиска: ' + e['expansion_text']
                                       for e in self.rag.lexicon.expand(stem_tokens(text), predicates))
                         for _, text, predicates in queries]
            missing = list(dict.fromkeys(t for t in texts if t not in self._query_vectors))
            if missing:
                started = time.perf_counter()
                self._query_vectors.update(zip(missing, self.embedder.encode(missing)))
                self.timings['encode_ms'] = self.timings.get('encode_ms', 0) + (time.perf_counter() - started) * 1000
            vectors = [self._query_vectors[t] for t in texts]
        else:
            vectors = [None] * len(texts)
        for (origin, text, predicates), vector in zip(queries, vectors):
            if mode in ('bm25', 'hybrid'):
                started = time.perf_counter()
                lists.append(('bm25', origin, self.bm25_units(text, sources, predicates, lexicon)))
                self.timings['bm25_ms'] = self.timings.get('bm25_ms', 0) + (time.perf_counter() - started) * 1000
            if mode in ('dense', 'hybrid'):
                started = time.perf_counter()
                ranking = self.dense_units(vector, tier, sources=sources)
                lists.append(('dense', origin, ranking))
                self.timings['dense_ms'] = self.timings.get('dense_ms', 0) + (time.perf_counter() - started) * 1000
        started = time.perf_counter()
        result = self._fuse(tier, lists)
        self.timings['rrf_ms'] = self.timings.get('rrf_ms', 0) + (time.perf_counter() - started) * 1000
        return result

    # Bundle-level retrieval ------------------------------------------------
    def queries_from_bundle(self, bundle: ObservationBundle):
        """Each fact keeps its status in the query text (refuted is negated, unknown is a question)."""
        return [(part.origin_id, part.text, {part.predicate} if part.predicate else set())
                for part in bundle.query_parts()]

    def retrieve(self, bundle, mode='hybrid', lexicon=True, top_k=5, tiers=('core', 'operational')):
        started = time.perf_counter()
        self._query_vectors.clear()  # per-request reuse across tiers; never unbounded process history
        self.timings.clear()
        queries = self.queries_from_bundle(bundle)
        result = dict(mode=mode, lexicon=lexicon, rrf_k=self.rrf_k, tiers={}, card_candidates=[])
        predicates = {f.predicate for f in bundle.facts}
        for card in self.rag.cards_for_predicates(predicates):
            for clause_id in card.clause_ids:
                source_id, number = clause_id.split(':')
                result['card_candidates'].append(dict(rule_id=card.rule_id, unit_id=f'{source_id}:rules1:p{number}',
                                                      route='card_predicate',
                                                      trigger_predicates=sorted(set(card.trigger_predicates) & predicates)))
        for tier in tiers:
            if tier == 'background':
                continue
            result['tiers'][tier] = [asdict(c) for c in self.rank_tier(tier, queries, mode, lexicon)[:top_k]]
        if 'background' in tiers:
            linked = set()
            for tier_hits in result['tiers'].values():
                for hit in tier_hits:
                    source = self.library.sources[self.library.units[hit['unit_id']].source_id]
                    linked |= set(source.get('linked_source_ids') or [])
            sources = linked & self.tier_sources['background']
            result['tiers']['background'] = ([asdict(c) for c in
                                              self.rank_tier('background', queries, mode, lexicon, sources)[:top_k]]
                                             if sources else [])
            result['background_scope'] = sorted(sources)
        self.timings['retrieve_ms'] = round((time.perf_counter() - started) * 1000, 1)
        result['timing_ms'] = self.timings['retrieve_ms']
        return result
