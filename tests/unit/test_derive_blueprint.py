from datetime import datetime

import pytest

from app.backend.blueprint.derive import derive_blueprint_from_paper
from app.backend.models.paper import Paper, Section
from app.backend.models.question import DifficultyFeatures, Question, QuestionType


def _difficulty_features() -> DifficultyFeatures:
    return DifficultyFeatures(
        operation_count=1,
        requires_carrying=False,
        step_count=1,
        vocabulary_level="basic",
        reasoning_required=False,
    )


def _question(number: str, difficulty: int) -> Question:
    return Question(
        id=f"Q-{number}",
        paper_id="PAPER-SOURCE",
        question_number=number,
        type=QuestionType.ARITHMETIC,
        text=f"{number} + 1",
        marks=1.0,
        topic="Addition",
        difficulty=difficulty,
        difficulty_features=_difficulty_features(),
        expected_answer="2",
        answer_type="numeric",
        source="existing_paper",
    )


def _paper() -> Paper:
    return Paper(
        id="PAPER-SOURCE",
        subject="Mathematics",
        class_standard="III",
        total_marks=6.0,
        duration_minutes=50,
        sections=[
            Section(name="Arithmetic", marks=3.0, question_count=3),
            Section(name="Word Problems", marks=3.0, question_count=1),
        ],
        source="existing_paper",
        created_at=datetime.now(),
    )


def test_derived_blueprint_copies_paper_scoping_and_sections():
    questions = [_question("1", difficulty=2), _question("2", difficulty=2)]

    blueprint = derive_blueprint_from_paper(_paper(), questions)

    assert blueprint.subject == "Mathematics"
    assert blueprint.class_standard == "III"
    assert blueprint.total_marks == 6.0
    assert blueprint.duration_minutes == 50
    assert [s.name for s in blueprint.sections] == ["Arithmetic", "Word Problems"]
    assert blueprint.sections[0].marks == 3.0
    assert blueprint.sections[0].question_count == 3
    assert blueprint.sections[0].allowed_types is None
    assert blueprint.derived_from_paper_id == "PAPER-SOURCE"


def test_difficulty_level_is_the_rounded_mean_of_question_difficulties():
    questions = [
        _question("1", difficulty=1),
        _question("2", difficulty=2),
        _question("3", difficulty=3),
    ]

    blueprint = derive_blueprint_from_paper(_paper(), questions)

    assert blueprint.difficulty_level == 2


def test_raises_when_no_questions_given():
    with pytest.raises(ValueError):
        derive_blueprint_from_paper(_paper(), [])
