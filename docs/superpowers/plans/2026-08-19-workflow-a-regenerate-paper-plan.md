# Workflow A 1:1 Regeneration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the mechanism Workflow A ("existing paper -> new paper") actually needs: replace each source question with a new one of the *same type* and the *same marks*, new values only — e.g. a 0.5-mark `375 + 125 = ?` becomes a 0.5-mark `436 + 234 = ?`. No section aggregation, no marks target to hit, no gap to balance.

**Why this replaces, not extends, the previous approach:** `generate_paper` (built two sessions ago) derives a `PaperBlueprint` — an *aggregate* of section names/marks/counts and one averaged difficulty — then asks `select_templates_for_blueprint` to pick templates that sum to those aggregate targets. That's the right mechanism for Workflow B (`chapter -> new paper`, spec's other entry point): there's no existing per-question structure to mirror, so you have to work from an aggregate spec the user configures. It is the *wrong* mechanism for Workflow A: an existing paper already has a marks value on every single question, so there is nothing to aggregate and re-target in the first place. Deriving a blueprint and re-selecting from a pool by matching an aggregate marks/difficulty target — which is what produced this session's "52.0 achieved vs 14.5 target" mismatch — was solving a problem this workflow doesn't have. `generate_paper`/`derive_blueprint_from_paper`/`select_templates_for_blueprint` are not deleted; they stay the right tool for Workflow B once it's built.

**Architecture:** Two small additions to files that already exist. `generation/question_generator.py` gains `regenerate_question(source_question, paper_id, rng, text_provider=None, templates=None)`: pick any registered template whose `question_type` matches the source question's `type` (marks/difficulty are irrelevant to this choice — "irrespective of complexity" per the user's own framing), call the existing `generate_question` to get fresh sampled values and a correctly-computed answer, then override the result's `marks` to the *source* question's marks so weightage never changes. `generation/paper_generator.py` gains `regenerate_paper(source_paper, source_questions, rng=None, text_provider=None)`: map `regenerate_question` over every source question 1:1 (same `question_number`, same `marks`), and build the new `Paper` by copying `source_paper`'s `sections` verbatim — since every question's marks matches its source counterpart exactly, the totals always already agree; there is no aggregation step left to introduce a mismatch.

**Tech Stack:** No new dependencies. Reuses `questions/template_registry.get_templates(question_type)` (already supports filtering by type), `generation/question_generator.generate_question`, `core/ids.new_id`.

**Spec:** `PIPELINE.md` ("Workflow A: existing paper -> new paper" — the extraction side already produces one `Question` per original question, each with its own real `marks`), `Master Claude Code Prompt` §14 (question generation: answer always computed by code, unchanged — this plan reuses `generate_question`, which already guarantees that), this session's conversation (`375+125 = ?` at 0.5 marks -> `436+234 = ?` at 0.5 marks — the literal spec for this task, given directly by the user after `generate_paper`'s aggregate-marks mismatch was traced to the wrong mechanism being used for Workflow A).

## Global Constraints

- `regenerate_question` never changes a question's `marks` from what the *source* question declared — the whole point of this plan. The template's own `marks` field is only ever used to build the intermediate `Question` via `generate_question`; it is always overridden before returning.
- Template selection here is by `question_type` only — no difficulty filtering, no marks filtering. The user's own framing: "let the weightage remain same irrespective of complexity."
- `regenerate_paper` never derives a `PaperBlueprint` and never calls `select_templates_for_blueprint` — those exist for Workflow B, not this path.
- Random choices go through the caller-supplied `random.Random`, never module-level `random.*` functions (established convention, unchanged).
- Every module boundary crosses with a Pydantic model, never a raw dict (DATA_MODEL.md line 3-4, spec §12, §35).

---

### Task 1: `regenerate_question`

**Files:**
- Modify: `app/backend/generation/question_generator.py`
- Test: `tests/unit/test_question_generator.py` (append)

