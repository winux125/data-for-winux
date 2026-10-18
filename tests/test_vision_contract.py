import pytest
from PIL import Image

from backend.video import Frame
from backend.vision import VisualObserver


def test_absence_is_not_inferred_from_sparse_frames():
    observer = VisualObserver(None, ['count_before_issue', 'issue_interval_fully_visible', 'cash_issue'])
    frames = [Frame(12.4, Image.new('RGB', (10, 10)))]
    result = observer.validate({'anchor_index': 0, 'description': 'Передача денег',
        'facts': [{'predicate': 'count_before_issue', 'status': 'refuted', 'statement': 'Деньги пересчитаны'}]}, frames)
    assert result['facts'][0]['status'] == 'unknown'
    assert result['time'] == 12.4


def test_model_cannot_invent_evidence_index():
    observer = VisualObserver(None, ['left_workplace'])
    with pytest.raises(ValueError, match='anchor'):
        observer.validate({'anchor_index': 40}, [Frame(0, Image.new('RGB', (10, 10)))])


def test_empty_text_is_rejected_after_generation():
    observer=VisualObserver(None,['left_workplace'])
    frames=[Frame(0,Image.new('RGB',(10,10)))]
    for empty in ('description','statement'):
        event={'anchor_index':0,'description':'Synthetic',
               'facts':[{'predicate':'left_workplace','status':'confirmed','statement':'Synthetic'}]}
        if empty=='description':event['description']=''
        else:event['facts'][0]['statement']=''
        with pytest.raises(ValueError,match='Invalid'):
            observer.validate(event,frames)


def test_action_label_minimum_length_allows_russian_from_first_character():
    from lmformatenforcer import JsonSchemaParser
    from legal_rag.structured import parser_config
    parser = JsonSchemaParser({'type':'string','minLength':3,'maxLength':80},config=parser_config())
    parser = parser.add_character('"')
    assert 'У' in parser.get_allowed_characters()


def test_camera_schema_does_not_offer_legal_ownership_or_history_as_observations():
    observer=VisualObserver(None,['phone_in_hands','item_belongs_to_employee',
        'item_is_allowed_category','previously_received_cash','count_before_issue'])
    assert observer.observation_vocabulary == {'phone_in_hands'}


def test_bypassed_camera_answer_cannot_confirm_nonvisual_legal_conditions():
    from backend.vision import NON_VISUAL_PREDICATES
    observer=VisualObserver(None,[*NON_VISUAL_PREDICATES,'phone_in_hands'])
    frames=[Frame(1,Image.new('RGB',(10,10)))]
    for predicate in NON_VISUAL_PREDICATES:
        event={'anchor_index':0,'description':'Synthetic','actor_role':'cashier','role_visible':True,
            'facts':[{'predicate':predicate,'status':'confirmed','statement':'Synthetic proposition'}]}
        assert observer.validate(event,frames)['facts'][0]['status']=='unknown'
    event['facts'][0]['predicate']='phone_in_hands'
    assert observer.validate(event,frames)['facts'][0]['status']=='confirmed'


def test_client_departure_cannot_become_employee_departure():
    observer=VisualObserver(None,['left_workplace','phone_in_hands'])
    frames=[Frame(1,Image.new('RGB',(10,10)))]
    event={'anchor_index':0,'description':'Synthetic','actor_role':'client','role_visible':True,
        'facts':[{'predicate':'left_workplace','status':'confirmed','statement':'Synthetic proposition'}]}
    assert observer.validate(event,frames)['facts'][0]['status']=='unknown'
    event['facts'][0]['predicate']='phone_in_hands'
    assert observer.validate(event,frames)['facts'][0]['status']=='confirmed'
    event['facts'][0]['predicate']='left_workplace';event['actor_role']='cashier'
    assert observer.validate(event,frames)['facts'][0]['status']=='confirmed'
