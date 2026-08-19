# generate_paper Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the caller gap every phase from 6 onward has flagged ("nothing produces a full generated `Paper` + `Question` set until Phase 7/8 give them a caller") by building `generate_paper` — a single function that takes an already-extracted source `Paper` + `list[Question]` and produces a new generated `Paper` + `list[Question]`, composing Phase 8's blueprint derivation/selection with Phase 7's question generation. This is PROJECT_PLAN.md's demo step 4 ("`generate-paper --source <run_id> --difficulty 2` — builds a blueprint from the extracted structure, generates candidate questions with new values, computes answers") minus the `--source <run_id>` CLI/disk-loading part.

**Scope decision (made with the user before writing this plan):** two gaps were found while scoping this that go beyond "no orchestrator exists" — (1) nothing in the codebase builds a `Paper` (subject/class/total_marks/duration/sections) from an extraction run, and (2) nothing converts Phase 4's `ExtractedSubQuestion` (no `id`, `expected_answer`, or `difficulty_features`) into Phase 5's full `Question`. Given that, this plan builds `generate_paper` as a pure function over already-constructed `Paper`/`Question` objects — formalizing what Phase 8's integration test already proved works, plus a `difficulty_override` parameter the demo's `--difficulty` flag implies. It does **not** build `--source <run_id>` CLI loading, the `ExtractedSubQuestion` → `Question` converter, or Paper-from-run assembly — those are new, separate gaps, recorded as still open.