**Interfaces:**
- Consumes: `Question`, `QuestionType` (already imported in this file); `QuestionTemplate` (already imported); `get_templates` from `app.backend.questions.template_registry` (new import — `generate_question`/this file didn't need the registry before, since template *choice* was always Phase 8's job until now).
- Produces: `regenerate_question(source_question: Question, paper_id: str, rng: random.Random, text_provider: TextGenerationProvider | None = None, templates: list[QuestionTemplate] | None = None) -> Question`. Raises `ValueError` when no template matches `source_question.type`. Task 2 imports this directly: `from app.backend.generation.question_generator import regenerate_question`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_question_generator.py` (its existing imports already include `random`, `generate_question`, `QuestionType`, `get_templates` — add `regenerate_question` to the existing `from app.backend.generation.question_generator import generate_question` line):

```python
# change the existing import line in tests/unit/test_question_generator.py to:
from app.backend.generation.question_generator import generate_question, regenerate_question
```

```python
# append to the end of tests/unit/test_question_generator.py
from datetime import datetime

from app.backend.models.paper import Paper, Section
from app.backend.models.question import DifficultyFeatures
from app.backend.models.question_template import QuestionTemplate


def _difficulty_features() -> DifficultyFeatures:
    return DifficultyFeatures(
        operation_count=1,
        requires_carrying=False,
        step_count=1,
        vocabulary_level="basic",
        reasoning_required=False,
    )


def _source_question(**overrides) -> "Question":
    from app.backend.models.question import Question

    fields = {
        "id": "Q-SOURCE",
        "paper_id": "PAPER-SOURCE",
        "question_number": "1",
        "type": QuestionType.ARITHMETIC,
        "text": "375 + 125 = ?",
        "marks": 0.5,
        "topic": "Addition",
        "difficulty": 3,
        "difficulty_features": _difficulty_features(),
        "expected_answer": "500",
        "answer_type": "numeric",
        "source": "existing_paper",
    }
    fields.update(overrides)
    return Question(**fields)


def test_regenerated_question_keeps_the_sources_number_and_marks():
    source = _source_question(question_number="1", marks=0.5)

    regenerated = regenerate_question(source, paper_id="PAPER-NEW", rng=random.Random(1))

    assert regenerated.question_number == "1"
    assert regenerated.marks == 0.5


def test_regenerated_question_matches_the_sources_type():
    source = _source_question(type=QuestionType.ROMAN_NUMERAL, text="Write the roman number for 27.")

    regenerated = regenerate_question(source, paper_id="PAPER-NEW", rng=random.Random(1))

    assert regenerated.type == QuestionType.ROMAN_NUMERAL


def test_regenerated_question_marks_override_the_templates_own_marks():
    # TPL-ARITHMETIC-ADD declares marks=1.0; the source question's marks
    # (0.5) must win, matching the "375+125=? at 0.5 marks -> new values,
    # still 0.5 marks" example this plan is named after.
    source = _source_question(type=QuestionType.ARITHMETIC, marks=0.5)

    regenerated = regenerate_question(source, paper_id="PAPER-NEW", rng=random.Random(1))

    assert regenerated.marks == 0.5


def test_regenerated_question_belongs_to_the_new_paper_id():
    source = _source_question()

    regenerated = regenerate_question(source, paper_id="PAPER-NEW", rng=random.Random(1))

    assert regenerated.paper_id == "PAPER-NEW"
    assert regenerated.source == "generated"


