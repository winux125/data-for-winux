"""BM25 over exact clauses. Retrieval order only; a score is never evidence of a violation.

Indexed text is the normative part of each clause (footnotes and official notes are
amendment history, not content) plus its chapter/paragraph headings. Editorial
section hints from the discovery brief form a separate, lightly weighted field.
"""
from __future__ import annotations

from collections import Counter
import json
import math
from pathlib import Path

from .corpus import FOOTNOTE, OFFICIAL_NOTE, SUSPENSION
from .text import stem_tokens
from .types import Hit

DEFAULT_LEXICON = Path(__file__).resolve().parent / 'data' / 'lexicon.json'


def _occurs(stems, key):
    return any(tuple(stems[i:i + len(key)]) == key for i in range(len(stems) - len(key) + 1))


class Lexicon:
    """Editorial query expansion: observation wording -> normative wording.

    An entry fires on a fact predicate, on a context phrase of at least two content
    words, or on a domain-specific term. Single generic words cannot be triggers.
    """

    def __init__(self, path=DEFAULT_LEXICON):
        self.path = Path(path)
        data = json.loads(self.path.read_text(encoding='utf-8'))
        if data.get('schema_version') != 2 or not isinstance(data.get('entries'), list):
            raise ValueError('Invalid lexicon schema (expected schema_version 2)')
        self.status = data.get('status')
        self.entries = []
        seen = set()
        for entry in data['entries']:
            if set(entry) != {'id', 'predicates', 'phrases', 'terms', 'expansion'} or entry['id'] in seen:
                raise ValueError('Invalid or duplicate lexicon entry: ' + str(entry.get('id')))
            seen.add(entry['id'])
            phrases = [tuple(stem_tokens(p)) for p in entry['phrases']]
            if any(len(p) < 2 for p in phrases):
                raise ValueError(f"{entry['id']}: a phrase needs at least two content words; use 'terms' "
                                 'only for domain-specific single words')
            terms = [tuple(stem_tokens(t)) for t in entry['terms']]
            if any(len(t) != 1 for t in terms) or not entry['expansion'].strip():
                raise ValueError(f"{entry['id']}: terms must be single content words; expansion is required")
            if not (entry['predicates'] or phrases or terms):
                raise ValueError(f"{entry['id']}: no way to fire")
            self.entries.append(dict(id=entry['id'], predicates=set(entry['predicates']), phrases=phrases,
                                     terms=terms, expansion=stem_tokens(entry['expansion']),
                                     expansion_text=entry['expansion']))

    def expand(self, query_stems, predicates=()):
        predicates = set(predicates)
        fired = []
        for entry in self.entries:
            if (entry['predicates'] & predicates or any(_occurs(query_stems, p) for p in entry['phrases'])
                    or any(_occurs(query_stems, t) for t in entry['terms'])):
                fired.append(entry)
        return fired


class _Field:
    def __init__(self, documents, k1, b):
        self.k1, self.b = k1, b
        self.tf = [Counter(d) for d in documents]
        self.length = [len(d) for d in documents]
        self.avg = sum(self.length) / max(1, len(documents)) or 1.
        df = Counter(term for d in documents for term in set(d))
        n = len(documents)
        self.idf = {t: math.log(1 + (n - f + .5) / (f + .5)) for t, f in df.items()}

    def score(self, index, weights):
        tf, length, total = self.tf[index], self.length[index], 0.
        for term, weight in weights.items():
            f = tf.get(term)
            if f:
                total += weight * self.idf[term] * f * (self.k1 + 1) / (
                    f + self.k1 * (1 - self.b + self.b * length / self.avg))
        return total


def normative_text(clause):
    return '\n'.join(line for line in clause.text.splitlines()
                     if not (FOOTNOTE.match(line) or line.startswith(OFFICIAL_NOTE) or SUSPENSION.match(line)))


class BM25Index:
    def __init__(self, corpus, lexicon=None, k1=1.2, b=.75, editorial_weight=.3, expansion_weight=.5,
                 include_repealed=False):
        self.corpus, self.lexicon = corpus, lexicon
        self.editorial_weight, self.expansion_weight = editorial_weight, expansion_weight
        self.ids = [cid for cid, c in corpus.clauses.items() if include_repealed or c.status != 'repealed']
        body, editorial = [], []
        for cid in self.ids:
            clause = corpus.clauses[cid]
            body.append(stem_tokens(normative_text(clause) + '\n' + '\n'.join(clause.headings)))
            section = corpus.brief.sections[clause.section_id]
            editorial.append(stem_tokens(section['short_title'] + ' ' + section['seek']))
        self.body, self.editorial = _Field(body, k1, b), _Field(editorial, k1, b)

    def query_weights(self, text, predicates=()):
        stems = stem_tokens(text)
        weights = Counter({s: 1. for s in stems})
        fired = self.lexicon.expand(stems, set(predicates)) if self.lexicon else []
        for entry in fired:
            for term in entry['expansion']:
                weights[term] = max(weights[term], self.expansion_weight)
        return dict(weights), [e['id'] for e in fired]

    def search(self, text, k=5, predicates=(), source_ids=None, exclude=()):
        weights, _ = self.query_weights(text, predicates)
        scored = []
        for index, cid in enumerate(self.ids):
            clause = self.corpus.clauses[cid]
            if (source_ids and clause.source_id not in source_ids) or cid in exclude:
                continue
            score = self.body.score(index, weights) + self.editorial_weight * self.editorial.score(index, weights)
            if score > 0:
                scored.append((score, cid))
        scored.sort(key=lambda item: (-item[0], item[1]))
        hits = []
        for rank, (score, cid) in enumerate(scored[:k], 1):
            clause = self.corpus.clauses[cid]
            terms = set(stem_tokens(normative_text(clause)))
            matched = tuple(sorted(t for t in weights if t in terms))
            best, best_overlap = None, 0
            for item in clause.subitems:
                overlap = sum(weights.get(t, 0) for t in set(stem_tokens(item.text)))
                if overlap > best_overlap:
                    best, best_overlap = item.number, overlap
            hits.append(Hit(clause_id=cid, score=round(score, 4), rank=rank, matched_subitem=best,
                            matched_terms=matched))
        return hits


