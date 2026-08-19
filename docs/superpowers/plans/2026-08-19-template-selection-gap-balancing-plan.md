# Template Selection Gap-Balancing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `select_templates_for_section`'s "exact match or raise" behavior with best-effort gap-minimization, so `generate_paper` no longer hard-fails on real extracted papers whose marks don't divide evenly onto a single seed template's marks (found while testing the application against the real golden `mental_maths` scan: `no template in section 'All Questions' has marks=0.5576923076923077 needed to fill 26 questions summing to 14.5`).

**Architecture:** Two small changes, both in code already built this session. `blueprint/template_selection.py`'s `select_templates_for_section` keeps its existing exact-match fast path (unchanged behavior/tests when an exact match exists) but replaces both "raise" branches with best-effort fallbacks: the `question_count` branch greedily picks, for each remaining slot, whichever pool template's marks is closest to the ideal per-slot share of what's left to fill; the marks-only branch keeps filling from affordable templates until nothing more fits, then stops instead of raising. `generation/paper_generator.py`'s `generate_paper` stops copying the blueprint's *aspirational* `total_marks`/section marks into the generated `Paper` and instead computes them from the *actually generated* questions — so the generated paper always accurately describes its own real content, and any residual gap against the blueprint's original target shows up where it belongs: as a `validate_blueprint_compliance` finding, not a crash.

**Tech Stack:** No new dependencies. Same `random.Random` convention as every other generation/blueprint module.

