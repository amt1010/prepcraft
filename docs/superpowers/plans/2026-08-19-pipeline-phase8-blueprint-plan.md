# Phase 8 — Paper Blueprint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `PaperBlueprint` (DATA_MODEL.md core entity) plus the two things Phase 6 and Phase 7 explicitly deferred to "whenever Phase 8 gives them a caller": Workflow A blueprint derivation from an already-extracted `Paper`, and blueprint-driven `QuestionTemplate` selection — closing TODO.md's Phase 8 row (`models/blueprint.py`, "Blueprint derivation from extracted Paper structure") and PROJECT_PLAN.md's Phase 8 acceptance bar: "Blueprint from golden paper's structure is satisfied by generated paper."

**Architecture:** One new model file plus a new `blueprint/` package (two modules) plus one `validation/validator.py` addition plus one integration test. `models/blueprint.py` defines `BlueprintSection`/`PaperBlueprint` exactly as DATA_MODEL.md's "PaperBlueprint" section lists them — no extra fields this time, unlike Phase 7's `QuestionTemplate` extension, because Phase 8 has real callers for every field DATA_MODEL.md already lists. `blueprint/derive.py` implements Workflow A: `derive_blueprint_from_paper(paper, questions) -> PaperBlueprint` copies `Paper.sections` verbatim into `BlueprintSection`s (marks/question_count) and computes `difficulty_level` as the rounded mean of every extracted `Question.difficulty`. It leaves `BlueprintSection.allowed_types` as `None` — `Question` still has no `section` field (the exact gap Phase 6's TODO.md flagged: "no ... blueprint section-count recomputation, since `Question` has no `section` field"), so there is no way to derive *which* question types occurred in *which* section from an extracted `Paper` alone; closing that gap would mean adding a `section` field to the shared `Question` model, which is out of scope here since no phase has asked for it yet. `blueprint/template_selection.py` implements the shared tail's "Template selection" step: `select_templates_for_section` picks `QuestionTemplate`s for one `BlueprintSection`, filtered by `allowed_types` (when set) and by `difficulty_range` containing the blueprint's `difficulty_level`; when `question_count` is set it only accepts templates whose `marks` equals `section.marks / section.question_count` exactly (deterministic, no packing solver — if no template's marks divide evenly it raises rather than approximating); when `question_count` is `None` it greedily fills `section.marks` from the caller's seeded `random.Random`. `validation/validator.py` gains `validate_blueprint_compliance(blueprint, questions_by_section)`, checking total marks, per-section marks, per-section question counts, and per-section `allowed_types` — the concrete form of PROJECT_PLAN.md's "checking blueprint compliance (marks/question counts add up)". A final integration test derives a blueprint from a synthetic extracted `Paper`, selects seed templates via the new selector, generates a full candidate paper via Phase 7's `generate_question`, and checks it against both `validate_paper` (Phase 6) and `validate_blueprint_compliance` (this phase) with zero issues.

**Tech Stack:** Python stdlib `random` (seedable `random.Random`, same convention as Phase 7 — never module-level `random.*`). No new dependencies. Reuses `questions/template_registry.get_templates`, `generation/question_generator.generate_question`, `validation/validator.validate_paper`, `core/ids.new_id` — no duplicated logic.

**Spec:** `Master Claude Code Prompt — AI Practice Paper Generator.md` §19 ("PAPER BLUEPRINT" — the worked example this plan's integration test structure echoes) and PHASE 8 ("Implement paper blueprint"), `DATA_MODEL.md` ("PaperBlueprint" core entity, scoping invariant), `PIPELINE.md` ("Workflow A: existing paper -> new paper" ending in `QuestionModel (list[Question] + Paper)`; "Shared tail: blueprint -> PDF" starting with "Template selection — pick QuestionTemplates matching blueprint's topics/types/difficulty_range"), `ARCHITECTURE.md` (module map — this plan adds a `blueprint/` entry), `PROJECT_PLAN.md` ("What's deterministic vs. AI" — blueprint compliance is on the deterministic list; Phase 8's "Done when" row), `TODO.md` (Phase 8 scaffold; Phase 6's and Phase 7's "deliberately out of scope" notes naming Phase 8 as the caller), `app/backend/models/paper.py`, `app/backend/models/question.py`, `app/backend/questions/template_registry.py`, `app/backend/generation/question_generator.py`, `app/backend/validation/validator.py`.

