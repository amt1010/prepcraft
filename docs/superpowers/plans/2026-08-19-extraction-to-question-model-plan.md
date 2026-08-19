# Extraction-to-Question-Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the two gaps TODO.md's `generate_paper orchestrator` section recorded as "found, not fixed": (1) nothing converts Phase 4's `ExtractedSubQuestion` into Phase 5's full `Question`, and (2) nothing builds a `Paper` from an extraction run's output. Together these are what's still blocking `generate-paper --source <run_id>` from having anything real to load — this plan closes both, without building that CLI command itself (out of scope, not requested).

**Architecture:** Two functions in one new file, `questions/paper_assembly.py` (ARCHITECTURE.md already scopes `questions/` to "QuestionExtraction, QuestionTemplate model + registry" — this is extraction's output-handling concern). `question_from_extracted` converts one `ExtractedSubQuestion` into a full `Question`, filling every field `Question` requires that `ExtractedSubQuestion` doesn't carry. `assemble_paper_from_extracted` builds a `Paper` + `list[Question]` from a whole run's extracted questions plus caller-supplied paper-level metadata (subject/class/duration) that spec §23's wizard treats as a pre-upload user selection, never something extraction infers.

**Real gaps this plan has to make judgment calls about (not hidden — documented in code and recorded in TODO.md):**

1. **`Question.expected_answer` is unknowable from extraction.** Extraction classifies question *text*, never determines the *correct answer* — there's no reliable way to recover it from OCR of an existing exam (the student's handwritten answer may be wrong, and nothing transcribes an answer key). `question_from_extracted` sets it to `""`, the same "field exists, no real data source yet" pattern as `AnswerKeyEntry.working = None` (Phase 10) and `BlueprintSection.allowed_types = None` (Phase 8). This is fine for this plan's actual consumer — `blueprint/derive.py` never reads `expected_answer` — but would need real work before any future code calls `validate_paper` on existing-paper questions.
2. **`Question.difficulty_features` can't be reconstructed from extraction's bare `difficulty: int`.** Phase 5's docstring says difficulty should "trace back to" `DifficultyFeatures.score()`, but that was always only true for *generated* questions (Phase 7's `question_generator.py` computes it from real sampled variables). Extraction's difficulty is direct LLM judgment on free text — there is no operation count/carrying/step count to recover from that. `question_from_extracted` keeps `difficulty` as extraction's real judgment (authoritative) and builds a clearly-labeled best-effort `DifficultyFeatures` placeholder alongside it — it does **not** call `.score()` to overwrite `difficulty`, which would silently replace real classification with a number derived from made-up feature defaults.
3. **No per-question section link exists** (`Question` still has no `section` field — the same gap Phase 6, 8, and 9 each independently hit). `assemble_paper_from_extracted` puts every extracted question into one section named `"All Questions"` rather than fabricating a grouping it has no data for.
4. **`duration_minutes`/`subject`/`class_standard` are not extraction output.** Spec §23's wizard mockup selects Class and Subject *before* "Create from Existing Paper" even starts, and no stage anywhere infers exam duration from a scan. `assemble_paper_from_extracted` takes these as required parameters — no invented defaults.

**Tech Stack:** No new dependencies. Reuses `core/ids.new_id`, `models/paper.py`, `models/question.py`, `questions/extraction.py`'s `ExtractedSubQuestion`.

