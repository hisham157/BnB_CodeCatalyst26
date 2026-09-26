import json

import pytest
from pydantic import ValidationError

from app.report_schemas import ReportNarrative, SkillNote
from app.schemas import FirstQuestion, StructuredModel
from app.services.gemini_service import generation_schema


def test_report_wire_schema_avoids_nested_bounds_without_mutating_validation():
    original = ReportNarrative.model_json_schema()
    wire = generation_schema(ReportNarrative)
    for keyword in ('maxItems', 'minItems', 'maxLength', 'minLength', 'maximum', 'minimum', 'default', 'title'):
        assert f'"{keyword}":' not in json.dumps(wire)
    assert wire['required'] == original['required']
    assert wire['additionalProperties'] is False
    assert wire['$defs']['ClaimInterpretation']['properties']['status']['enum'] == original['$defs']['ClaimInterpretation']['properties']['status']['enum']
    assert original == ReportNarrative.model_json_schema()
    with pytest.raises(ValidationError):
        SkillNote(skill='Python', why='x' * 801, supporting_turns=[1], remaining_gap='Gap')
    with pytest.raises(ValidationError):
        FirstQuestion(question='Question?', skill='Python', difficulty=99)


def test_schema_property_names_are_never_removed():
    class Example(StructuredModel):
        title: str
        minimum: int
    assert set(generation_schema(Example)['properties']) == {'title', 'minimum'}