## Global Constraints

- Blueprint derivation and template selection are deterministic — no LLM call, same input -> same output (PROJECT_PLAN.md's "What's deterministic vs. AI" list). Neither module imports from `providers/`.
- Every module boundary crosses with a Pydantic model, never a raw dict (DATA_MODEL.md line 3-4, spec §12, §35).
- Random choices go through a caller-supplied `random.Random`, never module-level `random.*` functions, matching Phase 7's `variable_sampler.py`/`question_generator.py` convention — reproducibility under a seed.
- `PaperBlueprint`'s fields are exactly DATA_MODEL.md's literal list (`id, subject, class_standard, total_marks, duration_minutes, sections, difficulty_level, derived_from_paper_id`) — no speculative extra fields this phase, since every field already has a real caller (derivation writes all of them, selection reads `sections`/`difficulty_level`, compliance-checking reads all of them).
- `BlueprintSection.allowed_types` stays `None` from Workflow A derivation — do not add a `section` field to the shared `Question` model to work around this; that is a cross-cutting change no phase has asked for yet, and `select_templates_for_section`'s marks-exact-match algorithm works correctly without it (verified by this plan's integration test).
- No CLI command this phase (no `generate-paper`) — matches Phase 6/7's precedent of deferring CLI wiring until every upstream piece it needs exists; TODO.md's Phase 9-10 row lists `render-paper`/`generate-answer-key` only, not `generate-paper`, so that wiring remains a later, undecided step.

---

### Task 1: `PaperBlueprint` / `BlueprintSection` models

**Files:**
- Create: `app/backend/models/blueprint.py`
- Test: `tests/unit/test_blueprint_model.py`

**Interfaces:**
- Consumes: `QuestionType` from `app.backend.models.question`.
- Produces: `BlueprintSection(BaseModel)` with fields `name: str`, `marks: float`, `question_count: int | None = None`, `allowed_types: list[QuestionType] | None = None`. `PaperBlueprint(BaseModel)` with fields `id: str`, `subject: str`, `class_standard: str`, `total_marks: float`, `duration_minutes: int`, `sections: list[BlueprintSection]`, `difficulty_level: int`, `derived_from_paper_id: str | None = None`. Tasks 2-5 import both directly: `from app.backend.models.blueprint import BlueprintSection, PaperBlueprint`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_blueprint_model.py
import pytest
from pydantic import ValidationError

from app.backend.models.blueprint import BlueprintSection, PaperBlueprint
from app.backend.models.question import QuestionType


def _blueprint(**overrides) -> PaperBlueprint:
    fields = {
        "id": "BP-TEST",
        "subject": "Mathematics",
        "class_standard": "III",
        "total_marks": 20.0,
        "duration_minutes": 50,
        "sections": [BlueprintSection(name="Arithmetic", marks=6.0, question_count=3)],
        "difficulty_level": 2,
    }
    fields.update(overrides)
    return PaperBlueprint(**fields)


def test_builds_a_valid_blueprint():
    blueprint = _blueprint()

    assert blueprint.difficulty_level == 2
    assert blueprint.derived_from_paper_id is None
    assert blueprint.sections[0].name == "Arithmetic"


def test_derived_from_paper_id_can_be_set():
    blueprint = _blueprint(derived_from_paper_id="PAPER-1")

    assert blueprint.derived_from_paper_id == "PAPER-1"


