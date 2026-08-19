from datetime import datetime

from app.backend.answer_key.builder import build_answer_key
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


def _question(number: str, answer: str, marks: float) -> Question:
    return Question(
        id=f"Q-{number}",
        paper_id="PAPER-1",
        question_number=number,
        type=QuestionType.ARITHMETIC,
        text=f"question {number}",
        marks=marks,
        topic="Addition",
        difficulty=1,
        difficulty_features=_difficulty_features(),
        expected_answer=answer,
        answer_type="numeric",
        source="existing_paper",
    )


def _paper() -> Paper:
    return Paper(
        id="PAPER-1",
        subject="Mathematics",
        class_standard="III",
        total_marks=3.0,
        duration_minutes=50,
        sections=[Section(name="A", marks=3.0)],
        source="existing_paper",
        created_at=datetime.now(),
    )


def test_one_entry_per_question_in_order():
    questions = [
        _question("1", "72", 1.0),
        _question("2", "XXVII", 0.5),
        _question("3", "15", 1.5),
    ]

    answer_key = build_answer_key(_paper(), questions)

    assert [entry.question_number for entry in answer_key.entries] == ["1", "2", "3"]
    assert [entry.answer for entry in answer_key.entries] == ["72", "XXVII", "15"]
    assert [entry.marks for entry in answer_key.entries] == [1.0, 0.5, 1.5]


def test_entry_question_id_and_paper_id_are_set():
    questions = [_question("1", "72", 1.0)]

    answer_key = build_answer_key(_paper(), questions)

    assert answer_key.paper_id == "PAPER-1"
    assert answer_key.entries[0].question_id == "Q-1"


def test_working_is_always_none():
    questions = [_question("1", "72", 1.0)]

    answer_key = build_answer_key(_paper(), questions)

    assert answer_key.entries[0].working is None


def test_empty_questions_produces_an_empty_answer_key():
    answer_key = build_answer_key(_paper(), [])

    assert answer_key.entries == []
    assert answer_key.paper_id == "PAPER-1"
