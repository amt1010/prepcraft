# Phase 5 — Structured Question Models Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the full `Question`, `QuestionType`, and `DifficultyFeatures` Pydantic models from DATA_MODEL.md, with a working `DifficultyFeatures.score()` — closing PROJECT_PLAN.md's Phase 5 row ("Every extracted question round-trips through the model without data loss").

**Architecture:** One new file, `app/backend/models/question.py`, following the exact pattern already established by `app/backend/models/paper.py` (Phase 2): plain Pydantic `BaseModel`s, an `Enum`/`Literal` for closed value sets, no logic beyond the one pure-function method DATA_MODEL.md specifies (`DifficultyFeatures.score()`). No provider calls, no I/O, no CLI wiring — this phase is data shape only, matching the phase table's acceptance test ("round-trips ... without data loss"), which Phase 2's `test_paper_round_trips_through_the_model_without_data_loss` already shows the exact shape of.

**Tech Stack:** Pydantic v2 (`BaseModel`, `Enum`, `Literal`) — same as every other model file in the repo. No new dependencies.

**Spec:** `DATA_MODEL.md` ("Question" and "DifficultyFeatures" sections), master spec §16 ("DIFFICULTY ENGINE" — the easy/medium/harder worked examples), `PROJECT_PLAN.md` (phase table row 5), `tests/unit/test_paper_model.py` (the round-trip test pattern this plan reuses for `Question`).

## Global Constraints

- Every module boundary crosses with a Pydantic model, never a raw dict (DATA_MODEL.md line 3-4, spec §12, §35).
- MVP implements exactly the 9 `QuestionType` values DATA_MODEL.md lists — the commented-out types (`MATCH_THE_FOLLOWING`, `SHORT_ANSWER`, etc.) are out of scope (DATA_MODEL.md line 61-63, PROJECT_PLAN.md MVP scope).
- `DifficultyFeatures` fields and `Question` fields must match DATA_MODEL.md's field names and types exactly — later phases (6-8) will construct these models by name.
- Difficulty must be explainable, not an arbitrary number (spec §16: "The system should record why a question has a particular difficulty") — this is why `difficulty_features` is a required field on `Question`, not optional metadata.

---

### Task 1: `QuestionType` enum + `DifficultyFeatures` model with `score()`

**Files:**
- Create: `app/backend/models/question.py`
- Test: `tests/unit/test_difficulty_features.py`

**Interfaces:**
- Produces: `QuestionType(str, Enum)` with the 9 MVP values from DATA_MODEL.md; `DifficultyFeatures(BaseModel)` with fields `digit_count: int | None = None`, `operation_count: int`, `requires_carrying: bool | None = None`, `step_count: int`, `vocabulary_level: Literal["basic", "standard", "advanced"]`, `reasoning_required: bool`, and method `score(self) -> int`. Task 2 imports both directly from `app.backend.models.question`.

- [ ] **Step 1: Write the failing test — the spec §16 worked examples**

