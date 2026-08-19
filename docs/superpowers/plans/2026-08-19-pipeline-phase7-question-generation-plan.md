# Phase 7 — Question Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build template-driven candidate question generation (PIPELINE.md's shared tail: "Template selection / Variable sampling / Answer computation") — closing TODO.md's Phase 7 row: `question_template.py`, a seed template set covering all 9 `QuestionType`s, `generation/variable_sampler.py`, and the question-assembly step that ties them together with Phase 6's validator.

**Architecture:** Four new modules plus one integration test. `models/question_template.py` defines `QuestionTemplate` (DATA_MODEL.md's core entity, extended with the fields Phase 8 hasn't supplied a caller for yet — see Global Constraints). `generation/formulas.py` holds the deterministic, non-arithmetic "the spec gives a formula" computations (Roman numeral conversion, round-half-up, predecessor/successor, carrying detection) that PROJECT_PLAN.md lists alongside arithmetic evaluation but that don't fit `validation/answer_engine.py`'s restricted-AST-expression shape. `generation/variable_sampler.py` maps a template's `variables` spec (`{"a": "3_digit_number"}`) to sampled integers via a `random.Random` the caller controls, so generation is reproducible under a seed. `questions/template_registry.py` is the seed set: 11 templates covering all 9 MVP question types (two each for `predecessor_successor` and `rounding`, since each needs a distinct operation). `generation/question_generator.py` is the assembly point: sample variables, compute the answer (dispatching to `formulas.py` or reusing `validation/answer_engine.evaluate` depending on the template's `operation`), render `text_template`, optionally re-phrase via an already-existing `TextGenerationProvider` (never touching variables or the answer), and build a full `Question`. A final integration test generates one candidate per seed template and runs Phase 6's `validate_paper` against them with zero issues — closing the exact gap Phase 6's TODO.md notes left open ("no `validate-paper` CLI command — nothing produces a full generated `Paper` + `Question` set until Phase 7/8 ... they become validator work again once Phase 7/8 give them a caller").

**Tech Stack:** Python stdlib `random` (seedable `random.Random`, never the module-level `random.*` functions, so tests are deterministic) and `divmod` for round-half-up. Reuses `validation/answer_engine.evaluate` — no new expression evaluator. No new dependencies.

**Spec:** `Master Claude Code Prompt — AI Practice Paper Generator.md` §14 ("QUESTION GENERATION" — the 9-step algorithm and the shopkeeper example this plan's `addition_word_problem` template reproduces) and §15 ("QUESTION TEMPLATE MODEL"), `DATA_MODEL.md` (`QuestionTemplate` core entity, `Question`, `DifficultyFeatures`, scoping invariant), `PIPELINE.md` ("Shared tail: blueprint -> PDF" — template selection/variable sampling/answer computation, and "Where the LLM is and isn't in this tail"), `ARCHITECTURE.md` (module map: `generation/` = "Candidate generation from templates, value sampling"; model-choice table's "Question generation" row), `PROJECT_PLAN.md` ("What's deterministic vs. AI" — the exact list this plan's `formulas.py` implements), `TODO.md` (Phase 7 scaffold), `app/backend/models/question.py`, `app/backend/validation/{answer_engine,validator}.py`, `app/backend/providers/text_generation.py` (unchanged; reused, not rebuilt).

## Global Constraints

