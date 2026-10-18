"""Structural units and parent-child chunks on the real library (CPU, offline)."""
from collections import Counter
import unittest

from legal_rag.corpus import Corpus
from legal_rag.library import SourceLibrary
from legal_rag.units import CHILD_MAX_CHARS, parse_document

A231, A14, FIRE = 'V1900019680', 'V2000020075', 'V2200026867'


def setUpModule():
    global library, corpus
    library = SourceLibrary()
    corpus = Corpus()


class UnitTests(unittest.TestCase):
    def test_every_line_in_exactly_one_unit_and_one_chunk_with_exact_text(self):
        for code, structure in library.structures.items():
            lines = library.lines[code]
            for spans in ([u.lines for u in structure.units], [c.lines for c in structure.chunks]):
                covered = Counter(i for a, b in spans for i in range(a, b + 1))
                self.assertEqual(set(covered), set(range(1, len(lines) + 1)), code)
                self.assertEqual(max(covered.values()), 1, code)
            for item in list(structure.units) + list(structure.chunks):
                a, b = item.lines
                self.assertEqual(item.text, '\n'.join(lines[a - 1:b]) + '\n')

    def test_core_acts_match_the_verified_clause_layer(self):
        for code in corpus.acts:
            mine = {(u.number, u.body_start, u.lines[1]) for u in library.structures[code].units
                    if u.kind == 'clause' and u.container == 'rules1'}
            reference = {(c.number, c.lines[0], c.lines[1]) for c in corpus.clauses.values() if c.source_id == code}
            self.assertEqual(mine, reference, code)

    def test_resolution_and_appendix_numbers_do_not_collide_with_rules(self):
        units = library.structures[A231].units
        self.assertIn(f'{A231}:rules1:p1', {u.unit_id for u in units})
        self.assertTrue(any(u.container == 'resolution' and u.kind == 'resolution_clause' for u in units))
        appendix = [u for u in units if u.container.startswith('appendix')]
        self.assertTrue(appendix and all(u.structure == 'fallback' and u.citation_level == 'document' and u.label is None
                                         for u in appendix))

    def test_notes_and_suspensions_belong_to_their_provision(self):
        units = {u.unit_id: u for u in library.structures[A14].units}
        suspended = units[f'{A14}:rules1:p11']
        self.assertEqual(suspended.status, 'suspended_wording_uncertain')
        self.assertLess(suspended.lines[0], suspended.body_start)          # the official note opens the unit
        self.assertNotIn('Примечание ИЗПИ', units[f'{A14}:rules1:p10'].text)
        self.assertEqual(units[f'{A14}:rules1:p13'].status, 'partially_suspended_wording_uncertain')
        self.assertNotIn('Сноска.', units[f'{A231}:rules1:p2'].search_text if f'{A231}:rules1:p2' in units else
                         library.units[f'{A231}:rules1:p2'].search_text)

    def test_fire_rules_are_structured_with_flagged_misprint(self):
        structure = library.structures[FIRE]
        rules = next(c for c in structure.containers if c['name'] == 'rules1')
        self.assertEqual(rules['structure'], 'structured')
        flagged = [u for u in structure.units if u.numbering_anomaly]
        self.assertEqual(len(flagged), 1)
        clause = next(u for u in structure.units if u.number == '1267')
        self.assertEqual([h.split()[0] for h in clause.headings], ['Раздел', 'Глава'])

    def test_large_parents_split_into_children_that_keep_the_lead(self):
        def body_lines(u):
            return sum(1 for i in range(u.body_start, u.lines[1] + 1)
                       if not library.lines[u.source_id][i - 1].startswith(('Сноска.', 'Примечание ИЗПИ')))
        # A single very long line cannot be split without cutting text; it stays one child.
        large = [u for u in library.units.values() if u.kind == 'clause' and len(u.search_text) > CHILD_MAX_CHARS
                 and body_lines(u) >= 2]
        children_of = {}
        for structure in library.structures.values():
            for chunk in structure.chunks:
                children_of.setdefault(chunk.unit_id, []).append(chunk)
        split = [u for u in large if len(children_of[u.unit_id]) > 1]
        self.assertGreater(len(split), len(large) // 2)
        for unit in large:
            children = children_of[unit.unit_id]
            lead = library.lines[unit.source_id][unit.body_start - 1]
            self.assertTrue(all(c.parent_sha256 == unit.text_sha256 for c in children))
            if len(children) == 1:
                self.assertEqual(children[0].search_text, unit.search_text)   # nothing lost when not split
                continue
            self.assertIn(lead, children[0].search_text)                      # full lead in the first child
            self.assertTrue(all(lead[:40] in c.search_text for c in children), unit.unit_id)
        short = library.units[f'{A231}:rules1:p22']
        self.assertEqual(len([c for c in library.structures[A231].chunks if c.unit_id == short.unit_id]), 1)

    def test_unreliable_numbering_falls_back_to_exact_ranges(self):
        lines = ['Глава 1. Общие', '1. Первый.', '3. Третий.', '2. Второй.', '2. Повтор второго.', '5. Пятый.']
        structure = parse_document('TEST', lines, 'operational')
        self.assertEqual(structure.containers[0]['structure'], 'fallback')
        self.assertTrue(all(u.citation_level == 'document' for u in structure.units))

    def test_search_returns_one_hit_per_parent_with_unit_metadata(self):
        for query in ('кассир ушёл с рабочего места', 'пересчёт денег в присутствии клиента', 'дверь кассы'):
            hits = library.search(query, k=10)
            self.assertEqual(len(hits), len({h['unit_id'] for h in hits}))
            for hit in hits:
                self.assertIn(hit['citation_granularity'], ('unit', 'document'))
                self.assertEqual(hit['text'], library.chunks[hit['chunk_id']]['text'])


if __name__ == '__main__':
    unittest.main()
