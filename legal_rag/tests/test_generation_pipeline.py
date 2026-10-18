"""Integration and adversarial regressions for the interrupted generation implementation.

Scripted answers test orchestration and invariants, not Qwen's semantic quality.
"""
import copy
from dataclasses import replace
import json
from pathlib import Path
import unittest

from legal_rag import shared
from legal_rag.apply import (Scope, apply_card, decide, reading_states, validate_reading)
from legal_rag.config import load_config
from legal_rag.contracts import ConditionMapping, RequirementItem, parse_input
from legal_rag.generate import FakeGenerator, parse_json_object
from legal_rag.pipeline import LegalRAGRuntime
from legal_rag.prompts import DECISION_RU
from legal_rag.validate import validate_explanation

EXAMPLE = Path(__file__).parents[1] / 'examples' / 'leaving_workplace.json'


def raw():
    return json.loads(EXAMPLE.read_text(encoding='utf-8'))


def config():
    c = load_config().with_device('cpu', 'float32')
    return replace(c, retrieval=replace(c.retrieval, mode='bm25', top_k=1, tiers=('core',)))


def setUpModule():
    global rag
    rag = shared().warm()


def valid_b():
    return {'sentences': [
        dict(kind='observation', text='В 00:21.4 кассир покинул рабочее место.', fact_ids=['f1'], span_ids=[]),
        dict(kind='requirement', text='Кассиру не допускается покидать рабочее место до окончания обслуживания клиента.',
             fact_ids=[], span_ids=['norm']),
        dict(kind='conclusion', text=DECISION_RU['violation_supported'], fact_ids=[], span_ids=[])]}


def reading(parent):
    return dict(relevant=True, modality='prohibition', modality_quote=parent['text'].strip(),
                requirement='Кассиру не допускается уходить до завершения обслуживания клиента.',
                conditions=[dict(id='leaving', text='Работник покинул рабочее место', facet='breach',
                                 quote=parent['text'].strip(), facts=[dict(fact_id='f1', relation='same')]),
                            dict(id='serving', text='Обслуживание продолжается', facet='scope',
                                 quote=parent['text'].strip(), facts=[dict(fact_id='f2', relation='same')])],
                exceptions=[], unused_exception_segments=[])


class ApplyTests(unittest.TestCase):
    def test_card_positive_negative_unknown_and_exception(self):
        card = rag.cards['R231-22']
        for status, expected in (('confirmed', 'violation_supported'), ('refuted', 'refuted'), ('unknown', 'insufficient')):
            r = raw(); r['facts'][0]['status'] = status
            b = parse_input(r)
            items, states, modality = apply_card(card, b, Scope('worker1', 'service1', window=(20, 25)))
            self.assertEqual(decide(items, states, {'complete': True}, (True, None), modality)[0], expected)
        items = [RequirementItem('breach', 'condition', 'Нарушение'), RequirementItem('exception', 'exception', 'Допущение')]
        states = [ConditionMapping('breach', 'true', ('f1',)), ConditionMapping('exception', 'true', ('f2',))]
        self.assertEqual(decide(items, states, {'complete': True}, (True, None), 'obligation')[0], 'exception_applies')
        states[1] = ConditionMapping('exception', 'unknown')
        self.assertEqual(decide(items, states, {'complete': True}, (True, None), 'obligation')[0], 'insufficient')

    def test_permission_never_becomes_a_violation(self):
        self.assertEqual(decide([RequirementItem('a', 'condition', 'Действие')],
                                [ConditionMapping('a', 'true', ('f1',))], {'complete': True},
                                (True, None), 'permission')[0], 'not_applicable_scope')

    def test_other_operation_or_disjoint_time_cannot_complete_a_card(self):
        for field, value in (('operation_id', 'another'), ('t_start', 100)):
            r = raw(); r['facts'][1][field] = value
            if field == 't_start':
                r['facts'][1]['t_end'] = 120
            b = parse_input(r)
            items, states, mod = apply_card(rag.cards['R231-22'], b, Scope('worker1', 'service1', window=(20, 25)))
            self.assertEqual(decide(items, states, {'complete': True}, (True, None), mod)[0], 'insufficient')

    def test_inferred_role_does_not_confirm_scope(self):
        r = raw(); r['actors'][0]['role_status'] = 'inferred'
        b = parse_input(r)
        _, states, _ = apply_card(rag.cards['R231-22'], b, Scope('worker1', 'service1', window=(20, 25)))
        self.assertEqual(next(s.state for s in states if s.item_id == 'actor_is_cashier'), 'unknown')

    def test_bank_card_is_not_applied_to_an_exchange_office(self):
        r = raw(); r['context']['organization_type'] = 'exchange_office'
        result = LegalRAGRuntime(rag, config(), template_only=True).analyze(r)
        target = next(a for a in result.assessments if a.rule_id == 'R231-22')
        self.assertEqual(target.decision, 'not_applicable_scope')

    def test_reading_uses_original_polarity_and_rejects_modality_inversion(self):
        parent = rag.packet_sources(['V1900019680:rules1:p22'])['items'][0]
        r = raw(); r['facts'][0]['status'] = 'refuted'
        b = parse_input(r)
        a = reading(parent)
        validated = validate_reading(a, parent, [], b)
        self.assertFalse(validated.errors)
        self.assertEqual(reading_states(validated, b)[0].state, 'false')
        a['modality'] = 'obligation'
        self.assertTrue(validate_reading(a, parent, [], b).errors)

    def test_reading_requires_exact_quotes_and_accounts_for_exception_segments(self):
        parent = {'node_id': 'demo', 'text': 'Работнику запрещается покидать рабочее место. '
                  'За исключением случаев завершения обслуживания клиента.'}
        a = reading(parent)
        a['modality_quote'] = 'Работнику запрещается покидать рабочее место.'
        for entry in a['conditions']:
            entry['quote'] = a['modality_quote']
        self.assertTrue(any('exception segment' in e for e in validate_reading(a, parent, [], parse_input(raw())).errors))
        # Quoting the whole parent as a condition must not count as reading its exception.
        a['conditions'][0]['quote'] = parent['text']
        self.assertTrue(any('exception segment' in e for e in validate_reading(a, parent, [], parse_input(raw())).errors))
        a['conditions'][0]['quote'] = 'Неверная выдуманная формулировка'
        self.assertTrue(any('exact quote' in e for e in validate_reading(a, parent, [], parse_input(raw())).errors))

    def test_malformed_links_are_rejected_without_crashing(self):
        parent = rag.packet_sources(['V1900019680:rules1:p22'])['items'][0]
        for malformed in (42, [{'fact_id': [], 'relation': 'same'}], ['f1']):
            a = reading(parent); a['conditions'][0]['facts'] = malformed
            self.assertTrue(validate_reading(a, parent, [], parse_input(raw())).errors)


