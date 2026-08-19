"""Closes Phase 7's deferral ("PaperBlueprint-driven template selection ...
is Phase 8's job") and Phase 6's TODO.md note ("no ... blueprint
section-count recomputation ... they become validator work again once
Phase 7/8 give them a caller"). Derives a blueprint from an extracted
Paper's structure (Workflow A), uses it to pick seed templates, generates a
full candidate paper, and checks it against both Phase 6's validate_paper
and this phase's validate_blueprint_compliance with zero issues."""

import random
from datetime import datetime

from app.backend.blueprint.derive import derive_blueprint_from_paper
from app.backend.blueprint.template_selection import select_templates_for_blueprint
from app.backend.core.ids import new_id
from app.backend.generation.question_generator import generate_question
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


def _extracted_question(number: str) -> Question:
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


def test_blueprint_derived_from_extracted_paper_drives_a_compliant_generated_paper():
    rng = random.Random(7)
    extracted_questions = [_extracted_question(str(i)) for i in range(1, 9)]

    blueprint = derive_blueprint_from_paper(_source_paper(), extracted_questions)
    assert blueprint.difficulty_level == 2

    templates_by_section = select_templates_for_blueprint(blueprint, rng)

    generated_paper_id = new_id("PAPER")
    all_questions: list[Question] = []
    questions_by_section: dict[str, list[Question]] = {}
    number = 1
    for section in blueprint.sections:
        section_questions = []
        for template in templates_by_section[section.name]:
            question = generate_question(
                template, paper_id=generated_paper_id, question_number=str(number), rng=rng
            )
            section_questions.append(question)
            all_questions.append(question)
            number += 1
        questions_by_section[section.name] = section_questions

    generated_paper = Paper(
        id=generated_paper_id,
        subject=blueprint.subject,
        class_standard=blueprint.class_standard,
        total_marks=blueprint.total_marks,
        duration_minutes=blueprint.duration_minutes,
        sections=[
            Section(name=s.name, marks=s.marks, question_count=s.question_count)
            for s in blueprint.sections
        ],
        source="generated",
        source_paper_id=blueprint.derived_from_paper_id,
        created_at=datetime.now(),
    )

    assert validate_paper(generated_paper, all_questions) == []
    assert validate_blueprint_compliance(blueprint, questions_by_section) == []
