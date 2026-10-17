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