def test_raises_when_no_template_matches_the_sources_type():
    source = _source_question(type=QuestionType.ARITHMETIC)

    with pytest.raises(ValueError):
        regenerate_question(source, paper_id="PAPER-NEW", rng=random.Random(1), templates=[])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_question_generator.py -v`
Expected: FAIL — `ImportError: cannot import name 'regenerate_question'`

- [ ] **Step 3: Write minimal implementation**

Add to `app/backend/generation/question_generator.py`, after the existing imports (add `get_templates`) and after `generate_question`:

```python
# add to the existing import block:
from app.backend.questions.template_registry import get_templates
```

```python
# append to the end of app/backend/generation/question_generator.py
def regenerate_question(
    source_question: Question,
    paper_id: str,
    rng: random.Random,
    text_provider: TextGenerationProvider | None = None,
    templates: list[QuestionTemplate] | None = None,
) -> Question:
    pool = templates if templates is not None else get_templates(source_question.type)
    if not pool:
        raise ValueError(f"no template registered for question type {source_question.type}")
    template = rng.choice(pool)

    question = generate_question(
        template,
        paper_id=paper_id,
        question_number=source_question.question_number,
        rng=rng,
        text_provider=text_provider,
    )
    return question.model_copy(update={"marks": source_question.marks})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_question_generator.py -v`
Expected: PASS (all tests, existing + 5 new)

- [ ] **Step 5: Commit**

```bash
git add app/backend/generation/question_generator.py tests/unit/test_question_generator.py
git commit -m "add regenerate_question for 1:1 Workflow A replacement"
```

---

### Task 2: `regenerate_paper`

**Files:**
- Modify: `app/backend/generation/paper_generator.py`
- Test: `tests/unit/test_paper_generator.py` (append)

**Interfaces:**
- Consumes: `regenerate_question` (Task 1); `Paper`, `Section` (already imported); `Question` (already imported); `new_id` (already imported).
- Produces: `regenerate_paper(source_paper: Paper, source_questions: list[Question], rng: random.Random | None = None, text_provider: TextGenerationProvider | None = None) -> tuple[Paper, list[Question]]`. Raises `ValueError` when `source_questions` is empty. Task 3 imports this directly: `from app.backend.generation.paper_generator import regenerate_paper`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_paper_generator.py` (add `regenerate_paper` to the existing `from app.backend.generation.paper_generator import generate_paper` line):

```python
# change the existing import line in tests/unit/test_paper_generator.py to:
from app.backend.generation.paper_generator import generate_paper, regenerate_paper
```

```python
# append to the end of tests/unit/test_paper_generator.py
def test_regenerated_paper_preserves_total_marks_and_sections_from_source():
    # _source_question's fixture builder always uses marks=1.0; build these
    # directly since this test needs specific, differing marks values.
    source_questions = [
        Question(
            id="Q-1",
            paper_id="PAPER-SOURCE",
            question_number="1",
            type=QuestionType.ARITHMETIC,
            text="375 + 125 = ?",
            marks=0.5,
            topic="Addition",
            difficulty=3,
            difficulty_features=_difficulty_features(),
            expected_answer="500",
            answer_type="numeric",
            source="existing_paper",
        ),
        Question(
            id="Q-2",
            paper_id="PAPER-SOURCE",
            question_number="2",
            type=QuestionType.ROMAN_NUMERAL,
            text="Write the roman number for 27.",
            marks=1.5,
            topic="Roman numerals",
            difficulty=2,
            difficulty_features=_difficulty_features(),
            expected_answer="XXVII",
            answer_type="text",
            source="existing_paper",
        ),
    ]
    source_paper = _source_paper(
        [Section(name="Practice", marks=2.0, question_count=2)], total_marks=2.0
    )

    generated_paper, generated_questions = regenerate_paper(
        source_paper, source_questions, rng=random.Random(1)
    )

    assert generated_paper.total_marks == 2.0
    assert generated_paper.sections[0].marks == 2.0
    assert generated_paper.sections[0].question_count == 2
    assert generated_paper.source == "generated"
    assert generated_paper.source_paper_id == source_paper.id


def test_each_regenerated_question_keeps_its_sources_number_and_marks():
    source_questions = [
        Question(
            id="Q-1",
            paper_id="PAPER-SOURCE",
            question_number="1",
            type=QuestionType.ARITHMETIC,
            text="375 + 125 = ?",
            marks=0.5,
            topic="Addition",
            difficulty=3,
            difficulty_features=_difficulty_features(),
            expected_answer="500",
            answer_type="numeric",
            source="existing_paper",
        ),
    ]
    source_paper = _source_paper([Section(name="A", marks=0.5, question_count=1)], total_marks=0.5)

    generated_paper, generated_questions = regenerate_paper(
        source_paper, source_questions, rng=random.Random(2)
    )

    assert generated_questions[0].question_number == "1"
    assert generated_questions[0].marks == 0.5
    assert generated_questions[0].type == QuestionType.ARITHMETIC
    assert generated_questions[0].text != "375 + 125 = ?"  # new values, not a copy


def test_regenerate_paper_raises_when_source_has_no_questions():
    source_paper = _source_paper([Section(name="A", marks=1.0)], total_marks=1.0)

    with pytest.raises(ValueError):
        regenerate_paper(source_paper, [], rng=random.Random(1))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_paper_generator.py -v`
