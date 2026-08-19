"""Proves generate_paper's output actually satisfies the validators Phase 6
and Phase 8 built for it — the concrete meaning of "closes the caller gap."
Reuses the same realistic fixture shape as Phase 9/10's rendering
integration tests would recognize (Arithmetic / Word Problems / Mental
Maths), but as the *source* paper being regenerated from, not the output."""

import random
from datetime import datetime

from app.backend.blueprint.derive import derive_blueprint_from_paper
from app.backend.generation.paper_generator import generate_paper
from app.backend.models.paper import Paper, Section
from app.backend.models.question import DifficultyFeatures, Question, QuestionType
from app.backend.validation.validator import validate_blueprint_compliance, validate_paper


def _difficulty_features() -> DifficultyFeatures:
    return DifficultyFeatures(
        operation_count=1,
        requires_carrying=False,
        step_count=1,
        vocabulary_level="basic",
        reasoning_required=False,
    )


def _source_question(number: str) -> Question:
    return Question(
        id=f"Q-{number}",
        paper_id="PAPER-SOURCE",
        question_number=number,
        type=QuestionType.ARITHMETIC,
        text=f"question {number}",
        marks=1.0,
        topic="Addition",
        difficulty=2,
        difficulty_features=_difficulty_features(),
        expected_answer="0",
        answer_type="numeric",
        source="existing_paper",
    )


def _source_paper() -> Paper:
    return Paper(
        id="PAPER-SOURCE",
        subject="Mathematics",
        class_standard="III",
        total_marks=8.5,
        duration_minutes=50,
        sections=[
            Section(name="Arithmetic", marks=3.0, question_count=3),
            Section(name="Word Problems", marks=4.0, question_count=2),
            Section(name="Mental Maths", marks=1.5, question_count=3),
        ],
        source="existing_paper",
        created_at=datetime.now(),
    )


def test_generated_paper_passes_validate_paper_and_blueprint_compliance():
    source_paper = _source_paper()
    source_questions = [_source_question(str(i)) for i in range(1, 9)]

    generated_paper, generated_questions = generate_paper(
        source_paper, source_questions, rng=random.Random(7)
    )

    assert validate_paper(generated_paper, generated_questions) == []

    blueprint = derive_blueprint_from_paper(source_paper, source_questions)
    questions_by_section: dict[str, list[Question]] = {s.name: [] for s in blueprint.sections}
    remaining = list(generated_questions)
    for section in blueprint.sections:
        count = section.question_count or 0
        questions_by_section[section.name] = remaining[:count]
        remaining = remaining[count:]

    assert validate_blueprint_compliance(blueprint, questions_by_section) == []