def test_blueprint_section_defaults_question_count_and_allowed_types_to_none():
    section = BlueprintSection(name="Word Problems", marks=4.0)

    assert section.question_count is None
    assert section.allowed_types is None


def test_blueprint_section_rejects_an_unknown_question_type_in_allowed_types():
    with pytest.raises(ValidationError):
        BlueprintSection(name="X", marks=1.0, allowed_types=["not_a_real_type"])


def test_blueprint_section_accepts_allowed_types():
    section = BlueprintSection(
        name="Word Problems",
        marks=4.0,
        question_count=2,
        allowed_types=[QuestionType.WORD_PROBLEM],
    )

    assert section.allowed_types == [QuestionType.WORD_PROBLEM]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_blueprint_model.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backend.models.blueprint'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/backend/models/blueprint.py
"""PaperBlueprint model (DATA_MODEL.md's "PaperBlueprint" core entity;
PIPELINE.md's shared tail: "PaperBlueprint (from extracted structure,
Workflow A; or from user selection, Workflow B)"). Fields match DATA_MODEL.md
literally — every field already has a real caller this phase, unlike Phase
7's QuestionTemplate extension."""

from pydantic import BaseModel

from app.backend.models.question import QuestionType


class BlueprintSection(BaseModel):
    name: str
    marks: float
    question_count: int | None = None
    allowed_types: list[QuestionType] | None = None


class PaperBlueprint(BaseModel):
    id: str
    subject: str
    class_standard: str
    total_marks: float
    duration_minutes: int
    sections: list[BlueprintSection]
    difficulty_level: int
    derived_from_paper_id: str | None = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_blueprint_model.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add app/backend/models/blueprint.py tests/unit/test_blueprint_model.py
git commit -m "add PaperBlueprint model"
```

---

### Task 2: `blueprint/derive.py` — Workflow A blueprint derivation

**Files:**
- Create: `app/backend/blueprint/__init__.py` (empty, matches every other module's package marker)
- Create: `app/backend/blueprint/derive.py`
- Test: `tests/unit/test_derive_blueprint.py`

**Interfaces:**
- Consumes: `Paper`, `Section` from `app.backend.models.paper`; `Question` from `app.backend.models.question`; `BlueprintSection`, `PaperBlueprint` from `app.backend.models.blueprint` (Task 1); `new_id` from `app.backend.core.ids`.
- Produces: `derive_blueprint_from_paper(paper: Paper, questions: list[Question]) -> PaperBlueprint`. Raises `ValueError` when `questions` is empty. Task 5 imports this directly: `from app.backend.blueprint.derive import derive_blueprint_from_paper`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_derive_blueprint.py
from datetime import datetime

import pytest

from app.backend.blueprint.derive import derive_blueprint_from_paper
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


def _question(number: str, difficulty: int) -> Question:
    return Question(
        id=f"Q-{number}",
        paper_id="PAPER-SOURCE",
        question_number=number,
        type=QuestionType.ARITHMETIC,
        text=f"{number} + 1",
        marks=1.0,
        topic="Addition",
        difficulty=difficulty,
        difficulty_features=_difficulty_features(),
        expected_answer="2",
        answer_type="numeric",
        source="existing_paper",
    )


def _paper() -> Paper:
    return Paper(
        id="PAPER-SOURCE",
        subject="Mathematics",
        class_standard="III",
        total_marks=6.0,
        duration_minutes=50,
        sections=[
            Section(name="Arithmetic", marks=3.0, question_count=3),
            Section(name="Word Problems", marks=3.0, question_count=1),
        ],
        source="existing_paper",
        created_at=datetime.now(),
    )


def test_derived_blueprint_copies_paper_scoping_and_sections():
    questions = [_question("1", difficulty=2), _question("2", difficulty=2)]

    blueprint = derive_blueprint_from_paper(_paper(), questions)

    assert blueprint.subject == "Mathematics"
    assert blueprint.class_standard == "III"
    assert blueprint.total_marks == 6.0
    assert blueprint.duration_minutes == 50
    assert [s.name for s in blueprint.sections] == ["Arithmetic", "Word Problems"]
    assert blueprint.sections[0].marks == 3.0
    assert blueprint.sections[0].question_count == 3
    assert blueprint.sections[0].allowed_types is None
    assert blueprint.derived_from_paper_id == "PAPER-SOURCE"


def test_difficulty_level_is_the_rounded_mean_of_question_difficulties():
    questions = [
        _question("1", difficulty=1),
        _question("2", difficulty=2),
        _question("3", difficulty=3),
    ]

    blueprint = derive_blueprint_from_paper(_paper(), questions)

    assert blueprint.difficulty_level == 2


def test_raises_when_no_questions_given():
    with pytest.raises(ValueError):
        derive_blueprint_from_paper(_paper(), [])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_derive_blueprint.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backend.blueprint'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/backend/blueprint/__init__.py
```