```python
# tests/unit/test_difficulty_features.py
from app.backend.models.question import DifficultyFeatures


def test_easy_addition_with_no_carrying_scores_lowest():
    # spec §16 "Easy": 245 + 123 — no carrying, one operation, one step
    features = DifficultyFeatures(
        digit_count=3,
        operation_count=1,
        requires_carrying=False,
        step_count=1,
        vocabulary_level="basic",
        reasoning_required=False,
    )

    assert features.score() == 1


def test_medium_addition_with_carrying_scores_higher_than_easy():
    # spec §16 "Medium": 378 + 246 — same shape as Easy, but every column carries
    features = DifficultyFeatures(
        digit_count=3,
        operation_count=1,
        requires_carrying=True,
        step_count=1,
        vocabulary_level="basic",
        reasoning_required=False,
    )

    assert features.score() == 2


def test_harder_multi_step_word_problem_scores_highest():
    # spec §16 "Harder": shop has 458 books, receives 267, gives away 125,
    # how many remain — two operations, two steps, reasoning required,
    # word-problem vocabulary
    features = DifficultyFeatures(
        digit_count=3,
        operation_count=2,
        requires_carrying=True,
        step_count=2,
        vocabulary_level="advanced",
        reasoning_required=True,
    )

    assert features.score() == 5


def test_score_never_exceeds_five():
    features = DifficultyFeatures(
        digit_count=6,
        operation_count=4,
        requires_carrying=True,
        step_count=4,
        vocabulary_level="advanced",
        reasoning_required=True,
    )

    assert features.score() == 5


def test_score_treats_a_none_requires_carrying_as_no_bonus():
    # requires_carrying is None for question types where carrying doesn't
    # apply at all (e.g. roman_numeral, true_false) — must not raise and
    # must not be scored as if it were True
    features = DifficultyFeatures(
        operation_count=1,
        requires_carrying=None,
        step_count=1,
        vocabulary_level="basic",
        reasoning_required=False,
    )

    assert features.score() == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_difficulty_features.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backend.models.question'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/backend/models/question.py
"""Question and difficulty models (DATA_MODEL.md's "Question" and
"DifficultyFeatures" sections). DifficultyFeatures.score() is the one place
"difficulty" gets computed (spec §16: "record why a question has a
particular difficulty") — every question's 1-5 level must trace back to
this method, never be assigned as a bare number elsewhere."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel


class QuestionType(str, Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    FILL_BLANK = "fill_in_the_blank"
    TRUE_FALSE = "true_false"
    ARITHMETIC = "arithmetic"
    ROMAN_NUMERAL = "roman_numeral"
    PREDECESSOR_SUCCESSOR = "predecessor_successor"
    ROUNDING = "rounding"
    WORD_PROBLEM = "word_problem"
    MENTAL_MATHS = "mental_maths"


class DifficultyFeatures(BaseModel):
    digit_count: int | None = None
    operation_count: int
    requires_carrying: bool | None = None
    step_count: int
    vocabulary_level: Literal["basic", "standard", "advanced"]
    reasoning_required: bool

    def score(self) -> int:
        points = 1
        if self.requires_carrying:
            points += 1
        if self.operation_count >= 2:
            points += 1
        if self.step_count >= 2:
            points += 1
        if self.reasoning_required:
            points += 1
        if self.vocabulary_level == "advanced":
            points += 1
        return min(points, 5)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_difficulty_features.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add app/backend/models/question.py tests/unit/test_difficulty_features.py
git commit -m "add QuestionType enum and DifficultyFeatures.score()"
```

---

### Task 2: `Question` model

**Files:**
- Modify: `app/backend/models/question.py`
- Test: `tests/unit/test_question_model.py`

**Interfaces:**
- Consumes: `QuestionType`, `DifficultyFeatures` from Task 1.
- Produces: `Question(BaseModel)` with fields `id: str`, `paper_id: str`, `question_number: str`, `type: QuestionType`, `text: str`, `options: list[str] | None = None`, `marks: float`, `topic: str`, `difficulty: int`, `difficulty_features: DifficultyFeatures`, `expected_answer: str`, `answer_type: Literal["numeric", "text", "choice", "boolean"]`, `source: Literal["existing_paper", "generated"]`, `template_id: str | None = None`. Phase 6 (validation) and Phase 7 (generation) construct this model directly by these field names.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_question_model.py
import pytest
from pydantic import ValidationError

from app.backend.models.question import DifficultyFeatures, Question, QuestionType


def _difficulty_features() -> DifficultyFeatures:
    return DifficultyFeatures(
        digit_count=3,
        operation_count=1,
        requires_carrying=False,
        step_count=1,
        vocabulary_level="basic",
        reasoning_required=False,
    )


def test_question_round_trips_through_the_model_without_data_loss():
    question = Question(
        id="QUESTION-01",
        paper_id="PAPER-01",
        question_number="1a",
        type=QuestionType.MULTIPLE_CHOICE,
        text="___ + 305 = 800. What is the missing number?",
        options=["405", "450", "500", "495"],
        marks=0.5,
        topic="Addition",
        difficulty=2,
        difficulty_features=_difficulty_features(),
        expected_answer="495",
        answer_type="choice",
        source="existing_paper",
        template_id=None,
    )

    restored = Question.model_validate(question.model_dump())

    assert restored == question


def test_question_options_and_template_id_default_to_none():
    question = Question(
        id="QUESTION-02",
        paper_id="PAPER-01",
        question_number="2",
        type=QuestionType.ARITHMETIC,
        text="378 + 246",
        marks=1,
        topic="Addition",
        difficulty=2,
        difficulty_features=_difficulty_features(),
        expected_answer="624",
        answer_type="numeric",
        source="existing_paper",
    )

    assert question.options is None
    assert question.template_id is None


def test_question_rejects_an_invalid_type_value():
    with pytest.raises(ValidationError):
        Question(
            id="QUESTION-03",
            paper_id="PAPER-01",
            question_number="3",
            type="not_a_real_type",
            text="x",
            marks=1,
            topic="Addition",
            difficulty=1,
            difficulty_features=_difficulty_features(),
            expected_answer="1",
            answer_type="numeric",
            source="existing_paper",
        )


