import random
from datetime import datetime

import pytest

from app.backend.generation.paper_generator import generate_paper
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


def _source_question(number: str, difficulty: int) -> Question:
    return Question(
        id=f"Q-{number}",
        paper_id="PAPER-SOURCE",
        question_number=number,
        type=QuestionType.ARITHMETIC,
        text=f"question {number}",
        marks=1.0,
        topic="Addition",
        difficulty=difficulty,
        difficulty_features=_difficulty_features(),
        expected_answer="0",
        answer_type="numeric",
        source="existing_paper",
    )


def _source_paper(sections: list[Section], total_marks: float) -> Paper:
    return Paper(
        id="PAPER-SOURCE",
        subject="Mathematics",
        class_standard="III",
        total_marks=total_marks,
        duration_minutes=50,
        sections=sections,
        source="existing_paper",
        created_at=datetime.now(),
    )


def test_generated_paper_marks_and_sections_match_the_derived_blueprint():
    sections = [
        Section(name="Arithmetic", marks=3.0, question_count=3),
        Section(name="Mental Maths", marks=1.5, question_count=3),
    ]
    source_paper = _source_paper(sections, total_marks=4.5)
    source_questions = [_source_question(str(i), difficulty=2) for i in range(1, 5)]

    generated_paper, generated_questions = generate_paper(
        source_paper, source_questions, rng=random.Random(1)
    )

    assert generated_paper.subject == "Mathematics"
    assert generated_paper.class_standard == "III"
    assert generated_paper.total_marks == 4.5
    assert generated_paper.source == "generated"
    assert generated_paper.source_paper_id == "PAPER-SOURCE"
    assert [s.name for s in generated_paper.sections] == ["Arithmetic", "Mental Maths"]
    assert sum(q.marks for q in generated_questions) == 4.5
    assert len(generated_questions) == 6


def test_generated_questions_are_sequentially_numbered_and_tagged_generated():
    sections = [Section(name="Arithmetic", marks=2.0, question_count=2)]
    source_paper = _source_paper(sections, total_marks=2.0)
    source_questions = [_source_question("1", difficulty=1)]

    generated_paper, generated_questions = generate_paper(
        source_paper, source_questions, rng=random.Random(2)
    )

    assert [q.question_number for q in generated_questions] == ["1", "2"]
    assert all(q.source == "generated" for q in generated_questions)
    assert all(q.paper_id == generated_paper.id for q in generated_questions)
    assert all(q.template_id is not None for q in generated_questions)


def test_difficulty_override_changes_which_templates_are_eligible():
    # marks=2.0/count=1 only exactly matches TPL-ADDITION-WORD-PROBLEM (the
    # only seed template with marks=2.0), and that template's difficulty_range
    # is (2, 3) — unreachable at the source paper's natural difficulty (1).
    # Without the override, best-effort selection falls back to the closest
    # available marks (1.0) instead of raising; with the override, the exact
    # match succeeds.
    sections = [Section(name="Word Problems", marks=2.0, question_count=1)]
    source_paper = _source_paper(sections, total_marks=2.0)
    source_questions = [_source_question("1", difficulty=1)]  # -> derived difficulty_level=1

    _, natural_questions = generate_paper(source_paper, source_questions, rng=random.Random(3))
    assert natural_questions[0].type != QuestionType.WORD_PROBLEM
    assert natural_questions[0].marks == 1.0  # closest achievable, not the aspirational 2.0

    _, overridden_questions = generate_paper(
        source_paper, source_questions, difficulty_override=2, rng=random.Random(3)
    )
    assert overridden_questions[0].type == QuestionType.WORD_PROBLEM
    assert overridden_questions[0].marks == 2.0


def test_generated_paper_marks_reflect_what_was_actually_generated_not_the_target():
    sections = [Section(name="Word Problems", marks=2.0, question_count=1)]
    source_paper = _source_paper(sections, total_marks=2.0)
    # best-effort picks a 1.0-mark template (no exact match at difficulty 1)
    source_questions = [_source_question("1", difficulty=1)]

    generated_paper, generated_questions = generate_paper(
        source_paper, source_questions, rng=random.Random(3)
    )

    assert generated_paper.total_marks == sum(q.marks for q in generated_questions)
    assert generated_paper.sections[0].marks == sum(q.marks for q in generated_questions)
    assert generated_paper.sections[0].question_count == len(generated_questions)


def test_raises_when_source_has_no_questions():
    source_paper = _source_paper([Section(name="A", marks=1.0)], total_marks=1.0)

    with pytest.raises(ValueError):
        generate_paper(source_paper, [], rng=random.Random(1))
