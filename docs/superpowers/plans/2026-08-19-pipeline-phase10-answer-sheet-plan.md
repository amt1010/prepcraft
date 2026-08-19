# Phase 10 — Answer Sheet Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `AnswerKey` (DATA_MODEL.md core entity) and render it to `answer_sheet.pdf` — closing TODO.md's Phase 10 row (`models/answer_key.py` + builder, `answer_sheet.pdf` rendering) and PROJECT_PLAN.md's Phase 10 acceptance bar: "`answer_sheet.pdf` matches generated paper's questions 1:1."

**Architecture:** One new model file, one new small package for the builder, one new rendering template, and one `renderer.py` addition. `models/answer_key.py` defines `AnswerKeyEntry`/`AnswerKey` exactly as DATA_MODEL.md lists them. `answer_key/builder.py` implements spec §20's core rule — "generated from the structured question model, not regenerated independently by an LLM" — by mapping each `Question` directly to one `AnswerKeyEntry` (`expected_answer`, `marks`, `question_number` copied verbatim), in the order given, which is what makes the 1:1 correspondence hold by construction rather than by a separate check. It lives outside `models/` (mirroring Phase 8's `blueprint/derive.py`) because it calls `core.ids.new_id`, and nothing in `models/` generates IDs or performs pipeline logic (ARCHITECTURE.md: "nothing in `models` imports from a pipeline module"). `rendering/templates/answer_sheet.py` mirrors Phase 9's `simple_practice_paper.py` shape exactly — title, then one line per entry (`question_number`, `answer`, `marks`, optional `working`) — pure function, no I/O. `rendering/renderer.py` gains `render_answer_sheet`, sharing a small `_write_pdf` helper with the now-two-caller-strong page-size/`SimpleDocTemplate`/`mkdir` logic that `render_question_paper` (Phase 9) used to do inline.

**Tech Stack:** `reportlab` (same as Phase 9, no new dependency). Reuses `core/ids.new_id`, `models/paper.py`, `models/question.py` — no duplicated logic.

**Spec:** `Master Claude Code Prompt — AI Practice Paper Generator.md` §20 ("ANSWER SHEET" — "Question number / Correct answer / Expected working where relevant / Marks... generated from the structured question model, not regenerated independently by an LLM. This prevents question/answer mismatch") and PHASE 10 ("Implement answer sheet generation"), `DATA_MODEL.md` ("AnswerKey" core entity — "Built directly from the `Paper`'s `Question.expected_answer` fields, never regenerated independently"), `ARCHITECTURE.md` (module map — this plan adds an `answer_key/` entry, mirroring Phase 8's `blueprint/`), `PROJECT_PLAN.md` (Phase 10's "Done when" row), `TODO.md` (Phase 10 scaffold), `app/backend/models/paper.py`, `app/backend/models/question.py`, `app/backend/rendering/renderer.py` + `rendering/templates/simple_practice_paper.py` (Phase 9, being extended/modified here).

## Global Constraints

- The answer key is built by pure code from already-computed `Question.expected_answer` fields — never by calling a provider (PROJECT_PLAN.md's deterministic list; spec §20's explicit anti-mismatch rule). `answer_key/builder.py` imports nothing from `providers/`.
- `AnswerKeyEntry.working` stays `None` from `build_answer_key` — no `Question` field holds step-by-step working yet (spec §20 marks it optional: "Expected working where relevant"), so there is nothing to populate it from. The template still renders it when present, so a future phase can populate it without touching rendering code.
- `rendering/` still depends only on `app.backend.models` and `reportlab` (ARCHITECTURE.md's constraint, reaffirmed in Phase 9's plan) — `rendering/templates/answer_sheet.py` and the `render_answer_sheet` addition to `renderer.py` take an already-built `AnswerKey`, never importing `answer_key/builder.py` (that would pull a non-`models` pipeline module into `rendering/`).
- Every module boundary crosses with a Pydantic model, never a raw dict (DATA_MODEL.md line 3-4, spec §12, §35).
- No CLI command this phase (no `generate-answer-key`) — matches Phase 8/9's precedent: there is still no `generate-paper` orchestrator assembling a full pipeline run into one storable `Paper` + `list[Question]`, so a CLI command has nothing real to load from disk yet.

---

### Task 1: `AnswerKeyEntry` / `AnswerKey` models