class ExplanationTests(unittest.TestCase):
    def context(self):
        return dict(decision='violation_supported', modality='prohibition', items=[], spans={'norm': 'Запрет'},
                    decided_fact_ids=['f1'])

    def test_valid_and_fabricated_citation(self):
        self.assertFalse(validate_explanation(valid_b(), self.context(), parse_input(raw()))[1])
        for text in ('По пункту 999 нарушение подтверждается', 'Согласно статье 123', 'https://invented.test',
                     'Постановление № 999', 'Исключений нет'):
            b = valid_b(); b['sentences'][1]['text'] = text
            self.assertTrue(validate_explanation(b, self.context(), parse_input(raw()))[1], text)

    def test_missing_norm_and_invalid_id_shapes(self):
        b = valid_b(); b['sentences'].pop(1)
        self.assertTrue(validate_explanation(b, self.context(), parse_input(raw()))[1])
        for bad in ({}, ['f1', []], 5):
            b = valid_b(); b['sentences'][0]['fact_ids'] = bad
            self.assertTrue(validate_explanation(b, self.context(), parse_input(raw()))[1])

    def test_refuted_fact_cannot_be_described_as_an_action(self):
        r = raw(); r['facts'][0]['status'] = 'refuted'
        self.assertTrue(any('negation' in e for e in validate_explanation(valid_b(), self.context(), parse_input(r))[1]))

    def test_unknown_and_conclusion_cannot_be_changed(self):
        ctx = self.context(); ctx.update(decision='insufficient', items=[dict(item_id='open', state='unknown')])
        self.assertTrue(validate_explanation(valid_b(), ctx, parse_input(raw()))[1])


