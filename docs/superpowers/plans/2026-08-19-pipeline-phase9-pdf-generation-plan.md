# Phase 9 — PDF Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render a validated `Paper` + `list[Question]` into `question_paper.pdf` — closing TODO.md's `rendering/templates/simple_practice_paper.py` and `rendering/renderer.py` bullets and PROJECT_PLAN.md's Phase 9 acceptance bar: "`question_paper.pdf` renders and opens." Answer-sheet rendering (`answer_sheet.pdf`, `models/answer_key.py`) is spec PHASE 10, a separate phase with its own acceptance bar ("`answer_sheet.pdf` matches generated paper's questions 1:1") — out of scope here.

**Architecture:** One new `rendering/` package: `rendering/templates/simple_practice_paper.py` builds a flat, deterministic list of ReportLab `Flowable`s (title, subject/class/marks/duration header, then every question numbered with its marks, multiple-choice options lettered `(a)`/`(b)`/...) from a `Paper` + `list[Question]` — pure function, no I/O. `rendering/renderer.py` is the thin ReportLab driver: pick a page size, build a `SimpleDocTemplate` at a caller-given path, hand it the template's flowables, write the file. Per ARCHITECTURE.md's rendering constraint ("`rendering` depends only on `models`... must never import from `providers`, `generation`, or anything upstream of validation"), neither file imports `validation/validator.py` — "validated data in" (spec §22) is the caller's contract to uphold before calling the renderer, exactly like `models` never importing from a pipeline module. Section-grouped rendering ("School exam style" template, spec §22's other three template names) is deferred: `Question` still has no `section` field (the same gap Phase 6 and Phase 8 both hit), so `simple_practice_paper` renders one flat numbered list rather than grouping by `Paper.sections`.

**Tech Stack:** `reportlab` (already a `pyproject.toml` dependency since Phase 1, confirmed importable: `reportlab==5.0.0`), specifically `reportlab.platypus` (`SimpleDocTemplate`, `Paragraph`, `Spacer`, `Flowable`), `reportlab.lib.styles`, `reportlab.lib.pagesizes` (`A4`, `LETTER`), `reportlab.lib.units.cm`. No new dependencies.

**Spec:** `Master Claude Code Prompt — AI Practice Paper Generator.md` §22 ("PDF GENERATION" — "PDF rendering should be deterministic... accept structured paper JSON and produce question_paper.pdf... never need to understand the original LLM output... only consume validated structured data") and PHASE 9 ("Implement PDF generation"), `ARCHITECTURE.md` (module map's `rendering/` entry and its dependency-direction paragraph), `PROJECT_PLAN.md` (Phase 9's "Done when" row: "`question_paper.pdf` renders and opens"), `TODO.md` (Phase 9-10 scaffold — this plan implements the Phase 9 half only), `app/backend/models/paper.py`, `app/backend/models/question.py`, `config.yaml`'s `pdf_page_size: A4`.

## Global Constraints

