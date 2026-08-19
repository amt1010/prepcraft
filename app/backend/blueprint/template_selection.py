"""Blueprint-driven template selection (PIPELINE.md's shared tail: "Template
selection — pick QuestionTemplates matching blueprint's topics/types/
difficulty_range"), the exact step Phase 7's question_generator.py deferred
to this phase. Deterministic and marks-exact: given a BlueprintSection's
question_count, only templates whose declared marks equal
section.marks / section.question_count are eligible, so the generated
section's total marks always match the blueprint without a packing solver;
given only section.marks (no question_count), templates are greedily picked
by a caller-supplied random.Random until the marks are exactly filled."""

import random

from app.backend.models.blueprint import BlueprintSection, PaperBlueprint
from app.backend.models.question_template import QuestionTemplate
from app.backend.questions.template_registry import get_templates


def select_templates_for_section(
    section: BlueprintSection,
    difficulty_level: int,
    rng: random.Random,
    templates: list[QuestionTemplate] | None = None,
) -> list[QuestionTemplate]:
    pool = templates if templates is not None else get_templates()
    if section.allowed_types:
        pool = [t for t in pool if t.question_type in section.allowed_types]
    pool = [t for t in pool if t.difficulty_range[0] <= difficulty_level <= t.difficulty_range[1]]
    if not pool:
        raise ValueError(
            f"no templates match section {section.name!r} at difficulty {difficulty_level}"
        )

    if section.question_count is not None:
        if section.question_count == 0:
            return []
        per_question_marks = section.marks / section.question_count
        matching = [t for t in pool if abs(t.marks - per_question_marks) < 1e-9]
        if not matching:
            raise ValueError(
                f"no template in section {section.name!r} has marks={per_question_marks} "
                f"needed to fill {section.question_count} questions summing to {section.marks}"
            )
        return [rng.choice(matching) for _ in range(section.question_count)]

    selected: list[QuestionTemplate] = []
    remaining = section.marks
    while remaining > 1e-9:
        affordable = [t for t in pool if t.marks <= remaining + 1e-9]
        if not affordable:
            raise ValueError(
                f"cannot exactly fill section {section.name!r} marks={section.marks} "
                "from available template marks"
            )
        template = rng.choice(affordable)
        selected.append(template)
        remaining -= template.marks
    return selected


def select_templates_for_blueprint(
    blueprint: PaperBlueprint,
    rng: random.Random,
    templates: list[QuestionTemplate] | None = None,
) -> dict[str, list[QuestionTemplate]]:
    return {
        section.name: select_templates_for_section(
            section, blueprint.difficulty_level, rng, templates
        )
        for section in blueprint.sections
    }
