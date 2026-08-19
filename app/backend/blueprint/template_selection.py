"""Blueprint-driven template selection (PIPELINE.md's shared tail: "Template
selection — pick QuestionTemplates matching blueprint's topics/types/
difficulty_range"), the exact step Phase 7's question_generator.py deferred
to this phase. Tries an exact marks match first (deterministic, no solver);
when a section's target marks don't divide evenly onto any single seed
template's marks — the normal case for a real extracted paper's actual
mixed marks, not just hand-built test fixtures — falls back to a greedy
gap-minimizing choice instead of failing outright, so generate_paper always
produces *something* and lets validate_blueprint_compliance report any
residual gap precisely rather than crashing generation over it."""

import random

from app.backend.models.blueprint import BlueprintSection, PaperBlueprint
from app.backend.models.question_template import QuestionTemplate
from app.backend.questions.template_registry import get_templates


def _fill_by_count(
    pool: list[QuestionTemplate], section: BlueprintSection, rng: random.Random
) -> list[QuestionTemplate]:
    if section.question_count == 0:
        return []

    per_question_marks = section.marks / section.question_count
    matching = [t for t in pool if abs(t.marks - per_question_marks) < 1e-9]
    if matching:
        return [rng.choice(matching) for _ in range(section.question_count)]

    selected: list[QuestionTemplate] = []
    running_total = 0.0
    for slot in range(section.question_count):
        remaining_slots = section.question_count - slot
        ideal_remaining_per_slot = (section.marks - running_total) / remaining_slots
        best_gap = min(abs(t.marks - ideal_remaining_per_slot) for t in pool)
        closest = [
            t for t in pool if abs(abs(t.marks - ideal_remaining_per_slot) - best_gap) < 1e-9
        ]
        template = rng.choice(closest)
        selected.append(template)
        running_total += template.marks
    return selected


def _fill_by_marks(
    pool: list[QuestionTemplate], section: BlueprintSection, rng: random.Random
) -> list[QuestionTemplate]:
    selected: list[QuestionTemplate] = []
    remaining = section.marks
    while remaining > 1e-9:
        affordable = [t for t in pool if t.marks <= remaining + 1e-9]
        if not affordable:
            break
        template = rng.choice(affordable)
        selected.append(template)
        remaining -= template.marks
    return selected


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
        return _fill_by_count(pool, section, rng)
    return _fill_by_marks(pool, section, rng)


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
