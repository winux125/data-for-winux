"""Synthetic output mapping only. No claims about JEPA/RAG prediction quality."""
from types import SimpleNamespace
import pytest
from PIL import Image
from backend.pipeline import Pipeline, AnalysisUnavailable, observation_bundle
from backend.video import Frame


def setup_pipeline(monkeypatch, allowed):
    import backend.pipeline as module
    pipeline = Pipeline.__new__(Pipeline)
    pipeline.build_id = 'synthetic_contract_test'
    pipeline.jepa = SimpleNamespace(predict=lambda _: {
        'latency_sec': 0, 'label': 0, 'violation_detected': False, 'timecode_sec': None})
    frames = [Frame(t, Image.new('RGB', (64, 64), 'gray')) for t in (1., 9.)]
    events = [{'time': f.timestamp, 'description': 'Синтетический факт', 'role_visible': True,
               'frames': [f], 'facts': [{'predicate': 'left_workplace', 'status': 'confirmed',
                                      'statement': 'Синтетический факт'}]} for f in frames]
    pipeline.observer = SimpleNamespace(observe=lambda _: events)
    pipeline.rag = SimpleNamespace(cards={'test': SimpleNamespace(type_label_ru='Синтетический тип')})
    class Runtime:
        def analyze(self, bundle):
            assert len({f['fact_id'] for f in bundle['facts']}) == 2
            rows = [{'rule_id': 'test', 'decision': 'violation_supported',
                     'publishable': {'allowed': allowed},
                     'validation': {'scope': {'operation_id': f'event{i}'}},
                     'norm': {'title': 'Синтетический источник', 'unit_label': None,
                              'official_url': 'https://adilet.zan.kz/rus/docs/V1900019680', 'quote': 'Тест'},
                     'explanation_text': 'Исходное объяснение RAG'} for i in range(2)]
            return SimpleNamespace(to_dict=lambda: {'assessments': rows})
    pipeline.legal = Runtime()
    monkeypatch.setattr(module, 'metadata', lambda _: 10.)
    monkeypatch.setattr(module, 'sample', lambda *_: frames)
    return pipeline, events


def test_multiple_events_keep_explanations_rules_and_jpegs(monkeypatch):
    pipeline, _ = setup_pipeline(monkeypatch, True)
    result = pipeline.analyze('synthetic.mov', lambda _: None)
    assert result['verdict'] == 'violation'
    assert [v['timecode_sec'] for v in result['violations']] == [1., 9.]
    for event in result['violations']:
        assert event['description'] == 'Исходное объяснение RAG'
        assert 'section' not in event['rule']  # Frontend accepts omitted, not null.
        assert event['rule']['url'].startswith('https://adilet.zan.kz/')
        assert len(event['evidence_frames']) == 1


def test_draft_card_is_never_promoted_or_returned_as_clean(monkeypatch):
    pipeline, _ = setup_pipeline(monkeypatch, False)
    with pytest.raises(AnalysisUnavailable, match='publication_not_allowed'):
        pipeline.analyze('synthetic.mov', lambda _: None)


def test_rag_receives_facts_without_detector_labels(monkeypatch):
    from legal_rag.contracts import parse_input
    _, events = setup_pipeline(monkeypatch, False)
    bundle = observation_bundle(events)
    parse_input(bundle)
    assert set(bundle) == {'schema', 'bundle_id', 'context', 'actors', 'facts', 'provenance'}
    assert {f['operation_id'] for f in bundle['facts']} == {'event0', 'event1'}
