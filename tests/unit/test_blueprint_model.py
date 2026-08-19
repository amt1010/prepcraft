import pytest
from pydantic import ValidationError

from app.backend.models.blueprint import BlueprintSection, PaperBlueprint
from app.backend.models.question import QuestionType


def _blueprint(**overrides) -> PaperBlueprint:
    fields = {
        "id": "BP-TEST",
        "subject": "Mathematics",
        "class_standard": "III",
        "total_marks": 20.0,
        "duration_minutes": 50,
        "sections": [BlueprintSection(name="Arithmetic", marks=6.0, question_count=3)],
        "difficulty_level": 2,
    }
    fields.update(overrides)
    return PaperBlueprint(**fields)


def test_builds_a_valid_blueprint():
    blueprint = _blueprint()

    assert blueprint.difficulty_level == 2
    assert blueprint.derived_from_paper_id is None
    assert blueprint.sections[0].name == "Arithmetic"


def test_derived_from_paper_id_can_be_set():
    blueprint = _blueprint(derived_from_paper_id="PAPER-1")

    assert blueprint.derived_from_paper_id == "PAPER-1"


def test_blueprint_section_defaults_question_count_and_allowed_types_to_none():
    section = BlueprintSection(name="Word Problems", marks=4.0)

    assert section.question_count is None
    assert section.allowed_types is None


def test_blueprint_section_rejects_an_unknown_question_type_in_allowed_types():
    with pytest.raises(ValidationError):
        BlueprintSection(name="X", marks=1.0, allowed_types=["not_a_real_type"])


def test_blueprint_section_accepts_allowed_types():
    section = BlueprintSection(
        name="Word Problems",
        marks=4.0,
        question_count=2,
        allowed_types=[QuestionType.WORD_PROBLEM],
    )

    assert section.allowed_types == [QuestionType.WORD_PROBLEM]