def test_question_rejects_an_invalid_answer_type_value():
    with pytest.raises(ValidationError):
        Question(
            id="QUESTION-04",
            paper_id="PAPER-01",
            question_number="4",
            type=QuestionType.TRUE_FALSE,
            text="x",
            marks=1,
            topic="Addition",
            difficulty=1,
            difficulty_features=_difficulty_features(),
            expected_answer="true",
            answer_type="not_a_real_answer_type",
            source="existing_paper",
        )


def test_question_rejects_an_invalid_source_value():
    with pytest.raises(ValidationError):
        Question(
            id="QUESTION-05",
            paper_id="PAPER-01",
            question_number="5",
            type=QuestionType.MENTAL_MATHS,
            text="x",
            marks=1,
            topic="Addition",
            difficulty=1,
            difficulty_features=_difficulty_features(),
            expected_answer="1",
            answer_type="numeric",
            source="not_a_real_source",
        )


def test_question_type_enum_has_exactly_the_mvp_types():
    assert {member.value for member in QuestionType} == {
        "multiple_choice",
        "fill_in_the_blank",
        "true_false",
        "arithmetic",
        "roman_numeral",
        "predecessor_successor",
        "rounding",
        "word_problem",
        "mental_maths",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_question_model.py -v`
Expected: FAIL — `ImportError: cannot import name 'Question' from 'app.backend.models.question'`

- [ ] **Step 3: Write minimal implementation**

Append to `app/backend/models/question.py`:

```python
class Question(BaseModel):
    id: str
    paper_id: str
    question_number: str
    type: QuestionType
    text: str
    options: list[str] | None = None
    marks: float
    topic: str
    difficulty: int
    difficulty_features: DifficultyFeatures
    expected_answer: str
    answer_type: Literal["numeric", "text", "choice", "boolean"]
    source: Literal["existing_paper", "generated"]
    template_id: str | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_question_model.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Run the full test suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: All tests pass, no regressions in Phase 1-4 tests

- [ ] **Step 6: Commit**

```bash
git add app/backend/models/question.py tests/unit/test_question_model.py
git commit -m "add Question model"
```

---

### Task 3: Close out Phase 5 in TODO.md

**Files:**
- Modify: `TODO.md`

- [ ] **Step 1: Check off Phase 5's two items and add a one-line date marker**, matching how Phase 1/2's headers read (`## Phase 5 — Structured question models — **done <date>**`):

```markdown
## Phase 5 — Structured question models — **done 2026-08-18**

- [x] `app/backend/models/question.py` — `Question`, `QuestionType`,
      `DifficultyFeatures` (DATA_MODEL.md)
- [x] `DifficultyFeatures.score()` implementation + unit tests covering the
      spec §16 easy/medium/harder examples
```

- [ ] **Step 2: Commit**

```bash
git add TODO.md
git commit -m "mark Phase 5 question models complete"
```

---

## Self-Review Notes

- **Spec coverage:** DATA_MODEL.md's `Question` fields → Task 2, field-for-field. DATA_MODEL.md's `QuestionType` 9-value enum → Task 1, locked by `test_question_type_enum_has_exactly_the_mvp_types` so a future phase can't silently widen MVP scope. DATA_MODEL.md's `DifficultyFeatures` fields + `score()` → Task 1. Spec §16's three worked examples (easy/medium/harder) → Task 1's three named tests, using the exact numbers from the spec. PROJECT_PLAN.md's phase 5 acceptance ("round-trips ... without data loss") → Task 2's first test, same pattern as Phase 2's `test_paper_round_trips_through_the_model_without_data_loss`.
- **Deferred, not forgotten:** this plan does not build a converter from Phase 4's `ExtractedSubQuestion` to `Question` — `ExtractedSubQuestion` is missing `id`, `paper_id`, `difficulty_features`, `expected_answer`, and `answer_type` (Phase 4's plan Task 6 self-review notes this explicitly), and PROJECT_PLAN.md's phase table only asks Phase 5 for the model itself, not a builder. Wiring extraction output into a real `Question` (deciding where `expected_answer`/`answer_type`/`id`/`paper_id` come from for `existing_paper`-sourced questions) is Phase 6/7 territory, once validation and generation give that wiring a real caller instead of a speculative one.
- **Type consistency:** `QuestionType` and `DifficultyFeatures` (Task 1) are consumed unchanged by `Question` (Task 2) — same import path, same class objects, no re-definition.