**Files:**
- Create: `app/backend/models/answer_key.py`
- Test: `tests/unit/test_answer_key_model.py`

**Interfaces:**
- Produces: `AnswerKeyEntry(BaseModel)` with fields `question_id: str`, `question_number: str`, `answer: str`, `working: str | None = None`, `marks: float`. `AnswerKey(BaseModel)` with fields `id: str`, `paper_id: str`, `entries: list[AnswerKeyEntry]`. Tasks 2-5 import both directly: `from app.backend.models.answer_key import AnswerKey, AnswerKeyEntry`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_answer_key_model.py
from app.backend.models.answer_key import AnswerKey, AnswerKeyEntry


def _entry(**overrides) -> AnswerKeyEntry:
    fields = {
        "question_id": "Q-1",
        "question_number": "1",
        "answer": "72",
        "marks": 1.0,
    }
    fields.update(overrides)
    return AnswerKeyEntry(**fields)


def test_builds_a_valid_answer_key():
    key = AnswerKey(id="ANSKEY-1", paper_id="PAPER-1", entries=[_entry()])

    assert key.paper_id == "PAPER-1"
    assert key.entries[0].answer == "72"


def test_entry_working_defaults_to_none_but_can_be_set():
    default_entry = _entry()
    entry_with_working = _entry(working="47 + 25 = 72")

    assert default_entry.working is None
    assert entry_with_working.working == "47 + 25 = 72"


def test_answer_key_can_have_no_entries():
    key = AnswerKey(id="ANSKEY-1", paper_id="PAPER-1", entries=[])

    assert key.entries == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_answer_key_model.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backend.models.answer_key'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/backend/models/answer_key.py
"""AnswerKey model (DATA_MODEL.md's "AnswerKey" core entity; spec §20:
"The answer key should be generated from the structured question model,
not regenerated independently by an LLM. This prevents question/answer
mismatch.")."""

from pydantic import BaseModel


class AnswerKeyEntry(BaseModel):
    question_id: str
    question_number: str
    answer: str
    working: str | None = None
    marks: float


class AnswerKey(BaseModel):
    id: str
    paper_id: str
    entries: list[AnswerKeyEntry]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_answer_key_model.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add app/backend/models/answer_key.py tests/unit/test_answer_key_model.py
git commit -m "add AnswerKey model"
```

---

### Task 2: `answer_key/builder.py` — build from the structured question model

**Files:**
- Create: `app/backend/answer_key/__init__.py` (empty, package marker)
- Create: `app/backend/answer_key/builder.py`
- Test: `tests/unit/test_answer_key_builder.py`

**Interfaces:**
- Consumes: `Paper` from `app.backend.models.paper`; `Question` from `app.backend.models.question`; `AnswerKey`, `AnswerKeyEntry` from `app.backend.models.answer_key` (Task 1); `new_id` from `app.backend.core.ids`.
- Produces: `build_answer_key(paper: Paper, questions: list[Question]) -> AnswerKey`. Task 5 imports this directly: `from app.backend.answer_key.builder import build_answer_key`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_answer_key_builder.py
from datetime import datetime

from app.backend.answer_key.builder import build_answer_key
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


def _question(number: str, answer: str, marks: float) -> Question:
    return Question(
        id=f"Q-{number}",
        paper_id="PAPER-1",
        question_number=number,
        type=QuestionType.ARITHMETIC,
        text=f"question {number}",
        marks=marks,
        topic="Addition",
        difficulty=1,
        difficulty_features=_difficulty_features(),
        expected_answer=answer,
        answer_type="numeric",
        source="existing_paper",
    )


def _paper() -> Paper:
    return Paper(
        id="PAPER-1",
        subject="Mathematics",
        class_standard="III",
        total_marks=3.0,
        duration_minutes=50,
        sections=[Section(name="A", marks=3.0)],
        source="existing_paper",
        created_at=datetime.now(),
    )


def test_one_entry_per_question_in_order():
    questions = [_question("1", "72", 1.0), _question("2", "XXVII", 0.5), _question("3", "15", 1.5)]

    answer_key = build_answer_key(_paper(), questions)

    assert [entry.question_number for entry in answer_key.entries] == ["1", "2", "3"]
    assert [entry.answer for entry in answer_key.entries] == ["72", "XXVII", "15"]
    assert [entry.marks for entry in answer_key.entries] == [1.0, 0.5, 1.5]


def test_entry_question_id_and_paper_id_are_set():
    questions = [_question("1", "72", 1.0)]

    answer_key = build_answer_key(_paper(), questions)

    assert answer_key.paper_id == "PAPER-1"
    assert answer_key.entries[0].question_id == "Q-1"


def test_working_is_always_none():
    questions = [_question("1", "72", 1.0)]

    answer_key = build_answer_key(_paper(), questions)

    assert answer_key.entries[0].working is None


def test_empty_questions_produces_an_empty_answer_key():
    answer_key = build_answer_key(_paper(), [])

    assert answer_key.entries == []
    assert answer_key.paper_id == "PAPER-1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_answer_key_builder.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backend.answer_key'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/backend/answer_key/__init__.py
```

