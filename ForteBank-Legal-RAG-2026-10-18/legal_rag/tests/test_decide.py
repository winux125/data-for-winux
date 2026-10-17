"""Decision matrix, publication gate and citation-safe description."""
from dataclasses import replace
import unittest

from legal_rag.api import LegalRAG
from legal_rag.decide import assess, publishable
from legal_rag.describe import CitationError, describe
from legal_rag.types import Review

A231, A14 = 'V1900019680', 'V2000020075'


def setUpModule():
    global rag, card42, card22
    rag = LegalRAG()
    card42, card22 = rag.cards['R231-42'], rag.cards['R231-22']


def states(card, value='true', **override):
    result = {c: value for c in card.condition_ids()}
    result.update({e: 'false' for e in card.exception_ids()})
    result.update(override)
    return result


def reviewed(card):
    return replace(card, review=Review(text_verified_by='reviewer', logic_reviewed_by='reviewer',
                                       reviewed_at='2026-10-17', human_reviewed=True, production_active=True))


class AssessTests(unittest.TestCase):
    def test_matrix(self):
        self.assertEqual(assess(card42, states(card42)).l2, 'matched')
        self.assertEqual(assess(card42, states(card42, controller_absent='false')).l2, 'refuted')
        self.assertEqual(assess(card42, states(card42, client_receipt_or_issue='true')).l2, 'not_applicable')
        self.assertEqual(assess(card42, states(card42, cash_processing='not_visible')).l2, 'insufficient')
        self.assertEqual(assess(card42, states(card42, client_receipt_or_issue='not_visible')).l2, 'insufficient')

    def test_context_policy(self):
        open_context = states(card42, actor_is_cashier='not_visible')
        self.assertEqual(assess(card42, open_context).l2, 'insufficient')
        relaxed = assess(card42, open_context, policy='p_core')
        self.assertEqual((relaxed.l2, relaxed.caveats), ('matched', ['actor_is_cashier']))

    def test_not_visible_is_never_false(self):
        result = assess(card22, {c: 'not_visible' for c in card22.condition_ids()})
        self.assertEqual(result.l2, 'insufficient')
        self.assertFalse(result.refuted_by)
        missing = assess(card22, {})
        self.assertEqual((missing.l2, sorted(missing.missing)), ('insufficient', sorted(card22.condition_ids())))

    def test_bad_evidence_is_rejected(self):
        with self.assertRaises(ValueError):
            assess(card22, {'invented': 'true'})
        with self.assertRaises(ValueError):
            assess(card22, {'left_workplace': 'unknown'})


class PublishTests(unittest.TestCase):
    def test_drafts_never_reach_the_service(self):
        result = assess(card22, states(card22))
        self.assertEqual(publishable(card22, result, rag.corpus, 'service'), (False, 'rule_not_production_active'))
        self.assertEqual(publishable(card22, result, rag.corpus, 'dev'), (True, 'dev_only'))
        self.assertEqual(publishable(reviewed(card22), result, rag.corpus, 'service'), (True, None))

    def test_only_matched_and_in_force_clauses_publish(self):
        refuted = assess(card22, states(card22, left_workplace='false'))
        self.assertEqual(publishable(reviewed(card22), refuted, rag.corpus)[1], 'l2_refuted')
        suspended = replace(reviewed(card22), clause_ids=(f'{A14}:11',),
                            pinned_text_sha256={f'{A14}:11': rag.corpus.clause(f'{A14}:11').text_sha256})
        allowed, reason = publishable(suspended, assess(suspended, states(card22)), rag.corpus)
        self.assertFalse(allowed)
        self.assertTrue(reason.startswith('clause_suspended_wording_uncertain'))

    def test_applicability_is_declared_not_invented(self):
        info = rag.applicability('R231-22')
        self.assertEqual((info['basis'], info['event_date_known']), ('assumed_in_force_at_snapshot', False))


class DescribeTests(unittest.TestCase):
    def test_description_cites_only_card_sources(self):
        result = assess(card22, states(card22, actor_is_cashier='not_visible'), policy='p_core')
        text = describe(card22, result, rag.corpus, anchor_sec=44.2,
                        facts=['работник встал и вышел из зоны кассы', 'клиент остался у окна'])
        for part in ('00:44.2', 'п. 22', '№ 231', 'https://adilet.zan.kz/rus/docs/V1900019680', 'от 29.11.2019',
                     card22.type_label_ru, 'Не удалось подтвердить'):
            self.assertIn(part, text)

    def test_smuggled_citations_are_rejected(self):
        result = assess(card22, states(card22))
        for fact in ('нарушен п. 99 Правил', 'см. https://example.com', 'по постановлению № 7'):
            with self.assertRaises(CitationError):
                describe(card22, result, rag.corpus, anchor_sec=1, facts=[fact])


if __name__ == '__main__':
    unittest.main()
