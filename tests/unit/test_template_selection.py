import random

import pytest

from app.backend.blueprint.template_selection import (
    select_templates_for_blueprint,
    select_templates_for_section,
)
from app.backend.models.blueprint import BlueprintSection, PaperBlueprint
from app.backend.models.question import QuestionType
from app.backend.models.question_template import QuestionTemplate


def _template(**overrides) -> QuestionTemplate:
    fields = {
        "id": "TPL-X",
        "template_type": "x",
        "question_type": QuestionType.ARITHMETIC,
        "subject": "Mathematics",
        "grade": "III",
        "topic": "Addition",
        "marks": 1.0,
        "difficulty_range": (1, 2),
        "variables": {"a": "1_digit_number", "b": "1_digit_number"},
        "operation": "addition",
        "answer_expression": "a + b",
        "text_template": "{a} + {b}",
        "answer_type": "numeric",
    }
    fields.update(overrides)
    return QuestionTemplate(**fields)


def test_question_count_driven_selection_picks_templates_matching_per_question_marks():
    pool = [_template(id="TPL-1", marks=1.0), _template(id="TPL-2", marks=2.0)]
    section = BlueprintSection(name="Arithmetic", marks=3.0, question_count=3)

    selected = select_templates_for_section(
        section, difficulty_level=1, rng=random.Random(1), templates=pool
    )

    assert len(selected) == 3
    assert all(t.id == "TPL-1" for t in selected)


def test_question_count_driven_selection_falls_back_to_the_closest_available_marks():
    pool = [_template(id="TPL-1", marks=1.0)]
    # 1.5 marks/question, no exact match
    section = BlueprintSection(name="Arithmetic", marks=3.0, question_count=2)

    selected = select_templates_for_section(
        section, difficulty_level=1, rng=random.Random(1), templates=pool
    )

    assert len(selected) == 2
    assert all(t.id == "TPL-1" for t in selected)
    assert sum(t.marks for t in selected) == 2.0  # closest achievable from a 1-template pool


def test_question_count_driven_selection_minimizes_the_gap_across_multiple_marks_values():
    pool = [
        _template(id="TPL-SMALL", marks=1.0),
        _template(id="TPL-MED", marks=1.5),
        _template(id="TPL-BIG", marks=3.0),
    ]
    section = BlueprintSection(name="X", marks=5.0, question_count=2)  # 2.5 each, no exact match

    selected = select_templates_for_section(
        section, difficulty_level=1, rng=random.Random(1), templates=pool
    )

    # slot 1 ideal=2.5 -> closest 3.0; slot 2 ideal=(5.0-3.0)/1=2.0 -> closest 1.5
    assert [t.id for t in selected] == ["TPL-BIG", "TPL-MED"]
    assert sum(t.marks for t in selected) == 4.5


def test_marks_only_selection_fills_the_exact_section_marks():
    pool = [_template(id="TPL-1", marks=1.0), _template(id="TPL-2", marks=0.5)]
    section = BlueprintSection(name="Mental Maths", marks=2.0)

    selected = select_templates_for_section(
        section, difficulty_level=1, rng=random.Random(3), templates=pool
    )

    assert abs(sum(t.marks for t in selected) - 2.0) < 1e-9


def test_marks_only_selection_stops_when_nothing_more_is_affordable():
    pool = [_template(id="TPL-1", marks=2.0)]
    # the only template costs more than the whole section
    section = BlueprintSection(name="X", marks=1.0)

    selected = select_templates_for_section(
        section, difficulty_level=1, rng=random.Random(1), templates=pool
    )

    assert selected == []


def test_marks_only_selection_fills_as_much_as_possible_then_stops():
    pool = [_template(id="TPL-1", marks=1.0)]
    section = BlueprintSection(name="X", marks=2.5)  # 1.0 + 1.0 = 2.0, remaining 0.5 unaffordable

    selected = select_templates_for_section(
        section, difficulty_level=1, rng=random.Random(1), templates=pool
    )

    assert len(selected) == 2
    assert sum(t.marks for t in selected) == 2.0


def test_difficulty_range_filters_out_ineligible_templates():
    pool = [_template(id="TPL-EASY", marks=1.0, difficulty_range=(1, 1))]
    section = BlueprintSection(name="X", marks=1.0, question_count=1)

    with pytest.raises(ValueError):
        select_templates_for_section(
            section, difficulty_level=3, rng=random.Random(1), templates=pool
        )


def test_allowed_types_narrows_the_pool():
    pool = [
        _template(id="TPL-ARITH", marks=1.0, question_type=QuestionType.ARITHMETIC),
        _template(id="TPL-WORD", marks=1.0, question_type=QuestionType.WORD_PROBLEM),
    ]
    section = BlueprintSection(
        name="X", marks=1.0, question_count=1, allowed_types=[QuestionType.WORD_PROBLEM]
    )

    selected = select_templates_for_section(
        section, difficulty_level=1, rng=random.Random(1), templates=pool
    )

    assert selected[0].id == "TPL-WORD"


def test_select_templates_for_blueprint_returns_one_list_per_section():
    pool = [_template(id="TPL-1", marks=1.0)]
    blueprint = PaperBlueprint(
        id="BP-1",
        subject="Mathematics",
        class_standard="III",
        total_marks=2.0,
        duration_minutes=50,
        sections=[
            BlueprintSection(name="A", marks=1.0, question_count=1),
            BlueprintSection(name="B", marks=1.0, question_count=1),
        ],
        difficulty_level=1,
    )

    result = select_templates_for_blueprint(blueprint, rng=random.Random(1), templates=pool)

    assert set(result.keys()) == {"A", "B"}
    assert len(result["A"]) == 1
    assert len(result["B"]) == 1