Expected: FAIL — `ImportError: cannot import name 'regenerate_paper'`

- [ ] **Step 3: Write minimal implementation**

Append to `app/backend/generation/paper_generator.py` (add `regenerate_question` to the existing import from `question_generator`):

```python
# change the existing import line in app/backend/generation/paper_generator.py to:
from app.backend.generation.question_generator import generate_question, regenerate_question
```

```python
# append to the end of app/backend/generation/paper_generator.py
def regenerate_paper(
    source_paper: Paper,
    source_questions: list[Question],
    rng: random.Random | None = None,
    text_provider: TextGenerationProvider | None = None,
) -> tuple[Paper, list[Question]]:
    if not source_questions:
        raise ValueError("cannot regenerate a paper with no questions")
    rng = rng or random.Random()
    generated_paper_id = new_id("PAPER")

    generated_questions = [
        regenerate_question(question, generated_paper_id, rng, text_provider=text_provider)
        for question in source_questions
    ]

    generated_paper = Paper(
        id=generated_paper_id,
        subject=source_paper.subject,
        class_standard=source_paper.class_standard,
        total_marks=sum(question.marks for question in generated_questions),
        duration_minutes=source_paper.duration_minutes,
        sections=[
            Section(name=s.name, marks=s.marks, question_count=s.question_count)
            for s in source_paper.sections
        ],
        source="generated",
        source_paper_id=source_paper.id,
        created_at=datetime.now(),
    )
    return generated_paper, generated_questions
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_paper_generator.py -v`
Expected: PASS (all tests, existing + 3 new)

- [ ] **Step 5: Commit**

```bash
git add app/backend/generation/paper_generator.py tests/unit/test_paper_generator.py
git commit -m "add regenerate_paper for Workflow A 1:1 replacement"
```

---

### Task 3: Integration test + real-data re-verification

**Files:**
- Test: `tests/integration/test_regenerate_paper.py`

**Interfaces:**
- Consumes: `regenerate_paper` (Task 2), `validate_paper` (Phase 6), `assemble_paper_from_extracted` (extraction-gap-closing session).
- Produces: nothing consumed elsewhere — this is the closing proof, using the literal `375 + 125 = ?` / `0.5 marks` example from the conversation that specified this plan.

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_regenerate_paper.py
"""Closes the actual Workflow A requirement, given directly by the user
after generate_paper's aggregate-marks mismatch was traced to the wrong
mechanism: "replace the existing question with different values and let
the weightage remain same irrespective of complexity... 375+125=? with 0.5
weightage becomes 436+234=? of 0.5 weightage." No blueprint, no aggregate
marks target, no gap to balance — regenerate_paper preserves per-question
marks by construction."""

import random
from datetime import datetime

from app.backend.generation.paper_generator import regenerate_paper
from app.backend.models.paper import Paper, Section
from app.backend.models.question import DifficultyFeatures, Question, QuestionType
from app.backend.validation.validator import validate_paper


def _difficulty_features() -> DifficultyFeatures:
    return DifficultyFeatures(
        operation_count=1,
        requires_carrying=False,
        step_count=1,
        vocabulary_level="basic",
        reasoning_required=False,
    )


