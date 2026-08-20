"""Top-level entry point of the generation/ module (ARCHITECTURE.md:
"Candidate generation from templates, value sampling"). Closes the caller
gap Phase 6-10's TODO.md notes all cited: composes Phase 8's blueprint
derivation + template selection with Phase 7's question generation into one
function producing a full generated Paper + list[Question]
(PIPELINE.md's shared tail, minus validation and rendering — see this
plan's Global Constraints for why those stay separate steps)."""

import random
from datetime import datetime

from app.backend.blueprint.derive import derive_blueprint_from_paper
from app.backend.blueprint.template_selection import select_templates_for_blueprint
from app.backend.core.ids import new_id
from app.backend.generation.question_generator import generate_question, regenerate_question
from app.backend.models.paper import Paper, Section
from app.backend.models.question import Question
from app.backend.providers.text_generation import TextGenerationProvider


def generate_paper(
    source_paper: Paper,
    source_questions: list[Question],
    difficulty_override: int | None = None,
    rng: random.Random | None = None,
    text_provider: TextGenerationProvider | None = None,
) -> tuple[Paper, list[Question]]:
    rng = rng or random.Random()

    blueprint = derive_blueprint_from_paper(source_paper, source_questions)
    if difficulty_override is not None:
        blueprint = blueprint.model_copy(update={"difficulty_level": difficulty_override})

    templates_by_section = select_templates_for_blueprint(blueprint, rng)

    generated_paper_id = new_id("PAPER")
    generated_questions: list[Question] = []
    generated_sections: list[Section] = []
    number = 1
    for section in blueprint.sections:
        section_questions: list[Question] = []
        for template in templates_by_section[section.name]:
            question = generate_question(
                template,
                paper_id=generated_paper_id,
                question_number=str(number),
                rng=rng,
                text_provider=text_provider,
            )
            section_questions.append(question)
            generated_questions.append(question)
            number += 1
        generated_sections.append(
            Section(
                name=section.name,
                marks=sum(q.marks for q in section_questions),
                question_count=len(section_questions),
            )
        )

    generated_paper = Paper(
        id=generated_paper_id,
        subject=blueprint.subject,
        class_standard=blueprint.class_standard,
        total_marks=sum(section.marks for section in generated_sections),
        duration_minutes=blueprint.duration_minutes,
        sections=generated_sections,
        source="generated",
        source_paper_id=blueprint.derived_from_paper_id,
        created_at=datetime.now(),
    )
    return generated_paper, generated_questions


def regenerate_paper(
    source_paper: Paper,
    source_questions: list[Question],
    rng: random.Random | None = None,
    text_provider: TextGenerationProvider | None = None,
) -> tuple[Paper, list[Question]]:
    if not source_questions:
        raise ValueError("cannot regenerate a paper with no questions")
    rng = rng or random.Random()
    generated_paper_id = new_id("PAPER")

    generated_questions = [
        regenerate_question(
            question,
            generated_paper_id,
            rng,
            text_provider=text_provider,
        ).model_copy(update={"question_number": str(index)})
        for index, question in enumerate(source_questions, start=1)
    ]

    generated_paper = Paper(
        id=generated_paper_id,
        subject=source_paper.subject,
        class_standard=source_paper.class_standard,
        total_marks=sum(question.marks for question in generated_questions),
        duration_minutes=source_paper.duration_minutes,
        sections=[
            Section(name=s.name, marks=s.marks, question_count=s.question_count)
            for s in source_paper.sections
        ],
        source="generated",
        source_paper_id=source_paper.id,
        created_at=datetime.now(),
    )
    return generated_paper, generated_questions
