"""Bound citations are formatting, while unsupported numbers remain rejected."""
import unittest
from legal_rag.review import _validate_text
from legal_rag.review_citations import citation_binding

UID='V1900019680:rules1:p19'
URL='https://adilet.zan.kz/rus/docs/V1900019680'
NORM={'citation_level':'clause','unit_label':'Пункт 19','official_url':URL}


class BoundCitationTests(unittest.TestCase):
    def validate(self,text,binding=None,uid=UID):
        return _validate_text({'node_id':uid,'connection':text},uid,
                              binding if binding is not None else citation_binding(UID,NORM,'231'))

    def test_russian_cases_of_selected_clause_are_accepted(self):
        for form in ('пункт 19','пункта 19','пункту 19','пунктом 19','пункте 19','п. 19','пункт № 19'):
            with self.subTest(form=form):
                text='Следует проверить соответствие требованию: '+form+'.'
                value,errors=self.validate(text)
                self.assertFalse(errors);self.assertEqual(value,text)

    def test_only_bound_act_number_and_exact_official_url_are_accepted(self):
        for citation in ('Правила № 231',URL,URL+'.'):
            with self.subTest(citation=citation):
                self.assertFalse(self.validate('Следует проверить условия: '+citation)[1])
        for citation in ('Правила № 230',URL+'.evil.example',URL+'#unknown',
                         'https://example.org/rule','https://adilet.zan.kz/rus/docs/V19000196800'):
            with self.subTest(citation=citation):
                self.assertTrue(self.validate('Следует проверить условия: '+citation)[1])

    def test_foreign_partial_and_quantity_numbers_are_not_erased(self):
        for text in ('Следует проверить пункт 190.','Следует проверить пункт 19.1.',
                     'Следует проверить пункт 19а.','Следует проверить подпункт 19.',
                     'Следует проверить наличие 19 банкнот.',
                     'Следует проверить пункту 19 и наличие 12 банкнот.',
                     'Следует проверить Правила № 231а.'):
            with self.subTest(text=text):self.assertTrue(self.validate(text)[1])

    def test_missing_act_metadata_does_not_authorize_an_act_number(self):
        binding=citation_binding(UID,NORM)
        self.assertTrue(self.validate('Следует проверить Правила № 231.',binding)[1])

    def test_document_context_cannot_be_promoted_to_an_exact_clause(self):
        binding=citation_binding(UID,dict(NORM,citation_level='document'),'231')
        self.assertTrue(self.validate('Следует проверить пункт 19.',binding)[1])
        self.assertFalse(self.validate('Документ № 231 служит общим контекстом проверки.',binding)[1])

    def test_article_citation_is_distinct_from_clause(self):
        uid='act:law1:a12';binding=citation_binding(uid,{'citation_level':'article'})
        self.assertFalse(self.validate('Следует проверить соответствие статье 12.',binding,uid)[1])
        self.assertTrue(self.validate('Следует проверить соответствие пункту 12.',binding,uid)[1])

    def test_citation_binding_does_not_remove_accusation_checks(self):
        self.assertTrue(self.validate('Следует проверить. Работник нарушил пункт 19.')[1])
        self.assertFalse(self.validate('Следует проверить, не нарушил ли работник пункт 19.')[1])

    def test_related_citations_require_actual_same_source_packet_nodes(self):
        norm=dict(NORM,source_id='V1900019680')
        binding=citation_binding(UID,norm,'231',[
            {'source_id':'V1900019680','node_id':'V1900019680:rules1:p57'},
            {'source_id':'V1900019680','node_id':'V1900019680:rules1:p58'},
            {'source_id':'other','node_id':'other:rules1:p99'}])
        self.assertEqual(binding['related_numbers'],['57','58'])
        for text in ('Следует проверить пункты 57 и 58.',
                     'Следует проверить условия пунктов 19, 57 и 58.',
                     'Следует проверить условия пункта 57.'):
            with self.subTest(text=text):self.assertFalse(self.validate(text,binding)[1])
        for text in ('Следует проверить пункты 57 и 99.',
                     'Следует проверить пункт 19, 57 банкнот.',
                     'Следует проверить наличие 58 банкнот.'):
            with self.subTest(text=text):self.assertTrue(self.validate(text,binding)[1])

    def test_same_act_different_container_does_not_authorize_bare_clause_number(self):
        binding=citation_binding(UID,dict(NORM,source_id='V1900019680'),'231',[
            {'source_id':'V1900019680','node_id':'V1900019680:appendix1:p57'},
            {'source_id':'V1900019680','node_id':'V1900019680:rules1:p58'}])
        self.assertEqual(binding['related_numbers'],['58'])
        self.assertTrue(self.validate('Следует проверить пункт 57.',binding)[1])
        self.assertFalse(self.validate('Следует проверить пункт 58.',binding)[1])


if __name__=='__main__':unittest.main()
