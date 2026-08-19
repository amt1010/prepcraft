import pytest
from pydantic import ValidationError

from app.backend.models.question import QuestionType
from app.backend.models.question_template import QuestionTemplate


def _template(**overrides) -> QuestionTemplate:
    fields = {
        "id": "TPL-TEST",
        "template_type": "addition_word_problem",
        "question_type": QuestionType.WORD_PROBLEM,
        "subject": "Mathematics",
        "grade": "III",
        "topic": "Addition",
        "marks": 2.0,
        "difficulty_range": (2, 3),
        "variables": {"a": "3_digit_number", "b": "3_digit_number"},
        "operation": "addition",
        "answer_expression": "a + b",
        "text_template": "{a} + {b}",
        "answer_type": "numeric",
    }
    fields.update(overrides)
    return QuestionTemplate(**fields)


def test_builds_a_valid_template():
    template = _template()

    assert template.question_type == QuestionType.WORD_PROBLEM
    assert template.difficulty_range == (2, 3)
    assert template.distractor_offsets is None


def test_distractor_offsets_default_to_none_but_can_be_set():
    template = _template(
        question_type=QuestionType.MULTIPLE_CHOICE, distractor_offsets=[-10, -1, 10]
    )

    assert template.distractor_offsets == [-10, -1, 10]


def test_rejects_an_unknown_question_type():
    with pytest.raises(ValidationError):
        _template(question_type="not_a_real_type")


def test_rejects_an_unknown_answer_type():
    with pytest.raises(ValidationError):
        _template(answer_type="essay")