def test_the_375_plus_125_example_from_the_conversation():
    source_question = Question(
        id="Q-1",
        paper_id="PAPER-SOURCE",
        question_number="1",
        type=QuestionType.ARITHMETIC,
        text="375 + 125 = ?",
        marks=0.5,
        topic="Addition",
        difficulty=3,
        difficulty_features=_difficulty_features(),
        expected_answer="500",
        answer_type="numeric",
        source="existing_paper",
    )
    source_paper = Paper(
        id="PAPER-SOURCE",
        subject="Mathematics",
        class_standard="III",
        total_marks=0.5,
        duration_minutes=50,
        sections=[Section(name="Arithmetic", marks=0.5, question_count=1)],
        source="existing_paper",
        created_at=datetime.now(),
    )

    generated_paper, generated_questions = regenerate_paper(
        source_paper, [source_question], rng=random.Random(5)
    )

    regenerated = generated_questions[0]
    assert regenerated.type == QuestionType.ARITHMETIC
    assert regenerated.marks == 0.5  # weightage unchanged
    assert regenerated.text != "375 + 125 = ?"  # different values
    assert generated_paper.total_marks == 0.5
    assert validate_paper(generated_paper, generated_questions) == []


def test_realistic_multi_type_paper_regenerates_1_to_1():
    questions = [
        Question(
            id="Q-1", paper_id="PAPER-SOURCE", question_number="1a",
            type=QuestionType.MULTIPLE_CHOICE,
            text="___ + 305 = 800. What is the missing number?",
            options=["405", "450", "500", "495"], marks=0.5, topic="Addition",
            difficulty=2, difficulty_features=_difficulty_features(),
            expected_answer="495", answer_type="choice", source="existing_paper",
        ),
        Question(
            id="Q-2", paper_id="PAPER-SOURCE", question_number="2a",
            type=QuestionType.PREDECESSOR_SUCCESSOR,
            text="Write the predecessor and successor of 4759.",
            marks=1.0, topic="Predecessor and successor", difficulty=1,
            difficulty_features=_difficulty_features(), expected_answer="4758, 4760",
            answer_type="numeric", source="existing_paper",
        ),
        Question(
            id="Q-3", paper_id="PAPER-SOURCE", question_number="6c",
            type=QuestionType.ROMAN_NUMERAL, text="Which is the greatest roman number?",
            marks=0.5, topic="Roman Numerals", difficulty=3,
            difficulty_features=_difficulty_features(), expected_answer="XXVII",
            answer_type="text", source="existing_paper",
        ),
    ]
    source_paper = Paper(
        id="PAPER-SOURCE",
        subject="Mathematics",
        class_standard="III",
        total_marks=2.0,
        duration_minutes=20,
        sections=[Section(name="All Questions", marks=2.0, question_count=3)],
        source="existing_paper",
        created_at=datetime.now(),
    )

    generated_paper, generated_questions = regenerate_paper(
        source_paper, questions, rng=random.Random(9)
    )

    assert [q.question_number for q in generated_questions] == ["1a", "2a", "6c"]
    assert [q.marks for q in generated_questions] == [0.5, 1.0, 0.5]
    assert [q.type for q in generated_questions] == [
        QuestionType.MULTIPLE_CHOICE,
        QuestionType.PREDECESSOR_SUCCESSOR,
        QuestionType.ROMAN_NUMERAL,
    ]
    assert generated_paper.total_marks == 2.0
    assert validate_paper(generated_paper, generated_questions) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/integration/test_regenerate_paper.py -v`
Expected: FAIL before Tasks 1-2 exist (`ImportError`); once Tasks 1-2 are done this test should already pass without further implementation.

- [ ] **Step 3: No implementation step — this task only adds a test**

Tasks 1-2 already provide everything this test calls.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/integration/test_regenerate_paper.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Re-verify against the real golden-paper data from earlier this session**

Run (reuses the same run this session already ingested/cleaned/extracted; re-run `ingest-paper`/`clean-paper`/`extract-questions` against `tests/fixtures/existing_paper/mental_maths/page_1.jpg` first if `data/processed/RUN-01M0D0SBSJ2JSCB9S0DNNR50EM` no longer exists):

```bash
.venv/Scripts/python.exe -c "
import json, random
from app.backend.questions.extraction import ExtractedSubQuestion
from app.backend.questions.paper_assembly import assemble_paper_from_extracted
from app.backend.generation.paper_generator import regenerate_paper
from app.backend.validation.validator import validate_paper

