"""Episode transport; no claims about visual model accuracy."""
from PIL import Image
from backend.events import select_observations, action_type
from backend.pipeline import observation_bundle
from backend.video import Frame


def event(t, predicate='left_workplace', role='cashier'):
    return {'time':t,'description':'Synthetic','actor_role':role,'role_visible':True,
        'frames':[Frame(t,Image.new('RGB',(16,16)))],
        'facts':[{'predicate':predicate,'status':'confirmed','statement':'Synthetic fact'}]}


def test_repeated_action_merges_context_and_keeps_both_frames():
    a,b=event(10),event(12)
    b['facts'].append({'predicate':'cash_unattended','status':'confirmed','statement':'Extra context'})
    rows=select_observations([a,b],peak=10)
    assert len(rows)==1
    assert {f['predicate'] for f in rows[0]['facts']}=={'left_workplace','cash_unattended'}
    assert {f.timestamp for f in rows[0]['support_frames']}=={10,12}


def test_different_actions_roles_and_distant_repetitions_stay_separate():
    assert len(select_observations([event(10),event(11,'phone_in_hands'),event(25)]))==3
    assert len(select_observations([event(10),event(11,role='collector')]))==2


def test_no_top_three_cut():
    assert len(select_observations([event(t) for t in (1,10,20,30)]))==4


def test_unknown_only_is_not_evidence():
    row=event(10);row['facts'][0]['status']='unknown'
    assert select_observations([row])==[]


def test_observation_is_not_reclassified_by_experimental_field():
    assert len(select_observations([dict(event(10),risk_level='routine')]))==1


def test_type_is_action_not_retrieved_clause():
    assert action_type(event(10))=='Наблюдаемое действие: Уход с рабочего места'
    assert action_type(event(10,'phone_in_hands'))=='Наблюдаемое действие: Использование телефона'
    assert action_type(event(10,'other_observed_action'))=='Наблюдение для проверки'


def test_role_is_not_replaced_with_cashier():
    row=event(10,'bag_opened','collector')
    actor=observation_bundle([row])['actors'][0]
    assert actor['role']=='collector' and actor['role_status']=='confirmed'
    row.pop('actor_role')
    actor=observation_bundle([row])['actors'][0]
    assert actor['role']=='unknown' and actor['role_status']=='unknown'