```python
# app/backend/answer_key/builder.py
"""Builds an AnswerKey directly from a Paper's already-computed
Question.expected_answer fields (spec §20: "generated from the structured
question model, not regenerated independently by an LLM" — this prevents
question/answer mismatch). One AnswerKeyEntry per question, in the order
given, so PROJECT_PLAN.md's Phase 10 acceptance bar ("answer_sheet.pdf
matches generated paper's questions 1:1") holds by construction. `working`
is always None — no Question field holds step-by-step working yet (spec
§20's "Expected working where relevant" is optional), so there is nothing
to populate it from."""

from app.backend.core.ids import new_id
from app.backend.models.answer_key import AnswerKey, AnswerKeyEntry
from app.backend.models.paper import Paper
from app.backend.models.question import Question


def build_answer_key(paper: Paper, questions: list[Question]) -> AnswerKey:
    entries = [
        AnswerKeyEntry(
            question_id=question.id,
            question_number=question.question_number,
            answer=question.expected_answer,
            marks=question.marks,
        )
        for question in questions
    ]
    return AnswerKey(id=new_id("ANSKEY"), paper_id=paper.id, entries=entries)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_answer_key_builder.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add app/backend/answer_key/__init__.py app/backend/answer_key/builder.py tests/unit/test_answer_key_builder.py
git commit -m "add build_answer_key from the structured question model"
```

---

### Task 3: `rendering/templates/answer_sheet.py` — flowable builder

**Files:**
- Create: `app/backend/rendering/templates/answer_sheet.py`
- Test: `tests/unit/test_answer_sheet_template.py`

**Interfaces:**
- Consumes: `Paper` from `app.backend.models.paper`; `AnswerKey`, `AnswerKeyEntry` from `app.backend.models.answer_key` (Task 1).
- Produces: `build_flowables(paper: Paper, answer_key: AnswerKey) -> list[Flowable]`. Flowable index `[0]` is always the title `Paragraph`. Task 4 imports this directly: `from app.backend.rendering.templates.answer_sheet import build_flowables`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_answer_sheet_template.py
from reportlab.platypus import Paragraph

from app.backend.models.answer_key import AnswerKey, AnswerKeyEntry
from app.backend.models.paper import Paper, Section
from app.backend.rendering.templates.answer_sheet import build_flowables


def _entry(**overrides) -> AnswerKeyEntry:
    fields = {
        "question_id": "Q-1",
        "question_number": "1",
        "answer": "72",
        "marks": 1.0,
    }
    fields.update(overrides)
    return AnswerKeyEntry(**fields)


def _paper() -> Paper:
    from datetime import datetime

    return Paper(
        id="P-1",
        subject="Mathematics",
        class_standard="III",
        total_marks=1.0,
        duration_minutes=50,
        sections=[Section(name="A", marks=1.0)],
        source="existing_paper",
        created_at=datetime.now(),
    )


def _paragraph_texts(flowables) -> list[str]:
    return [f.text for f in flowables if isinstance(f, Paragraph)]


def _index_containing(texts: list[str], needle: str) -> int:
    return next(i for i, t in enumerate(texts) if needle in t)


def test_title_includes_subject_class_and_answer_key_label():
    key = AnswerKey(id="ANSKEY-1", paper_id="P-1", entries=[])

    title = build_flowables(_paper(), key)[0]

    assert isinstance(title, Paragraph)
    assert "Mathematics" in title.text
    assert "III" in title.text
    assert "Answer Key" in title.text


