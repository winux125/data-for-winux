"""Synthetic transport tests, not a model-quality evaluation."""
import copy
from backend.legal import assess, publishable_assessments


def test_only_public_analyze_is_called_and_result_is_unmodified():
    payload = {'assessments': [{'decision': 'insufficient', 'publishable': {'allowed': False}}]}
    expected = copy.deepcopy(payload)
    bundle = {'facts': []}
    class Result:
        def to_dict(self):
            return payload
    class Runtime:
        def analyze(self, actual):
            assert actual is bundle
            return Result()
    assert assess(Runtime(), bundle) is payload
    assert payload == expected


def test_publication_requires_both_original_decision_and_explicit_gate():
    allowed = {'decision': 'violation_supported', 'publishable': {'allowed': True}}
    rows = [allowed,
        {'decision': 'violation_supported', 'publishable': {'allowed': False}},
        {'decision': 'insufficient', 'publishable': {'allowed': True}},
        {'decision': 'violation_supported'}]
    assert publishable_assessments({'assessments': rows}) == [allowed]
