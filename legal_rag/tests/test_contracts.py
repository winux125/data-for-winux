"""Input/output contract: statuses, polarity, classifier rejection, output invariants."""
import copy
import unittest

from legal_rag.contracts import (ConditionMapping, ContractError, LegalAssessment, NormAssessment, NormRef,
                                 RequirementItem, Sentence, parse_input, validate_output)

BASE = {
    'schema': 'legal_rag.input.v1',
    'bundle_id': 'b1',
    'context': {'organization_type': 'bank', 'operation': 'cash_issue', 'event_date': None},
    'actors': [{'actor_id': 'a1', 'role': 'cashier', 'role_status': 'confirmed', 'fact_ids': ['f1']},
               {'actor_id': 'a2', 'role': 'client', 'role_status': 'inferred'}],
    'facts': [
        {'fact_id': 'f1', 'predicate': 'cash_issue', 'statement': 'кассир выдаёт клиенту деньги', 'status': 'confirmed',
         'actor_id': 'a1', 't_start': 20.0, 't_end': 22.0, 'anchor_sec': 21.4, 'evidence_refs': ['frame:21.4']},
        {'fact_id': 'f2', 'predicate': 'count_before_issue', 'statement': 'пересчёт подготовленной суммы при клиенте',
         'status': 'refuted', 'actor_id': 'a1', 't_start': 15.0, 't_end': 21.0, 'evidence_refs': ['clip:15-21']},
        {'fact_id': 'f3', 'predicate': 'packaging_intact', 'statement': 'целая неповреждённая банковская упаковка',
         'status': 'unknown'},
    ],
    'free_observations': [{'observation_id': 'o1', 'text': 'клиент сразу отошёл от окна', 'status': 'confirmed',
                           'evidence_refs': ['frame:22.0']}],
}


def bundle(**changes):
    raw = copy.deepcopy(BASE)
    raw.update(changes)
    return raw


class InputTests(unittest.TestCase):
    def test_statuses_absent_conflict_and_roles(self):
        b = parse_input(bundle())
        self.assertEqual(b.state('cash_issue').status, 'confirmed')
        self.assertEqual(b.state('count_before_issue').status, 'refuted')
        self.assertEqual(b.state('packaging_intact').status, 'unknown')
        self.assertEqual(b.state('never_reported').status, 'unknown')  # absent is unknown, not false
        self.assertTrue(b.role_confirmed('a1', 'cashier'))
        self.assertFalse(b.role_confirmed('a2', 'client'))              # inferred role confirms nothing
        raw = bundle()
        raw['facts'].append(dict(raw['facts'][0], fact_id='f4', status='refuted'))
        self.assertEqual(parse_input(raw).state('cash_issue').status, 'conflict')

    def test_sequence_in_time_is_not_a_conflict(self):
        raw = bundle()
        raw['actors'][0]['fact_ids'] = []
        raw['facts'] = [
            {'fact_id': 'p1', 'predicate': 'cashier_at_workplace', 'statement': 'кассир на рабочем месте',
             'status': 'confirmed', 'actor_id': 'a1', 't_start': 0.0, 't_end': 10.0, 'evidence_refs': ['clip:0-10']},
            {'fact_id': 'p2', 'predicate': 'cashier_at_workplace', 'statement': 'кассир на рабочем месте',
             'status': 'refuted', 'actor_id': 'a1', 't_start': 12.0, 't_end': 20.0, 'evidence_refs': ['clip:12-20']}]
        b = parse_input(raw)
        self.assertEqual(b.state('cashier_at_workplace').status, 'scope_required')
        self.assertEqual(b.state('cashier_at_workplace', window=(0, 10)).status, 'confirmed')
        self.assertEqual(b.state('cashier_at_workplace', window=(12, 20)).status, 'refuted')
        raw['facts'][1]['t_start'] = 5.0                      # overlapping opposite statuses: a real conflict
        self.assertEqual(parse_input(raw).state('cashier_at_workplace').status, 'conflict')

    def test_missing_scope_is_not_read_as_simultaneity(self):
        raw = bundle()
        raw['actors'][0]['fact_ids'] = []
        raw['facts'] = [
            {'fact_id': 'p1', 'predicate': 'cash_counted', 'statement': 'пересчёт денег', 'status': 'confirmed',
             'actor_id': 'a1', 'operation_id': 'op1', 'evidence_refs': ['frame:1']},
            {'fact_id': 'p2', 'predicate': 'cash_counted', 'statement': 'пересчёт денег', 'status': 'refuted',
             'actor_id': 'a1', 'operation_id': 'op2', 'evidence_refs': ['clip:2']}]
        b = parse_input(raw)
        self.assertEqual(b.state('cash_counted').status, 'scope_required')   # untimed: neither conflict nor a pick
        self.assertEqual(b.state('cash_counted', operation_id='op1').status, 'confirmed')
        self.assertEqual(b.state('cash_counted', operation_id='op2').status, 'refuted')
        self.assertEqual(b.state('cash_counted', window=(0, 100)).status, 'unknown')  # untimed facts cannot be placed

    def test_query_parts_preserve_polarity_and_origin(self):
        parts = {p.origin_id: p for p in parse_input(bundle()).query_parts()}
        self.assertEqual(parts['f1'].text, 'кассир выдаёт клиенту деньги')
        self.assertTrue(parts['f2'].text.startswith('не выполнено: '))   # refuted never reads as done
        self.assertEqual(parts['f2'].status, 'refuted')
        self.assertTrue(parts['f3'].text.startswith('не установлено: '))
        self.assertEqual((parts['o1'].origin, parts['o1'].status), ('free_observation', 'confirmed'))

    def test_classifier_fields_are_rejected_anywhere(self):
        for path in (('score',), ('facts', 0, 'confidence'), ('provenance', 'jepa')):
            raw = bundle(provenance={})
            target = raw
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = 0.9
            with self.assertRaises(ContractError):
                parse_input(raw)

    def test_invalid_inputs_fail_closed(self):
        cases = []
        raw = bundle(); raw['facts'][1]['evidence_refs'] = []; cases.append(raw)          # refuted without evidence
        raw = bundle(); raw['facts'][0]['actor_id'] = 'ghost'; cases.append(raw)
        raw = bundle(); raw['facts'][0]['anchor_sec'] = 30.0; cases.append(raw)
        raw = bundle(); raw['facts'][0]['status'] = 'probably'; cases.append(raw)
        raw = bundle(); raw['facts'][2]['fact_id'] = 'f1'; cases.append(raw)               # duplicate id
        raw = bundle(); raw['facts'][0]['extra'] = 1; cases.append(raw)
        raw = bundle(); raw['context']['event_date'] = '17.10.2026'; cases.append(raw)
        raw = bundle(schema='other'); cases.append(raw)
        for raw in cases:
            with self.assertRaises(ContractError):
                parse_input(raw)