def test_entry_line_includes_number_answer_and_marks():
    key = AnswerKey(
        id="ANSKEY-1",
        paper_id="P-1",
        entries=[_entry(question_number="1", answer="72", marks=1.0)],
    )

    texts = _paragraph_texts(build_flowables(_paper(), key))

    assert any(t.startswith("1. 72") and "[1.0 marks]" in t for t in texts)


def test_working_line_appears_when_present():
    key = AnswerKey(
        id="ANSKEY-1",
        paper_id="P-1",
        entries=[_entry(working="47 + 25 = 72")],
    )

    texts = _paragraph_texts(build_flowables(_paper(), key))

    assert any("Working: 47 + 25 = 72" in t for t in texts)


def test_no_working_line_when_absent():
    key = AnswerKey(id="ANSKEY-1", paper_id="P-1", entries=[_entry()])

    texts = _paragraph_texts(build_flowables(_paper(), key))

    assert not any("Working:" in t for t in texts)


def test_entries_render_in_the_order_given():
    key = AnswerKey(
        id="ANSKEY-1",
        paper_id="P-1",
        entries=[
            _entry(question_number="10", answer="second"),
            _entry(question_number="2", answer="first"),
        ],
    )

    texts = _paragraph_texts(build_flowables(_paper(), key))

    assert _index_containing(texts, "10. second") < _index_containing(texts, "2. first")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_answer_sheet_template.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backend.rendering.templates.answer_sheet'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/backend/rendering/templates/answer_sheet.py
""""Answer Key" PDF template (spec §20: "Question number / Correct answer /
Expected working where relevant / Marks"). Pure function, no I/O — mirrors
simple_practice_paper.py's shape, swapping list[Question] for an
already-built AnswerKey (spec §20: the key is built from the structured
question model; this template never regenerates it)."""

from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Flowable, Paragraph

from app.backend.models.answer_key import AnswerKey, AnswerKeyEntry
from app.backend.models.paper import Paper

_STYLES = getSampleStyleSheet()
_TITLE_STYLE = ParagraphStyle("AnswerSheetTitle", parent=_STYLES["Title"])
_ENTRY_STYLE = ParagraphStyle(
    "AnswerEntry", parent=_STYLES["Normal"], spaceBefore=6, spaceAfter=2
)
_WORKING_STYLE = ParagraphStyle("Working", parent=_STYLES["Normal"], leftIndent=18)


def _entry_flowables(entry: AnswerKeyEntry) -> list[Flowable]:
    flowables: list[Flowable] = [
        Paragraph(
            f"{entry.question_number}. {entry.answer} <i>[{entry.marks} marks]</i>",
            _ENTRY_STYLE,
        )
    ]
    if entry.working:
        flowables.append(Paragraph(f"Working: {entry.working}", _WORKING_STYLE))
    return flowables


def build_flowables(paper: Paper, answer_key: AnswerKey) -> list[Flowable]:
    flowables: list[Flowable] = [
        Paragraph(
            f"{paper.subject} — Class {paper.class_standard} Answer Key", _TITLE_STYLE
        ),
    ]
    for entry in answer_key.entries:
        flowables.extend(_entry_flowables(entry))
    return flowables
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_answer_sheet_template.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add app/backend/rendering/templates/answer_sheet.py tests/unit/test_answer_sheet_template.py
git commit -m "add answer_sheet PDF template"
```

---

### Task 4: `render_answer_sheet` in `rendering/renderer.py`

**Files:**
- Modify: `app/backend/rendering/renderer.py`
- Test: `tests/unit/test_renderer.py` (append; existing Phase 9 tests must still pass unchanged)

**Interfaces:**
- Consumes: `AnswerKey` from `app.backend.models.answer_key`; `build_flowables` from `app.backend.rendering.templates.answer_sheet` (Task 3, imported as `build_answer_sheet_flowables` to avoid colliding with the existing `simple_practice_paper` import).
- Produces: `render_answer_sheet(paper: Paper, answer_key: AnswerKey, output_path: Path, page_size: str = "A4", build_flowables_fn: Callable[[Paper, AnswerKey], list[Flowable]] = build_answer_sheet_flowables) -> Path`. Same `ValueError`-on-bad-`page_size` and parent-directory-creation behavior as `render_question_paper`. Task 5 imports this directly: `from app.backend.rendering.renderer import render_answer_sheet`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_renderer.py`:

```python
# add to the existing import block at the top of tests/unit/test_renderer.py:
from app.backend.models.answer_key import AnswerKey, AnswerKeyEntry
from app.backend.rendering.renderer import render_answer_sheet, render_question_paper
```

```python
# append to the end of tests/unit/test_renderer.py
def _answer_key() -> AnswerKey:
    return AnswerKey(
        id="ANSKEY-1",
        paper_id="P-1",
        entries=[
            AnswerKeyEntry(question_id="Q-1", question_number="1", answer="72", marks=1.0)
        ],
    )


def test_renders_a_valid_answer_sheet_pdf(tmp_path: Path):
    output_path = tmp_path / "answer_sheet.pdf"

    result = render_answer_sheet(_paper(), _answer_key(), output_path)

    assert result == output_path
    content = output_path.read_bytes()
    assert content.startswith(b"%PDF-")
    assert b"%%EOF" in content[-64:]


def test_answer_sheet_creates_missing_parent_directories(tmp_path: Path):
    output_path = tmp_path / "nested" / "dir" / "answer_sheet.pdf"

    render_answer_sheet(_paper(), _answer_key(), output_path)

    assert output_path.exists()


def test_answer_sheet_unknown_page_size_raises():
    with pytest.raises(ValueError):
        render_answer_sheet(_paper(), _answer_key(), Path("unused.pdf"), page_size="A3")
```

Note: `render_question_paper`'s own import in `tests/unit/test_renderer.py` already exists — the import edit above adds `render_answer_sheet` to the same `from app.backend.rendering.renderer import ...` line rather than duplicating it.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_renderer.py -v`
Expected: FAIL — `ImportError: cannot import name 'render_answer_sheet'`

- [ ] **Step 3: Write minimal implementation**

Replace the full contents of `app/backend/rendering/renderer.py` (refactors the Phase 9 body into a shared `_write_pdf` helper so both render functions share one page-size/`SimpleDocTemplate`/`mkdir` implementation — behavior for `render_question_paper` is unchanged):

```python
# app/backend/rendering/renderer.py
"""ReportLab driver (ARCHITECTURE.md's rendering/ module: "PDF templates +
ReportLab renderer"). Deliberately thin — page-size lookup and
SimpleDocTemplate wiring only; all layout decisions live in the template
modules. Depends only on app.backend.models and reportlab, never
validation/providers/generation/answer_key (ARCHITECTURE.md's rendering
dependency rule) — "validated data in" (spec §22) and an already-built
AnswerKey (spec §20) are the caller's contract, not something this module
builds or re-checks."""

from collections.abc import Callable
from pathlib import Path

from reportlab.lib.pagesizes import A4, LETTER
from reportlab.platypus import Flowable, SimpleDocTemplate

from app.backend.models.answer_key import AnswerKey
from app.backend.models.paper import Paper
from app.backend.models.question import Question
from app.backend.rendering.templates.answer_sheet import (
    build_flowables as build_answer_sheet_flowables,
)
from app.backend.rendering.templates.simple_practice_paper import (
    build_flowables as build_question_paper_flowables,
)

_PAGE_SIZES = {"A4": A4, "LETTER": LETTER}


def _write_pdf(flowables: list[Flowable], output_path: Path, page_size: str) -> Path:
    if page_size not in _PAGE_SIZES:
        raise ValueError(f"unknown page_size: {page_size!r}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(output_path), pagesize=_PAGE_SIZES[page_size])
    doc.build(flowables)
    return output_path


def render_question_paper(
    paper: Paper,
    questions: list[Question],
    output_path: Path,
    page_size: str = "A4",
    build_flowables_fn: Callable[
        [Paper, list[Question]], list[Flowable]
    ] = build_question_paper_flowables,
) -> Path:
    return _write_pdf(build_flowables_fn(paper, questions), output_path, page_size)


def render_answer_sheet(
    paper: Paper,
    answer_key: AnswerKey,
    output_path: Path,
    page_size: str = "A4",
    build_flowables_fn: Callable[
        [Paper, AnswerKey], list[Flowable]
    ] = build_answer_sheet_flowables,
) -> Path:
    return _write_pdf(build_flowables_fn(paper, answer_key), output_path, page_size)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_renderer.py -v`