data = json.loads(open('data/processed/RUN-01M0D0SBSJ2JSCB9S0DNNR50EM/09_questions.json').read())
extracted = [ExtractedSubQuestion(**q) for q in data['questions']]

paper, questions = assemble_paper_from_extracted(
    subject='Mathematics', class_standard='III', duration_minutes=20,
    extracted_questions=extracted,
)
generated_paper, generated_questions = regenerate_paper(paper, questions, rng=random.Random(1))
print(f'regenerate_paper SUCCEEDED: {len(generated_questions)} questions, '
      f'total_marks={generated_paper.total_marks} (source paper had {paper.total_marks})')
print('validate_paper issues:', validate_paper(generated_paper, generated_questions))
for source, regenerated in zip(questions, generated_questions, strict=True):
    assert source.marks == regenerated.marks
    assert source.type == regenerated.type
print('every regenerated question matches its source type and marks exactly')
"
```

Expected: `total_marks` for the generated paper exactly equals the source paper's `14.5` (not `52.0` — this is the real proof the mismatch is gone, not just relocated), `validate_paper` issues is `[]`, and the final assert loop prints its success line without raising.

- [ ] **Step 6: Commit**

```bash
git add tests/integration/test_regenerate_paper.py
git commit -m "add regenerate_paper integration test with the 375+125 example"
```

---

### Task 4: Update TODO.md

**Files:**
- Modify: `TODO.md`

**Interfaces:** None — documentation only.

- [ ] **Step 1: Run the full test suite and ruff as a pre-flight check**

Run: `.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m ruff check app/backend/generation/question_generator.py app/backend/generation/paper_generator.py tests/unit/test_question_generator.py tests/unit/test_paper_generator.py tests/integration/test_regenerate_paper.py`
Expected: all tests pass; ruff reports no issues in the files this plan touched.

- [ ] **Step 2: Record the correction, right after the gap-balancing section**

Insert a new section in `TODO.md` immediately after the `Template selection: best-effort gap-balancing` section (before `## Phase 11+`):

```markdown
## Workflow A: 1:1 question regeneration — **done 2026-08-19**

Corrects the actual requirement, given directly after the gap-balancing fix
above: Workflow A ("existing paper -> new paper") should replace each
source question with a same-type, same-marks question using new values —
not derive an aggregate blueprint and re-select templates against an
aggregate target, which is what `generate_paper` does and is the *wrong*
mechanism here (that aggregate approach produced the 52.0-vs-14.5 mismatch
the gap-balancing fix papered over rather than actually solving).
`generate_paper`/`derive_blueprint_from_paper`/`select_templates_for_blueprint`
are unchanged and stay the right tool for Workflow B (`chapter -> new
paper`), where there's no existing per-question structure to mirror.

- [x] `app/backend/generation/question_generator.py` — `regenerate_question`:
      picks any template matching the source question's `type` (no
      difficulty/marks filtering — "irrespective of complexity"), calls
      the existing `generate_question` for fresh values, then overrides
      the result's `marks` to the *source* question's marks
- [x] `app/backend/generation/paper_generator.py` — `regenerate_paper`:
      maps `regenerate_question` 1:1 over every source question (same
      `question_number`, same `marks`) and copies `source_paper.sections`
      verbatim — since every question's marks matches its source
      counterpart by construction, there is no aggregation step left to
      introduce a marks mismatch
- [x] Integration test: the literal `375 + 125 = ?` (0.5 marks) example
      from the conversation, plus a realistic 3-question multi-type paper
- [x] Re-ran the real `mental_maths` extraction (the same 26 real
      questions, 14.5 marks, that broke `generate_paper`) through
      `regenerate_paper`: achieved `total_marks` now equals the source's
      `14.5` exactly (not `52.0`) — the mismatch is actually gone, not
      relocated to a validation warning
```

- [ ] **Step 3: Commit**

```bash
git add TODO.md
git commit -m "record Workflow A 1:1 regeneration, correcting the aggregate-blueprint approach"
```
