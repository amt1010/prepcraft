import pytest

from app.backend.models.question import QuestionType
from app.backend.questions.extraction import ExtractedSubQuestion
from app.backend.questions.paper_assembly import (
    assemble_paper_from_extracted,
    question_from_extracted,
)


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


def test_assembled_paper_uses_the_given_subject_class_and_duration():
    paper, questions = assemble_paper_from_extracted(
        subject="Mathematics",
        class_standard="III",
        duration_minutes=50,
        extracted_questions=[_extracted()],
    )

    assert paper.subject == "Mathematics"
    assert paper.class_standard == "III"
    assert paper.duration_minutes == 50
    assert paper.source == "existing_paper"


def test_total_marks_is_the_sum_of_extracted_marks():
    paper, questions = assemble_paper_from_extracted(
        subject="Mathematics",
        class_standard="III",
        duration_minutes=50,
        extracted_questions=[
            _extracted(question_number="1", marks=1.0),
            _extracted(question_number="2", marks=2.0),
        ],
    )

    assert paper.total_marks == 3.0


def test_all_questions_land_in_one_default_section():
    paper, questions = assemble_paper_from_extracted(
        subject="Mathematics",
        class_standard="III",
        duration_minutes=50,
        extracted_questions=[
            _extracted(question_number="1", marks=1.0),
            _extracted(question_number="2", marks=2.0),
        ],
    )

    assert len(paper.sections) == 1
    assert paper.sections[0].name == "All Questions"
    assert paper.sections[0].marks == 3.0
    assert paper.sections[0].question_count == 2


def test_questions_reference_the_assembled_papers_id():
    paper, questions = assemble_paper_from_extracted(
        subject="Mathematics",
        class_standard="III",
        duration_minutes=50,
        extracted_questions=[_extracted()],
    )

    assert questions[0].paper_id == paper.id


def test_empty_extracted_questions_produces_an_empty_paper():
    paper, questions = assemble_paper_from_extracted(
        subject="Mathematics",
        class_standard="III",
        duration_minutes=50,
        extracted_questions=[],
    )

    assert questions == []
    assert paper.total_marks == 0.0
    assert paper.sections[0].question_count == 0


def test_propagates_the_converters_error_for_an_unclassified_question():
    with pytest.raises(ValueError):
        assemble_paper_from_extracted(
            subject="Mathematics",
            class_standard="III",
            duration_minutes=50,
            extracted_questions=[_extracted(marks=None, topic=None, difficulty=None)],
        )


def test_preserves_sections_and_natural_question_order():
    paper, questions = assemble_paper_from_extracted(
        subject="Mathematics",
        class_standard="III",
        duration_minutes=50,
        extracted_questions=[
            _extracted(question_number="1a", section_name="Section A"),
            _extracted(question_number="2a", section_name="Section B"),
            _extracted(question_number="3a", section_name="Section B"),
        ],
    )

    assert [question.question_number for question in questions] == ["1a", "2a", "3a"]
    assert [(section.name, section.question_count) for section in paper.sections] == [
        ("Section A", 1),
        ("Section B", 2),
    ]