Expected: PASS (all tests, existing 4 from Phase 9 + 3 new — the existing 4 must pass unchanged, confirming the `_write_pdf` refactor didn't change `render_question_paper`'s behavior)

- [ ] **Step 5: Commit**

```bash
git add app/backend/rendering/renderer.py tests/unit/test_renderer.py
git commit -m "add render_answer_sheet, share PDF-writing logic via _write_pdf"
```

---

### Task 5: Integration test — 1:1 answer sheet from a validated paper

**Files:**
- Test: `tests/integration/test_render_answer_sheet.py`

**Interfaces:**
- Consumes: `build_answer_key` (Task 2), `render_answer_sheet` (Task 4), `validate_paper` (Phase 6, `app.backend.validation.validator`), the same realistic fixture shape used by Phase 9's `tests/integration/test_render_question_paper.py`.
- Produces: nothing consumed by later tasks — this is the phase's closing acceptance check (PROJECT_PLAN.md Phase 10 "Done when": "`answer_sheet.pdf` matches generated paper's questions 1:1").

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_render_answer_sheet.py
"""Closes PROJECT_PLAN.md's Phase 10 acceptance bar: "answer_sheet.pdf
matches generated paper's questions 1:1." Reuses the same realistic
4-question fixture Phase 9's rendering integration test used, validates it,
builds the answer key straight from the questions (spec §20: never
regenerated by an LLM), checks the 1:1 correspondence explicitly, then
renders and checks the output is a well-formed, non-trivial PDF."""

from pathlib import Path

from app.backend.answer_key.builder import build_answer_key
from app.backend.rendering.renderer import render_answer_sheet
from app.backend.validation.validator import validate_paper
from tests.integration.test_render_question_paper import _paper, _questions


def test_answer_key_matches_a_validated_papers_questions_1_to_1_and_renders(tmp_path: Path):
    questions = _questions()
    paper = _paper(total_marks=sum(q.marks for q in questions))
    assert validate_paper(paper, questions) == []

    answer_key = build_answer_key(paper, questions)

    assert len(answer_key.entries) == len(questions)
    for entry, question in zip(answer_key.entries, questions, strict=True):
        assert entry.question_id == question.id
        assert entry.question_number == question.question_number
        assert entry.answer == question.expected_answer
        assert entry.marks == question.marks

    output_path = render_answer_sheet(paper, answer_key, tmp_path / "answer_sheet.pdf")

    content = output_path.read_bytes()
    assert content.startswith(b"%PDF-")
    assert b"%%EOF" in content[-64:]
    assert len(content) > 500
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/integration/test_render_answer_sheet.py -v`
Expected: FAIL before Tasks 1-4 exist (`ModuleNotFoundError`); once Tasks 1-4 are done this test should already pass without further implementation, since it only composes existing functions.

- [ ] **Step 3: No implementation step — this task only adds a test**

Tasks 1-4 already provide every function this test calls.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/integration/test_render_answer_sheet.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_render_answer_sheet.py
git commit -m "add answer_sheet.pdf 1:1 correspondence integration test"
```

---

### Task 6: Manual verification — render and visually inspect a demo answer sheet

**Files:** None (manual step, no code changes)

Mirrors Phase 9's Task 4 — an automated test proves the PDF is well-formed, but only opening it proves the layout is readable.

- [ ] **Step 1: Render a demo PDF outside pytest**

```bash
.venv/Scripts/python.exe -c "
from pathlib import Path
import sys
sys.path.insert(0, '.')
from tests.integration.test_render_question_paper import _paper, _questions
from app.backend.answer_key.builder import build_answer_key
from app.backend.rendering.renderer import render_answer_sheet

questions = _questions()
paper = _paper(total_marks=sum(q.marks for q in questions))
answer_key = build_answer_key(paper, questions)
path = render_answer_sheet(paper, answer_key, Path('data/generated/PHASE10-DEMO/answer_sheet.pdf'))
print('wrote', path)
"
```

- [ ] **Step 2: Open and visually inspect the PDF**

Read `data/generated/PHASE10-DEMO/answer_sheet.pdf` (Read tool PDF support). Confirm: title shows "Mathematics — Class III Answer Key", all 4 entries appear numbered in order with their answers and marks, and no `Working:` lines appear (this fixture's questions have no working data, per Task 2's constraint).