**Spec:** `PROJECT_PLAN.md` ("What's deterministic vs. AI" — this stays deterministic, no model call), `TODO.md` (Phase 8's `select_templates_for_section` entry — this plan supersedes its "no packing solver" note), this session's own finding: running `ingest-paper` → `clean-paper` → `extract-questions` against `tests/fixtures/existing_paper/mental_maths/page_1.jpg` (a real scan, real Claude OCR/classification calls) produced 26 real questions totaling 14.5 marks, none of which `generate_paper` could turn into a generated paper before this fix.

## Global Constraints

- The exact-match path is unchanged and stays the first thing tried — best-effort fallback only engages when no template's marks equal the exact target. Every existing test that relied on an exact match succeeding continues to pass unmodified.
- Best-effort selection never raises for "couldn't hit the target exactly" — it only raises when the eligible template pool is empty after `allowed_types`/`difficulty_range` filtering (unchanged; that's a different failure — no template can serve this section *at all*, not "couldn't balance the marks").
- `generate_paper`'s output `Paper.total_marks` and every `Section.marks`/`question_count` always equal the sum/count of the `Question`s actually returned alongside it — `validate_paper(generated_paper, generated_questions)` must never report `marks_mismatch` purely because best-effort selection under- or over-shot a target.
- Random choices go through the caller-supplied `random.Random`, never module-level `random.*` functions (established convention, unchanged).

---

### Task 1: Best-effort gap-minimizing `select_templates_for_section`

**Files:**
- Modify: `app/backend/blueprint/template_selection.py`
- Modify: `tests/unit/test_template_selection.py`

**Interfaces:**
- `select_templates_for_section`'s signature and its exact-match behavior are unchanged. New behavior only: when `question_count` is set and no template's marks equal `section.marks / section.question_count` exactly, it now returns a `question_count`-length list picked to minimize the gap against `section.marks`, instead of raising. When `question_count` is `None` and the remaining marks can't be exactly filled, it now returns whatever it filled so far, instead of raising.

- [ ] **Step 1: Update the two tests whose old assertions describe the raising behavior this task removes**

Replace these two tests in `tests/unit/test_template_selection.py`:

```python
# replaces test_question_count_driven_selection_raises_when_no_template_matches_per_question_marks
def test_question_count_driven_selection_falls_back_to_the_closest_available_marks():
    pool = [_template(id="TPL-1", marks=1.0)]
    section = BlueprintSection(name="Arithmetic", marks=3.0, question_count=2)  # 1.5 each, no exact match

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

    # slot 1 ideal=2.5 -> closest is 3.0 (gap 0.5); slot 2 ideal=(5.0-3.0)/1=2.0 -> closest is 1.5 (gap 0.5)
    assert [t.id for t in selected] == ["TPL-BIG", "TPL-MED"]
    assert sum(t.marks for t in selected) == 4.5
```

```python
# replaces test_marks_only_selection_raises_when_remaining_marks_cannot_be_afforded
def test_marks_only_selection_stops_when_nothing_more_is_affordable():
    pool = [_template(id="TPL-1", marks=2.0)]
    section = BlueprintSection(name="X", marks=1.0)  # smallest template costs more than the whole section

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
```

- [ ] **Step 2: Run the updated tests to confirm they fail against the current (raising) implementation**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_template_selection.py -v`
Expected: FAIL — the four new/changed tests fail (`Failed: DID NOT RAISE <class 'ValueError'>` for the ones that used to raise, since the old code still raises); the untouched exact-match tests still pass.

- [ ] **Step 3: Implement best-effort selection**

Replace `app/backend/blueprint/template_selection.py` in full:

```python
# app/backend/blueprint/template_selection.py
"""Blueprint-driven template selection (PIPELINE.md's shared tail: "Template
selection — pick QuestionTemplates matching blueprint's topics/types/
difficulty_range"), the exact step Phase 7's question_generator.py deferred
to this phase. Tries an exact marks match first (deterministic, no solver);
when a section's target marks don't divide evenly onto any single seed
template's marks — the normal case for a real extracted paper's actual
mixed marks, not just hand-built test fixtures — falls back to a greedy
gap-minimizing choice instead of failing outright, so generate_paper always
produces *something* and lets validate_blueprint_compliance report any
residual gap precisely rather than crashing generation over it."""

import random

from app.backend.models.blueprint import BlueprintSection, PaperBlueprint
from app.backend.models.question_template import QuestionTemplate
from app.backend.questions.template_registry import get_templates


def _fill_by_count(
    pool: list[QuestionTemplate], section: BlueprintSection, rng: random.Random
) -> list[QuestionTemplate]:
    if section.question_count == 0:
        return []

    per_question_marks = section.marks / section.question_count
    matching = [t for t in pool if abs(t.marks - per_question_marks) < 1e-9]
    if matching:
        return [rng.choice(matching) for _ in range(section.question_count)]

    selected: list[QuestionTemplate] = []
    running_total = 0.0
    for slot in range(section.question_count):
        remaining_slots = section.question_count - slot
        ideal_remaining_per_slot = (section.marks - running_total) / remaining_slots
        best_gap = min(abs(t.marks - ideal_remaining_per_slot) for t in pool)
        closest = [
            t for t in pool if abs(abs(t.marks - ideal_remaining_per_slot) - best_gap) < 1e-9
        ]
        template = rng.choice(closest)
        selected.append(template)
        running_total += template.marks
    return selected


def _fill_by_marks(
    pool: list[QuestionTemplate], section: BlueprintSection, rng: random.Random
) -> list[QuestionTemplate]:
    selected: list[QuestionTemplate] = []
    remaining = section.marks
    while remaining > 1e-9:
        affordable = [t for t in pool if t.marks <= remaining + 1e-9]
        if not affordable:
            break
        template = rng.choice(affordable)
        selected.append(template)
        remaining -= template.marks
    return selected


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
        return _fill_by_count(pool, section, rng)
    return _fill_by_marks(pool, section, rng)


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
Expected: PASS (9 tests — the 5 untouched ones plus the 4 new/replaced ones)

- [ ] **Step 5: Commit**

```bash
git add app/backend/blueprint/template_selection.py tests/unit/test_template_selection.py
git commit -m "make template selection best-effort instead of exact-or-raise"
```

---

### Task 2: `generate_paper` reports achieved marks, not aspirational blueprint marks

**Files:**
- Modify: `app/backend/generation/paper_generator.py`
- Modify: `tests/unit/test_paper_generator.py`

**Interfaces:**
- `generate_paper`'s signature is unchanged. Behavior change: the returned `Paper.total_marks` and each `Section.marks`/`question_count` are computed from the actually-generated `Question`s for that section, not copied from the blueprint.

- [ ] **Step 1: Update the difficulty-override test — it can no longer rely on the natural-difficulty call raising**

Replace `test_difficulty_override_changes_which_templates_are_eligible` in `tests/unit/test_paper_generator.py`:

```python
def test_difficulty_override_changes_which_templates_are_eligible():
    # marks=2.0/count=1 only exactly matches TPL-ADDITION-WORD-PROBLEM (the
    # only seed template with marks=2.0), and that template's difficulty_range
    # is (2, 3) — unreachable at the source paper's natural difficulty (1).
    # Without the override, best-effort selection (Task 1) now falls back to
    # the closest available marks (1.0) instead of raising; with the
    # override, the exact match succeeds.
    sections = [Section(name="Word Problems", marks=2.0, question_count=1)]
    source_paper = _source_paper(sections, total_marks=2.0)
    source_questions = [_source_question("1", difficulty=1)]  # -> derived difficulty_level=1

    _, natural_questions = generate_paper(source_paper, source_questions, rng=random.Random(3))
    assert natural_questions[0].type != QuestionType.WORD_PROBLEM
    assert natural_questions[0].marks == 1.0  # closest achievable, not the aspirational 2.0

    _, overridden_questions = generate_paper(
        source_paper, source_questions, difficulty_override=2, rng=random.Random(3)
    )
    assert overridden_questions[0].type == QuestionType.WORD_PROBLEM
    assert overridden_questions[0].marks == 2.0
```

Also add a new test proving the generated `Paper`'s declared totals track reality even when best-effort selection under-fills:

```python
def test_generated_paper_marks_reflect_what_was_actually_generated_not_the_target():
    sections = [Section(name="Word Problems", marks=2.0, question_count=1)]
    source_paper = _source_paper(sections, total_marks=2.0)
    source_questions = [_source_question("1", difficulty=1)]  # best-effort picks a 1.0-mark template

    generated_paper, generated_questions = generate_paper(
        source_paper, source_questions, rng=random.Random(3)
    )

    assert generated_paper.total_marks == sum(q.marks for q in generated_questions)
    assert generated_paper.sections[0].marks == sum(q.marks for q in generated_questions)
    assert generated_paper.sections[0].question_count == len(generated_questions)
```

- [ ] **Step 2: Run tests to verify the new/changed ones fail against the current implementation**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_paper_generator.py -v`
Expected: `test_difficulty_override_changes_which_templates_are_eligible` should already PASS at this point — Task 1's fix to `select_templates_for_section` is what made the natural-difficulty call stop raising and fall back to the closest marks, and that's independent of this task's `Paper`-totals change. `test_generated_paper_marks_reflect_what_was_actually_generated_not_the_target` should FAIL — this is the one this task's Step 3 actually fixes: `generated_paper.total_marks` still equals the aspirational `2.0` (copied straight from the blueprint) while `sum(q.marks for q in generated_questions) == 1.0` (what best-effort selection actually produced).

- [ ] **Step 3: Compute achieved totals from the real generated questions**

Replace `app/backend/generation/paper_generator.py`'s body from `generated_paper_id = new_id("PAPER")` onward:

```python
    generated_paper_id = new_id("PAPER")
    generated_questions: list[Question] = []
    generated_sections: list[Section] = []
    number = 1
    for section in blueprint.sections:
        section_questions: list[Question] = []
        for template in templates_by_section[section.name]:
            question = generate_question(
                template,
                paper_id=generated_paper_id,
                question_number=str(number),
                rng=rng,
                text_provider=text_provider,
            )
            section_questions.append(question)
            generated_questions.append(question)
            number += 1
        generated_sections.append(
            Section(
                name=section.name,
                marks=sum(q.marks for q in section_questions),
                question_count=len(section_questions),
            )
        )

    generated_paper = Paper(
        id=generated_paper_id,
        subject=blueprint.subject,
        class_standard=blueprint.class_standard,
        total_marks=sum(section.marks for section in generated_sections),
        duration_minutes=blueprint.duration_minutes,
        sections=generated_sections,
        source="generated",
        source_paper_id=blueprint.derived_from_paper_id,
        created_at=datetime.now(),
    )
    return generated_paper, generated_questions
```

- [ ] **Step 4: Run the full unit + integration suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: PASS, all tests — including Phase 8/9/10's own integration tests and the `generate_paper`/extraction-to-generated-paper integration tests from prior sessions, all of which were built around exact-match fixtures and should be unaffected by this change (their achieved totals already equaled their blueprint targets exactly).

- [ ] **Step 5: Commit**

```bash
git add app/backend/generation/paper_generator.py tests/unit/test_paper_generator.py
git commit -m "generate_paper reports achieved marks instead of the aspirational blueprint target"
```

---

### Task 3: Re-verify against the real golden-paper data that triggered this fix

**Files:** None (verification step, no code changes expected)

- [ ] **Step 1: Re-run the exact script that originally surfaced the failure**

Run (reusing the already-ingested/cleaned/extracted run from this session — if `data/processed/RUN-01M0D0SBSJ2JSCB9S0DNNR50EM/09_questions.json` no longer exists, re-run `ingest-paper`/`clean-paper`/`extract-questions` against `tests/fixtures/existing_paper/mental_maths/page_1.jpg` first):

```bash
.venv/Scripts/python.exe -c "
import json, random
from app.backend.questions.extraction import ExtractedSubQuestion
from app.backend.questions.paper_assembly import assemble_paper_from_extracted
from app.backend.generation.paper_generator import generate_paper
from app.backend.validation.validator import validate_paper, validate_blueprint_compliance
from app.backend.blueprint.derive import derive_blueprint_from_paper

data = json.loads(open('data/processed/RUN-01M0D0SBSJ2JSCB9S0DNNR50EM/09_questions.json').read())
extracted = [ExtractedSubQuestion(**q) for q in data['questions']]

paper, questions = assemble_paper_from_extracted(
    subject='Mathematics', class_standard='III', duration_minutes=20,
    extracted_questions=extracted,
)
generated_paper, generated_questions = generate_paper(paper, questions, rng=random.Random(1))
print(f'generate_paper SUCCEEDED: {len(generated_questions)} questions, '
      f'achieved total_marks={generated_paper.total_marks} (source paper had {paper.total_marks})')
print('validate_paper issues:', validate_paper(generated_paper, generated_questions))

blueprint = derive_blueprint_from_paper(paper, questions)
questions_by_section = {'All Questions': generated_questions}
print('validate_blueprint_compliance issues:', validate_blueprint_compliance(blueprint, questions_by_section))
"
```

Expected: no exception; `generate_paper SUCCEEDED` with some achieved `total_marks` close to (but not necessarily exactly) `14.5`; `validate_paper` issues is `[]` (the generated paper is internally self-consistent by construction); `validate_blueprint_compliance` issues may be non-empty (e.g. `blueprint_section_marks_mismatch`) if the achieved total genuinely falls short of the blueprint's aspirational `14.5` — that is the correct, informative outcome this plan's Global Constraints describe, not a bug.

- [ ] **Step 2: Record the actual output**

Note the printed achieved `total_marks` and any `validate_blueprint_compliance` issues for the TODO.md update in Task 4 — this plan can't predict the exact random draw's result in advance.

---

### Task 4: Update TODO.md

**Files:**
- Modify: `TODO.md`

**Interfaces:** None — documentation only.

- [ ] **Step 1: Run the full test suite and ruff as a pre-flight check**

Run: `.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m ruff check app/backend/blueprint/template_selection.py app/backend/generation/paper_generator.py tests/unit/test_template_selection.py tests/unit/test_paper_generator.py`
Expected: all tests pass; ruff reports no issues in the files this plan touched.

- [ ] **Step 2: Record the change, right after the `generate_paper orchestrator` section**

Insert a new section in `TODO.md` immediately after the `generate_paper orchestrator` section (before the extraction-gap-closing section or `## Phase 11+`, whichever currently follows it):

```markdown
## Template selection: best-effort gap-balancing — **done 2026-08-19**

Found by testing the application against a real scan: `ingest-paper` ->
`clean-paper` -> `extract-questions` on `tests/fixtures/existing_paper/
mental_maths/page_1.jpg` produced 26 real questions totaling 14.5 marks;
`generate_paper` raised `ValueError` because Phase 8's original
`select_templates_for_section` required a section's `marks /
question_count` to equal some seed template's marks *exactly*, with no
packing solver — fine for hand-built test fixtures, but 14.5/26 doesn't
land on 0.5, 1.0, or 2.0 (the only seed template marks values).

- [x] `app/backend/blueprint/template_selection.py` — exact match is
      still tried first (unchanged); when no template matches exactly,
      `select_templates_for_section` now falls back to a greedy
      gap-minimizing choice (closest available marks per remaining slot
      for the `question_count` path; fill-until-nothing-more-affordable
      for the marks-only path) instead of raising
- [x] `app/backend/generation/paper_generator.py` — `generate_paper`'s
      returned `Paper.total_marks`/`Section.marks`/`Section.question_count`
      now reflect what was *actually* generated, not the blueprint's
      aspirational target, so the generated paper is always internally
      self-consistent (`validate_paper` never flags `marks_mismatch`
      purely from a best-effort shortfall) — any real gap against the
      *source* paper's structure shows up in `validate_blueprint_compliance`
      instead, which is the tool built for exactly that signal
- [x] Re-ran the real `mental_maths` extraction from this session through
      `generate_paper`: [fill in the achieved total_marks and any
      validate_blueprint_compliance issues from Task 3's actual output]

`select_templates_for_section` only raises now when the eligible template
pool is empty after `allowed_types`/`difficulty_range` filtering — a
different failure ("no template can serve this section at all"), not
"couldn't hit the marks target exactly."
```

- [ ] **Step 3: Commit**

```bash
git add TODO.md
git commit -m "record template selection gap-balancing fix"
```