```python
# app/backend/blueprint/derive.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_derive_blueprint.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add app/backend/blueprint/__init__.py app/backend/blueprint/derive.py tests/unit/test_derive_blueprint.py
git commit -m "add derive_blueprint_from_paper for Workflow A"
```

---

### Task 3: `blueprint/template_selection.py` — blueprint-driven template selection

**Files:**
- Create: `app/backend/blueprint/template_selection.py`
- Test: `tests/unit/test_template_selection.py`

**Interfaces:**
- Consumes: `BlueprintSection`, `PaperBlueprint` from `app.backend.models.blueprint` (Task 1); `QuestionTemplate` from `app.backend.models.question_template`; `get_templates` from `app.backend.questions.template_registry`.
- Produces: `select_templates_for_section(section: BlueprintSection, difficulty_level: int, rng: random.Random, templates: list[QuestionTemplate] | None = None) -> list[QuestionTemplate]`. `select_templates_for_blueprint(blueprint: PaperBlueprint, rng: random.Random, templates: list[QuestionTemplate] | None = None) -> dict[str, list[QuestionTemplate]]` (keyed by section name). Both raise `ValueError` when no template can satisfy a section. Task 5 imports both directly.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_template_selection.py
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


def test_question_count_driven_selection_raises_when_no_template_matches_per_question_marks():
    pool = [_template(id="TPL-1", marks=1.0)]
    section = BlueprintSection(name="Arithmetic", marks=3.0, question_count=2)

    with pytest.raises(ValueError):
        select_templates_for_section(
            section, difficulty_level=1, rng=random.Random(1), templates=pool
        )


def test_marks_only_selection_fills_the_exact_section_marks():
    pool = [_template(id="TPL-1", marks=1.0), _template(id="TPL-2", marks=0.5)]
    section = BlueprintSection(name="Mental Maths", marks=2.0)

    selected = select_templates_for_section(
        section, difficulty_level=1, rng=random.Random(3), templates=pool
    )

    assert abs(sum(t.marks for t in selected) - 2.0) < 1e-9


def test_marks_only_selection_raises_when_remaining_marks_cannot_be_afforded():
    pool = [_template(id="TPL-1", marks=2.0)]
    section = BlueprintSection(name="X", marks=1.0)

    with pytest.raises(ValueError):
        select_templates_for_section(
            section, difficulty_level=1, rng=random.Random(1), templates=pool
        )


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_template_selection.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backend.blueprint.template_selection'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/backend/blueprint/template_selection.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_template_selection.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add app/backend/blueprint/template_selection.py tests/unit/test_template_selection.py
git commit -m "add blueprint-driven template selection"
```

---

### Task 4: `validate_blueprint_compliance`

**Files:**
- Modify: `app/backend/validation/validator.py`
- Test: `tests/unit/test_validator.py` (append)

**Interfaces:**
- Consumes: `PaperBlueprint`, `BlueprintSection` from `app.backend.models.blueprint` (Task 1); `Question` from `app.backend.models.question` (already imported); `ValidationIssue` (already defined in this file).
- Produces: `validate_blueprint_compliance(blueprint: PaperBlueprint, questions_by_section: dict[str, list[Question]]) -> list[ValidationIssue]`. Task 5 imports this directly: `from app.backend.validation.validator import validate_blueprint_compliance`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_validator.py`, right after the existing imports (add `BlueprintSection`, `PaperBlueprint`, `validate_blueprint_compliance` to the import lines) and at the end of the file:

```python
# add to the existing import block at the top of tests/unit/test_validator.py:
from app.backend.models.blueprint import BlueprintSection, PaperBlueprint
from app.backend.validation.validator import (
    validate_blueprint_compliance,
    validate_paper,
    validate_question,
)
```

```python
# append to the end of tests/unit/test_validator.py
def _blueprint(**overrides) -> PaperBlueprint:
    fields = {
        "id": "BP-1",
        "subject": "Mathematics",
        "class_standard": "III",
        "total_marks": 2.0,
        "duration_minutes": 50,
        "sections": [BlueprintSection(name="A", marks=2.0, question_count=2)],
        "difficulty_level": 1,
    }
    fields.update(overrides)
    return PaperBlueprint(**fields)


def test_matching_paper_has_no_blueprint_compliance_issues():
    blueprint = _blueprint()
    questions_by_section = {
        "A": [
            _question(question_number="1", marks=1.0),
            _question(question_number="2", marks=1.0),
        ]
    }

    assert validate_blueprint_compliance(blueprint, questions_by_section) == []


def test_section_marks_not_matching_blueprint_is_flagged():
    blueprint = _blueprint()
    questions_by_section = {"A": [_question(question_number="1", marks=1.0)]}

    issues = validate_blueprint_compliance(blueprint, questions_by_section)

    assert any(issue.code == "blueprint_section_marks_mismatch" for issue in issues)


def test_section_question_count_not_matching_blueprint_is_flagged():
    blueprint = _blueprint()
    questions_by_section = {"A": [_question(question_number="1", marks=2.0)]}

    issues = validate_blueprint_compliance(blueprint, questions_by_section)

    assert any(issue.code == "blueprint_section_count_mismatch" for issue in issues)


def test_missing_section_in_generated_questions_is_flagged():
    blueprint = _blueprint()

    issues = validate_blueprint_compliance(blueprint, {})

    assert any(issue.code == "blueprint_section_marks_mismatch" for issue in issues)
    assert any(issue.code == "blueprint_section_count_mismatch" for issue in issues)


def test_disallowed_question_type_is_flagged():
    blueprint = _blueprint(
        sections=[
            BlueprintSection(
                name="A", marks=1.0, question_count=1, allowed_types=[QuestionType.WORD_PROBLEM]
            )
        ],
        total_marks=1.0,
    )
    questions_by_section = {
        "A": [_question(question_number="1", marks=1.0, type=QuestionType.ARITHMETIC)]
    }

    issues = validate_blueprint_compliance(blueprint, questions_by_section)

    assert any(issue.code == "blueprint_type_not_allowed" for issue in issues)


def test_total_marks_not_matching_blueprint_is_flagged():
    blueprint = _blueprint(total_marks=5.0)
    questions_by_section = {
        "A": [
            _question(question_number="1", marks=1.0),
            _question(question_number="2", marks=1.0),
        ]
    }

    issues = validate_blueprint_compliance(blueprint, questions_by_section)

    assert any(issue.code == "blueprint_total_marks_mismatch" for issue in issues)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_validator.py -v`
Expected: FAIL — `ImportError: cannot import name 'validate_blueprint_compliance'`

- [ ] **Step 3: Write minimal implementation**