- Rendering is deterministic — no LLM call, same `Paper`+`list[Question]` input always produces the same visible content (PROJECT_PLAN.md's "What's deterministic vs. AI" list; spec §22 "PDF rendering should be deterministic").
- `rendering/` imports only from `app.backend.models` and `reportlab` — never `providers`, `generation`, or `validation` (ARCHITECTURE.md: "`rendering` depends only on `models`... it must never import from `providers`, `generation`, or anything upstream of validation"). The renderer trusts its caller already ran `validate_paper`/`validate_blueprint_compliance`; it does not re-validate.
- No CLI command this phase (no `render-paper`) — matches Phase 6/7/8's precedent of deferring CLI wiring until a real orchestrator exists to call it. There is still no `generate-paper` command assembling a full pipeline run into one storable `Paper`+`list[Question]`, so `render-paper` has nothing real to load from disk yet; TODO.md's Phase 9 completion notes will record this explicitly, same as Phase 8's did for `generate-paper`.
- `simple_practice_paper.build_flowables` renders questions as a flat numbered list in the order given — it does not sort by `question_number` (lexicographic sort would misorder "10" before "2") and does not group by `Paper.sections` (no `Question.section` field exists to group by). Ordering and grouping are the caller's responsibility.
- Every module boundary crosses with a Pydantic model, never a raw dict (DATA_MODEL.md line 3-4, spec §12, §35) — `build_flowables` and `render_question_paper` both take `Paper`/`Question` instances, never dicts.

---

### Task 1: `rendering/templates/simple_practice_paper.py` — flowable builder

**Files:**
- Create: `app/backend/rendering/__init__.py` (empty, package marker)
- Create: `app/backend/rendering/templates/__init__.py` (empty, package marker)
- Create: `app/backend/rendering/templates/simple_practice_paper.py`
- Test: `tests/unit/test_simple_practice_paper_template.py`

**Interfaces:**
- Consumes: `Paper` from `app.backend.models.paper`; `Question`, `QuestionType` from `app.backend.models.question`.
- Produces: `build_flowables(paper: Paper, questions: list[Question]) -> list[Flowable]`. Flowable index `[0]` is always the title `Paragraph`, index `[1]` is always the meta-line `Paragraph` (total marks/duration). Task 2 imports this directly: `from app.backend.rendering.templates.simple_practice_paper import build_flowables`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_simple_practice_paper_template.py
from datetime import datetime

from reportlab.platypus import Paragraph

from app.backend.models.paper import Paper, Section
from app.backend.models.question import DifficultyFeatures, Question, QuestionType
from app.backend.rendering.templates.simple_practice_paper import build_flowables


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
        "text": "47 + 25 = ?",
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


def _paper() -> Paper:
    return Paper(
        id="P-1",
        subject="Mathematics",
        class_standard="III",
        total_marks=2.0,
        duration_minutes=50,
        sections=[Section(name="A", marks=2.0)],
        source="existing_paper",
        created_at=datetime.now(),
    )


def _paragraph_texts(flowables) -> list[str]:
    return [f.text for f in flowables if isinstance(f, Paragraph)]


def test_title_includes_subject_and_class():
    flowables = build_flowables(_paper(), [])

    title = flowables[0]
    assert isinstance(title, Paragraph)
    assert "Mathematics" in title.text
    assert "III" in title.text


def test_meta_line_includes_total_marks_and_duration():
    flowables = build_flowables(_paper(), [])

    meta = flowables[1]
    assert isinstance(meta, Paragraph)
    assert "2.0" in meta.text
    assert "50" in meta.text


def test_question_number_text_and_marks_appear_together():
    question = _question(question_number="1", text="47 + 25 = ?", marks=1.0)

    texts = _paragraph_texts(build_flowables(_paper(), [question]))

    assert any(t.startswith("1. 47 + 25 = ?") and "[1.0 marks]" in t for t in texts)


def _index_containing(texts: list[str], needle: str) -> int:
    return next(i for i, t in enumerate(texts) if needle in t)


def test_multiple_choice_options_are_lettered_in_order():
    question = _question(
        question_number="1",
        type=QuestionType.MULTIPLE_CHOICE,
        text="Pick the right sum",
        options=["10", "20", "30"],
        expected_answer="20",
        answer_type="choice",
    )

    texts = _paragraph_texts(build_flowables(_paper(), [question]))

    assert any(t.startswith("(a)") and "10" in t for t in texts)
    assert any(t.startswith("(b)") and "20" in t for t in texts)
    assert any(t.startswith("(c)") and "30" in t for t in texts)


def test_non_multiple_choice_question_has_no_option_lines():
    question = _question(type=QuestionType.ARITHMETIC, text="47 + 25 = ?")

    texts = _paragraph_texts(build_flowables(_paper(), [question]))

    assert not any(t.startswith("(a)") for t in texts)


def test_questions_render_in_the_order_given_not_sorted():
    first = _question(question_number="10", text="Second in the list")
    second = _question(question_number="2", text="First in the list")

    texts = _paragraph_texts(build_flowables(_paper(), [first, second]))

    assert _index_containing(texts, "10. Second in the list") < _index_containing(
        texts, "2. First in the list"
    )
```

Note: `reportlab.platypus.Paragraph` runs `cleanBlockQuotedText` on its input
during construction, which collapses runs of whitespace to a single space —
so the template's f-strings use single spaces, not the double/triple spaces
that might look more readable in source, and this test compares by
substring (`_index_containing`) rather than an exact string match for
exactly that reason.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_simple_practice_paper_template.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backend.rendering'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/backend/rendering/__init__.py
```

```python
# app/backend/rendering/templates/__init__.py
```

```python
# app/backend/rendering/templates/simple_practice_paper.py
""""Simple practice paper" PDF template (spec §22's template list: "School
exam style / Simple practice paper / Worksheet / Mental Maths" — this is
the one MVP template). Pure function: Paper + list[Question] in, a flat
list of ReportLab Flowables out, no I/O, no randomness (spec §22: "PDF
rendering should be deterministic"). Renders questions in the order given,
not grouped by Paper.sections — Question has no section field to group by
(the same gap Phase 6's and Phase 8's TODO.md notes flagged)."""

from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Flowable, Paragraph, Spacer

from app.backend.models.paper import Paper
from app.backend.models.question import Question, QuestionType

_STYLES = getSampleStyleSheet()
_TITLE_STYLE = ParagraphStyle("PaperTitle", parent=_STYLES["Title"])
_META_STYLE = ParagraphStyle("PaperMeta", parent=_STYLES["Normal"], alignment=1)
_QUESTION_STYLE = ParagraphStyle(
    "Question", parent=_STYLES["Normal"], spaceBefore=10, spaceAfter=4
)
_OPTION_STYLE = ParagraphStyle("Option", parent=_STYLES["Normal"], leftIndent=18)
_OPTION_LABELS = "abcdefgh"


def _question_flowables(question: Question) -> list[Flowable]:
    flowables: list[Flowable] = [
        Paragraph(
            f"{question.question_number}. {question.text} <i>[{question.marks} marks]</i>",
            _QUESTION_STYLE,
        )
    ]
    if question.type == QuestionType.MULTIPLE_CHOICE and question.options:
        for label, option in zip(_OPTION_LABELS, question.options, strict=False):
            flowables.append(Paragraph(f"({label}) {option}", _OPTION_STYLE))
    return flowables


def build_flowables(paper: Paper, questions: list[Question]) -> list[Flowable]:
    flowables: list[Flowable] = [
        Paragraph(f"{paper.subject} — Class {paper.class_standard}", _TITLE_STYLE),
        Paragraph(
            f"Total Marks: {paper.total_marks} Duration: {paper.duration_minutes} minutes",
            _META_STYLE,
        ),
        Spacer(1, 0.5 * cm),
    ]
    for question in questions:
        flowables.extend(_question_flowables(question))
    return flowables
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_simple_practice_paper_template.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add app/backend/rendering/__init__.py app/backend/rendering/templates/__init__.py app/backend/rendering/templates/simple_practice_paper.py tests/unit/test_simple_practice_paper_template.py
git commit -m "add simple_practice_paper PDF template"
```

---

### Task 2: `rendering/renderer.py` — ReportLab driver

**Files:**
- Create: `app/backend/rendering/renderer.py`
- Test: `tests/unit/test_renderer.py`

**Interfaces:**
- Consumes: `Paper` from `app.backend.models.paper`; `Question` from `app.backend.models.question`; `build_flowables` from `app.backend.rendering.templates.simple_practice_paper` (Task 1).
- Produces: `render_question_paper(paper: Paper, questions: list[Question], output_path: Path, page_size: str = "A4", build_flowables_fn: Callable[[Paper, list[Question]], list] = build_flowables) -> Path`. Raises `ValueError` for an unrecognized `page_size`. Creates `output_path`'s parent directories if missing. Returns `output_path` on success. Task 3 imports this directly: `from app.backend.rendering.renderer import render_question_paper`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_renderer.py
from datetime import datetime
from pathlib import Path

import pytest

from app.backend.models.paper import Paper, Section
from app.backend.models.question import DifficultyFeatures, Question, QuestionType
from app.backend.rendering.renderer import render_question_paper


def _difficulty_features() -> DifficultyFeatures:
    return DifficultyFeatures(
        operation_count=1,
        requires_carrying=False,
        step_count=1,
        vocabulary_level="basic",
        reasoning_required=False,
    )


def _question() -> Question:
    return Question(
        id="Q-1",
        paper_id="P-1",
        question_number="1",
        type=QuestionType.ARITHMETIC,
        text="47 + 25 = ?",
        marks=1.0,
        topic="Addition",
        difficulty=1,
        difficulty_features=_difficulty_features(),
        expected_answer="72",
        answer_type="numeric",
        source="existing_paper",
    )


def _paper() -> Paper:
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


def test_renders_a_valid_pdf_file(tmp_path: Path):
    output_path = tmp_path / "question_paper.pdf"

    result = render_question_paper(_paper(), [_question()], output_path)

    assert result == output_path
    content = output_path.read_bytes()
    assert content.startswith(b"%PDF-")
    assert b"%%EOF" in content[-64:]


def test_creates_missing_parent_directories(tmp_path: Path):
    output_path = tmp_path / "nested" / "dir" / "question_paper.pdf"

    render_question_paper(_paper(), [_question()], output_path)

    assert output_path.exists()


def test_unknown_page_size_raises():
    with pytest.raises(ValueError):
        render_question_paper(_paper(), [_question()], Path("unused.pdf"), page_size="A3")


def test_letter_page_size_also_renders(tmp_path: Path):
    output_path = tmp_path / "letter.pdf"

    render_question_paper(_paper(), [_question()], output_path, page_size="LETTER")

    assert output_path.read_bytes().startswith(b"%PDF-")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_renderer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backend.rendering.renderer'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/backend/rendering/renderer.py
"""ReportLab driver (ARCHITECTURE.md's rendering/ module: "PDF templates +
ReportLab renderer"). Deliberately thin — page-size lookup and
SimpleDocTemplate wiring only; all layout decisions live in the template
module. Depends only on app.backend.models and reportlab, never
validation/providers/generation (ARCHITECTURE.md's rendering dependency
rule) — "validated data in" (spec §22) is the caller's contract, not
something this module re-checks."""

from collections.abc import Callable
from pathlib import Path

from reportlab.lib.pagesizes import A4, LETTER
from reportlab.platypus import Flowable, SimpleDocTemplate

from app.backend.models.paper import Paper
from app.backend.models.question import Question
from app.backend.rendering.templates.simple_practice_paper import build_flowables

_PAGE_SIZES = {"A4": A4, "LETTER": LETTER}


def render_question_paper(
    paper: Paper,
    questions: list[Question],
    output_path: Path,
    page_size: str = "A4",
    build_flowables_fn: Callable[[Paper, list[Question]], list[Flowable]] = build_flowables,
) -> Path:
    if page_size not in _PAGE_SIZES:
        raise ValueError(f"unknown page_size: {page_size!r}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(output_path), pagesize=_PAGE_SIZES[page_size])
    doc.build(build_flowables_fn(paper, questions))
    return output_path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_renderer.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add app/backend/rendering/renderer.py tests/unit/test_renderer.py
git commit -m "add ReportLab renderer for question_paper.pdf"
```

---

### Task 3: Integration test — realistic paper renders to a valid PDF

**Files:**
- Test: `tests/integration/test_render_question_paper.py`

**Interfaces:**
- Consumes: `render_question_paper` (Task 2), `validate_paper` (Phase 6, `app.backend.validation.validator`), `Paper`/`Section` (`models/paper.py`), `Question`/`DifficultyFeatures`/`QuestionType` (`models/question.py`).
- Produces: nothing consumed by later tasks — this is the phase's closing acceptance check (PROJECT_PLAN.md Phase 9 "Done when": "`question_paper.pdf` renders and opens"), demonstrating the intended caller pattern of validating before rendering.

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_render_question_paper.py
"""Closes PROJECT_PLAN.md's Phase 9 acceptance bar: "question_paper.pdf
renders and opens." Builds a realistic multi-type Class III paper (echoing
the golden paper's hand-transcribed content style from
tests/fixtures/expected/main/questions.json), validates it with Phase 6's
validate_paper the way a real caller must before rendering (spec §21: "Do
not generate the PDF" on a validation failure), then renders it and checks
the output is a well-formed, non-trivial PDF file."""

from datetime import datetime
from pathlib import Path

from app.backend.models.paper import Paper, Section
from app.backend.models.question import DifficultyFeatures, Question, QuestionType
from app.backend.rendering.renderer import render_question_paper
from app.backend.validation.validator import validate_paper


def _difficulty_features(**overrides) -> DifficultyFeatures:
    fields = {
        "operation_count": 1,
        "requires_carrying": False,
        "step_count": 1,
        "vocabulary_level": "basic",
        "reasoning_required": False,
    }
    fields.update(overrides)
    return DifficultyFeatures(**fields)


def _questions() -> list[Question]:
    return [
        Question(
            id="Q-1",
            paper_id="PAPER-1",
            question_number="1",
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
        ),
        Question(
            id="Q-2",
            paper_id="PAPER-1",
            question_number="2",
            type=QuestionType.FILL_BLANK,
            text="Write the predecessor and successor of 4759.",
            marks=1.0,
            topic="Predecessor and successor",
            difficulty=1,
            difficulty_features=_difficulty_features(),
            expected_answer="4758, 4760",
            answer_type="text",
            source="existing_paper",
        ),
        Question(
            id="Q-3",
            paper_id="PAPER-1",
            question_number="3",
            type=QuestionType.ROMAN_NUMERAL,
            text="Write the roman number for 27.",
            marks=0.5,
            topic="Roman numerals",
            difficulty=2,
            difficulty_features=_difficulty_features(),
            expected_answer="XXVII",
            answer_type="text",
            source="existing_paper",
        ),
        Question(
            id="Q-4",
            paper_id="PAPER-1",
            question_number="4",
            type=QuestionType.WORD_PROBLEM,
            text=(
                "The cost of two toys is Rs 47 and Rs 64. Find the exact total cost "
                "by adding the two amounts."
            ),
            marks=2.0,
            topic="Addition word problem",
            difficulty=3,
            difficulty_features=_difficulty_features(
                reasoning_required=True, vocabulary_level="standard"
            ),
            expected_answer="111",
            answer_type="numeric",
            source="existing_paper",
        ),
    ]


def _paper(total_marks: float) -> Paper:
    return Paper(
        id="PAPER-1",
        subject="Mathematics",
        class_standard="III",
        total_marks=total_marks,
        duration_minutes=50,
        sections=[Section(name="Practice", marks=total_marks, question_count=4)],
        source="existing_paper",
        created_at=datetime.now(),
    )


def test_a_realistic_validated_paper_renders_to_a_well_formed_pdf(tmp_path: Path):
    questions = _questions()
    paper = _paper(total_marks=sum(q.marks for q in questions))

    assert validate_paper(paper, questions) == []

    output_path = render_question_paper(paper, questions, tmp_path / "question_paper.pdf")

    content = output_path.read_bytes()
    assert content.startswith(b"%PDF-")
    assert b"%%EOF" in content[-64:]
    assert len(content) > 1000  # more than an empty/near-empty document
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/integration/test_render_question_paper.py -v`
Expected: FAIL before Tasks 1-2 exist (`ModuleNotFoundError`); once Tasks 1-2 are done this test should already pass without further implementation, since it only composes existing functions.

- [ ] **Step 3: No implementation step — this task only adds a test**

Tasks 1-2 already provide every function this test calls.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/integration/test_render_question_paper.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_render_question_paper.py
git commit -m "add question_paper.pdf rendering integration test"
```

---

### Task 4: Manual verification — render and visually inspect a demo PDF

**Files:** None (manual step, no code changes)

This mirrors Phase 3's "Golden paper verification findings": an automated test proves the PDF is *well-formed*, but only opening it proves the *layout* is actually readable. Since the executor can read PDF files directly (page images), do this instead of trusting bytes alone.

- [ ] **Step 1: Render a demo PDF outside pytest**

Run a one-off Python snippet (not saved as a file) that builds the same fixture Task 3 used and writes it to a real, inspectable path:

```bash
.venv/Scripts/python.exe -c "
from datetime import datetime
from pathlib import Path
import sys
sys.path.insert(0, '.')
from tests.integration.test_render_question_paper import _paper, _questions
from app.backend.rendering.renderer import render_question_paper

questions = _questions()
paper = _paper(total_marks=sum(q.marks for q in questions))
path = render_question_paper(paper, questions, Path('data/generated/PHASE9-DEMO/question_paper.pdf'))
print('wrote', path)
"
```

- [ ] **Step 2: Open and visually inspect the PDF**

Read `data/generated/PHASE9-DEMO/question_paper.pdf` (the Read tool supports PDF page images). Confirm: title shows "Mathematics — Class III", the meta line shows total marks and duration, all 4 questions appear numbered in order, and question 1's four multiple-choice options are lettered `(a)`-`(d)` and indented under the question.

- [ ] **Step 3: Record findings**

Add a short "Golden paper verification findings" note under Phase 9 in TODO.md (folded into Task 5's edit) describing what was visually confirmed, and any layout issues found. If a real issue is found (e.g., text overflowing the page, options not indented), fix it in `simple_practice_paper.py`, rerun Task 3's integration test to confirm nothing broke, and redo Steps 1-2 of this task before recording findings.

---

### Task 5: Update TODO.md

**Files:**
- Modify: `TODO.md`

**Interfaces:** None — documentation only.

- [ ] **Step 1: Run the full test suite and ruff as a pre-flight check**

Run: `.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m ruff check app/backend/rendering tests/unit/test_simple_practice_paper_template.py tests/unit/test_renderer.py tests/integration/test_render_question_paper.py`
Expected: all tests pass; ruff reports no issues in the files this plan touched (the repo has a handful of pre-existing line-length errors elsewhere, predating this phase — do not fix unrelated files as part of this task).

- [ ] **Step 2: Split TODO.md's `Phase 9-10` heading, mark Phase 9 done**

Replace the `## Phase 9-10 — PDF + answer sheet` section with two headings — Phase 9 done, Phase 10 still pending:

```markdown
## Phase 9 — PDF generation — **done 2026-08-19**

- [x] `app/backend/rendering/templates/simple_practice_paper.py` —
      `build_flowables`: title, subject/class/marks/duration header, then
      every question numbered with its marks in the order given (no
      section-grouping — `Question` still has no `section` field),
      multiple-choice options lettered `(a)`/`(b)`/...
- [x] `app/backend/rendering/renderer.py` — `render_question_paper`:
      picks a ReportLab page size (`A4`/`LETTER`), writes the PDF via
      `SimpleDocTemplate`. Depends only on `models` + `reportlab`, per
      ARCHITECTURE.md's rendering constraint — never imports
      `validation`/`providers`/`generation`; "validated data in" is the
      caller's contract, demonstrated by this phase's integration test
      calling `validate_paper` before rendering
- [x] Integration test: a realistic multi-question-type paper (echoing
      the golden paper's hand-transcribed fixture content) passes
      `validate_paper` and renders to a well-formed, non-trivial PDF —
      closes PROJECT_PLAN.md's Phase 9 acceptance bar
- [x] Manual verification: rendered a demo PDF to
      `data/generated/PHASE9-DEMO/question_paper.pdf` and read it back
      with the Read tool's PDF support. Confirmed: title "Mathematics —
      Class III" renders centered/bold with the em dash intact, the meta
      line shows total marks and duration, all 4 questions appear
      numbered in the given order with marks in italic brackets, and
      question 1's four multiple-choice options are lettered `(a)`-`(d)`
      and indented under it. No layout issues found, no fix needed.

Deliberately out of scope this phase (no caller exists yet to need them):
no `render-paper` CLI command — there is still no `generate-paper`
orchestrator assembling a full pipeline run into one storable `Paper` +
`list[Question]`, so a CLI command has nothing real to load from disk yet
(same deferral Phase 8 recorded for `generate-paper` itself). No
section-grouped "School exam style" template — deferred alongside the
`Question.section` field gap.

## Phase 10 — Answer sheet generation

- [ ] `app/backend/models/answer_key.py` + builder from `Paper`
- [ ] `answer_sheet.pdf` rendering
- [ ] CLI: `generate-answer-key`
```

- [ ] **Step 3: Commit**

```bash
git add TODO.md
git commit -m "mark Phase 9 PDF generation complete"
```
