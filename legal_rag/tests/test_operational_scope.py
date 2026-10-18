"""Operational applicability guards; no video labels or model quality claims."""
import unittest
from types import SimpleNamespace

from legal_rag.review_sources import scope_mismatch
from legal_rag.structured import explanation_schema, parser_config


def bundle(predicate, statement='Наблюдаемый факт', status='confirmed'):
    return SimpleNamespace(facts=[SimpleNamespace(predicate=predicate, statement=statement, status=status)])


class OperationalScopeTests(unittest.TestCase):
    def test_cash_handling_does_not_establish_escort_operation(self):
        text = 'После окончания сопровождения клиент заполняет явочную карточку.'
        headings = ['Порядок осуществления сопровождения клиента']
        self.assertEqual(scope_mismatch(headings, text, bundle('cash_issue')), 'escort_operation_not_observed')
        self.assertIsNone(scope_mismatch(headings, text,
            bundle('other_observed_action', 'Сотрудники сопровождают клиента по маршруту')))

    def test_refuted_or_unknown_escort_does_not_establish_operation(self):
        for status in ('unknown', 'refuted'):
            self.assertIsNotNone(scope_mismatch(['Сопровождение'], '',
                bundle('other_observed_action', 'Сопровождение клиента', status)))

    def test_collection_chapter_requires_collection_observation(self):
        headings = ['Порядок осуществления операций по инкассации банкнот']
        self.assertIsNotNone(scope_mismatch(headings, '', bundle('cash_counting')))
        self.assertIsNone(scope_mismatch(headings, '', bundle('collection_bag')))

    def test_known_opposite_cash_flow_is_filtered_but_unknown_flow_is_not_invented(self):
        headings = ['Порядок осуществления кассовых операций по приему наличных денег']
        self.assertIsNotNone(scope_mismatch(headings, '', bundle('cash_issue')))
        self.assertIsNone(scope_mismatch(headings, '', bundle('cash_receipt')))
        self.assertIsNone(scope_mismatch(headings, '', bundle('phone_in_hands')))

    def test_explanation_schema_keeps_cyrillic_and_fixes_the_source_binding(self):
        from lmformatenforcer import JsonSchemaParser
        import json
        schema = explanation_schema('act:p19')
        parser = JsonSchemaParser(schema, config=parser_config())
        text = json.dumps({'node_id':'act:p19','connection':'Следует проверить связь с требованием.'},ensure_ascii=False)
        for character in text:parser = parser.add_character(character)
        self.assertTrue(parser.can_end())
        self.assertEqual(schema['properties']['node_id']['enum'], ['act:p19'])
        self.assertEqual(schema['properties']['connection']['maxLength'], 450)

    def test_bound_clause_and_explicit_question_are_not_false_accusations(self):
        from legal_rag.review import _validate_text
        uid = 'V1900019680:rules1:p12'
        text = 'Следует проверить, не нарушил ли работник требование пункта 12.'
        self.assertFalse(_validate_text({'node_id':uid,'connection':text}, uid)[1])
        for wrong in ('Следует проверить требование пункта 99.',
                      'Следует проверить. Работник нарушил правило.',
                      'Следует проверить наличие 12 банкнот.'):
            self.assertTrue(_validate_text({'node_id':uid,'connection':wrong},uid)[1])

    def test_alternate_qwen_endoftext_cannot_stop_inside_json(self):
        from legal_rag.structured import eos_kwargs
        generator = SimpleNamespace(processor=SimpleNamespace(tokenizer=SimpleNamespace(eos_token_id=151645)),
            model=SimpleNamespace(generation_config=SimpleNamespace(eos_token_id=[151645,151643],suppress_tokens=None)))
        self.assertEqual(eos_kwargs(generator),{'eos_token_id':151645,'suppress_tokens':[151643]})


if __name__ == '__main__':unittest.main()