**Architecture:** One new function in `generation/paper_generator.py` (the module ARCHITECTURE.md already describes as "Candidate generation from templates, value sampling" — `generate_paper` is that module's top-level entry point, calling into `blueprint/derive.py`, `blueprint/template_selection.py`, and `generation/question_generator.py`, all built already). No new models, no new dependencies — pure composition of Phase 7 and Phase 8 code, with one new behavior: an optional `difficulty_override` that replaces the blueprint's derived `difficulty_level` before template selection runs, giving the CLI's future `--difficulty N` flag something real to plug into.

**Tech Stack:** Python stdlib `random` (seedable, caller-supplied, same convention as every generation/blueprint module). No new dependencies.

**Spec:** `PROJECT_PLAN.md` ("First end-to-end demo" step 4 — the literal source of `--difficulty` and the generate/validate/render step split; "What's deterministic vs. AI" list), `PIPELINE.md` ("Shared tail: blueprint -> PDF" — this function *is* that shared tail, minus rendering), `TODO.md` (Phase 6/7/8/9/10's repeated "no caller yet" deferrals, all citing this exact gap), `app/backend/blueprint/derive.py`, `app/backend/blueprint/template_selection.py` (Phase 8), `app/backend/generation/question_generator.py` (Phase 7), `app/backend/validation/validator.py` (`validate_paper`, `validate_blueprint_compliance` — used by this plan's tests to prove the output is well-formed, not called internally by `generate_paper` itself — see Global Constraints).

## Global Constraints

- `generate_paper` does **not** call `validate_paper`/`validate_blueprint_compliance` internally. PROJECT_PLAN.md's demo flow treats "generate" (step 4) and "validate" (step 5) as separate stages with separate CLI commands; this function stays a single-responsibility "assemble candidates" step, matching that split, even though neither CLI command exists yet.
- Random choices go through a caller-supplied `random.Random`, never module-level `random.*` functions (established convention across `variable_sampler.py`, `question_generator.py`, `template_selection.py`).
- Every module boundary crosses with a Pydantic model, never a raw dict (DATA_MODEL.md line 3-4, spec §12, §35).
- Question numbering in the generated paper is flat sequential ("1", "2", "3", ...) across all sections in blueprint order — it does not attempt to mirror the source paper's numbering scheme (e.g. "1a"/"1b"), matching the precedent already set by Phase 8's own integration test.
- Out of scope, explicitly not attempted here: `--source <run_id>` CLI loading, `ExtractedSubQuestion` → `Question` conversion, Paper-from-extraction-run assembly. These are real, separate gaps (see "Scope decision" above) — recorded in TODO.md as still open, not silently worked around with placeholder data.

---

### Task 1: `generation/paper_generator.py` — `generate_paper`

**Files:**
- Create: `app/backend/generation/paper_generator.py`
- Test: `tests/unit/test_paper_generator.py`

**Interfaces:**
- Consumes: `Paper`, `Section` from `app.backend.models.paper`; `Question` from `app.backend.models.question`; `derive_blueprint_from_paper` from `app.backend.blueprint.derive`; `select_templates_for_blueprint` from `app.backend.blueprint.template_selection`; `generate_question` from `app.backend.generation.question_generator`; `new_id` from `app.backend.core.ids`; `TextGenerationProvider` from `app.backend.providers.text_generation`.
- Produces: `generate_paper(source_paper: Paper, source_questions: list[Question], difficulty_override: int | None = None, rng: random.Random | None = None, text_provider: TextGenerationProvider | None = None) -> tuple[Paper, list[Question]]`. Task 2's integration test imports this directly: `from app.backend.generation.paper_generator import generate_paper`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_paper_generator.py
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
    # marks=2.0/count=1 only matches TPL-ADDITION-WORD-PROBLEM (the only seed
    # template with marks=2.0), and that template's difficulty_range is
    # (2, 3) — it is not reachable at the source paper's natural difficulty.
    sections = [Section(name="Word Problems", marks=2.0, question_count=1)]
    source_paper = _source_paper(sections, total_marks=2.0)
    source_questions = [_source_question("1", difficulty=1)]  # -> derived difficulty_level=1

    with pytest.raises(ValueError):
        generate_paper(source_paper, source_questions, rng=random.Random(3))

    generated_paper, generated_questions = generate_paper(
        source_paper, source_questions, difficulty_override=2, rng=random.Random(3)
    )

    assert len(generated_questions) == 1
    assert generated_questions[0].type == QuestionType.WORD_PROBLEM


def test_raises_when_source_has_no_questions():
    source_paper = _source_paper([Section(name="A", marks=1.0)], total_marks=1.0)

    with pytest.raises(ValueError):
        generate_paper(source_paper, [], rng=random.Random(1))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_paper_generator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backend.generation.paper_generator'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/backend/generation/paper_generator.py
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
from app.backend.generation.question_generator import generate_question
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
    number = 1
    for section in blueprint.sections:
        for template in templates_by_section[section.name]:
            question = generate_question(
                template,
                paper_id=generated_paper_id,
                question_number=str(number),
                rng=rng,
                text_provider=text_provider,
            )
            generated_questions.append(question)
            number += 1

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
    return generated_paper, generated_questions
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_paper_generator.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add app/backend/generation/paper_generator.py tests/unit/test_paper_generator.py
git commit -m "add generate_paper orchestrator"
```

---

### Task 2: Integration test — generated paper is valid and blueprint-compliant

**Files:**
- Test: `tests/integration/test_generate_paper.py`

**Interfaces:**
- Consumes: `generate_paper` (Task 1), `validate_paper` (Phase 6), `validate_blueprint_compliance` (Phase 8, both from `app.backend.validation.validator`), `derive_blueprint_from_paper` (Phase 8, to independently recompute the expected blueprint for the compliance check — `generate_paper` doesn't return the blueprint it used internally).
- Produces: nothing consumed elsewhere — this is the closing proof that `generate_paper`'s output is usable by the very validators every earlier phase built for exactly this purpose.

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_generate_paper.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/integration/test_generate_paper.py -v`
Expected: FAIL before Task 1 exists (`ModuleNotFoundError`); once Task 1 is done this test should already pass without further implementation, since it only composes existing functions. If `validate_paper` fails on `duplicate_question` for seed `7`, try consecutive small integer seeds until no collision occurs (same note as Phase 8's own roundtrip test) — this is a property of the RNG draw, not a bug.

- [ ] **Step 3: No implementation step — this task only adds a test**

Task 1 already provides everything this test calls.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/integration/test_generate_paper.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_generate_paper.py
git commit -m "add generate_paper validity/compliance integration test"
```

---

### Task 3: Update TODO.md

**Files:**
- Modify: `TODO.md`

**Interfaces:** None — documentation only.

- [ ] **Step 1: Run the full test suite and ruff as a pre-flight check**

Run: `.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m ruff check app/backend/generation/paper_generator.py tests/unit/test_paper_generator.py tests/integration/test_generate_paper.py`
Expected: all tests pass; ruff reports no issues in the files this plan touched.

- [ ] **Step 2: Record the closed gap and the two new ones, between Phase 10 and Phase 11+**

Insert a new section in `TODO.md` immediately after the Phase 10 section and before `## Phase 11+ — deferred until MVP (Phases 2-10) is solid`:

```markdown
## generate_paper orchestrator — closes the Phase 6-10 caller gap — **done 2026-08-19**

- [x] `app/backend/generation/paper_generator.py` — `generate_paper(source_paper,
      source_questions, difficulty_override=None, rng=None, text_provider=None)
      -> tuple[Paper, list[Question]]`: composes Phase 8's blueprint
      derivation + template selection with Phase 7's question generation
      into one function, closing every "no caller yet" note Phases 6-10
      left in this file. `difficulty_override` gives PROJECT_PLAN.md's
      demo `--difficulty` flag something real to plug into once a CLI
      exists. Does not call `validate_paper`/`validate_blueprint_compliance`
      internally — PROJECT_PLAN.md's demo treats generate and validate as
      separate steps
- [x] Integration test: a generated paper from a realistic source paper
      passes both `validate_paper` and `validate_blueprint_compliance`
      with zero issues

**Two new gaps surfaced while scoping this** (found, not fixed — same
"deliberately out of scope" discipline every phase has used):
1. Nothing in the codebase builds a `Paper` (subject/class/total_marks/
   duration_minutes/sections) from an extraction run. `ingest-paper` /
   `clean-paper` / `extract-questions` never construct one.
2. Nothing converts `questions/extraction.py`'s `ExtractedSubQuestion`
   (no `id`, `expected_answer`, or `difficulty_features`) into Phase 5's
   full `Question`. `extraction.py`'s own module docstring says this
   conversion is "Phase 5's job" — Phase 5 built the `Question` model but
   never actually wrote the converter.

Together these mean `generate-paper --source <run_id>` (PROJECT_PLAN.md's
demo step 4, spec's CLI list) still has nothing real to load from disk.
Closing them is prerequisite work for that CLI command and for Phase 11's
browser wizard, whichever comes first.
```

- [ ] **Step 3: Commit**

```bash
git add TODO.md
git commit -m "record generate_paper orchestrator, document two new caller gaps"
```