- [ ] **Step 3: Record findings**

Fold the actual findings from Step 2 into Task 7's TODO.md edit. If a real layout issue is found, fix it in `answer_sheet.py`, rerun Task 5's integration test, and redo Steps 1-2 before recording findings.

---

### Task 7: Update TODO.md and ARCHITECTURE.md

**Files:**
- Modify: `TODO.md`
- Modify: `ARCHITECTURE.md`

**Interfaces:** None — documentation only.

- [ ] **Step 1: Run the full test suite and ruff as a pre-flight check**

Run: `.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m ruff check app/backend/models/answer_key.py app/backend/answer_key app/backend/rendering tests/unit/test_answer_key_model.py tests/unit/test_answer_key_builder.py tests/unit/test_answer_sheet_template.py tests/unit/test_renderer.py tests/integration/test_render_answer_sheet.py`
Expected: all tests pass; ruff reports no issues in the files this plan touched.

- [ ] **Step 2: Mark Phase 10 complete in TODO.md**

Replace the `## Phase 10 — Answer sheet generation` section:

```markdown
## Phase 10 — Answer sheet generation — **done 2026-08-19**

- [x] `app/backend/models/answer_key.py` — `AnswerKeyEntry`, `AnswerKey`
      (DATA_MODEL.md core entity, fields match the spec literally)
- [x] `app/backend/answer_key/builder.py` — `build_answer_key`: one
      `AnswerKeyEntry` per `Question` in the order given, copying
      `expected_answer`/`marks`/`question_number` straight from the
      structured question model (spec §20: never regenerated by an LLM).
      `working` stays `None` — no `Question` field holds it yet
- [x] `app/backend/rendering/templates/answer_sheet.py` — `build_flowables`:
      title + one numbered line per entry with its answer and marks,
      optional `Working:` line when `entry.working` is set
- [x] `app/backend/rendering/renderer.py` — `render_answer_sheet`,
      sharing a `_write_pdf` helper with `render_question_paper`
      (Phase 9) now that two callers need identical page-size/mkdir/
      `SimpleDocTemplate` logic
- [x] Integration test: a validated paper's answer key has exactly one
      entry per question, in order, with matching `question_id`/
      `question_number`/`answer`/`marks` — closes PROJECT_PLAN.md's
      Phase 10 acceptance bar ("answer_sheet.pdf matches generated
      paper's questions 1:1") — and renders to a well-formed PDF
- [x] Manual verification: rendered a demo PDF to
      `data/generated/PHASE10-DEMO/answer_sheet.pdf` and read it back
      with the Read tool's PDF support. Confirmed: title "Mathematics —
      Class III Answer Key" renders centered/bold with the em dash
      intact, all 4 entries appear numbered in order with their answers
      and marks in italic brackets, and no `Working:` lines appear
      (this fixture's questions carry no working data). No layout
      issues found, no fix needed.

Deliberately out of scope this phase (no caller exists yet to need it):
no `generate-answer-key` CLI command — same deferral Phase 8 recorded for
`generate-paper` and Phase 9 recorded for `render-paper`: there is still
no orchestrator assembling a full pipeline run into one storable `Paper` +
`list[Question]` for a CLI command to load from disk.

MVP (Phases 1-10) is now complete per PROJECT_PLAN.md's phase table.
Remaining work is Phase 11+ (basic UI, chapter ingestion, difficulty
controls, evaluation dashboard) plus the still-open orchestration gap
every phase from 6 onward has flagged: no `generate-paper` command wiring
extraction -> blueprint -> generation -> validation -> rendering into one
real, disk-backed run.
```

- [ ] **Step 3: Add `answer_key/` to ARCHITECTURE.md's module map**

In `ARCHITECTURE.md`'s `## Module map` code block, insert a new line between `blueprint/` and `knowledge/`:

```
    blueprint/     PaperBlueprint derivation (Workflow A) + blueprint-driven template selection
    answer_key/    AnswerKey builder — one entry per Question, from expected_answer (spec §20)
    knowledge/     Chapter knowledge extraction (Workflow B only)
```

- [ ] **Step 4: Commit**

```bash
git add TODO.md ARCHITECTURE.md
git commit -m "mark Phase 10 answer sheet generation complete"
```
