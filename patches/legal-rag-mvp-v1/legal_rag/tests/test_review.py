"""Review-contract regressions; scripted outputs are not model-quality metrics."""
from dataclasses import replace
import json
import unittest

from legal_rag import shared
from legal_rag.generate import FakeGenerator
from legal_rag.pipeline import LegalRAGRuntime
from legal_rag.review import _validate_text
from legal_rag.tests.test_generation_pipeline import config, raw


class SimulatedReal(FakeGenerator):
    is_real_model = True  # Contract simulation only, not neural inference.


class ReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rag = shared().warm()

    def worker(self, real=True):
        def script(system, user):
            node = json.loads(user)['node_id']
            return json.dumps({'node_id': node, 'connection':
                'Возможную связь с требованием следует проверить по полному эпизоду.'}, ensure_ascii=False)
        cfg = config()
        cfg = replace(cfg, execution=replace(cfg.execution, explain_supported_only=True, max_model_calls=6))
        return LegalRAGRuntime(self.rag, cfg, generator=(SimulatedReal if real else FakeGenerator)(script)).warm()

    def test_unknown_context_is_review_not_legal_proof(self):
        data = raw()
        data['facts'][1]['status'] = 'unknown'
        row = self.worker().review(data)['review_findings'][0]
        self.assertEqual(row['decision'], 'insufficient')
        self.assertEqual(row['source_relation'], 'candidate_clause')
        self.assertTrue(row['unknown_conditions'])
        self.assertTrue(row['publishable']['allowed'])
        self.assertEqual(row['publishable']['policy'], 'possible_indications')
        self.assertIn('не окончательное', row['explanation_text'])
        self.assertFalse(self.rag.cards['R231-22'].review.human_reviewed)
        self.assertFalse(self.rag.cards['R231-22'].review.production_active)

    def test_unknowns_do_not_participate_in_search_or_become_observations(self):
        data = raw()
        for fact in data['facts'][1:]:
            fact['status'] = 'unknown'
        result = self.worker().review(data)
        row = result['review_findings'][0]
        self.assertEqual([f['fact_id'] for f in row['evidence']], ['f1'])
        for hits in result['retrieval'][0]['retrieval']['tiers'].values():
            for hit in hits:
                self.assertEqual(hit['query_origins'], ['f1'])

    def test_refuted_action_does_not_claim_its_clause_was_breached(self):
        data = raw()
        data['facts'][0]['status'] = 'refuted'
        row = self.worker().review(data)['review_findings'][0]
        self.assertEqual(row['source_relation'], 'context_only')
        self.assertIsNone(row['rule_id'])
        self.assertIsNone(row['norm']['unit_label'])
        self.assertEqual(row['norm']['citation_level'], 'document')
        self.assertEqual(row['decision'], 'not_established')
        self.assertIn('Опровергнуто наблюдением', row['explanation_text'])

    def test_all_unknown_does_not_invent_an_episode(self):
        data = raw()
        for fact in data['facts']:
            fact['status'] = 'unknown'
        worker = self.worker()
        self.assertEqual(worker.review(data)['review_findings'], [])
        self.assertEqual(worker.generator.calls, [])

    def test_fake_backend_cannot_publish_real_results(self):
        self.assertFalse(self.worker(False).review(raw())['review_findings'][0]['publishable']['allowed'])

    def test_generation_cannot_invent_citations_or_categorical_accusations(self):
        for text in ('Кассир нарушил закон.', 'Нарушен пункт 99.', 'См. https://example.com', 'Кража доказана.'):
            self.assertTrue(_validate_text({'node_id': 'a', 'connection': text}, 'a')[1])
        self.assertTrue(_validate_text({'node_id': 'wrong', 'connection': 'Следует проверить связь.'}, 'a')[1])

    def test_malformed_generation_uses_visible_facts_and_exact_source(self):
        worker = self.worker()
        worker.generator.script = lambda *_: 'bad json'
        data = raw(); data['facts'][1]['status'] = 'unknown'
        row = worker.review(data)['review_findings'][0]
        self.assertEqual(row['generator'], 'template_fallback')
        self.assertEqual(row['norm']['quote_sha256'], self.rag.corpus.clauses['V1900019680:22'].text_sha256)
        self.assertEqual(row['decision'], 'insufficient')


if __name__ == '__main__':
    unittest.main()
