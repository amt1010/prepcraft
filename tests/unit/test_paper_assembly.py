import pytest

from app.backend.models.question import QuestionType
from app.backend.questions.extraction import ExtractedSubQuestion
from app.backend.questions.paper_assembly import question_from_extracted


def _extracted(**overrides) -> ExtractedSubQuestion:
    fields = {
        "question_number": "1",
        "text": "47 + 25 = ?",
        "type": "arithmetic",
        "marks": 1.0,
        "topic": "Addition",
        "difficulty": 2,
    }
    fields.update(overrides)
    return ExtractedSubQuestion(**fields)


def test_converts_a_fully_classified_question():
    question = question_from_extracted(_extracted(), paper_id="PAPER-1")

    assert question.paper_id == "PAPER-1"
    assert question.question_number == "1"
    assert question.text == "47 + 25 = ?"
    assert question.type == QuestionType.ARITHMETIC
    assert question.marks == 1.0
    assert question.topic == "Addition"
    assert question.difficulty == 2
    assert question.source == "existing_paper"
    assert question.id  # a real generated id, not empty


def test_expected_answer_is_the_unknown_placeholder():
    question = question_from_extracted(_extracted(), paper_id="PAPER-1")

    assert question.expected_answer == ""


def test_multiple_choice_gets_choice_answer_type_and_keeps_options():
    extracted = _extracted(
        type="multiple_choice", options=["405", "450", "500", "495"], text="___ + 305 = 800"
    )

    question = question_from_extracted(extracted, paper_id="PAPER-1")

    assert question.answer_type == "choice"
    assert question.options == ["405", "450", "500", "495"]


def test_true_false_gets_boolean_answer_type():
    extracted = _extracted(type="true_false", text="47 + 25 = 72")

    question = question_from_extracted(extracted, paper_id="PAPER-1")

    assert question.answer_type == "boolean"


def test_roman_numeral_gets_text_answer_type():
    extracted = _extracted(type="roman_numeral", text="Write the roman number for 27.")

    question = question_from_extracted(extracted, paper_id="PAPER-1")

    assert question.answer_type == "text"


def test_word_problem_gets_numeric_answer_type():
    extracted = _extracted(type="word_problem", text="A shopkeeper sold...")

    question = question_from_extracted(extracted, paper_id="PAPER-1")

    assert question.answer_type == "numeric"


@pytest.mark.parametrize("missing_field", ["marks", "topic", "difficulty"])
def test_raises_when_a_required_classification_field_is_missing(missing_field):
    extracted = _extracted(**{missing_field: None})

    with pytest.raises(ValueError):
        question_from_extracted(extracted, paper_id="PAPER-1")


def test_raises_on_the_unclassified_fallback_type():
    extracted = _extracted(type="unknown", marks=None, topic=None, difficulty=None)

    with pytest.raises(ValueError):
        question_from_extracted(extracted, paper_id="PAPER-1")
