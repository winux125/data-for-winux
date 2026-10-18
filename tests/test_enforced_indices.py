"""Regression: LM-format-enforcer ignores numeric minimum/maximum, but enforces enum."""
import pytest


def test_finite_integer_enum_rejects_out_of_range_frame_reference():
    from lmformatenforcer import JsonSchemaParser
    parser=JsonSchemaParser({'type':'integer','enum':list(range(12))})
    assert '4' in parser.get_allowed_characters()
    parser=parser.add_character('4')
    assert parser.can_end()
    assert '2' not in parser.get_allowed_characters()
