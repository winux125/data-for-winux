"""Regressions for the 17.10.2026 audit findings, on the real corpus."""
import unittest

from legal_rag import shared
from legal_rag.source_packet import PacketOverflow
from legal_rag.units import parse_document


def setUpModule():
    global rag, library
    rag = shared()
    library = rag.source_library()


def refs(unit_id):
    return library.units[unit_id].references


class ReferenceRegressions(unittest.TestCase):
    def test_point_of_this_article_targets_internal_part_not_another_article(self):
        art2 = [r for r in refs('Z070000234_:law:art2') if 'пункте 3 настоящей статьи' in r['phrase']]
        self.assertEqual(art2[0]['target_unit_id'], 'Z070000234_:law:art2/part3')
        art7 = [r for r in refs('Z070000234_:law:art7') if 'пунктом 2 настоящей статьи' in r['phrase']]
        self.assertEqual(art7[0]['target_unit_id'], 'Z070000234_:law:art7/part2')
        self.assertFalse(any(r['target_unit_id'] in ('Z070000234_:law:art3', 'Z070000234_:law:art2')
                             for r in art2 + art7))

    def test_missing_internal_part_stays_unresolved(self):
        lines = ['Глава 1. Общие', 'Статья 1. Первая', '1. Текст части.', 'Статья 2. Вторая',
                 '1. Согласно пункту 5 настоящей статьи допускается.', 'Статья 3. Третья', '1. Текст.']
        unit = next(u for u in parse_document('TEST', lines, 'background').units if u.unit_id == 'TEST:law:art2')
        reference = next(r for r in unit.references if r['number'] == '5')
        self.assertIsNone(reference['target_unit_id'])
        self.assertEqual(reference['unresolved_reason'], 'internal_part_not_found')

    def test_same_rules_reference_still_resolves(self):
        targets = {r['target_unit_id'] for r in refs('V1900019680:rules1:p19')}
        self.assertTrue({'V1900019680:rules1:p57', 'V1900019680:rules1:p58'} <= targets)


class HeadingAndDefinitionRegressions(unittest.TestCase):
    def test_uppercase_and_roman_section_headings(self):
        self.assertEqual(library.units['Z2600000258:law:art1'].headings[0], 'РАЗДЕЛ 1. ОБЩИЕ ПОЛОЖЕНИЯ')
        roman = next(u for u in library.units.values() if u.source_id == 'Z950002444_' and u.kind == 'article')
        self.assertTrue(roman.headings[0].startswith('Раздел I.'))
        lines = ['Глава 1. Общие', '1. Пункт.', 'Глава представительства осуществляет деятельность.', '2. Пункт.']
        units = parse_document('TEST', lines, 'operational').units
        self.assertFalse(any(u.kind == 'heading' and u.lines[0] == 3 for u in units))

    def test_definitions_are_read_from_the_article_body(self):
        for unit_id in ('Z1300000094:law:art1', 'Z2600000258:law:art1'):
            self.assertGreater(len(library.units[unit_id].definitions), 10, unit_id)


class ParentPacketRegressions(unittest.TestCase):
    def test_child_hit_returns_whole_parent_with_lead(self):
        for unit_id, lead in (('V1200007978:rules1:p7', '7. Функциями главного бухгалтера'),
                              ('V1200007978:rules1:p24', '24.')):
            unit = library.units[unit_id]
            children = [c for c in library.by_source[unit.source_id] if library.chunks[c]['unit_id'] == unit_id]
            self.assertGreater(len(children), 1)
            packet = rag.packet_sources([children[-1]], budget_tokens=6000)
            parent = packet['items'][0]
            self.assertEqual((parent['kind'], parent['text']), ('parent', unit.text))
            self.assertTrue(parent['text'].startswith(lead))

    def test_dependencies_and_completeness(self):
        packet = rag.packet_sources(['V1900019680:rules1:p19'], budget_tokens=6000)
        nodes = {i['node_id'] for i in packet['items']}
        self.assertTrue({'V1900019680:rules1:p57', 'V1900019680:rules1:p58'} <= nodes)
        self.assertTrue(any(i['kind'] == 'definition' for i in packet['items']))
        # A document-only cross-reference carries the other act's scope clause,
        # not the specific applicable provision. This must remain incomplete.
        self.assertFalse(packet['completeness']['V1900019680:rules1:p19']['complete'])
        self.assertTrue(any(r['reason'] == 'applicable_clause_of_cited_act_not_specified' and r['blocking']
                            for r in packet['unresolved']))
        tight = rag.packet_sources(['V1900019680:rules1:p19'], budget_tokens=700)
        info = tight['completeness']['V1900019680:rules1:p19']
        self.assertFalse(info['complete'])
        self.assertIn('dependencies_omitted_by_budget', info['incomplete_reasons'])
        self.assertLessEqual(tight['used_tokens'], 700)
        with self.assertRaises(PacketOverflow):
            rag.packet_sources(['V1900019680:rules1:p19'], budget_tokens=100)

    def test_suspended_norm_is_never_complete(self):
        info = rag.packet_sources(['V2000020075:rules1:p11'])['completeness']['V2000020075:rules1:p11']
        self.assertFalse(info['complete'])
        self.assertIn('status_suspended_wording_uncertain', info['incomplete_reasons'])

    def test_internal_parts_are_not_duplicated_as_items(self):
        packet = rag.packet_sources(['Z070000234_:law:art2'], budget_tokens=8000)
        self.assertFalse(any(i['node_id'].startswith('Z070000234_:law:art2/part') for i in packet['items']))


if __name__ == '__main__':
    unittest.main()