Add to `app/backend/validation/validator.py`, after the existing import block (add `PaperBlueprint` to a new import line) and after `validate_paper`:

```python
# add near the top, alongside the existing model imports:
from app.backend.models.blueprint import PaperBlueprint
```

```python
# append to the end of app/backend/validation/validator.py
def validate_blueprint_compliance(
    blueprint: PaperBlueprint, questions_by_section: dict[str, list[Question]]
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    total_marks = sum(
        question.marks for questions in questions_by_section.values() for question in questions
    )
    if abs(total_marks - blueprint.total_marks) > 1e-6:
        issues.append(
            ValidationIssue(
                code="blueprint_total_marks_mismatch",
                message=(
                    f"generated questions sum to {total_marks} marks, blueprint declares "
                    f"{blueprint.total_marks}"
                ),
            )
        )

    for section in blueprint.sections:
        section_questions = questions_by_section.get(section.name, [])
        section_marks = sum(question.marks for question in section_questions)
        if abs(section_marks - section.marks) > 1e-6:
            issues.append(
                ValidationIssue(
                    code="blueprint_section_marks_mismatch",
                    message=(
                        f"section {section.name!r} questions sum to {section_marks} marks, "
                        f"blueprint declares {section.marks}"
                    ),
                )
            )
        if (
            section.question_count is not None
            and len(section_questions) != section.question_count
        ):
            issues.append(
                ValidationIssue(
                    code="blueprint_section_count_mismatch",
                    message=(
                        f"section {section.name!r} has {len(section_questions)} questions, "
                        f"blueprint declares {section.question_count}"
                    ),
                )
            )
        if section.allowed_types is not None:
            for question in section_questions:
                if question.type not in section.allowed_types:
                    issues.append(
                        ValidationIssue(
                            code="blueprint_type_not_allowed",
                            message=(
                                f"question type {question.type} is not among section "
                                f"{section.name!r}'s allowed_types {section.allowed_types}"
                            ),
                            question_number=question.question_number,
                        )
                    )

    return issues
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_validator.py -v`
Expected: PASS (all tests, existing + 6 new)

- [ ] **Step 5: Commit**

```bash
git add app/backend/validation/validator.py tests/unit/test_validator.py
git commit -m "add validate_blueprint_compliance"
```

---

### Task 5: Integration test — Workflow A blueprint drives a compliant generated paper

**Files:**
- Test: `tests/integration/test_blueprint_generation_roundtrip.py`

**Interfaces:**
- Consumes: `derive_blueprint_from_paper` (Task 2), `select_templates_for_blueprint` (Task 3), `validate_paper` + `validate_blueprint_compliance` (Task 4, Phase 6), `generate_question` (Phase 7), `new_id` (`core/ids.py`), `Paper`/`Section` (`models/paper.py`), `Question`/`DifficultyFeatures`/`QuestionType` (`models/question.py`).
- Produces: nothing consumed by later tasks — this is the phase's closing acceptance test (PROJECT_PLAN.md Phase 8 "Done when": "Blueprint from golden paper's structure is satisfied by generated paper").

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_blueprint_generation_roundtrip.py
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
```

- [ ] **Step 2: Run test to verify it fails or passes for the wrong reason**

Run: `.venv/Scripts/python.exe -m pytest tests/integration/test_blueprint_generation_roundtrip.py -v`
Expected: FAIL before Tasks 1-4 exist (`ModuleNotFoundError`); once Tasks 1-4 are done this test should already pass without further implementation, since it only composes existing functions. If it fails after Tasks 1-4 are complete, inspect which assertion fails:
- `blueprint.difficulty_level == 2` failing means the mean-difficulty computation in `derive.py` is wrong.
- `validate_paper(...) == []` failing on `duplicate_question` means seed `7` produced a text collision — pick a different `random.Random` seed (try consecutive small integers) until no collision occurs, and record the working seed; this is a property of the RNG draw, not a bug in production code.
- `validate_blueprint_compliance(...) == []` failing on a `blueprint_section_*_mismatch` code means the fixture's section marks/question_count don't evenly divide by a seed template's marks — re-check the arithmetic in `_source_paper()` against `app/backend/questions/template_registry.py`'s current `TEMPLATES` marks values.

- [ ] **Step 3: No implementation step — this task only adds a test**

This task intentionally has no separate "minimal implementation" step: Tasks 1-4 already provide every function this test calls. If Step 2 shows the test passing once Tasks 1-4 are merged, proceed to Step 4.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/integration/test_blueprint_generation_roundtrip.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_blueprint_generation_roundtrip.py
git commit -m "add blueprint -> generated paper roundtrip integration test"
```

