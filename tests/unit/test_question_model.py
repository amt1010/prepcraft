import pytest
from pydantic import ValidationError

from app.backend.models.question import DifficultyFeatures, Question, QuestionType


def _difficulty_features() -> DifficultyFeatures:
    return DifficultyFeatures(
        digit_count=3,
        operation_count=1,
        requires_carrying=False,
        step_count=1,
        vocabulary_level="basic",
        reasoning_required=False,
    )


def test_question_round_trips_through_the_model_without_data_loss():
    question = Question(
        id="QUESTION-01",
        paper_id="PAPER-01",
        question_number="1a",
        type=QuestionType.MULTIPLE_CHOICE,
        text="___ + 305 = 800. What is the missing number?",
        options=["405", "450", "500", "495"],
        marks=0.5,
        topic="Addition",
        difficulty=2,
        difficulty_features=_difficulty_features(),
        expected_answer="495",
        answer_type="choice",
        source="existing_paper",
        template_id=None,
    )

    restored = Question.model_validate(question.model_dump())

    assert restored == question


def test_question_options_and_template_id_default_to_none():
    question = Question(
        id="QUESTION-02",
        paper_id="PAPER-01",
        question_number="2",
        type=QuestionType.ARITHMETIC,
        text="378 + 246",
        marks=1,
        topic="Addition",
        difficulty=2,
        difficulty_features=_difficulty_features(),
        expected_answer="624",
        answer_type="numeric",
        source="existing_paper",
    )

    assert question.options is None
    assert question.template_id is None


def test_question_rejects_an_invalid_type_value():
    with pytest.raises(ValidationError):
        Question(
            id="QUESTION-03",
            paper_id="PAPER-01",
            question_number="3",
            type="not_a_real_type",
            text="x",
            marks=1,
            topic="Addition",
            difficulty=1,
            difficulty_features=_difficulty_features(),
            expected_answer="1",
            answer_type="numeric",
            source="existing_paper",
        )


def test_question_rejects_an_invalid_answer_type_value():
    with pytest.raises(ValidationError):
        Question(
            id="QUESTION-04",
            paper_id="PAPER-01",
            question_number="4",
            type=QuestionType.TRUE_FALSE,
            text="x",
            marks=1,
            topic="Addition",
            difficulty=1,
            difficulty_features=_difficulty_features(),
            expected_answer="true",
            answer_type="not_a_real_answer_type",
            source="existing_paper",
        )


def test_question_rejects_an_invalid_source_value():
    with pytest.raises(ValidationError):
        Question(
            id="QUESTION-05",
            paper_id="PAPER-01",
            question_number="5",
            type=QuestionType.MENTAL_MATHS,
            text="x",
            marks=1,
            topic="Addition",
            difficulty=1,
            difficulty_features=_difficulty_features(),
            expected_answer="1",
            answer_type="numeric",
            source="not_a_real_source",
        )


def test_question_type_enum_has_exactly_the_mvp_types():
    assert {member.value for member in QuestionType} == {
        "multiple_choice",
        "fill_in_the_blank",
        "true_false",
        "arithmetic",
        "roman_numeral",
        "predecessor_successor",
        "rounding",
        "word_problem",
        "mental_maths",
    }