def assessment(decision, states, complete=True):
    norm = NormRef('X:1', 'X', 'Учебный акт', 'https://example.invalid', 'unit', None, 'Учебная цитата нормы.',
                   '0' * 64, (1, 1), 'in_force_at_snapshot', None)
    items = [RequirementItem('c1', 'condition', 'выдача'), RequirementItem('c2', 'condition', 'нет пересчёта'),
             RequirementItem('e1', 'exception', 'целая упаковка', quote_span=(0, 7))]
    mapping = [ConditionMapping(k, v, ('f1',)) for k, v in states.items()]
    return NormAssessment(norm, 'obligation', items, mapping, decision, [], 'card', {'complete': complete},
                          [Sentence('s1', 'observation', 'текст', ('f1',))])


class OutputTests(unittest.TestCase):
    def setUp(self):
        self.b = parse_input(bundle())

    def test_violation_requires_all_conditions_exceptions_and_context(self):
        good = {'c1': 'true', 'c2': 'true', 'e1': 'false'}
        validate_output(LegalAssessment('b1', [assessment('violation_supported', good)]), self.b)
        for states, complete in (({'c1': 'true', 'c2': 'unknown', 'e1': 'false'}, True),
                                 ({'c1': 'true', 'c2': 'true', 'e1': 'unknown'}, True),
                                 ({'c1': 'true', 'c2': 'true'}, True),
                                 (good, False)):
            with self.assertRaises(ContractError):
                validate_output(LegalAssessment('b1', [assessment('violation_supported', states, complete)]), self.b)
        validate_output(LegalAssessment('b1', [assessment('insufficient', {'c1': 'true', 'e1': 'unknown'})]), self.b)

    def test_empty_requirement_cannot_support_a_violation(self):
        empty = assessment('violation_supported', {})
        empty.items, empty.mapping = [], []
        with self.assertRaises(ContractError):
            validate_output(LegalAssessment('b1', [empty]), self.b)
        only_exception = assessment('violation_supported', {'e1': 'false'})
        only_exception.items = [only_exception.items[2]]
        with self.assertRaises(ContractError):
            validate_output(LegalAssessment('b1', [only_exception]), self.b)

    def test_item_ids_unique_and_decided_states_cite_facts(self):
        duplicate = assessment('insufficient', {'c1': 'true'})
        duplicate.items.append(RequirementItem('c1', 'condition', 'повтор'))
        with self.assertRaises(ContractError):
            validate_output(LegalAssessment('b1', [duplicate]), self.b)
        uncited = assessment('insufficient', {'c1': 'true'})
        uncited.mapping[0].fact_ids = ()
        with self.assertRaises(ContractError):
            validate_output(LegalAssessment('b1', [uncited]), self.b)

    def test_unknown_facts_spans_and_empty_results_are_rejected(self):
        bad = assessment('insufficient', {'c1': 'true'})
        bad.mapping[0].fact_ids = ('ghost',)
        with self.assertRaises(ContractError):
            validate_output(LegalAssessment('b1', [bad]), self.b)
        span = assessment('insufficient', {'c1': 'true'})
        span.items[2].quote_span = (0, 999)
        with self.assertRaises(ContractError):
            validate_output(LegalAssessment('b1', [span]), self.b)
        with self.assertRaises(ContractError):
            validate_output(LegalAssessment('b1', []), self.b)
        validate_output(LegalAssessment('b1', [], no_norm={'reason': 'no_candidate_in_tiers'}), self.b)


if __name__ == '__main__':
    unittest.main()
