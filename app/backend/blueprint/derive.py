"""Blueprint derivation from an already-extracted Paper (PIPELINE.md
Workflow A: "PaperBlueprint (from extracted structure, Workflow A...)").
Copies Paper.sections verbatim into BlueprintSection — allowed_types is left
None per section since Question has no section field to derive a
per-section type breakdown from (the same gap Phase 6's TODO.md noted: "no
... blueprint section-count recomputation, since Question has no section
field"). difficulty_level is the rounded mean of every extracted question's
difficulty, clamped to the spec §16 1-5 scale."""

from app.backend.core.ids import new_id
from app.backend.models.blueprint import BlueprintSection, PaperBlueprint
from app.backend.models.paper import Paper
from app.backend.models.question import Question


def derive_blueprint_from_paper(paper: Paper, questions: list[Question]) -> PaperBlueprint:
    if not questions:
        raise ValueError("cannot derive a blueprint from a paper with no questions")

    sections = [
        BlueprintSection(
            name=section.name, marks=section.marks, question_count=section.question_count
        )
        for section in paper.sections
    ]
    mean_difficulty = sum(question.difficulty for question in questions) / len(questions)
    difficulty_level = max(1, min(5, round(mean_difficulty)))

    return PaperBlueprint(
        id=new_id("BP"),
        subject=paper.subject,
        class_standard=paper.class_standard,
        total_marks=paper.total_marks,
        duration_minutes=paper.duration_minutes,
        sections=sections,
        difficulty_level=difficulty_level,
        derived_from_paper_id=paper.id,
    )