class PipelineTests(unittest.TestCase):
    def test_real_corpus_template_chain_and_draft_publication_gate(self):
        worker = LegalRAGRuntime(rag, config(), template_only=True)
        result = worker.analyze(raw())
        target = next(a for a in result.assessments if a.rule_id == 'R231-22')
        self.assertEqual(target.decision, 'violation_supported')
        self.assertFalse(target.publishable['allowed'])
        self.assertEqual(target.generator, 'template_fallback')
        self.assertIn('https://adilet.zan.kz/rus/docs/V1900019680', target.explanation_text)
        self.assertIn('example:frame:21.4', target.explanation_text)
        self.assertIs(worker.warm(), worker)

    def test_valid_scripted_generation_is_labelled_fake(self):
        gen = FakeGenerator([json.dumps(valid_b(), ensure_ascii=False)])
        worker = LegalRAGRuntime(rag, config(), generator=gen).warm()
        assessment, _ = worker._assess(parse_input(raw()), 'V1900019680:rules1:p22', rag.cards['R231-22'],
                                      Scope('worker1', 'service1', window=(20, 25)))
        self.assertEqual(assessment.generator, 'fake_scripted')
        self.assertTrue(assessment.validation['call_b']['valid'])
        self.assertFalse(assessment.publishable['allowed'])
        self.assertEqual(len(gen.calls), 1)

    def test_failed_generation_retries_once_then_uses_template(self):
        gen = FakeGenerator(['not JSON', '{"sentences": []}'])
        worker = LegalRAGRuntime(rag, config(), generator=gen).warm()
        a, _ = worker._assess(parse_input(raw()), 'V1900019680:rules1:p22', rag.cards['R231-22'],
                              Scope('worker1', 'service1', window=(20, 25)))
        self.assertEqual(len(gen.calls), 2)
        self.assertIn('Предыдущий ответ отклонён', gen.calls[1][1])
        self.assertEqual(a.generator, 'template_fallback')
        self.assertEqual(a.decision, 'violation_supported')

    def test_reading_and_explanation_calls_share_a_generator(self):
        parent = rag.packet_sources(['V1900019680:rules1:p22'])['items'][0]
        gen = FakeGenerator([json.dumps(reading(parent), ensure_ascii=False), json.dumps(valid_b(), ensure_ascii=False)])
        worker = LegalRAGRuntime(rag, config(), generator=gen).warm()
        a, _ = worker._assess(parse_input(raw()), parent['node_id'])
        self.assertEqual(a.requirement_source, 'llm_reading_validated')
        self.assertEqual(a.decision, 'violation_supported')
        self.assertEqual(len(gen.calls), 2)

    def test_empty_bundle_and_shared_runtime(self):
        b = raw(); b['facts'] = []; b['actors'] = []
        result = LegalRAGRuntime(rag, config(), template_only=True).analyze(b)
        self.assertEqual(result.no_norm['decision'], 'no_norm')
        self.assertFalse(result.no_norm['exhaustive'])
        self.assertIs(rag.runtime(config(), template_only=True), rag.runtime(config(), template_only=True))

    def test_public_analyze_retrieves_a_noncard_norm_and_runs_both_calls(self):
        r = raw(); r['facts'] = [dict(r['facts'][0], predicate='cash_transfer',
                                   statement='Кассир передал деньги другому кассиру без записи в документе учета')]
        parent = rag.packet_sources(['V1900019680:rules1:p15'])['items'][0]
        a = dict(relevant=True, modality='obligation', modality_quote=parent['text'].splitlines()[0],
                 requirement='Передачу наличных между кассовыми работниками отражают в документе учета.',
                 conditions=[dict(id='unrecorded', text='Передача не отражена в документе учета', facet='breach',
                                  quote=parent['text'].splitlines()[0], facts=[dict(fact_id='f1', relation='same')])],
                 exceptions=[], unused_exception_segments=[])
        b = valid_b()
        b['sentences'][0]['text'] = 'В 00:21.4 кассир передал деньги другому кассиру без записи в документе учета.'
        b['sentences'][1]['text'] = a['requirement']
        gen = FakeGenerator([json.dumps(a, ensure_ascii=False), json.dumps(b, ensure_ascii=False)])
        result = LegalRAGRuntime(rag, config(), generator=gen).analyze(r)
        self.assertEqual(len(result.assessments), 1)
        assessment = result.assessments[0]
        self.assertEqual(assessment.norm.norm_id, parent['node_id'])
        self.assertEqual(assessment.requirement_source, 'llm_reading_validated')
        self.assertEqual(assessment.decision, 'violation_supported')
        self.assertEqual(assessment.generator, 'fake_scripted')
        self.assertEqual(result.tokens['model_calls'], 2)
        self.assertFalse(assessment.publishable['allowed'])

    def test_no_json_or_incomplete_object_is_rejected(self):
        for answer in ('garbage', '{"a":', '```json\n{"a": 1'):
            with self.assertRaises(ValueError):
                parse_json_object(answer)
        self.assertEqual(parse_json_object('```json\n{"a": {"b": "}"}}\n```'), {'a': {'b': '}'}})


if __name__ == '__main__':
    unittest.main()
