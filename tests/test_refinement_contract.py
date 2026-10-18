"""Candidate selection only; no real visual or legal quality claims."""
from types import SimpleNamespace
from backend.pipeline import refinement_request


def setup():
    question=SimpleNamespace(id='context',question_ru='Видна ли продолжающаяся операция?')
    rag=SimpleNamespace(cards={'test':SimpleNamespace(conditions=(question,),exceptions=(),
      trigger_predicates=('left_workplace',),kind='commission')})
    event={'time':8,'facts':[{'predicate':'left_workplace','status':'confirmed'}]}
    assessment={'decision':'insufficient','rule_id':'test','context_completeness':{'complete':True},
      'items':[{'item_id':'action','facet':'breach'}],
      'mapping':[{'item_id':'action','state':'true'},{'item_id':'context','state':'unknown'}],
      'validation':{'scope':{'operation_id':'event0'}}}
    return rag,event,assessment


def test_refinement_is_factual_and_scoped_to_one_event():
    rag,event,a=setup()
    index,focus=refinement_request({'assessments':[a]},[event],rag)
    assert index==0 and focus['anchor_sec']==8
    assert focus['questions'][0]['id']=='context'
    assert 'decision' not in focus


def test_no_refinement_for_unobserved_trigger_or_incomplete_norm():
    for key in ('breach','context','decision'):
        rag,event,a=setup()
        if key=='breach':event['facts'][0]['status']='unknown'
        if key=='context':a['context_completeness']['complete']=False
        if key=='decision':a['decision']='refuted'
        assert refinement_request({'assessments':[a]},[event],rag) is None


def test_uncertain_breach_can_be_checked_when_trigger_is_observed():
    rag,event,a=setup()
    a['mapping'][0]['state']='unknown'
    assert refinement_request({'assessments':[a]},[event],rag) is not None
