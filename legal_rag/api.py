"""Facade used by experiments and the service. Offline: reads only local verified files."""
from __future__ import annotations

import hashlib
from pathlib import Path
import threading

from .bm25 import DEFAULT_LEXICON, BM25Index, Lexicon
from .cards import DEFAULT_CARDS, load_cards
from .corpus import Corpus, load_brief
from .decide import applicability, assess, publishable
from .describe import describe
from .packer import build_packet
from .refs import ReferenceIndex

PACKAGE = Path(__file__).resolve().parent


def _file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class LegalRAG:
    def __init__(self, bundle_path=None, cards_path=None, lexicon_path=None, source_library_path=None):
        self._source_library_path=source_library_path
        self._warm_lock = threading.RLock()  # lazy library/index creation must not race
        self.paths = dict(cards=Path(cards_path or DEFAULT_CARDS), lexicon=Path(lexicon_path or DEFAULT_LEXICON))
        self.corpus = Corpus(load_brief(bundle_path))
        self.refs = ReferenceIndex(self.corpus)
        self.lexicon = Lexicon(self.paths['lexicon'])
        self.index = BM25Index(self.corpus, self.lexicon)
        self._raw_index = None
        self.cards, self.cards_meta = load_cards(self.corpus, self.paths['cards'])

    def search(self, text, k=5, predicates=(), lexicon=True, source_ids=None):
        if not lexicon:
            with self._warm_lock:
                self._raw_index = self._raw_index or BM25Index(self.corpus, None)
            return self._raw_index.search(text, k=k, source_ids=source_ids)
        return self.index.search(text, k=k, predicates=predicates, source_ids=source_ids)

    def cards_for_predicates(self, predicates):
        wanted = set(predicates)
        return [card for card in self.cards.values() if wanted & set(card.trigger_predicates)]

    def packet(self, *, rule_ids=(), clause_ids=(), query_texts=(), predicates=(), budget_chars=24000,
               alternatives_k=5):
        return build_packet(self.corpus, self.refs, self.index, self.cards, rule_ids=rule_ids, clause_ids=clause_ids,
                            query_texts=query_texts, predicates=predicates, budget_chars=budget_chars,
                            alternatives_k=alternatives_k)

    def assess(self, rule_id, states, policy='strict'):
        return assess(self.cards[rule_id], states, policy)

    def applicability(self, rule_id):
        return applicability(self.cards[rule_id], self.corpus)

    def source_library(self):
        """Expanded document-level retrieval; formal-card search remains reproducible."""
        with self._warm_lock:
            if not hasattr(self, '_expanded_library'):
                from .library import SourceLibrary
                self._expanded_library = SourceLibrary(self._source_library_path) if self._source_library_path else SourceLibrary()
        return self._expanded_library

    def search_sources(self, text, **kwargs):
        return self.source_library().search(text, **kwargs)

    def runtime(self, config=None, *, template_only=False, index_dir=None):
        """One resident serialized RAG worker per configuration in this facade."""
        from .config import load_config
        from .pipeline import LegalRAGRuntime
        import json
        config = config or load_config()
        key = (json.dumps(config.to_dict(), sort_keys=True), bool(template_only), str(index_dir))
        with self._warm_lock:
            if not hasattr(self, '_runtimes'):
                self._runtimes = {}
            if key not in self._runtimes:
                self._runtimes[key] = LegalRAGRuntime(self, config, index_dir=index_dir, template_only=template_only)
            return self._runtimes[key]

    def analyze(self, bundle, config=None, *, template_only=False, index_dir=None):
        return self.runtime(config, template_only=template_only, index_dir=index_dir).analyze(bundle)

    def packet_sources(self, ids, budget_tokens=4000, counter=None):
        """Whole parent norms for retrieved chunk/unit IDs, with references, definitions and exception context."""
        from .source_packet import SourcePacketBuilder
        builder = SourcePacketBuilder(self.source_library(), self.corpus, self.refs, counter)
        return builder.build(list(ids), budget_tokens=budget_tokens)

    def publishable(self, rule_id, assessment, mode='service'):
        return publishable(self.cards[rule_id], assessment, self.corpus, mode)

    def describe(self, rule_id, assessment, *, anchor_sec, facts):
        return describe(self.cards[rule_id], assessment, self.corpus, anchor_sec=anchor_sec, facts=facts)

    def manifest(self):
        return dict(corpus=self.corpus.manifest(), cards_sha256=_file_sha(self.paths['cards']),
                    cards_status=self.cards_meta['status'], lexicon_sha256=_file_sha(self.paths['lexicon']),
                    lexicon_status=self.lexicon.status,
                    production_active_rules=sorted(r for r, c in self.cards.items() if c.review.production_active),
                    code_sha256={p.name: _file_sha(p) for p in sorted(PACKAGE.glob('*.py'))})

    def warm(self, include_sources=True):
        """Build lazily created indices up front (service start), so no request pays for them."""
        with self._warm_lock:
            if include_sources:
                from .library import DEFAULT_ROLES
                self.source_library()._index(DEFAULT_ROLES)
        return self


_SHARED = {}
_SHARED_LOCK = threading.Lock()


def shared(bundle_path=None, cards_path=None, lexicon_path=None, source_library_path=None):
    """One LegalRAG, with its indices, per process and configuration.

    Construction re-verifies every source hash and builds BM25 indices; callers in a
    long-running process should use this instead of instantiating LegalRAG per request.
    """
    key = tuple(str(Path(p).resolve()) if p else None
                for p in (bundle_path, cards_path, lexicon_path, source_library_path))
    with _SHARED_LOCK:
        if key not in _SHARED:
            _SHARED[key] = LegalRAG(bundle_path, cards_path, lexicon_path, source_library_path)
        return _SHARED[key]
