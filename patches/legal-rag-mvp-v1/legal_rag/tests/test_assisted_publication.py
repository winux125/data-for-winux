"""Policy regressions using scripted backends, not measurements of model quality."""
from dataclasses import replace
import json
import unittest

from legal_rag.apply import Scope, apply_card
from legal_rag.config import ExecutionConfig, PublicationConfig
from legal_rag.contracts import parse_input
from legal_rag.generate import FakeGenerator
from legal_rag.pipeline import LegalRAGRuntime
from legal_rag.tests.test_generation_pipeline import config, raw, valid_b
from legal_rag import shared


class ScriptedRealFlag(FakeGenerator):
    # Deliberately simulate backend metadata; this is NOT a real inference test.
    is_real_model = True


class AssistedPublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rag = shared().warm()

    def worker(self, *, real=True, fallback=False, enabled=True):
        cfg = replace(config(), publication=PublicationConfig('evidence_assisted',
            ('R231-22',) if enabled else (), fallback),
            execution=ExecutionConfig(True, 0, 2))
        gen = (ScriptedRealFlag if real else FakeGenerator)([json.dumps(valid_b(), ensure_ascii=False)] * 2)
        return LegalRAGRuntime(self.rag, cfg, generator=gen).warm()

    def assess(self, worker, data=None):
        return worker._assess(parse_input(data or raw()), 'V1900019680:rules1:p22',
            self.rag.cards['R231-22'], Scope('worker1', 'service1', window=(20, 25)))[0]

    def test_explicit_assisted_mode_does_not_forge_human_review(self):
        a = self.assess(self.worker())
        self.assertTrue(a.publishable['allowed'])
        self.assertFalse(a.publishable['review']['human_reviewed'])
        self.assertFalse(a.publishable['review']['production_active'])
        self.assertTrue(a.publishable['human_review_required'])

    def test_fake_and_not_enabled_cannot_publish(self):
        for kwargs in ({'real': False}, {'enabled': False}):
            self.assertFalse(self.assess(self.worker(**kwargs)).publishable['allowed'])

    def test_unknown_or_refuted_does_not_generate_or_publish(self):
        for status in ('unknown', 'refuted'):
            w = self.worker(); data = raw(); data['facts'][0]['status'] = status
            a = self.assess(w, data)
            self.assertFalse(a.publishable['allowed'])
            self.assertEqual(w.generator.calls, [])

    def test_fallback_is_an_explicit_choice(self):
        for fallback in (False, True):
            w = self.worker(fallback=fallback); w.generator.script = ['bad JSON'] * 2
            a = self.assess(w)
            self.assertEqual(a.generator, 'template_fallback')
            self.assertEqual(a.publishable['allowed'], fallback)

    def test_assisted_config_survives_device_override(self):
        w = self.worker()
        self.assertEqual(w.config.with_device('cpu').publication, w.config.publication)

    def test_generic_readings_are_budgeted_and_audited(self):
        w = self.worker()
        w.config = replace(w.config, retrieval=replace(w.config.retrieval, top_k=5))
        result = w.analyze(raw())
        self.assertLessEqual(result.tokens['model_calls'], 2)
        self.assertTrue(any(s['reason'] == 'general_candidate_budget'
                            for s in result.versions['skipped_candidates']))

    def test_default_policy_still_blocks_drafts_with_real_backend(self):
        w = self.worker(); w.config = replace(w.config, publication=PublicationConfig())
        a = self.assess(w)
        self.assertFalse(a.publishable['allowed'])
        self.assertEqual(a.publishable['reason'], 'rule_not_production_active')

    def test_exposed_cash_does_not_prove_previously_received_cash(self):
        data = raw()
        data['facts'] = [dict(data['facts'][0], predicate='cash_unattended')]
        data['actors'][0]['fact_ids'] = [data['facts'][0]['fact_id']]
        _, states, _ = apply_card(self.rag.cards['R231-20B'], parse_input(data),
                                 Scope('worker1', 'service1', window=(20, 25)))
        self.assertEqual(next(m.state for m in states if m.item_id == 'other_cash_on_desk'), 'unknown')

    def test_sheet_count_omission_requires_full_interval(self):
        card = self.rag.cards['R231-32']
        self.assertEqual(card.condition_map['issue_interval_visible']['facet'], 'evidence')
        self.assertEqual(card.condition_map['issue_interval_visible']['all'][0]['predicate'], 'issue_interval_fully_visible')

    def test_optional_background_reference_does_not_invalidate_self_contained_main_norm(self):
        w = self.worker()
        data = raw()
        a, _ = w._assess(parse_input(data), 'V1900019680:rules1:p12', self.rag.cards['R231-12'],
                         Scope('worker1', 'service1', window=(20, 25)))
        self.assertTrue(a.context_completeness['complete'])