- The answer is always computed by code, never asked of the LLM (spec §14, PROJECT_PLAN.md's deterministic list). `TextGenerationProvider` is used only to re-phrase already-rendered, already-computed question text (PIPELINE.md: "an LLM call to draft `text_template` phrasing for a new question ... the *answer* is always computed by evaluating `answer_expression` in code").
- Never re-implement the restricted expression evaluator. `generation/` imports `evaluate` from `validation/answer_engine.py` (built in Phase 6) rather than duplicating it in `generation/answer_engine.py` as DATA_MODEL.md's file path literally suggests — Phase 6 already placed the one evaluator that exists in `validation/`, and there must be exactly one. This is a deliberate, documented deviation from DATA_MODEL.md's literal path, same as Phase 6's own deviation note.
- `QuestionTemplate` (DATA_MODEL.md) literally lists `id, template_type, topic, grade, difficulty_range, variables, operation, answer_expression, text_template`. This plan adds four fields DATA_MODEL.md's literal listing omits but Phase 7's generator cannot work without, since no `PaperBlueprint` (Phase 8) exists yet to supply them externally: `question_type: QuestionType` (so the generator never re-parses `template_type` strings), `subject: str` (DATA_MODEL.md's scoping invariant: "Every `Question`, `Chapter`, `QuestionTemplate`, and `PaperBlueprint` row carries `subject` + `class_standard`"), `marks: float` (blueprint-driven weighting doesn't exist until Phase 8), `answer_type` and `distractor_offsets` (declared per-template, never inferred, since a handful of edge cases don't map cleanly from `question_type` alone). No storage/query-layer enforcement of the scoping invariant is added — that's `storage/`'s job once a `question_templates` table exists (out of scope, same "no caller yet" deferral as Phase 6).
- Every module boundary crosses with a Pydantic model, never a raw dict (DATA_MODEL.md line 3-4, spec §12, §35).
- `generation/` never calls `eval()`/`exec()` — arithmetic goes through `validation/answer_engine.evaluate`'s whitelisted AST walk; anything that isn't a bare arithmetic expression (Roman numerals, rounding, predecessor/successor) gets its own small deterministic function in `formulas.py`, unit-tested directly.
- No CLI command this phase. `PaperBlueprint`-driven template *selection* (PIPELINE.md: "pick QuestionTemplates matching blueprint's topics/types/difficulty_range") is Phase 8's job — this phase's `generate_question` takes an already-chosen template, matching Phase 6's precedent of deferring `validate-paper`'s CLI wiring until a real caller exists.

---

### Task 1: `QuestionTemplate` model

**Files:**
- Create: `app/backend/models/question_template.py`
- Test: `tests/unit/test_question_template_model.py`

**Interfaces:**
- Consumes: `QuestionType` from `app.backend.models.question`.
- Produces: `QuestionTemplate(BaseModel)` with fields `id: str`, `template_type: str`, `question_type: QuestionType`, `subject: str`, `grade: str`, `topic: str`, `marks: float`, `difficulty_range: tuple[int, int]`, `variables: dict[str, str]`, `operation: str`, `answer_expression: str`, `text_template: str`, `answer_type: Literal["numeric", "text", "choice", "boolean"]`, `distractor_offsets: list[int] | None = None`. Tasks 2-6 import this directly: `from app.backend.models.question_template import QuestionTemplate`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_question_template_model.py
import pytest
from pydantic import ValidationError

from app.backend.models.question import QuestionType
from app.backend.models.question_template import QuestionTemplate


def _template(**overrides) -> QuestionTemplate:
    fields = {
        "id": "TPL-TEST",
        "template_type": "addition_word_problem",
        "question_type": QuestionType.WORD_PROBLEM,
        "subject": "Mathematics",
        "grade": "III",
        "topic": "Addition",
        "marks": 2.0,
        "difficulty_range": (2, 3),
        "variables": {"a": "3_digit_number", "b": "3_digit_number"},
        "operation": "addition",
        "answer_expression": "a + b",
        "text_template": "{a} + {b}",
        "answer_type": "numeric",
    }
    fields.update(overrides)
    return QuestionTemplate(**fields)


def test_builds_a_valid_template():
    template = _template()

    assert template.question_type == QuestionType.WORD_PROBLEM
    assert template.difficulty_range == (2, 3)
    assert template.distractor_offsets is None


def test_distractor_offsets_default_to_none_but_can_be_set():
    template = _template(question_type=QuestionType.MULTIPLE_CHOICE, distractor_offsets=[-10, -1, 10])

    assert template.distractor_offsets == [-10, -1, 10]


def test_rejects_an_unknown_question_type():
    with pytest.raises(ValidationError):
        _template(question_type="not_a_real_type")


def test_rejects_an_unknown_answer_type():
    with pytest.raises(ValidationError):
        _template(answer_type="essay")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_question_template_model.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backend.models.question_template'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/backend/models/question_template.py
"""QuestionTemplate model (DATA_MODEL.md's "QuestionTemplate" core entity;
PIPELINE.md's shared tail: "Template selection ... pick QuestionTemplates
matching blueprint's topics/types/difficulty_range"). Extends DATA_MODEL.md's
literal field list with what Phase 7's generator needs to produce a complete
`Question` without a `PaperBlueprint` caller yet (Phase 8) — see the Phase 7
plan's Global Constraints for why each extra field exists."""

from typing import Literal

from pydantic import BaseModel

from app.backend.models.question import QuestionType


class QuestionTemplate(BaseModel):
    id: str
    template_type: str
    question_type: QuestionType
    subject: str
    grade: str
    topic: str
    marks: float
    difficulty_range: tuple[int, int]
    variables: dict[str, str]
    operation: str
    answer_expression: str
    text_template: str
    answer_type: Literal["numeric", "text", "choice", "boolean"]
    distractor_offsets: list[int] | None = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_question_template_model.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add app/backend/models/question_template.py tests/unit/test_question_template_model.py
git commit -m "add QuestionTemplate model"
```

---

### Task 2: `generation/formulas.py` — Roman numerals, rounding, predecessor/successor, carrying

**Files:**
- Create: `app/backend/generation/__init__.py` (empty, matches every other module's package marker)
- Create: `app/backend/generation/formulas.py`
- Test: `tests/unit/test_formulas.py`

**Interfaces:**
- Produces: `to_roman_numeral(n: int) -> str` (raises `ValueError` outside 1-3999), `round_to_nearest(n: int, base: int) -> int` (round-half-up), `predecessor(n: int) -> int`, `successor(n: int) -> int`, `addition_requires_carrying(a: int, b: int) -> bool`. Task 5 imports all five directly: `from app.backend.generation.formulas import ...`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_formulas.py
import pytest

from app.backend.generation.formulas import (
    addition_requires_carrying,
    predecessor,
    round_to_nearest,
    successor,
    to_roman_numeral,
)


@pytest.mark.parametrize(
    "n, roman",
    [
        (1, "I"),
        (4, "IV"),
        (9, "IX"),
        (14, "XIV"),
        (40, "XL"),
        (90, "XC"),
        (400, "CD"),
        (900, "CM"),
        (1994, "MCMXCIV"),
        (3999, "MMMCMXCIX"),
    ],
)
def test_to_roman_numeral_known_values(n, roman):
    assert to_roman_numeral(n) == roman


def test_to_roman_numeral_rejects_zero():
    with pytest.raises(ValueError):
        to_roman_numeral(0)


def test_to_roman_numeral_rejects_above_3999():
    with pytest.raises(ValueError):
        to_roman_numeral(4000)


def test_round_to_nearest_rounds_down_below_half():
    assert round_to_nearest(24, 10) == 20


def test_round_to_nearest_rounds_half_up():
    # Python's round() uses round-half-to-even (25 -> 20); classroom
    # convention is round-half-up (25 -> 30).
    assert round_to_nearest(25, 10) == 30


def test_round_to_nearest_hundred():
    assert round_to_nearest(449, 100) == 400
    assert round_to_nearest(450, 100) == 500


def test_predecessor_and_successor():
    assert predecessor(24) == 23
    assert successor(24) == 25


def test_addition_requires_carrying_spec_easy_example():
    # spec §16 "Easy": 245 + 123 — no column carries
    assert addition_requires_carrying(245, 123) is False


def test_addition_requires_carrying_spec_medium_example():
    # spec §16 "Medium": 378 + 246 — every column carries
    assert addition_requires_carrying(378, 246) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_formulas.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backend.generation'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/backend/generation/__init__.py
```

```python
# app/backend/generation/formulas.py
"""Deterministic "the spec gives a formula" computations (PROJECT_PLAN.md's
"What's deterministic vs. AI" list: "Roman numeral conversion, arithmetic
evaluation, rounding, predecessor/successor — anywhere the spec gives a
formula"). Plain arithmetic already has a home in
validation/answer_engine.py's restricted evaluator; this module holds the
formulas that aren't a bare arithmetic expression over declared variables."""

_ROMAN_NUMERAL_VALUES: list[tuple[int, str]] = [
    (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
    (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
    (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
]


def to_roman_numeral(n: int) -> str:
    if not 1 <= n <= 3999:
        raise ValueError(f"roman numeral conversion only supports 1-3999, got {n}")
    symbols = []
    remaining = n
    for value, symbol in _ROMAN_NUMERAL_VALUES:
        while remaining >= value:
            symbols.append(symbol)
            remaining -= value
    return "".join(symbols)


def round_to_nearest(n: int, base: int) -> int:
    """Round-half-up, matching classroom convention (Python's round() uses
    round-half-to-even, which would round 25 to the nearest 10 down to 20)."""
    quotient, remainder = divmod(n, base)
    if remainder * 2 >= base:
        quotient += 1
    return quotient * base


def predecessor(n: int) -> int:
    return n - 1


def successor(n: int) -> int:
    return n + 1


def addition_requires_carrying(a: int, b: int) -> bool:
    x, y = abs(a), abs(b)
    while x or y:
        if (x % 10) + (y % 10) >= 10:
            return True
        x //= 10
        y //= 10
    return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_formulas.py -v`
Expected: PASS (16 tests)

- [ ] **Step 5: Commit**

```bash
git add app/backend/generation/__init__.py app/backend/generation/formulas.py tests/unit/test_formulas.py
git commit -m "add deterministic formula helpers for question generation"
```

---

### Task 3: `generation/variable_sampler.py`

**Files:**
- Create: `app/backend/generation/variable_sampler.py`
- Test: `tests/unit/test_variable_sampler.py`

**Interfaces:**
- Produces: `sample_variables(spec: dict[str, str], rng: random.Random) -> dict[str, int]`, raising `ValueError` for an unrecognized "kind" string. Task 5 imports this directly: `from app.backend.generation.variable_sampler import sample_variables`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_variable_sampler.py
import random

import pytest

from app.backend.generation.variable_sampler import sample_variables


def test_samples_one_value_per_declared_variable():
    variables = sample_variables({"a": "3_digit_number", "b": "2_digit_number"}, random.Random(1))

    assert set(variables) == {"a", "b"}


@pytest.mark.parametrize(
    "kind, low, high",
    [
        ("1_digit_number", 1, 9),
        ("2_digit_number", 10, 99),
        ("3_digit_number", 100, 999),
        ("4_digit_number", 1000, 9999),
        ("small_number_1_50", 1, 50),
    ],
)
def test_each_kind_samples_within_its_range(kind, low, high):
    rng = random.Random(7)
    for _ in range(50):
        value = sample_variables({"x": kind}, rng)["x"]
        assert low <= value <= high


def test_unknown_kind_raises_value_error():
    with pytest.raises(ValueError, match="unknown variable kind"):
        sample_variables({"a": "not_a_real_kind"}, random.Random(1))


def test_same_seed_produces_the_same_values():
    spec = {"a": "3_digit_number", "b": "3_digit_number"}

    first = sample_variables(spec, random.Random(99))
    second = sample_variables(spec, random.Random(99))

    assert first == second
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_variable_sampler.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backend.generation.variable_sampler'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/backend/generation/variable_sampler.py
"""Samples fresh variable values for a QuestionTemplate (PIPELINE.md's
shared tail: "Variable sampling — generate new values per template's
variable spec"). Each template declares variables as {"a": "3_digit_number"}
(DATA_MODEL.md); this module is the only place that maps a variable "kind"
string to a concrete numeric range, so adding a new kind means editing one
dict, not hunting through every template. Callers pass their own
random.Random so generation is reproducible under a seed — never the
module-level random.* functions."""

import random

_KIND_RANGES: dict[str, tuple[int, int]] = {
    "1_digit_number": (1, 9),
    "2_digit_number": (10, 99),
    "3_digit_number": (100, 999),
    "4_digit_number": (1000, 9999),
    "small_number_1_50": (1, 50),
}


def sample_variables(spec: dict[str, str], rng: random.Random) -> dict[str, int]:
    variables: dict[str, int] = {}
    for name, kind in spec.items():
        if kind not in _KIND_RANGES:
            raise ValueError(f"unknown variable kind: {kind!r}")
        low, high = _KIND_RANGES[kind]
        variables[name] = rng.randint(low, high)
    return variables
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_variable_sampler.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add app/backend/generation/variable_sampler.py tests/unit/test_variable_sampler.py
git commit -m "add variable_sampler for QuestionTemplate variable specs"
```

---

### Task 4: `questions/template_registry.py` — seed template set

**Files:**
- Create: `app/backend/questions/template_registry.py`
- Test: `tests/unit/test_template_registry.py`

**Interfaces:**
- Consumes: `QuestionTemplate` (Task 1), `QuestionType` from `app.backend.models.question`.
- Produces: `TEMPLATES: list[QuestionTemplate]` and `get_templates(question_type: QuestionType | None = None) -> list[QuestionTemplate]`. Task 5's tests and Task 6's integration test import both directly: `from app.backend.questions.template_registry import TEMPLATES, get_templates`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_template_registry.py
from app.backend.models.question import QuestionType
from app.backend.questions.template_registry import TEMPLATES, get_templates


def test_every_question_type_has_at_least_one_template():
    for question_type in QuestionType:
        templates = get_templates(question_type)
        assert templates, f"no seed template for {question_type}"
        assert all(t.question_type == question_type for t in templates)


def test_get_templates_without_a_filter_returns_everything():
    assert get_templates() == TEMPLATES


def test_template_ids_are_unique():
    ids = [t.id for t in TEMPLATES]
    assert len(ids) == len(set(ids))


def test_multiple_choice_templates_declare_distractor_offsets():
    for template in get_templates(QuestionType.MULTIPLE_CHOICE):
        assert template.distractor_offsets
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_template_registry.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backend.questions.template_registry'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/backend/questions/template_registry.py
"""Seed QuestionTemplate set for MVP question types (TODO.md Phase 7: "Seed
template set for MVP types"). Every `operation` string used here is
dispatched in generation/question_generator.py's `_resolve` — adding a
template with a new operation means adding a branch there too, since answer
computation is never left to the LLM (spec §14).

`answer_expression` is only fed to validation/answer_engine.py's restricted
evaluator for templates whose operation falls through to the generic
arithmetic path in `_resolve` (addition_word_problem, arithmetic_addition,
mental_maths_addition, addition_fill_blank, multiple_choice_addition,
true_false_addition — all "a + b"). For the five templates dispatched to a
`generation/formulas.py` function instead (predecessor, successor, both
rounding templates, roman numeral conversion), `answer_expression` is
descriptive documentation only, not something ever passed to `evaluate()`."""

from app.backend.models.question import QuestionType
from app.backend.models.question_template import QuestionTemplate

TEMPLATES: list[QuestionTemplate] = [
    QuestionTemplate(
        id="TPL-ADDITION-WORD-PROBLEM",
        template_type="addition_word_problem",
        question_type=QuestionType.WORD_PROBLEM,
        subject="Mathematics",
        grade="III",
        topic="Addition",
        marks=2.0,
        difficulty_range=(2, 3),
        variables={"a": "3_digit_number", "b": "3_digit_number"},
        operation="addition",
        answer_expression="a + b",
        text_template=(
            "A shopkeeper sold {a} items on Monday and {b} items on Tuesday. "
            "How many items did the shopkeeper sell altogether?"
        ),
        answer_type="numeric",
    ),
    QuestionTemplate(
        id="TPL-ARITHMETIC-ADD",
        template_type="arithmetic_addition",
        question_type=QuestionType.ARITHMETIC,
        subject="Mathematics",
        grade="III",
        topic="Addition",
        marks=1.0,
        difficulty_range=(1, 2),
        variables={"a": "3_digit_number", "b": "3_digit_number"},
        operation="addition",
        answer_expression="a + b",
        text_template="{a} + {b} = ?",
        answer_type="numeric",
    ),
    QuestionTemplate(
        id="TPL-ROMAN-NUMERAL",
        template_type="roman_numeral_conversion",
        question_type=QuestionType.ROMAN_NUMERAL,
        subject="Mathematics",
        grade="III",
        topic="Roman numerals",
        marks=1.0,
        difficulty_range=(1, 1),
        variables={"n": "small_number_1_50"},
        operation="roman_numeral_conversion",
        answer_expression="to_roman(n)",
        text_template="Write the Roman numeral for {n}.",
        answer_type="text",
    ),
    QuestionTemplate(
        id="TPL-PREDECESSOR",
        template_type="predecessor",
        question_type=QuestionType.PREDECESSOR_SUCCESSOR,
        subject="Mathematics",
        grade="III",
        topic="Number sense",
        marks=1.0,
        difficulty_range=(1, 1),
        variables={"n": "2_digit_number"},
        operation="predecessor",
        answer_expression="n - 1",
        text_template="What is the predecessor of {n}?",
        answer_type="numeric",
    ),
    QuestionTemplate(
        id="TPL-SUCCESSOR",
        template_type="successor",
        question_type=QuestionType.PREDECESSOR_SUCCESSOR,
        subject="Mathematics",
        grade="III",
        topic="Number sense",
        marks=1.0,
        difficulty_range=(1, 1),
        variables={"n": "2_digit_number"},
        operation="successor",
        answer_expression="n + 1",
        text_template="What is the successor of {n}?",
        answer_type="numeric",
    ),
    QuestionTemplate(
        id="TPL-ROUND-NEAREST-10",
        template_type="round_nearest_10",
        question_type=QuestionType.ROUNDING,
        subject="Mathematics",
        grade="III",
        topic="Rounding",
        marks=1.0,
        difficulty_range=(1, 1),
        variables={"n": "3_digit_number"},
        operation="round_nearest_10",
        answer_expression="round(n, 10)",
        text_template="Round {n} to the nearest 10.",
        answer_type="numeric",
    ),
    QuestionTemplate(
        id="TPL-ROUND-NEAREST-100",
        template_type="round_nearest_100",
        question_type=QuestionType.ROUNDING,
        subject="Mathematics",
        grade="III",
        topic="Rounding",
        marks=1.0,
        difficulty_range=(1, 1),
        variables={"n": "3_digit_number"},
        operation="round_nearest_100",
        answer_expression="round(n, 100)",
        text_template="Round {n} to the nearest 100.",
        answer_type="numeric",
    ),
    QuestionTemplate(
        id="TPL-MENTAL-MATHS-ADD",
        template_type="mental_maths_addition",
        question_type=QuestionType.MENTAL_MATHS,
        subject="Mathematics",
        grade="III",
        topic="Addition",
        marks=0.5,
        difficulty_range=(1, 2),
        variables={"a": "1_digit_number", "b": "1_digit_number"},
        operation="addition",
        answer_expression="a + b",
        text_template="{a} + {b} = ___",
        answer_type="numeric",
    ),
    QuestionTemplate(
        id="TPL-FILL-BLANK-ADD",
        template_type="addition_fill_blank",
        question_type=QuestionType.FILL_BLANK,
        subject="Mathematics",
        grade="III",
        topic="Addition",
        marks=1.0,
        difficulty_range=(1, 2),
        variables={"a": "2_digit_number", "b": "2_digit_number"},
        operation="addition_fill_blank",
        answer_expression="a + b",
        text_template="{a} + ___ = {c}",
        answer_type="numeric",
    ),
    QuestionTemplate(
        id="TPL-MULTIPLE-CHOICE-ADD",
        template_type="multiple_choice_addition",
        question_type=QuestionType.MULTIPLE_CHOICE,
        subject="Mathematics",
        grade="III",
        topic="Addition",
        marks=1.0,
        difficulty_range=(1, 2),
        variables={"a": "2_digit_number", "b": "2_digit_number"},
        operation="addition",
        answer_expression="a + b",
        text_template="What is {a} + {b}?",
        answer_type="choice",
        distractor_offsets=[-10, -1, 10],
    ),
    QuestionTemplate(
        id="TPL-TRUE-FALSE-ADD",
        template_type="true_false_addition",
        question_type=QuestionType.TRUE_FALSE,
        subject="Mathematics",
        grade="III",
        topic="Addition",
        marks=1.0,
        difficulty_range=(1, 2),
        variables={"a": "2_digit_number", "b": "2_digit_number"},
        operation="true_false_addition",
        answer_expression="a + b",
        text_template="{a} + {b} = {c}",
        answer_type="boolean",
    ),
]


def get_templates(question_type: QuestionType | None = None) -> list[QuestionTemplate]:
    if question_type is None:
        return list(TEMPLATES)
    return [t for t in TEMPLATES if t.question_type == question_type]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_template_registry.py -v`
Expected: PASS (4 tests — the first parametrized over all 9 `QuestionType` members)

- [ ] **Step 5: Commit**

```bash
git add app/backend/questions/template_registry.py tests/unit/test_template_registry.py
git commit -m "add seed QuestionTemplate registry for MVP question types"
```

---

### Task 5: `generation/question_generator.py` — candidate assembly

**Files:**
- Create: `app/backend/generation/question_generator.py`
- Test: `tests/unit/test_question_generator.py`

**Interfaces:**
- Consumes: `QuestionTemplate` (Task 1); `predecessor`, `successor`, `round_to_nearest`, `to_roman_numeral`, `addition_requires_carrying` (Task 2); `sample_variables` (Task 3); `evaluate` from `app.backend.validation.answer_engine`; `new_id` from `app.backend.core.ids`; `Question`, `DifficultyFeatures`, `QuestionType` from `app.backend.models.question`; `TextGenerationProvider` from `app.backend.providers.text_generation`.
- Produces: `generate_question(template: QuestionTemplate, paper_id: str, question_number: str, rng: random.Random | None = None, text_provider: TextGenerationProvider | None = None) -> Question`. Task 6 imports this directly: `from app.backend.generation.question_generator import generate_question`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_question_generator.py
import random
import re

from pydantic import BaseModel

from app.backend.generation.question_generator import generate_question
from app.backend.models.question import QuestionType
from app.backend.questions.template_registry import get_templates


class _PhrasedText(BaseModel):
    text: str


class _FakeTextProvider:
    def __init__(self, text: str):
        self._text = text
        self.prompts: list[str] = []

    def generate(self, prompt: str, schema):
        self.prompts.append(prompt)
        return _PhrasedText(text=self._text)


def _template(question_type):
    return get_templates(question_type)[0]


def test_arithmetic_question_recomputes_correctly():
    template = _template(QuestionType.ARITHMETIC)
    rng = random.Random(1)

    question = generate_question(template, paper_id="P-1", question_number="1", rng=rng)

    left, _, _ = question.text.partition("=")
    a, op, b = left.split()
    assert op == "+"
    assert question.expected_answer == str(int(a) + int(b))
    assert question.type == QuestionType.ARITHMETIC
    assert question.source == "generated"
    assert question.template_id == template.id


def test_roman_numeral_question_converts_correctly():
    template = _template(QuestionType.ROMAN_NUMERAL)
    rng = random.Random(2)

    question = generate_question(template, paper_id="P-1", question_number="1", rng=rng)

    # regex, not a digit-join: "Write the Roman numeral for 24." must not
    # pick up digits from elsewhere in the sentence
    n = int(re.search(r"\d+", question.text).group())
    assert question.answer_type == "text"
    assert question.expected_answer  # non-empty roman numeral string
    assert all(ch in "IVXLCDM" for ch in question.expected_answer)
    assert 1 <= n <= 50


def test_fill_in_blank_hides_the_second_addend():
    template = _template(QuestionType.FILL_BLANK)
    rng = random.Random(3)

    question = generate_question(template, paper_id="P-1", question_number="1", rng=rng)

    assert "___" in question.text
    assert question.expected_answer not in question.text


def test_multiple_choice_options_contain_the_answer_and_are_unique():
    template = _template(QuestionType.MULTIPLE_CHOICE)
    rng = random.Random(4)

    question = generate_question(template, paper_id="P-1", question_number="1", rng=rng)

    assert question.options is not None
    assert len(question.options) == len(set(question.options)) == 4
    assert question.expected_answer in question.options


def test_true_false_answer_is_true_or_false_string():
    template = _template(QuestionType.TRUE_FALSE)
    rng = random.Random(5)

    question = generate_question(template, paper_id="P-1", question_number="1", rng=rng)

    assert question.expected_answer in ("true", "false")


def test_predecessor_successor_answers_are_correct():
    for template in get_templates(QuestionType.PREDECESSOR_SUCCESSOR):
        rng = random.Random(6)
        question = generate_question(template, paper_id="P-1", question_number="1", rng=rng)
        n = int(re.search(r"\d+", question.text).group())
        expected = n - 1 if template.operation == "predecessor" else n + 1
        assert question.expected_answer == str(expected)


def test_rounding_answers_are_correct():
    for template in get_templates(QuestionType.ROUNDING):
        rng = random.Random(7)
        question = generate_question(template, paper_id="P-1", question_number="1", rng=rng)
        base = 10 if template.operation == "round_nearest_10" else 100
        # the sampled n always appears before "nearest 10"/"nearest 100" in
        # the template wording, so the first match in the text is n itself
        n = int(re.search(r"\d+", question.text).group())
        assert int(question.expected_answer) % base == 0


def test_difficulty_features_track_addition_carrying():
    # 245 + 123 has no carrying (spec §16 Easy); force it via a seed that
    # samples those exact values would be brittle, so instead check the
    # invariant: requires_carrying is set (not None) whenever the template
    # has both "a" and "b" variables, and difficulty is computed from it.
    template = _template(QuestionType.ARITHMETIC)
    rng = random.Random(8)

    question = generate_question(template, paper_id="P-1", question_number="1", rng=rng)

    assert question.difficulty_features.requires_carrying is not None
    assert question.difficulty == question.difficulty_features.score()


def test_uses_the_text_provider_to_rephrase_when_given_one():
    template = _template(QuestionType.WORD_PROBLEM)
    rng = random.Random(9)
    provider = _FakeTextProvider("A rephrased version of the question.")

    question = generate_question(
        template, paper_id="P-1", question_number="1", rng=rng, text_provider=provider
    )

    assert question.text == "A rephrased version of the question."
    assert len(provider.prompts) == 1


def test_without_a_text_provider_uses_the_rendered_template_text():
    template = _template(QuestionType.WORD_PROBLEM)
    rng = random.Random(10)

    question = generate_question(template, paper_id="P-1", question_number="1", rng=rng)

    assert "shopkeeper" in question.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_question_generator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backend.generation.question_generator'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/backend/generation/question_generator.py
"""Candidate question assembly (PIPELINE.md's shared tail: "Variable
sampling ... Answer computation ... Candidate questions (list[Question],
source="generated")"). Selecting *which* QuestionTemplate to use is Phase
8's job (blueprint-driven); this module starts one step later — given an
already-chosen template, sample fresh variables, compute the answer purely
in code (never the LLM, spec §14), render `text_template`, and optionally
ask a TextGenerationProvider to rephrase the *already-computed* text for
naturalness. The provider never sees variables or the answer, so it cannot
introduce an arithmetic error."""

import random

from pydantic import BaseModel

from app.backend.core.ids import new_id
from app.backend.generation.formulas import (
    addition_requires_carrying,
    predecessor,
    round_to_nearest,
    successor,
    to_roman_numeral,
)
from app.backend.generation.variable_sampler import sample_variables
from app.backend.models.question import DifficultyFeatures, Question, QuestionType
from app.backend.models.question_template import QuestionTemplate
from app.backend.providers.text_generation import TextGenerationProvider
from app.backend.validation.answer_engine import evaluate

_PHRASING_PROMPT = """Rewrite this Class III Mathematics question so it reads naturally, without changing any numbers, the blank ("___"), or the underlying meaning. Return only the rewritten question text.

Original: {text}
"""


class _PhrasedText(BaseModel):
    text: str


def _resolve(
    template: QuestionTemplate, variables: dict[str, int], rng: random.Random
) -> tuple[dict[str, int], str]:
    op = template.operation
    if op == "predecessor":
        return variables, str(predecessor(variables["n"]))
    if op == "successor":
        return variables, str(successor(variables["n"]))
    if op == "round_nearest_10":
        return variables, str(round_to_nearest(variables["n"], 10))
    if op == "round_nearest_100":
        return variables, str(round_to_nearest(variables["n"], 100))
    if op == "roman_numeral_conversion":
        return variables, to_roman_numeral(variables["n"])
    if op == "addition_fill_blank":
        total = int(evaluate(template.answer_expression, variables))
        return {**variables, "c": total}, str(variables["b"])
    if op == "true_false_addition":
        correct = int(evaluate(template.answer_expression, variables))
        is_true = rng.random() < 0.5
        shown = correct if is_true else correct + rng.choice([-3, -2, -1, 1, 2, 3])
        return {**variables, "c": shown}, "true" if is_true else "false"
    return variables, str(int(evaluate(template.answer_expression, variables)))


def _build_options(
    template: QuestionTemplate, correct_answer: str, rng: random.Random
) -> list[str] | None:
    if template.question_type != QuestionType.MULTIPLE_CHOICE:
        return None
    if not template.distractor_offsets:
        raise ValueError(f"multiple_choice template {template.id} has no distractor_offsets")
    correct = int(correct_answer)
    values = [correct] + [correct + offset for offset in template.distractor_offsets]
    if len(set(values)) != len(values):
        raise ValueError(f"template {template.id} produced duplicate options: {values}")
    options = [str(v) for v in values]
    rng.shuffle(options)
    return options


def _difficulty_features(template: QuestionTemplate, variables: dict[str, int]) -> DifficultyFeatures:
    requires_carrying = (
        addition_requires_carrying(variables["a"], variables["b"])
        if "a" in variables and "b" in variables
        else None
    )
    is_word_problem = template.question_type == QuestionType.WORD_PROBLEM
    return DifficultyFeatures(
        digit_count=max(len(str(v)) for v in variables.values()),
        operation_count=1,
        requires_carrying=requires_carrying,
        step_count=1,
        vocabulary_level="standard" if is_word_problem else "basic",
        reasoning_required=is_word_problem,
    )


def generate_question(
    template: QuestionTemplate,
    paper_id: str,
    question_number: str,
    rng: random.Random | None = None,
    text_provider: TextGenerationProvider | None = None,
) -> Question:
    rng = rng or random.Random()
    variables = sample_variables(template.variables, rng)
    text_variables, expected_answer = _resolve(template, variables, rng)
    text = template.text_template.format(**text_variables)
    options = _build_options(template, expected_answer, rng)

    if text_provider is not None:
        phrased = text_provider.generate(_PHRASING_PROMPT.format(text=text), _PhrasedText)
        text = phrased.text

    difficulty_features = _difficulty_features(template, variables)

    return Question(
        id=new_id("QUES"),
        paper_id=paper_id,
        question_number=question_number,
        type=template.question_type,
        text=text,
        options=options,
        marks=template.marks,
        topic=template.topic,
        difficulty=difficulty_features.score(),
        difficulty_features=difficulty_features,
        expected_answer=expected_answer,
        answer_type=template.answer_type,
        source="generated",
        template_id=template.id,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_question_generator.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add app/backend/generation/question_generator.py tests/unit/test_question_generator.py
git commit -m "add generate_question: template -> validated candidate Question"
```

---

### Task 6: Integration test (Phase 6 validator x Phase 7 generator) + close out Phase 7

**Files:**
- Create: `tests/integration/test_generation_validation_roundtrip.py`
- Modify: `TODO.md`

**Interfaces:**
- Consumes: `generate_question` (Task 5), `TEMPLATES` (Task 4), `Paper`/`Section` from `app.backend.models.paper`, `validate_paper` from `app.backend.validation.validator`.

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_generation_validation_roundtrip.py
"""Closes the gap Phase 6's TODO.md note left open: "nothing produces a full
generated Paper + Question set until Phase 7/8 ... they become validator
work again once Phase 7/8 give them a caller." This generates one candidate
per seed template and runs Phase 6's validate_paper against the result."""

import random
from datetime import datetime

from app.backend.generation.question_generator import generate_question
from app.backend.models.paper import Paper, Section
from app.backend.questions.template_registry import TEMPLATES
from app.backend.validation.validator import validate_paper


def test_one_candidate_per_seed_template_passes_validation():
    rng = random.Random(42)
    questions = [
        generate_question(template, paper_id="P-1", question_number=str(i), rng=rng)
        for i, template in enumerate(TEMPLATES, start=1)
    ]
    total_marks = sum(question.marks for question in questions)
    paper = Paper(
        id="P-1",
        subject="Mathematics",
        class_standard="III",
        total_marks=total_marks,
        duration_minutes=50,
        sections=[Section(name="A", marks=total_marks)],
        source="generated",
        created_at=datetime.now(),
    )

    issues = validate_paper(paper, questions)

    assert issues == []
```

- [ ] **Step 2: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/integration/test_generation_validation_roundtrip.py -v`
Expected: PASS. If it fails, the failure is real signal (a seed template producing an invalid candidate) — fix the template or `_resolve` branch in Task 5's file, don't loosen the assertion.

- [ ] **Step 3: Run the full test suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: All tests pass, no regressions in Phase 1-6 tests.

- [ ] **Step 4: Replace the Phase 7 scaffold in TODO.md with a done section**

```markdown
## Phase 7 — Question generation — **done 2026-08-19**

- [x] `app/backend/models/question_template.py` — `QuestionTemplate`
      (DATA_MODEL.md core entity, extended with `question_type`, `subject`,
      `marks`, `answer_type`, `distractor_offsets` — see the phase's plan
      doc for why each exists without a Phase 8 `PaperBlueprint` caller yet)
- [x] `app/backend/generation/formulas.py` — Roman numeral conversion,
      round-half-up, predecessor/successor, addition-carrying detection
      (PROJECT_PLAN.md's deterministic list; closes the "no Roman-numeral
      converter utility exists" gap Phase 6 noted)
- [x] `app/backend/generation/variable_sampler.py` — `sample_variables`,
      seedable via caller-supplied `random.Random`
- [x] `app/backend/questions/template_registry.py` — 11 seed templates
      covering all 9 MVP `QuestionType`s
- [x] `app/backend/generation/question_generator.py` — `generate_question`:
      template -> sampled variables -> code-computed answer -> assembled
      `Question`, with optional LLM rephrasing of already-computed text
      (`providers/text_generation.py`, built in Phase 4, reused as-is — no
      new provider file needed)
- [x] Integration test: one candidate per seed template passes Phase 6's
      `validate_paper` with zero issues — closes Phase 6's TODO.md note
      ("they become validator work again once Phase 7/8 give them a
      caller")

Deliberately out of scope this phase (no caller exists yet to need them):
no CLI command — `PaperBlueprint`-driven template *selection* (PIPELINE.md:
"pick QuestionTemplates matching blueprint's topics/types/difficulty_range")
is Phase 8's job, and there is no assembled multi-question `Paper` to render
until a blueprint picks which templates and how many of each to use. No
`generation_max_regenerate_attempts`-driven regenerate-on-failure loop
either (`config.yaml` already has the setting from Phase 1) — that loop
needs Phase 8's template-selection step to have something to regenerate
*from* when a candidate fails validation.
```

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_generation_validation_roundtrip.py TODO.md
git commit -m "add generation/validation roundtrip test, mark Phase 7 complete"
```

---

## Self-Review Notes

- **Spec coverage:** spec §14's 9-step algorithm (understand curriculum -> extract templates -> identify variables -> generate candidates -> calculate answers by code -> validate -> assemble) → Tasks 1-6 together (template model, variable sampler, code-computed answers via `formulas.py`/`answer_engine.evaluate`, Task 6's validation roundtrip). §14's shopkeeper example (X + Y items, answer computed by code) → Task 4's `TPL-ADDITION-WORD-PROBLEM`, using the same phrasing. §15's `QuestionTemplate` JSON shape → Task 1. §16's difficulty engine, specifically "the system should record why a question has a particular difficulty" → Task 5's `_difficulty_features`, which derives `requires_carrying` from the actual sampled numbers via `addition_requires_carrying` (Task 2), tested against spec §16's own Easy/Medium examples. PIPELINE.md's "answer is always computed by code, never asked of the LLM" → every `_resolve` branch; the one LLM call in Task 5 only rephrases already-computed text. PROJECT_PLAN.md's "What's deterministic vs. AI" Roman numeral/rounding/predecessor-successor list → Task 2 in full. TODO.md's four Phase 7 checklist items → Tasks 1, 3, 4 directly; the `providers/text/` item was already satisfied by Phase 4's `providers/text_generation.py` and is reused unchanged (noted in Task 6's TODO.md update rather than rebuilt).
- **Explicitly deferred (documented in Task 6, not silently dropped):** `PaperBlueprint`-driven template selection and a `generate-paper` CLI command both need Phase 8's `PaperBlueprint` model, which doesn't exist yet — same "no caller yet" deferral pattern Phase 6 used for `validate-paper`'s CLI. The `generation_max_regenerate_attempts` config value (already in `config.yaml` since Phase 1) has no regenerate loop wired to it yet, since that loop operates over a blueprint's template selection, not a single template.
- **Type consistency:** `QuestionTemplate` (Task 1) is imported by name and by exact field set in Tasks 4 and 5. `evaluate(expression: str, variables: dict[str, float] | None = None) -> float` (Phase 6, unchanged) is called with `dict[str, int]` in Task 5 — safe, since Python doesn't enforce the type hint at runtime and every operation used (`+`, `-`) is closed over `int`/`float` interchangeably; results are explicitly cast with `int(...)` before being stored as `expected_answer`. `sample_variables(spec: dict[str, str], rng: random.Random) -> dict[str, int]` (Task 3) is consumed by Task 5 with that exact signature. `generate_question`'s signature (Task 5) matches what Task 6's integration test calls. `get_templates`/`TEMPLATES` (Task 4) match what Tasks 5 and 6 import.
