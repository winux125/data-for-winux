"""Source-selection integrity with scripted answers, not a semantic-quality score."""
from dataclasses import replace
import json
import unittest

from legal_rag import shared
from legal_rag.contracts import parse_input
from legal_rag.review import _validate_text
from legal_rag.review_sources import validate_selection, source_spans, prompt_packet
from legal_rag.tests.test_review import SimulatedReal
from legal_rag.tests.test_generation_pipeline import raw, config
from legal_rag.pipeline import LegalRAGRuntime


class RetrievedSourcesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rag = shared().warm()
        cls.uid = 'V1900019680:rules1:p75'
        cls.text = cls.rag.source_library().units[cls.uid].text

    def data(self):
        data = raw()
        data['facts'] = [dict(data['facts'][0], predicate='other_observed_action',
                              statement='Синтетическое наблюдение доступа в помещение')]
        data['actors'][0]['fact_ids'] = ['f1']
        return data

    def worker(self, *, reject=False, invent_quote=False, no_core=False):
        calls = []
        def script(system, user):
            value = json.loads(user); calls.append(value)
            if 'candidate_ids' in value:
                if reject:
                    return json.dumps(dict(node_id=None, span_id=None, fact_ids=[]))
                return json.dumps(dict(node_id=self.uid,
                    span_id='invented-line' if invent_quote else next(iter(source_spans({'text': self.text}))), fact_ids=['f1']), ensure_ascii=False)
            return json.dumps(dict(node_id=value['node_id'],
                connection='Возможную связь с требованием следует проверить с учётом исключений.'), ensure_ascii=False)
        cfg = config(); cfg = replace(cfg, execution=replace(cfg.execution, max_model_calls=9))
        worker = LegalRAGRuntime(self.rag, cfg, generator=SimulatedReal(script)).warm()
        worker.retriever.retrieve = lambda *args: {'tiers': {
            'core': [] if no_core else [{'unit_id': self.uid, 'rank': 1}],
            'operational': [{'unit_id': self.uid, 'rank': 1}] if no_core else []}}
        return worker, calls

    def test_norm_outside_eight_cards_is_selected_with_full_parent_and_context(self):
        worker, calls = self.worker()
        result = worker.review(self.data()); row = result['review_findings'][0]
        self.assertIsNone(row['rule_id'])
        self.assertEqual(row['norm']['norm_id'], self.uid)
        self.assertEqual(row['norm']['quote'], self.text)
        self.assertEqual(row['source_relation'], 'candidate_clause')
        self.assertEqual(row['decision'], 'insufficient')
        self.assertTrue(row['unknown_conditions'])
        self.assertTrue(row['publishable']['allowed'])
        self.assertEqual(len(calls), 2)  # selection + explanation, no formal reader cascade
        self.assertIn(self.text, [i['text'] for i in calls[-1]['packet']['items']])
        self.assertGreater(len(calls[-1]['packet']['items']), 1)
        self.assertTrue(row['supporting_norms'])
        self.assertEqual(row['validation']['source_selection'][0]['selected'], self.uid)

    def test_operational_tier_is_separate_fallback(self):
        worker, calls = self.worker(no_core=True)
        row = worker.review(self.data())['review_findings'][0]
        self.assertEqual([t['tier'] for t in row['validation']['source_selection']], ['core', 'operational'])
        self.assertEqual(row['norm']['norm_id'], self.uid)

    def test_no_match_does_not_fabricate_a_broken_clause(self):
        worker, _ = self.worker(reject=True)
        row = worker.review(self.data())['review_findings'][0]
        self.assertEqual(row['source_relation'], 'context_only')
        self.assertIsNone(row['norm']['unit_label'])
        self.assertEqual(row['decision'], 'not_established')

    def test_invented_requirement_line_is_rejected(self):
        worker, _ = self.worker(invent_quote=True)
        row = worker.review(self.data())['review_findings'][0]
        self.assertEqual(row['source_relation'], 'context_only')
        self.assertFalse(row['validation']['source_selection'][0]['generation']['valid'])

    def test_selector_cannot_cite_unknown_facts_or_unretrieved_nodes(self):
        base = dict(node_id=self.uid, span_id=next(iter(source_spans({'text': self.text}))), fact_ids=['f1'])
        parents = {self.uid: {'text': self.text}}
        for raw_value in (dict(base, fact_ids=['not_in_this_episode']), dict(base, node_id='other:p99')):
            self.assertTrue(validate_selection(raw_value, parents, {'f1': object()})[1])

    def test_known_card_norm_is_not_reinterpreted_to_bypass_refutation(self):
        worker, calls = self.worker()
        worker.retriever.retrieve = lambda *args: {'tiers': {'core': [{'unit_id': 'V1900019680:rules1:p22', 'rank': 1}]}}
        row = worker.review(self.data())['review_findings'][0]
        self.assertEqual(row['source_relation'], 'context_only')
        self.assertFalse(any('candidate_ids' in c for c in calls))

    def test_prompt_keeps_full_source_text_and_blank_lines_without_repeating_titles(self):
        worker, _ = self.worker()
        packet = worker._packet([self.uid])
        prepared = prompt_packet(packet, [self.uid])
        for original, shown in zip(packet['items'], prepared['items']):
            text = ''.join(shown['lines'].values()) if 'lines' in shown else shown['text']
            self.assertEqual(text, original['text'])
            self.assertNotIn('title', shown)
            self.assertEqual(prepared['sources'][shown['source_id']], original['title'])
        self.assertEqual(''.join(source_spans({'text': 'A\n\nB\n'}).values()), 'A\n\nB\n')


if __name__ == '__main__':
    unittest.main()