**Spec:** `Master Claude Code Prompt — AI Practice Paper Generator.md` §23 ("UI DESIGN" — Class/Subject selected on the main screen, before either workflow starts), `ARCHITECTURE.md` (module map's `questions/` entry), `DATA_MODEL.md` (`Paper`, `Question`, `DifficultyFeatures`), `TODO.md` (the `generate_paper orchestrator` section's "Two new gaps surfaced" note — the exact source of this plan), `app/backend/questions/extraction.py` (`ExtractedSubQuestion`'s own docstring: "Phase 5's job" — the conversion this plan finally writes), `app/backend/models/question.py`, `app/backend/models/paper.py`, `app/backend/generation/paper_generator.py` (this plan's ultimate consumer, unchanged).

## Global Constraints

- No fabricated data presented as real: every placeholder value this plan introduces (`expected_answer=""`, the placeholder `DifficultyFeatures`, the single `"All Questions"` section) is documented in code as a placeholder, not left to look authoritative.
- `question_from_extracted` fails loudly (raises `ValueError`) rather than guessing when extraction data is genuinely missing (`marks`/`topic`/`difficulty` are `None`, or `type` isn't a real `QuestionType` — both happen on the classification fallback path when no `TextGenerationProvider` is configured, per `extraction.py`'s own `if text_provider is None` branch).
- Every module boundary crosses with a Pydantic model, never a raw dict (DATA_MODEL.md line 3-4, spec §12, §35).
- `answer_type` inference reuses the exact same per-`QuestionType` mapping Phase 7's seed template registry (`questions/template_registry.py`) already established (`MULTIPLE_CHOICE` -> `"choice"`, `TRUE_FALSE` -> `"boolean"`, `ROMAN_NUMERAL` -> `"text"`, everything else -> `"numeric"`) — not a new, independently-invented mapping.

---

### Task 1: `question_from_extracted`

**Files:**
- Create: `app/backend/questions/paper_assembly.py`
- Test: `tests/unit/test_paper_assembly.py`

**Interfaces:**
- Consumes: `ExtractedSubQuestion` from `app.backend.questions.extraction`; `Question`, `QuestionType`, `DifficultyFeatures` from `app.backend.models.question`; `new_id` from `app.backend.core.ids`.
- Produces: `question_from_extracted(extracted: ExtractedSubQuestion, paper_id: str) -> Question`. Raises `ValueError` when `extracted.marks`, `extracted.topic`, or `extracted.difficulty` is `None`, or when `extracted.type` isn't a valid `QuestionType` value. Task 2 imports this directly: `from app.backend.questions.paper_assembly import question_from_extracted`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_paper_assembly.py
import pytest

from app.backend.models.question import QuestionType
from app.backend.questions.extraction import ExtractedSubQuestion
from app.backend.questions.paper_assembly import question_from_extracted


def _extracted(**overrides) -> ExtractedSubQuestion:
    fields = {
        "question_number": "1",
        "text": "47 + 25 = ?",
        "type": "arithmetic",
        "marks": 1.0,
        "topic": "Addition",
        "difficulty": 2,
    }
    fields.update(overrides)
    return ExtractedSubQuestion(**fields)


def test_converts_a_fully_classified_question():
    question = question_from_extracted(_extracted(), paper_id="PAPER-1")

    assert question.paper_id == "PAPER-1"
    assert question.question_number == "1"
    assert question.text == "47 + 25 = ?"
    assert question.type == QuestionType.ARITHMETIC
    assert question.marks == 1.0
    assert question.topic == "Addition"
    assert question.difficulty == 2
    assert question.source == "existing_paper"
    assert question.id  # a real generated id, not empty


def test_expected_answer_is_the_unknown_placeholder():
    question = question_from_extracted(_extracted(), paper_id="PAPER-1")

    assert question.expected_answer == ""


def test_multiple_choice_gets_choice_answer_type_and_keeps_options():
    extracted = _extracted(
        type="multiple_choice", options=["405", "450", "500", "495"], text="___ + 305 = 800"
    )

    question = question_from_extracted(extracted, paper_id="PAPER-1")

    assert question.answer_type == "choice"
    assert question.options == ["405", "450", "500", "495"]


def test_true_false_gets_boolean_answer_type():
    extracted = _extracted(type="true_false", text="47 + 25 = 72")

    question = question_from_extracted(extracted, paper_id="PAPER-1")

    assert question.answer_type == "boolean"


def test_roman_numeral_gets_text_answer_type():
    extracted = _extracted(type="roman_numeral", text="Write the roman number for 27.")

    question = question_from_extracted(extracted, paper_id="PAPER-1")

    assert question.answer_type == "text"


def test_word_problem_gets_numeric_answer_type():
    extracted = _extracted(type="word_problem", text="A shopkeeper sold...")

    question = question_from_extracted(extracted, paper_id="PAPER-1")

    assert question.answer_type == "numeric"


@pytest.mark.parametrize("missing_field", ["marks", "topic", "difficulty"])
def test_raises_when_a_required_classification_field_is_missing(missing_field):
    extracted = _extracted(**{missing_field: None})

    with pytest.raises(ValueError):
        question_from_extracted(extracted, paper_id="PAPER-1")


def test_raises_on_the_unclassified_fallback_type():
    extracted = _extracted(type="unknown", marks=None, topic=None, difficulty=None)

    with pytest.raises(ValueError):
        question_from_extracted(extracted, paper_id="PAPER-1")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_paper_assembly.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backend.questions.paper_assembly'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/backend/questions/paper_assembly.py
"""Turns Phase 4 extraction output into Phase 5's real Question/Paper
models — the conversion questions/extraction.py's own docstring calls
"Phase 5's job" but Phase 5 never actually wrote (TODO.md's generate_paper
orchestrator section: "Two new gaps surfaced while scoping this"). See this
plan's header for the judgment calls this file has to make about data
extraction genuinely doesn't produce (expected_answer, difficulty_features,
section grouping, paper-level metadata)."""

from app.backend.core.ids import new_id
from app.backend.models.question import DifficultyFeatures, Question, QuestionType
from app.backend.questions.extraction import ExtractedSubQuestion

_ANSWER_TYPE_BY_QUESTION_TYPE = {
    QuestionType.MULTIPLE_CHOICE: "choice",
    QuestionType.TRUE_FALSE: "boolean",
    QuestionType.ROMAN_NUMERAL: "text",
}
_DEFAULT_ANSWER_TYPE = "numeric"


def _placeholder_difficulty_features(question_type: QuestionType) -> DifficultyFeatures:
    """Best-effort structural guess only — NOT the source of truth for this
    question's difficulty (extraction's own LLM-judged `difficulty` int is).
    There is nothing in extraction output to compute operation_count/
    requires_carrying/step_count from without re-parsing question text,
    which is out of scope here."""
    reasoning_required = question_type in (QuestionType.WORD_PROBLEM, QuestionType.MENTAL_MATHS)
    return DifficultyFeatures(
        operation_count=1,
        requires_carrying=None,
        step_count=1,
        vocabulary_level="standard",
        reasoning_required=reasoning_required,
    )


def question_from_extracted(extracted: ExtractedSubQuestion, paper_id: str) -> Question:
    if extracted.marks is None or extracted.topic is None or extracted.difficulty is None:
        raise ValueError(
            f"question {extracted.question_number!r} is missing marks/topic/difficulty — "
            "was it extracted without a text_provider, leaving it unclassified "
            "('type=unknown')?"
        )
    question_type = QuestionType(extracted.type)

    return Question(
        id=new_id("QUES"),
        paper_id=paper_id,
        question_number=extracted.question_number,
        type=question_type,
        text=extracted.text,
        options=extracted.options,
        marks=extracted.marks,
        topic=extracted.topic,
        difficulty=extracted.difficulty,
        difficulty_features=_placeholder_difficulty_features(question_type),
        expected_answer="",
        answer_type=_ANSWER_TYPE_BY_QUESTION_TYPE.get(question_type, _DEFAULT_ANSWER_TYPE),
        source="existing_paper",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_paper_assembly.py -v`
Expected: PASS (10 tests — 7 named + 3 parametrized)

- [ ] **Step 5: Commit**

```bash
git add app/backend/questions/paper_assembly.py tests/unit/test_paper_assembly.py
git commit -m "add question_from_extracted converter"
```

---

### Task 2: `assemble_paper_from_extracted`

**Files:**
- Modify: `app/backend/questions/paper_assembly.py`
- Test: `tests/unit/test_paper_assembly.py` (append)

**Interfaces:**
- Consumes: `question_from_extracted` (Task 1); `Paper`, `Section` from `app.backend.models.paper`; `new_id` from `app.backend.core.ids`; `datetime.now`.
- Produces: `assemble_paper_from_extracted(subject: str, class_standard: str, duration_minutes: int, extracted_questions: list[ExtractedSubQuestion]) -> tuple[Paper, list[Question]]`. Every returned `Question.paper_id` equals the returned `Paper.id`. Propagates `question_from_extracted`'s `ValueError` unchanged (no per-question try/except swallowing). Task 3 imports this directly: `from app.backend.questions.paper_assembly import assemble_paper_from_extracted`.

- [ ] **Step 1: Write the failing tests**

First, change Task 1's import to include both names (avoids a mid-file import that ruff's E402 would flag):

```python
# tests/unit/test_paper_assembly.py — replace the Task 1 import line
from app.backend.questions.paper_assembly import (
    assemble_paper_from_extracted,
    question_from_extracted,
)
```

Then append to the end of `tests/unit/test_paper_assembly.py`:

```python
def test_assembled_paper_uses_the_given_subject_class_and_duration():
    paper, questions = assemble_paper_from_extracted(
        subject="Mathematics",
        class_standard="III",
        duration_minutes=50,
        extracted_questions=[_extracted()],
    )

    assert paper.subject == "Mathematics"
    assert paper.class_standard == "III"
    assert paper.duration_minutes == 50
    assert paper.source == "existing_paper"


def test_total_marks_is_the_sum_of_extracted_marks():
    paper, questions = assemble_paper_from_extracted(
        subject="Mathematics",
        class_standard="III",
        duration_minutes=50,
        extracted_questions=[
            _extracted(question_number="1", marks=1.0),
            _extracted(question_number="2", marks=2.0),
        ],
    )

    assert paper.total_marks == 3.0


def test_all_questions_land_in_one_default_section():
    paper, questions = assemble_paper_from_extracted(
        subject="Mathematics",
        class_standard="III",
        duration_minutes=50,
        extracted_questions=[
            _extracted(question_number="1", marks=1.0),
            _extracted(question_number="2", marks=2.0),
        ],
    )

    assert len(paper.sections) == 1
    assert paper.sections[0].name == "All Questions"
    assert paper.sections[0].marks == 3.0
    assert paper.sections[0].question_count == 2


def test_questions_reference_the_assembled_papers_id():
    paper, questions = assemble_paper_from_extracted(
        subject="Mathematics",
        class_standard="III",
        duration_minutes=50,
        extracted_questions=[_extracted()],
    )

    assert questions[0].paper_id == paper.id


def test_empty_extracted_questions_produces_an_empty_paper():
    paper, questions = assemble_paper_from_extracted(
        subject="Mathematics",
        class_standard="III",
        duration_minutes=50,
        extracted_questions=[],
    )

    assert questions == []
    assert paper.total_marks == 0.0
    assert paper.sections[0].question_count == 0


def test_propagates_the_converters_error_for_an_unclassified_question():
    with pytest.raises(ValueError):
        assemble_paper_from_extracted(
            subject="Mathematics",
            class_standard="III",
            duration_minutes=50,
            extracted_questions=[_extracted(marks=None, topic=None, difficulty=None)],
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_paper_assembly.py -v`
Expected: FAIL — `ImportError: cannot import name 'assemble_paper_from_extracted'`

- [ ] **Step 3: Write minimal implementation**

Append to `app/backend/questions/paper_assembly.py` (and add the two new imports to its existing import block):

```python
# add to the top of app/backend/questions/paper_assembly.py's imports:
from datetime import datetime

from app.backend.models.paper import Paper, Section
```

```python
# append to the end of app/backend/questions/paper_assembly.py
def assemble_paper_from_extracted(
    subject: str,
    class_standard: str,
    duration_minutes: int,
    extracted_questions: list[ExtractedSubQuestion],
) -> tuple[Paper, list[Question]]:
    paper_id = new_id("PAPER")
    questions = [question_from_extracted(extracted, paper_id) for extracted in extracted_questions]
    total_marks = sum(question.marks for question in questions)

    paper = Paper(
        id=paper_id,
        subject=subject,
        class_standard=class_standard,
        total_marks=total_marks,
        duration_minutes=duration_minutes,
        sections=[
            Section(name="All Questions", marks=total_marks, question_count=len(questions))
        ],
        source="existing_paper",
        created_at=datetime.now(),
    )
    return paper, questions
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_paper_assembly.py -v`
Expected: PASS (all tests, existing 10 from Task 1 + 6 new)

- [ ] **Step 5: Commit**

```bash
git add app/backend/questions/paper_assembly.py tests/unit/test_paper_assembly.py
git commit -m "add assemble_paper_from_extracted"
```

---

### Task 3: Integration test — extraction output reaches generate_paper end to end

**Files:**
- Test: `tests/integration/test_extraction_to_generated_paper.py`

**Interfaces:**
- Consumes: `assemble_paper_from_extracted` (Task 2), `generate_paper` (already built — `app.backend.generation.paper_generator`), `validate_paper` (`app.backend.validation.validator`), `ExtractedSubQuestion` (`app.backend.questions.extraction`).
- Produces: nothing consumed elsewhere — this is the closing proof that both gaps are actually closed, not just unit-tested in isolation.

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_extraction_to_generated_paper.py
"""Closes the loop TODO.md's generate_paper orchestrator section left open:
realistic extraction output (the ExtractedSubQuestion shape
questions/extraction.py actually produces, echoing the golden paper's
hand-transcribed content) now has a real path all the way to a validated
generated Paper, with no fixture-only Question/Paper construction in
between."""

import random

from app.backend.generation.paper_generator import generate_paper
from app.backend.questions.extraction import ExtractedSubQuestion
from app.backend.questions.paper_assembly import assemble_paper_from_extracted
from app.backend.validation.validator import validate_paper


def _extracted_questions() -> list[ExtractedSubQuestion]:
    # All three at marks=1.0 and difficulty=2 so the single auto-generated
    # "All Questions" section (marks=3.0, question_count=3) lands on
    # per_question_marks=1.0 — a value questions/template_registry.py's
    # TPL-ARITHMETIC-ADD/TPL-FILL-BLANK-ADD/TPL-MULTIPLE-CHOICE-ADD/
    # TPL-TRUE-FALSE-ADD all match at difficulty_level=2, so template
    # selection (Phase 8's marks-exact-match rule, no packing solver)
    # succeeds deterministically regardless of which of those it picks.
    return [
        ExtractedSubQuestion(
            question_number="1a",
            text="___ + 305 = 800. What is the missing number?",
            type="multiple_choice",
            options=["405", "450", "500", "495"],
            marks=1.0,
            topic="Addition",
            difficulty=2,
        ),
        ExtractedSubQuestion(
            question_number="2a",
            text="Write the predecessor and successor of 4759.",
            type="fill_in_the_blank",
            marks=1.0,
            topic="Predecessor and successor",
            difficulty=2,
        ),
        ExtractedSubQuestion(
            question_number="4a",
            text="Solve by breaking up to make ten: 7 + 8",
            type="arithmetic",
            marks=1.0,
            topic="Addition",
            difficulty=2,
        ),
    ]


def test_extracted_questions_assemble_and_generate_a_valid_paper():
    source_paper, source_questions = assemble_paper_from_extracted(
        subject="Mathematics",
        class_standard="III",
        duration_minutes=50,
        extracted_questions=_extracted_questions(),
    )

    assert source_paper.total_marks == 3.0
    assert len(source_questions) == 3
    assert all(q.paper_id == source_paper.id for q in source_questions)

    generated_paper, generated_questions = generate_paper(
        source_paper, source_questions, rng=random.Random(11)
    )

    assert validate_paper(generated_paper, generated_questions) == []
    assert generated_paper.source_paper_id == source_paper.id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/integration/test_extraction_to_generated_paper.py -v`
Expected: FAIL before Tasks 1-2 exist (`ModuleNotFoundError`); once Tasks 1-2 are done this test should already pass without further implementation, since it only composes existing functions and the fixture's marks (1.0/1.0/1.0, total 3.0 over 3 questions) already land on `per_question_marks=1.0`, a value real seed templates match at `difficulty_level=2`.

- [ ] **Step 3: No implementation step — this task only adds a test**

Tasks 1-2 already provide everything this test calls.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/integration/test_extraction_to_generated_paper.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_extraction_to_generated_paper.py
git commit -m "add extraction-to-generate_paper end-to-end integration test"
```

---

### Task 4: Update TODO.md

**Files:**
- Modify: `TODO.md`

**Interfaces:** None — documentation only.

- [ ] **Step 1: Run the full test suite and ruff as a pre-flight check**

Run: `.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m ruff check app/backend/questions/paper_assembly.py tests/unit/test_paper_assembly.py tests/integration/test_extraction_to_generated_paper.py`
Expected: all tests pass; ruff reports no issues in the files this plan touched.

- [ ] **Step 2: Update the `generate_paper orchestrator` section's gap note**

In `TODO.md`, replace the `**Two new gaps surfaced while scoping this**` paragraph (added when the orchestrator was built) with:

```markdown
**Two gaps that blocked `generate-paper --source <run_id>` — closed 2026-08-19:**
1. `app/backend/questions/paper_assembly.py` — `question_from_extracted`
   converts one `ExtractedSubQuestion` into a full `Question`. Real,
   documented placeholders where extraction genuinely has no data:
   `expected_answer=""` (extraction classifies text, never determines the
   correct answer), and a best-effort `DifficultyFeatures` that does *not*
   override extraction's own LLM-judged `difficulty` int (the two can
   legitimately diverge for existing-paper questions — see the file's
   docstring). Raises `ValueError` on the unclassified fallback path
   (`type="unknown"`, no `text_provider` configured) rather than guessing.
2. `assemble_paper_from_extracted` builds a `Paper` + `list[Question]`
   from a run's extracted questions plus caller-supplied `subject`/
   `class_standard`/`duration_minutes` (spec §23: these are wizard
   selections made before either workflow starts, never extracted data).
   All questions land in one `"All Questions"` section — `Question` still
   has no `section` field to group by (same gap Phase 6/8/9 each hit).
3. Integration test: realistic `ExtractedSubQuestion`s assemble into a
   source `Paper`, feed `generate_paper`, and the result passes
   `validate_paper` with zero issues — closes the loop end to end.

Still open: no `generate-paper --source <run_id>` CLI command wiring these
functions to `ArtifactStore`'s `09_questions.json` — that's now genuinely
unblocked (both prerequisite gaps are closed) but wasn't requested as part
of this work.
```

- [ ] **Step 3: Commit**

```bash
git add TODO.md
git commit -m "close the extraction-to-Question and Paper-assembly gaps"
```
