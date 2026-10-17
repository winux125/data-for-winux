"""Clause references inside the corpus: same act, other corpus acts, or explicit external.

Real phrasing in these acts is 'пунктами 57 и 58 Правил', 'части второй пункта 46
Правил', 'подпунктом 2) пункта 1 статьи 8 Закона'. An act is resolved only by its
own '(далее – Правила)' or by a corpus alias carrying the act's registry number;
everything else stays an explicit unresolved dependency.
"""
from __future__ import annotations

from collections import deque
import re

from .corpus import FOOTNOTE, OFFICIAL_NOTE, SUSPENSION
from .text import stem_tokens, tokens
from .types import Reference

REF = re.compile(
    r'(?<![а-яё])(?P<sub>под)?пункт(?:а|е|ом|у|ы|ов|ами|ах)?\s+'
    r'(?P<nums>\d+(?:-\d+)?\)?(?:\s*(?:,|и|или)\s*\d+(?:-\d+)?\)?)*)'
    r'(?:\s+(?:части|абзаца)\s+[а-яё]+)*'
    r'(?:\s+пункта\s+(?P<parent>\d+(?:-\d+)?))?', re.I)
NUMBER = re.compile(r'\d+(?:-\d+)?')
DOCUMENT_WORDS = ('правил', 'закон', 'кодекс', 'положени', 'требовани', 'указ', 'постановлени', 'приложени',
                  'настоящ', 'стать', 'перечн', 'инструкци', 'договор')


def _first_document_word(tail, window=8):
    for position, word in enumerate(tokens(tail)[:window]):
        for prefix in DOCUMENT_WORDS:
            if word.startswith(prefix):
                return position, word, prefix
    return None


class ReferenceIndex:
    def __init__(self, corpus):
        self.corpus = corpus
        self.by_clause = {cid: self._extract(clause) for cid, clause in corpus.clauses.items()}

    def _title_key(self, source_id):
        """Stemmed words after 'Правил' in the act's own title, for 'Правил осуществления …' self-references."""
        words = stem_tokens(self.corpus.acts[source_id].title)
        return tuple(words[words.index('правил') + 1:][:3]) if 'правил' in words else ()

    def _resolve_act(self, source_id, tail):
        """Return (resolution, target_source_id, reason) for the document named after a reference."""
        found = _first_document_word(tail)
        if found is None:
            return 'implicit_same_act', source_id, None
        position, word, prefix = found
        following = tokens(tail)[position:]
        if prefix == 'настоящ':
            nxt = following[1] if len(following) > 1 else ''
            if nxt.startswith('пункт'):
                return 'self_clause', source_id, None
            if nxt.startswith(('правил', 'параграф', 'глав')):
                return 'same_act', source_id, None
            return 'external', None, 'resolution_or_other_document_text'
        if prefix != 'правил':
            return 'external', None, 'other_document:' + prefix
        stems = tuple(stem_tokens(' '.join(following)))
        best = None
        for alias in self.corpus.aliases[source_id]:
            if alias.key and stems[:len(alias.key)] == alias.key and (best is None or len(alias.key) > len(best.key)):
                best = alias
        if best is not None and best.name != 'Правила':
            if best.target_source_id is None:
                return 'external', None, 'alias_outside_corpus:' + best.name
            return 'cross_act', best.target_source_id, None
        raw = tail[tail.lower().find('правил'):]
        after = re.match(r'правил[а-я]*\s*(.?)', raw, re.I)
        if after and after.group(1) == '№':
            return 'external', None, 'numbered_rules_not_in_corpus'
        if after and (not after.group(1) or not after.group(1).isalpha()):
            return 'same_act', source_id, None
        title = self._title_key(source_id)
        if title and stems[1:1 + len(title)] == title:
            return 'same_act', source_id, None
        return 'external', None, 'other_rules_not_in_corpus'

    def _extract(self, clause):
        result = []
        for offset, line in enumerate(clause.text.splitlines()):
            if FOOTNOTE.match(line) or line.startswith(OFFICIAL_NOTE) or SUSPENSION.match(line):
                continue  # amendment history, not normative references
            for match in REF.finditer(line):
                numbers = tuple(n for n in NUMBER.findall(match.group('nums')))
                parent = match.group('parent')
                kind = 'subitem' if match.group('sub') else 'clause'
                tail = line[match.end():match.end() + 200]
                resolution, target, reason = self._resolve_act(clause.source_id, tail)
                if resolution == 'self_clause':
                    clause_numbers = (clause.number,)
                elif kind == 'subitem':
                    clause_numbers = (parent,) if parent else (clause.number,)
                else:
                    clause_numbers = numbers
                targets = ()
                if target is not None:
                    targets = tuple(f'{target}:{n}' for n in clause_numbers)
                    missing = [t for t in targets if t not in self.corpus.clauses]
                    if missing:
                        reason = 'clause_not_found:' + ','.join(missing)
                        targets = tuple(t for t in targets if t in self.corpus.clauses)
                result.append(Reference(clause_id=clause.clause_id, line=clause.lines[0] + offset,
                                        phrase=line[match.start():match.end() + 60].split('\n')[0],
                                        kind=kind, numbers=numbers, parent=parent, resolution=resolution,
                                        target_source_id=target, target_clause_ids=targets,
                                        unresolved_reason=reason))
            result.extend(self._document_references(clause, offset, line))
        return result

    def _document_references(self, clause, offset, line):
        """'в соответствии с Правилами № 230' cites another corpus act without a clause number.

        The target act's scope clause is linked; which of its clauses applies stays open
        (resolution 'cross_act_document'), and the packet adds search-ranked candidates.
        """
        stems = stem_tokens(line)
        result = []
        for alias in self.corpus.aliases[clause.source_id]:
            target = alias.target_source_id
            if target in (None, clause.source_id) or not alias.key:
                continue
            width = len(alias.key)
            if any(tuple(stems[i:i + width]) == alias.key for i in range(len(stems) - width + 1)):
                scope = self.corpus.scope_clause(target)
                result.append(Reference(clause_id=clause.clause_id, line=clause.lines[0] + offset,
                                        phrase=alias.name, kind='document', numbers=(), parent=None,
                                        resolution='cross_act_document', target_source_id=target,
                                        target_clause_ids=(scope.clause_id,) if scope else (),
                                        unresolved_reason='applicable_clause_of_cited_act_not_specified'))
        return result

    def references(self, clause_id):
        return self.by_clause[clause_id]

    def closure(self, seeds, depth=2):
        """Breadth-first closure over resolvable references.

        Returns ([(clause_id, depth, via_clause_id)], unresolved_references). Seeds have depth 0.
        """
        seen = {s: 0 for s in seeds}
        order, unresolved = [], []
        queue = deque((s, 0) for s in seeds)
        while queue:
            clause_id, level = queue.popleft()
            for ref in self.by_clause[clause_id]:
                if ref.unresolved_reason or ref.resolution == 'external':
                    unresolved.append(ref)
                if ref.resolution == 'self_clause' or level >= depth:
                    continue
                for target in ref.target_clause_ids:
                    if target not in seen:
                        seen[target] = level + 1
                        order.append((target, level + 1, clause_id))
                        queue.append((target, level + 1))
        return order, unresolved
