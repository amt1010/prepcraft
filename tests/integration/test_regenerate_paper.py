"""Closes the actual Workflow A requirement, given directly by the user
after generate_paper's aggregate-marks mismatch was traced to the wrong
mechanism: "replace the existing question with different values and let
the weightage remain same irrespective of complexity... 375+125=? with 0.5
weightage becomes 436+234=? of 0.5 weightage." No blueprint, no aggregate
marks target, no gap to balance — regenerate_paper preserves per-question
marks by construction."""

import random
from datetime import datetime

from app.backend.generation.paper_generator import regenerate_paper
from app.backend.models.paper import Paper, Section
from app.backend.models.question import DifficultyFeatures, Question, QuestionType
from app.backend.validation.validator import validate_paper


def _difficulty_features() -> DifficultyFeatures:
    return DifficultyFeatures(
        operation_count=1,
        requires_carrying=False,
        step_count=1,
        vocabulary_level="basic",
        reasoning_required=False,
    )


def test_the_375_plus_125_example_from_the_conversation():
    source_question = Question(
        id="Q-1",
        paper_id="PAPER-SOURCE",
        question_number="1",
        type=QuestionType.ARITHMETIC,
        text="375 + 125 = ?",
        marks=0.5,
        topic="Addition",
        difficulty=3,
        difficulty_features=_difficulty_features(),
        expected_answer="500",
        answer_type="numeric",
        source="existing_paper",
    )
    source_paper = Paper(
        id="PAPER-SOURCE",
        subject="Mathematics",
        class_standard="III",
        total_marks=0.5,
        duration_minutes=50,
        sections=[Section(name="Arithmetic", marks=0.5, question_count=1)],
        source="existing_paper",
        created_at=datetime.now(),
    )

    generated_paper, generated_questions = regenerate_paper(
        source_paper, [source_question], rng=random.Random(5)
    )

    regenerated = generated_questions[0]
    assert regenerated.type == QuestionType.ARITHMETIC
    assert regenerated.marks == 0.5  # weightage unchanged
    assert regenerated.text != "375 + 125 = ?"  # different values
    assert generated_paper.total_marks == 0.5
    assert validate_paper(generated_paper, generated_questions) == []


def test_realistic_multi_type_paper_regenerates_1_to_1():
    questions = [
        Question(
            id="Q-1",
            paper_id="PAPER-SOURCE",
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
        ),
        Question(
            id="Q-2",
            paper_id="PAPER-SOURCE",
            question_number="2a",
            type=QuestionType.PREDECESSOR_SUCCESSOR,
            text="Write the predecessor and successor of 4759.",
            marks=1.0,
            topic="Predecessor and successor",
            difficulty=1,
            difficulty_features=_difficulty_features(),
            expected_answer="4758, 4760",
            answer_type="numeric",
            source="existing_paper",
        ),
        Question(
            id="Q-3",
            paper_id="PAPER-SOURCE",
            question_number="6c",
            type=QuestionType.ROMAN_NUMERAL,
            text="Which is the greatest roman number?",
            marks=0.5,
            topic="Roman Numerals",
            difficulty=3,
            difficulty_features=_difficulty_features(),
            expected_answer="XXVII",
            answer_type="text",
            source="existing_paper",
        ),
    ]
    source_paper = Paper(
        id="PAPER-SOURCE",
        subject="Mathematics",
        class_standard="III",
        total_marks=2.0,
        duration_minutes=20,
        sections=[Section(name="All Questions", marks=2.0, question_count=3)],
        source="existing_paper",
        created_at=datetime.now(),
    )

    generated_paper, generated_questions = regenerate_paper(
        source_paper, questions, rng=random.Random(9)
    )

    assert [q.question_number for q in generated_questions] == ["1a", "2a", "6c"]
    assert [q.marks for q in generated_questions] == [0.5, 1.0, 0.5]
    assert [q.type for q in generated_questions] == [
        QuestionType.MULTIPLE_CHOICE,
        QuestionType.PREDECESSOR_SUCCESSOR,
        QuestionType.ROMAN_NUMERAL,
    ]
    assert generated_paper.total_marks == 2.0
    assert validate_paper(generated_paper, generated_questions) == []
