"""Rule card validation and tiered packet guarantees on the real corpus."""
import json
from pathlib import Path
import tempfile
import unittest

from legal_rag.api import LegalRAG
from legal_rag.cards import DEFAULT_CARDS, CardError, load_cards
from legal_rag.packer import PacketOverflow, compact_json

A231, A14, A230 = 'V1900019680', 'V2000020075', 'V1700016120'


def setUpModule():
    global rag
    rag = LegalRAG()


def mutated_cards(change):
    data = json.loads(Path(DEFAULT_CARDS).read_text(encoding='utf-8'))
    change(data['cards'][0])
    folder = tempfile.mkdtemp()
    path = Path(folder) / 'cards.json'
    path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    return path


class CardTests(unittest.TestCase):
    def test_drafts_load_and_none_is_active(self):
        self.assertEqual(len(rag.cards), 8)
        self.assertFalse(any(c.review.production_active or c.review.human_reviewed for c in rag.cards.values()))

    def test_invalid_cards_fail_closed(self):
        cases = [
            lambda c: c['pinned_text_sha256'].update({c['clause_ids'][0]: '0' * 64}),
            lambda c: c.update(clause_ids=['V1900019680:999']),
            lambda c: c['review'].update(production_active=True),
            lambda c: c['exceptions'][0].update(source_clause_id='V1900019680:57'),
            lambda c: c.update(trigger_predicates=['invented_predicate']),
            lambda c: c.update(conditions=[dict(x, tier='context') for x in c['conditions']]),
        ]
        for change in cases:
            with self.assertRaises(CardError):
                load_cards(rag.corpus, mutated_cards(change))


class PacketTests(unittest.TestCase):
    def test_primary_clause_text_is_exact_and_definitions_are_linked(self):
        packet = rag.packet(rule_ids=['R231-42'])
        primary = next(i for i in packet.items if i.tier == 0)
        clause = rag.corpus.clause(f'{A231}:42')
        self.assertEqual((primary.text, primary.text_sha256), (clause.text, clause.text_sha256))
        self.assertIn('за исключением случаев', primary.text)  # the exception travels with the clause
        reasons = [i.reason for i in packet.items if i.kind == 'definition']
        self.assertTrue(any('контролирующий работник' in r for r in reasons))
        self.assertNotIn(f'{A231}:2', packet.clause_ids(tier=1))

    def test_reference_closure_reaches_cited_act(self):
        packet = rag.packet(rule_ids=['R231-20A'])
        ids = set(packet.clause_ids())
        self.assertTrue({f'{A231}:57', f'{A231}:58', f'{A230}:1'} <= ids)
        self.assertFalse(packet.needs_review)

    def test_budget_drops_lower_tiers_never_primary(self):
        full = rag.packet(rule_ids=['R231-31.4'], query_texts=['кассир выдал деньги'])
        tight = rag.packet(rule_ids=['R231-31.4'], query_texts=['кассир выдал деньги'], budget_chars=5000)
        self.assertLessEqual(tight.serialized_chars, 5000)
        self.assertLessEqual(full.serialized_chars, 24000)
        self.assertEqual(tight.clause_ids(tier=0), [f'{A231}:31'])
        self.assertTrue(tight.omitted and min(o['tier'] for o in tight.omitted) >= 1)
        self.assertEqual(tight.serialized_chars, len(compact_json(tight.to_dict())))
        with self.assertRaises(PacketOverflow):
            rag.packet(rule_ids=['R231-31.4'], budget_chars=1500)

    def test_suspended_clause_forces_review(self):
        packet = rag.packet(clause_ids=[f'{A14}:11'])
        self.assertTrue(packet.needs_review)
        self.assertIn(dict(clause_id=f'{A14}:11', status='suspended_wording_uncertain'),
                      packet.coverage['non_in_force_clauses'])

    def test_unknown_rule_is_an_error(self):
        with self.assertRaises(KeyError):
            rag.packet(rule_ids=['R999'])


if __name__ == '__main__':
    unittest.main()
