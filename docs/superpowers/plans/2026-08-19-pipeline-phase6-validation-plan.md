# Phase 6 — Question Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `validation/` module (ARCHITECTURE.md: "Answer recomputation, blueprint compliance, dedup, leakage checks") — closing PROJECT_PLAN.md's Phase 6 row ("Validator catches a deliberately-broken fixture (wrong answer, marks mismatch) in a unit test").

**Architecture:** Two new files. `app/backend/validation/answer_engine.py` is a restricted arithmetic expression evaluator (AST-based, whitelisted node types only, never Python's `eval()`) — the deterministic mechanism behind spec §21's example (`47 + 25` must recompute to `72`; a stated `73` must fail). `app/backend/validation/validator.py` builds on it: `validate_question` checks one `Question` (missing answer, multiple-choice options, arithmetic recomputation), `validate_paper` checks a `Paper` plus its `Question`s (everything `validate_question` does, plus total-marks compliance, duplicate detection, and answer leakage). Both are pure functions over existing models — no provider calls, no I/O, no CLI wiring (there's no generator yet to run `validate-paper` against; that's Phase 7/8's job per PROJECT_PLAN.md's phase table).

**Tech Stack:** Python's `ast` + `operator` stdlib modules for the expression evaluator, Pydantic v2 for `ValidationIssue`, `re` for the two text patterns (arithmetic extraction, leakage). No new dependencies.

**Spec:** `Master Claude Code Prompt — AI Practice Paper Generator.md` §21 ("VALIDATION ENGINE" — the exact 47+25 example this plan reproduces as a test), `DATA_MODEL.md` (line 100-103: "answer_expression is parsed and evaluated with a restricted expression evaluator"), `ARCHITECTURE.md` (module map: `validation/` = "Answer recomputation, blueprint compliance, dedup, leakage checks"), `PROJECT_PLAN.md` (phase table row 6, and "What's deterministic vs. AI" section), `TODO.md` (existing Phase 6 scaffold naming `answer_engine.py` and `validator.py`), `app/backend/models/question.py` and `app/backend/models/paper.py` (the models this phase validates, unchanged).

## Global Constraints

- Every module boundary crosses with a Pydantic model, never a raw dict (DATA_MODEL.md line 3-4, spec §12, §35) — `ValidationIssue` is a `BaseModel`, not a dict or tuple.
- `validation/` never calls a provider — every check is deterministic (PROJECT_PLAN.md's "What's deterministic vs. AI" list; ARCHITECTURE.md's dependency direction has `validation` depending only on `models`).
- The expression evaluator must never call Python's `eval()`/`exec()` on the raw string — parse via `ast.parse` and whitelist node types only (DATA_MODEL.md line 100-103, spec §14/§21).
- No schema changes to `Question` or `Paper` in this phase — both are consumed exactly as Phase 2 and Phase 5 defined them.

---

### Task 1: `answer_engine.py` — restricted expression evaluator

**Files:**
- Create: `app/backend/validation/__init__.py` (empty, matches every other module's package marker)
- Create: `app/backend/validation/answer_engine.py`
- Test: `tests/unit/test_answer_engine.py`

**Interfaces:**
- Produces: `evaluate(expression: str, variables: dict[str, float] | None = None) -> float`, raising `ValueError` for anything outside `+ - * /`, parentheses, numeric literals, and known variable names. Task 2 imports this directly: `from app.backend.validation.answer_engine import evaluate`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_answer_engine.py
import pytest

from app.backend.validation.answer_engine import evaluate


def test_evaluates_simple_addition():
    assert evaluate("47 + 25") == 72


def test_evaluates_subtraction():
    assert evaluate("100 - 37") == 63


def test_evaluates_multiplication():
    assert evaluate("6 * 7") == 42


def test_evaluates_division():
    assert evaluate("20 / 4") == 5


def test_respects_operator_precedence():
    assert evaluate("2 + 3 * 4") == 14


def test_respects_parentheses():
    assert evaluate("(2 + 3) * 4") == 20


def test_supports_unary_negation():
    assert evaluate("-5 + 10") == 5


def test_substitutes_variables():
    assert evaluate("a + b", {"a": 3, "b": 4}) == 7


def test_raises_on_undefined_variable():
    with pytest.raises(ValueError, match="undefined variable"):
        evaluate("a + 1")


def test_raises_on_function_call():
    with pytest.raises(ValueError):
        evaluate("__import__('os').system('ls')")


def test_raises_on_attribute_access():
    with pytest.raises(ValueError):
        evaluate("a.b", {"a": 1})


def test_raises_on_syntax_error():
    with pytest.raises(ValueError):
        evaluate("47 +")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_answer_engine.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backend.validation'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/backend/validation/__init__.py
```

```python
# app/backend/validation/answer_engine.py
"""Restricted arithmetic expression evaluator (DATA_MODEL.md: "answer_expression
is parsed and evaluated with a restricted expression evaluator (arithmetic
operators only, no eval() on arbitrary strings)"). This is the deterministic
mechanism behind spec §21's example — recomputing 47 + 25 to catch a stated
answer of 73 — and the only thing in this module allowed to touch an
expression string. AST node types are whitelisted explicitly; anything not
listed (calls, attribute access, comparisons, ...) raises ValueError."""

import ast
import operator

_BINARY_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}

_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def evaluate(expression: str, variables: dict[str, float] | None = None) -> float:
    variables = variables or {}
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"not a valid expression: {expression!r}") from exc
    return _eval_node(tree.body, variables)


def _eval_node(node: ast.AST, variables: dict[str, float]) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.Name):
        if node.id not in variables:
            raise ValueError(f"undefined variable: {node.id}")
        return variables[node.id]
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPS:
        left = _eval_node(node.left, variables)
        right = _eval_node(node.right, variables)
        return _BINARY_OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand, variables))
    raise ValueError(f"disallowed expression element: {ast.dump(node)}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_answer_engine.py -v`
Expected: PASS (12 tests)

- [ ] **Step 5: Commit**

```bash
git add app/backend/validation/__init__.py app/backend/validation/answer_engine.py tests/unit/test_answer_engine.py
git commit -m "add restricted expression evaluator for answer validation"
```

---

### Task 2: `validator.py` — `ValidationIssue` + `validate_question`

**Files:**
- Create: `app/backend/validation/validator.py`
- Test: `tests/unit/test_validator.py`

**Interfaces:**
- Consumes: `evaluate` from Task 1; `Question`, `QuestionType` from `app.backend.models.question`.
- Produces: `ValidationIssue(BaseModel)` with fields `code: str`, `message: str`, `question_number: str | None = None`; `validate_question(question: Question) -> list[ValidationIssue]`. Task 3 imports both directly from `app.backend.validation.validator`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_validator.py
from app.backend.models.question import DifficultyFeatures, Question, QuestionType
from app.backend.validation.validator import validate_question


def _difficulty_features() -> DifficultyFeatures:
    return DifficultyFeatures(
        operation_count=1,
        requires_carrying=False,
        step_count=1,
        vocabulary_level="basic",
        reasoning_required=False,
    )


def _question(**overrides) -> Question:
    fields = {
        "id": "Q-1",
        "paper_id": "P-1",
        "question_number": "1",
        "type": QuestionType.ARITHMETIC,
        "text": "47 + 25",
        "marks": 1.0,
        "topic": "Addition",
        "difficulty": 1,
        "difficulty_features": _difficulty_features(),
        "expected_answer": "72",
        "answer_type": "numeric",
        "source": "existing_paper",
    }
    fields.update(overrides)
    return Question(**fields)


def test_a_correct_arithmetic_question_has_no_issues():
    assert validate_question(_question()) == []


def test_spec_47_plus_25_stated_as_73_fails_validation():
    question = _question(text="47 + 25", expected_answer="73")

    issues = validate_question(question)

    assert len(issues) == 1
    assert issues[0].code == "arithmetic_mismatch"
    assert issues[0].question_number == "1"


def test_missing_expected_answer_is_flagged():
    question = _question(expected_answer="")

    issues = validate_question(question)

    assert any(issue.code == "missing_answer" for issue in issues)


def test_multiple_choice_without_options_is_flagged():
    question = _question(
        type=QuestionType.MULTIPLE_CHOICE, text="Pick one", expected_answer="A", options=None
    )

    issues = validate_question(question)

    assert any(issue.code == "multiple_choice_missing_options" for issue in issues)


def test_multiple_choice_answer_not_in_options_is_flagged():
    question = _question(
        type=QuestionType.MULTIPLE_CHOICE,
        text="Pick one",
        expected_answer="D",
        options=["A", "B", "C"],
    )

    issues = validate_question(question)

    assert any(issue.code == "answer_not_in_options" for issue in issues)


def test_multiple_choice_answer_in_options_has_no_issues():
    question = _question(
        type=QuestionType.MULTIPLE_CHOICE,
        text="Pick one",
        expected_answer="B",
        options=["A", "B", "C"],
    )

    assert validate_question(question) == []


def test_arithmetic_question_with_unparseable_text_is_skipped_not_flagged():
    question = _question(
        type=QuestionType.ARITHMETIC,
        text="A shopkeeper sold some items",
        expected_answer="unknown",
    )

    assert validate_question(question) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_validator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backend.validation.validator'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/backend/validation/validator.py
"""Question and Paper validation (ARCHITECTURE.md's validation/ module:
"Answer recomputation, blueprint compliance, dedup, leakage checks"). Every
check here is deterministic (PROJECT_PLAN.md's "What's deterministic vs.
AI" list) — this module never calls a provider. Per spec §21: if a
question's stated answer doesn't recompute, it must fail validation and the
PDF must never be generated from it."""

import re

from pydantic import BaseModel

from app.backend.models.question import Question, QuestionType
from app.backend.validation.answer_engine import evaluate

_ARITHMETIC_PATTERN = re.compile(r"(-?\d+(?:\.\d+)?)\s*([+\-*/])\s*(-?\d+(?:\.\d+)?)")


class ValidationIssue(BaseModel):
    code: str
    message: str
    question_number: str | None = None


def validate_question(question: Question) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    if not question.expected_answer.strip():
        issues.append(
            ValidationIssue(
                code="missing_answer",
                message="expected_answer is empty",
                question_number=question.question_number,
            )
        )

    if question.type == QuestionType.MULTIPLE_CHOICE:
        if not question.options:
            issues.append(
                ValidationIssue(
                    code="multiple_choice_missing_options",
                    message="multiple_choice question has no options",
                    question_number=question.question_number,
                )
            )
        elif question.expected_answer not in question.options:
            issues.append(
                ValidationIssue(
                    code="answer_not_in_options",
                    message=(
                        f"expected_answer {question.expected_answer!r} is not "
                        f"among options {question.options!r}"
                    ),
                    question_number=question.question_number,
                )
            )

    if question.type == QuestionType.ARITHMETIC:
        match = _ARITHMETIC_PATTERN.search(question.text)
        if match:
            try:
                stated = float(question.expected_answer)
            except ValueError:
                stated = None
            if stated is not None:
                expression = f"{match.group(1)} {match.group(2)} {match.group(3)}"
                computed = evaluate(expression)
                if computed != stated:
                    issues.append(
                        ValidationIssue(
                            code="arithmetic_mismatch",
                            message=(
                                f"recomputed {expression} = {computed}, but "
                                f"expected_answer states {stated}"
                            ),
                            question_number=question.question_number,
                        )
                    )

    return issues
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_validator.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add app/backend/validation/validator.py tests/unit/test_validator.py
git commit -m "add validate_question with arithmetic recomputation"
```

---

### Task 3: `validate_paper` — marks, duplicates, leakage

**Files:**
- Modify: `app/backend/validation/validator.py`
- Modify: `tests/unit/test_validator.py`

**Interfaces:**
- Consumes: `Paper` from `app.backend.models.paper`; `validate_question` and `ValidationIssue` already defined in this file.
- Produces: `validate_paper(paper: Paper, questions: list[Question]) -> list[ValidationIssue]`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_validator.py`:

```python
from app.backend.models.paper import Paper, Section
from app.backend.validation.validator import validate_paper


def _paper(total_marks: float) -> Paper:
    return Paper(
        id="P-1",
        subject="Mathematics",
        class_standard="III",
        total_marks=total_marks,
        duration_minutes=50,
        sections=[Section(name="A", marks=total_marks)],
        source="existing_paper",
        created_at="2026-08-19T00:00:00",
    )


def test_paper_with_marks_not_summing_to_total_is_flagged():
    paper = _paper(total_marks=5.0)
    questions = [_question(marks=1.0)]

    issues = validate_paper(paper, questions)

    assert any(issue.code == "marks_mismatch" for issue in issues)


def test_paper_with_matching_marks_has_no_marks_issue():
    paper = _paper(total_marks=1.0)
    questions = [_question(marks=1.0)]

    issues = validate_paper(paper, questions)

    assert not any(issue.code == "marks_mismatch" for issue in issues)


def test_duplicate_question_text_is_flagged():
    paper = _paper(total_marks=2.0)
    questions = [
        _question(question_number="1", marks=1.0),
        _question(question_number="2", marks=1.0),
    ]

    issues = validate_paper(paper, questions)

    assert any(
        issue.code == "duplicate_question" and issue.question_number == "2"
        for issue in issues
    )


def test_answer_leaked_into_question_text_is_flagged():
    paper = _paper(total_marks=1.0)
    questions = [
        _question(
            type=QuestionType.FILL_BLANK,
            text="The answer is 72, what is 47 + 25?",
            expected_answer="72",
            marks=1.0,
        )
    ]

    issues = validate_paper(paper, questions)

    assert any(issue.code == "answer_leakage" for issue in issues)


def test_multiple_choice_options_are_not_treated_as_leakage():
    paper = _paper(total_marks=1.0)
    questions = [
        _question(
            type=QuestionType.MULTIPLE_CHOICE,
            text="Pick one: A, B, C",
            expected_answer="A",
            options=["A", "B", "C"],
            marks=1.0,
        )
    ]

    issues = validate_paper(paper, questions)

    assert not any(issue.code == "answer_leakage" for issue in issues)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_validator.py -v`
Expected: FAIL — `ImportError: cannot import name 'validate_paper' from 'app.backend.validation.validator'`

- [ ] **Step 3: Write minimal implementation**

Add to `app/backend/validation/validator.py` (update the import line and append the function):

```python
from app.backend.models.paper import Paper
from app.backend.models.question import Question, QuestionType
```

```python
def validate_paper(paper: Paper, questions: list[Question]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    for question in questions:
        issues.extend(validate_question(question))

    total_marks = sum(question.marks for question in questions)
    if abs(total_marks - paper.total_marks) > 1e-6:
        issues.append(
            ValidationIssue(
                code="marks_mismatch",
                message=(
                    f"questions sum to {total_marks} marks, paper declares "
                    f"{paper.total_marks}"
                ),
            )
        )

    seen_by_text: dict[str, str] = {}
    for question in questions:
        normalized = " ".join(question.text.split()).lower()
        if normalized in seen_by_text:
            issues.append(
                ValidationIssue(
                    code="duplicate_question",
                    message=f"question {question.question_number} duplicates {seen_by_text[normalized]}",
                    question_number=question.question_number,
                )
            )
        else:
            seen_by_text[normalized] = question.question_number

    for question in questions:
        if question.type == QuestionType.MULTIPLE_CHOICE or not question.expected_answer.strip():
            continue
        if re.search(rf"\b{re.escape(question.expected_answer)}\b", question.text, re.IGNORECASE):
            issues.append(
                ValidationIssue(
                    code="answer_leakage",
                    message="expected_answer appears verbatim in question text",
                    question_number=question.question_number,
                )
            )

    return issues
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_validator.py -v`
Expected: PASS (12 tests)

- [ ] **Step 5: Run the full test suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: All tests pass, no regressions in Phase 1-5 tests

- [ ] **Step 6: Commit**

```bash
git add app/backend/validation/validator.py tests/unit/test_validator.py
git commit -m "add validate_paper for marks, duplicate, and leakage checks"
```

---

### Task 4: Close out Phase 6 in TODO.md

**Files:**
- Modify: `TODO.md`

- [ ] **Step 1: Replace the Phase 6 scaffold with a done section**, matching how Phase 5's header reads:

```markdown
## Phase 6 — Validation — **done 2026-08-19**

- [x] `app/backend/validation/answer_engine.py` — restricted (`ast`-based)
      arithmetic expression evaluator, never `eval()` on a raw string
      (DATA_MODEL.md)
- [x] `app/backend/validation/validator.py` — `validate_question` (missing
      answer, multiple-choice options, arithmetic recomputation) and
      `validate_paper` (total marks, duplicate questions, answer leakage)
- [x] Unit test: spec §21's 47+25=73 example, literally — `expected_answer`
      recomputes wrong and validation fails with `arithmetic_mismatch`

Deliberately out of scope this phase (no caller exists yet to need them):
no `validate-paper` CLI command — nothing produces a full generated `Paper`
+ `Question` set until Phase 7/8 — and no Roman-numeral or blueprint
section-count recomputation, since `Question` has no `section` field and
no Roman-numeral converter utility exists in the repo yet. Both are real
gaps, not forgotten ones; they become validator work again once Phase 7/8
give them a caller.
```

- [ ] **Step 2: Commit**

```bash
git add TODO.md
git commit -m "mark Phase 6 validation complete"
```

---

## Self-Review Notes

- **Spec coverage:** spec §21's canonical example (47+25 must recompute to 72; a stated 73 fails) → Task 2's `test_spec_47_plus_25_stated_as_73_fails_validation`, using the exact numbers from the spec. §21's "Total marks" and "No duplicate questions" and "No accidental answer leakage" checks → Task 3's `marks_mismatch`, `duplicate_question`, `answer_leakage`. §21's "Multiple-choice answer exists" / "Correct answer belongs to options" → Task 2's multiple-choice checks. §21's "Missing answers" → Task 2's `missing_answer`. DATA_MODEL.md's restricted-evaluator requirement → Task 1, whitelist-only AST walk. PROJECT_PLAN.md's Phase 6 acceptance line → Task 2 + Task 3 together (wrong-answer fixture and marks-mismatch fixture both fail validation in a unit test).
- **Explicitly deferred (documented in Task 4, not silently dropped):** §21 also lists "Difficulty within requested range," "Question belongs to selected chapter," "No contradictory instructions," and "No impossible questions" — these need a `PaperBlueprint`/`Chapter` to check against, neither of which exists until Phase 8/12. Roman-numeral recomputation needs a converter utility that doesn't exist yet (PROJECT_PLAN.md lists it as a deterministic component but no phase has built it) — adding one here to serve a single check would be speculative, not driven by an actual golden question needing it validated this way.
- **Type consistency:** `Question`, `QuestionType` (Task 1 doesn't touch these; Task 2 imports them) and `evaluate` (Task 1 → Task 2) are consumed with the exact names and signatures they're defined with. `ValidationIssue` and `validate_question` (Task 2 → Task 3) are extended, not redefined, in the same file.