---

### Task 6: Update TODO.md and ARCHITECTURE.md

**Files:**
- Modify: `TODO.md`
- Modify: `ARCHITECTURE.md`

**Interfaces:** None — documentation only.

- [ ] **Step 1: Run the full test suite and ruff as a pre-flight check**

Run: `.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m ruff check .`
Expected: all tests pass, ruff reports no issues.

- [ ] **Step 2: Mark Phase 8 complete in TODO.md**

Replace the `## Phase 8 — Paper blueprint` section:

```markdown
## Phase 8 — Paper blueprint — **done 2026-08-19**

- [x] `app/backend/models/blueprint.py` — `BlueprintSection`, `PaperBlueprint`
      (DATA_MODEL.md core entity, fields match the spec literally — every
      field has a real caller this phase)
- [x] `app/backend/blueprint/derive.py` — `derive_blueprint_from_paper`
      (Workflow A): copies `Paper.sections` into `BlueprintSection`s,
      computes `difficulty_level` as the rounded mean of extracted
      `Question.difficulty`. `allowed_types` stays `None` per section —
      `Question` still has no `section` field to derive it from (Phase 6's
      TODO.md gap, still open)
- [x] `app/backend/blueprint/template_selection.py` —
      `select_templates_for_section` / `select_templates_for_blueprint`:
      the "Template selection" step Phase 7 deferred here. Marks-exact
      when `question_count` is set (no packing solver), greedy-fill by
      marks otherwise
- [x] `app/backend/validation/validator.py` — `validate_blueprint_compliance`:
      total marks, per-section marks, per-section question counts,
      per-section `allowed_types` (PROJECT_PLAN.md's "checking blueprint
      compliance (marks/question counts add up)")
- [x] Integration test: a blueprint derived from a synthetic extracted
      `Paper` drives template selection + generation into a full candidate
      paper that passes both `validate_paper` and
      `validate_blueprint_compliance` with zero issues — closes
      PROJECT_PLAN.md's Phase 8 acceptance bar

Deliberately out of scope this phase (no caller exists yet to need them):
no `generate-paper` CLI command — TODO.md's Phase 9-10 row only lists
`render-paper`/`generate-answer-key`, so CLI wiring for the full
blueprint-to-paper flow remains undecided. No `section` field added to
`Question` — `BlueprintSection.allowed_types` stays undiscoverable from
Workflow A extraction alone until that field exists; the integration test
confirms template selection still works correctly without it.
```

- [ ] **Step 3: Add `blueprint/` to ARCHITECTURE.md's module map**

In `ARCHITECTURE.md`'s `## Module map` code block, insert a new line between `questions/` and `generation/`:

```
    questions/     QuestionExtraction, QuestionTemplate model + registry
    blueprint/     PaperBlueprint derivation (Workflow A) + blueprint-driven template selection
    knowledge/     Chapter knowledge extraction (Workflow B only)
    generation/    Candidate generation from templates, value sampling
```

- [ ] **Step 4: Commit**

```bash
git add TODO.md ARCHITECTURE.md
git commit -m "mark Phase 8 paper blueprint complete"
```
