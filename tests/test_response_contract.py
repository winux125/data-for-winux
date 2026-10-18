import pytest
from pydantic import TypeAdapter, ValidationError

from backend.contracts import JobResponse, append_citation


def test_full_quote_extensions_survive_response_validation():
    quote = 'Полный пункт\n' + 'Содержимое ' * 1000 + 'Конец.'
    body = {'job_id':'test','status':'done','verdict':'violation','build_id':'keep',
        'violations':[{'type':'Действие','timecode_sec':1,'description':'Наблюдение',
            'rule':{'title':'Правила','quote':quote,'context':[{'quote':quote}]},
            'evidence_frames':[{'timestamp_sec':1,'image_base64':'test'}]}]}
    result = TypeAdapter(JobResponse).validate_python(body).model_dump(exclude_none=True)
    assert result['build_id'] == 'keep'
    assert result['violations'][0]['rule']['quote'] == quote
    assert result['violations'][0]['rule']['context'][0]['quote'] == quote


@pytest.mark.parametrize('body', [
    {'job_id':'test','status':'done','verdict':'violation','violations':[]},
    {'job_id':'test','status':'failed','verdict':'no_violation'},
    {'job_id':'test','status':'done','verdict':'unsupported','violations':[]}])
def test_inconsistent_or_third_verdict_is_rejected(body):
    with pytest.raises(ValidationError):TypeAdapter(JobResponse).validate_python(body)


def test_required_description_contains_source_even_if_extensions_ignored():
    rule = {'title':'Полный документ','section':'п. 19','url':'https://adilet.zan.kz/rus/docs/V1900019680',
            'unit_id':'V1900019680:rules1:p19','source_relation':'candidate_clause'}
    text = append_citation('Наблюдаемое действие.', rule)
    assert '№231' in text and 'п. 19' in text and rule['url'] in text


def test_context_only_citation_does_not_invent_a_clause():
    text = append_citation('Видимый признак.', {'title':'Правила','source_relation':'context_only','url':'https://adilet.zan.kz/'})
    assert 'общий контекст' in text and 'п.' not in text
