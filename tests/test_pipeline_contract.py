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
    pipeline.detector_version = 'JEPA-LGBM-FULL'
    pipeline.jepa = SimpleNamespace(predict=lambda _: {
        'latency_sec': 0, 'label': 1, 'violation_detected': True, 'timecode_sec': None})
    frames = [Frame(t, Image.new('RGB', (64, 64), 'gray')) for t in (1., 9.)]
    events = [{'time': f.timestamp, 'description': 'Синтетический факт', 'role_visible': True, 'actor_role': 'cashier',
               'risk_level': 'possible_risk', 'risk_reason': 'Видимый тестовый признак', 'action_type': 'Уход с рабочего места',
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


def test_negative_classifier_skips_all_visual_and_legal_calls(monkeypatch):
    pipeline, _ = setup_pipeline(monkeypatch, True)
    pipeline.jepa = SimpleNamespace(predict=lambda _: {
        'latency_sec': 0, 'label': 0, 'violation_detected': False, 'timecode_sec': None})
    def forbidden(*args, **kwargs):
        raise AssertionError('Negative classifier must not call observation, sampling or RAG')
    pipeline.observer.observe = forbidden
    pipeline.legal.analyze = forbidden
    monkeypatch.setattr('backend.pipeline.sample', forbidden)
    result = pipeline.analyze('synthetic.mov', lambda _: None)
    assert result['verdict'] == 'no_violation'
    assert result['violations'] == []
    assert result['model_versions']['legal'] == 'not_run'
    assert result['model_versions']['detector'] == 'JEPA-LGBM-FULL'


def test_review_result_keeps_unknown_legal_conditions_and_real_frames(monkeypatch):
    pipeline, _ = setup_pipeline(monkeypatch, True)
    pipeline.review_mode = True
    def review(bundle):
        assert all(f['status'] == 'confirmed' for f in bundle['facts'])
        return {'schema': 'legal_rag.review.v1', 'assessments': [], 'review_findings': [{
            'schema': 'legal_rag.review.v1', 'finding_kind': 'possible_indication',
            'operation_id': 'event0', 'rule_id': 'test', 'decision': 'insufficient',
            'type_label': 'Возможный признак', 'source_relation': 'candidate_clause',
            'norm': {'title': 'Источник', 'unit_label': 'п. 22', 'quote': 'Тест',
                     'official_url': 'https://adilet.zan.kz/rus/docs/V1900019680'},
            'explanation_text': 'Работник ушёл; завершённость обслуживания неизвестна.',
            'unknown_conditions': ['Завершено ли обслуживание?'],
            'validation': {'scope': {'operation_id': 'event0'}},
            'evidence': [{'fact_id': 'e0_f0', 'evidence_refs': ['frame:1.0000']}],
            'human_review_required': True,
            'publishable': {'allowed': True, 'policy': 'possible_indications'}}]}
    pipeline.legal.review = review
    result = pipeline.analyze('synthetic-review.mov', lambda _: None)
    assert result['verdict'] == 'violation'
    row = result['violations'][0]
    assert row['legal_decision'] == 'insufficient'
    assert row['unknown_conditions'] == ['Завершено ли обслуживание?']
    assert row['rule']['section'] == 'п. 22'
    assert row['evidence_frames'][0]['timestamp_sec'] == 1.
    assert row['human_review_required'] is True


def test_different_retrieved_norms_without_card_ids_keep_full_quotes_and_are_not_merged(monkeypatch):
    import time
    pipeline, events = setup_pipeline(monkeypatch, True)
    events[1] = dict(events[1], time=4., frames=[Frame(4., Image.new('RGB', (64, 64), 'gray'))],
                     facts=[{'predicate': 'phone_in_hands', 'status': 'confirmed', 'statement': 'Синтетический второй факт'}])
    quote = 'Полный пункт.\n' + 'Строка нормы. ' * 200 + 'Конец пункта.'
    def review(bundle):
        return {'schema': 'legal_rag.review.v1', 'review_findings': [dict(
            schema='legal_rag.review.v1', finding_kind='possible_indication', rule_id=None,
            decision='insufficient', source_relation='candidate_clause', human_review_required=True,
            type_label='Эпизод для проверки', explanation_text='Условная связь с требованием.',
            unknown_conditions=['Условия применения'], validation={'scope': {'operation_id': f'event{i}'}},
            publishable={'allowed': True, 'policy': 'possible_indications'},
            norm={'norm_id': f'act:rules1:p{75+i}', 'title': 'Правила', 'unit_label': f'п. {75+i}',
                  'quote': quote, 'official_url': 'https://adilet.zan.kz/', 'headings': ['Глава 3']},
            supporting_norms=[{'title': 'Правила', 'unit_label': 'п. 2', 'quote': 'Полное исключение.',
                               'official_url': 'https://adilet.zan.kz/'}],
            evidence=[{'fact_id': f'e{i}_f0', 'evidence_refs': [f'frame:{event["time"]:.4f}']}]
        ) for i, event in enumerate(events)]}
    pipeline.legal.review = review
    result = pipeline.review_result('synthetic-norms.mov', events, {'timecode_sec': None}, 10., time.monotonic(), lambda _: None)
    assert len(result['violations']) == 2
    assert result['violations'][0]['rule']['quote'] == quote
    assert result['violations'][0]['rule']['path'] == ['Глава 3', 'п. 75']
    assert result['violations'][0]['rule']['context'][0]['quote'] == 'Полное исключение.'
