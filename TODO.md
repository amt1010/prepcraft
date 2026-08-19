# TODO

Tracks the current task list. Update as phases complete — this file is a
work queue, not a history log (git history is the log).

## Phase 0 — Planning (this commit)

- [x] Inspect repository
- [x] README.md
- [x] PROJECT_PLAN.md
- [x] ARCHITECTURE.md
- [x] DATA_MODEL.md
- [x] PIPELINE.md
- [x] EVALUATION.md
- [x] TODO.md
- [x] Present plan, get approval before Phase 1 — **approved 2026-08-17**
- [x] Golden dataset raw images received, copied to
      `tests/fixtures/existing_paper/` — see PROJECT_PLAN.md note: it's
      two separate documents (20-mark main paper, 3 pages; 10-mark Mental
      Maths paper, 1 page), not one 4-page paper as originally assumed

## Phase 1 — Project skeleton — **done 2026-08-17**

- [x] `pyproject.toml` — deps: fastapi, pydantic>=2, pydantic-settings,
      opencv-python-headless, pillow, numpy, pytesseract, reportlab,
      sqlalchemy, typer, anthropic, pyyaml; dev: pytest, ruff
- [x] `.venv` created, `pip install -e ".[dev]"` succeeds on Python 3.14
- [x] `app/__main__.py` + `app/cli.py` — Typer app, `--help` and `version`
      work (`python -m app version`). Note: a single-command Typer app
      collapses into a no-subcommand CLI — worked around with an explicit
      `@app.callback()` so `version` (and later commands) need their name.
- [x] `app/backend/core/config.py` — `AppConfig` + `load_config()`, reads
      `config.yaml`, Pydantic-validated, defaults for missing fields
- [x] `app/backend/core/secrets.py` — `Secrets` (pydantic-settings), reads
      `.env` for `ANTHROPIC_API_KEY`, kept separate from `AppConfig` so
      secrets can never land in the committed `config.yaml`
- [x] `.env.example` — provider API key placeholder, no real secrets
- [x] `config.yaml` — AI provider/model, OCR provider, storage root, log
      level, PDF page size, generation retry count (spec §36)
- [x] `app/backend/core/logging.py` — `configure_logging()` / `get_logger()`
- [x] `app/backend/core/ids.py` — hand-rolled Crockford-base32 ULID +
      `new_id(prefix)`, TDD'd: 26 chars, sortable by timestamp, unique
- [x] `ruff` config in `pyproject.toml`, `ruff check .` passes clean
- [x] `tests/unit/`, `tests/integration/`, `tests/e2e/`,
      `tests/fixtures/` exist; `pytest` runs 17/17 green (ids, config,
      secrets, logging, CLI — all TDD'd red-then-green)
- [x] `.gitignore` — `.venv/`, `__pycache__/`, `.env`,
      `data/processed/`, `data/generated/`
- [x] README.md "Local development"/"Testing" sections updated to real
      commands

## Phase 2 — Ingestion — **done 2026-08-18**

- [x] `app/backend/models/paper.py` — `Paper`, `Section` (DATA_MODEL.md)
- [x] `app/backend/ingestion/image_loader.py` — PDF/JPG/PNG -> page images
      (PyMuPDF for PDF rasterization, no Poppler dependency)
- [x] `app/backend/ingestion/page_detector.py` — contour-based boundary
      detection + perspective warp, with a "page fills frame" fallback
      when no quad is found
- [x] `app/backend/preprocessing/quality_gate.py` — skew/sharpness
      measurement + pass/flagged/fail verdict (added to Phase 2 rather
      than Phase 3 since it sits right after PageDetector in PIPELINE.md
      and needs nothing from PerspectiveCorrector)
- [x] `app/backend/storage/artifact_store.py` — per-page
      `data/processed/<run_id>/page_<NN>/<stage>.<ext>` artifacts
- [x] `AppConfig.quality` (`max_skew_degrees`, `min_sharpness`) — closes
      the Phase 1 follow-up noted in `config.yaml`
- [x] CLI: `python -m app ingest-paper <path> [--storage-root PATH]
      [--config-path PATH]`
- [x] Unit/integration tests: image_loader on JPG + a generated PDF
      fixture + unsupported extension; page_detector on synthetic
      unrotated/rotated/blank fixtures; quality_gate verdict logic +
      sharpness/skew measurement; CLI end-to-end
- [x] Run against golden paper, inspect `01_original.png` /
      `02_document_detected.png` manually — **finding**: on all 4 golden
      paper pages, `PageDetector` takes the "page fills frame" fallback
      path (no 4-point contour found), not the perspective-warp path.
      These particular photos are already tightly cropped against a
      plain background with no strong external edge to key off — not a
      bug, but it means the perspective-warp code path is untested
      against real data so far. Sharpness scores (1117-2671) are all
      comfortably above the 100 threshold; all 4 pages verdict `pass`
      with `skew=0.0` (the fallback's default). Before Phase 3 leans on
      `PageDetector`'s corners for anything beyond this quality gate,
      get a golden-paper photo that actually has visible background
      around the page (e.g. shot on a desk, not pre-cropped) to exercise
      the perspective-warp path for real.

## Phase 3 — Image cleaning

- [x] `preprocessing/perspective.py`, `enhancement.py`
- [x] `preprocessing/annotation_detector.py` — color-space + stroke +
      layout heuristics (PIPELINE.md detail)
- [x] `preprocessing/annotation_remover.py` — inpainting
- [x] `providers/vision/` — `VisionProvider` interface + Claude
      implementation, used for low-confidence annotation regions
- [ ] Hand-label a mask for golden paper page 1, wire up the precision/
      recall check from EVALUATION.md — `compute_mask_precision_recall`
      exists and is unit-tested, but there is still no real ground-truth
      mask to run it against. Deferred; needs a human to hand-label one
      golden paper page.
- [x] CLI: `python -m app clean-paper <run_id>`

### Golden paper verification findings (2026-08-18)

Ran `clean-paper` against all 4 golden paper pages and visually inspected
every `05_annotation_mask.png` / `06_cleaned.png` against the source. Found
and fixed three real bugs in `annotation_detector.py`, all confirmed only
by this real-photo test — the synthetic unit fixtures never exercised
them:

1. **Header self-calibration got skewed by the school banner's near-black
   fill**, pulling the "printed" brightness threshold too low and making
   ordinary printed text elsewhere look like pencil by comparison. Fixed
   by excluding near-pure-black pixels from calibration and adding a
   margin above the calibrated threshold before calling something pencil.
2. **Anti-aliased/JPEG edges around ordinary printed glyphs produced
   thousands of 1-6px specks** in the same brightness range as light
   pencil marks (median component area 2px, 9634 components on page 1
   alone). Added a `min_area=20` floor to `filter_by_stroke_shape` —
   real strokes are far bigger than compression noise.
3. **The header/calibration region was being flagged against its own
   calibration** — a colorful banner graphic is more saturated than
   plain black text, so it read as "colored ink." Now excluded from the
   output mask entirely, since it's the "this is what printed looks
   like" reference region by construction.
4. **Bright colored ink was being zeroed out as background.** `background
   = v_channel > 200` keyed on brightness alone; real red pen ink under
   good lighting is often v>200 too (confirmed ~90% of one red circle's
   ink pixels). Background now also requires low saturation, and the
   `colored_ink` branch's redundant `v < 220` cap was removed.

Net effect on page 1: 63887 → 16402 flagged pixels, and the difference is
qualitative, not just quantitative — before the fix the mask was mostly
printed text and table lines; after, it closely tracks the actual visible
red-ink annotations (score circle, ✗/✓ marks, circled numbers,
signatures) while leaving the banner, questions, and tables untouched.
Confirmed on all 4 pages.

**Known limitation, not yet fixed:** pencil/graphite student answers
(the actual handwritten digits, as opposed to the teacher's red-ink
marks) are still under-detected by the heuristics alone — real pencil
strokes and anti-aliased printed-text edges overlap too much in
brightness to separate reliably without help. This is expected: PIPELINE.md's
design always intended the `vision_provider` step to disambiguate
exactly this kind of ambiguous case, and there is no `ANTHROPIC_API_KEY`
configured in this environment, so that path is untested end-to-end.
Also open: whether `uncertainty_band` should route to vision-assist by
component size (current behavior) or by signal type — e.g. always
vision-checking anything classified as "pencil" rather than "colored
ink," since pencil is inherently the more ambiguous signal regardless of
size.

## Phase 4 — OCR + extraction

- [x] `providers/ocr/tesseract_provider.py` (+ `claude_provider.py` fallback,
      `ocr/orchestrator.py` confidence routing)
- [x] `ocr/layout_analysis.py`
- [x] `questions/extraction.py` (+ `providers/text_generation.py`)
- [x] Hand-transcribe `tests/fixtures/expected/main/questions.json` and
      `tests/fixtures/expected/mental_maths/questions.json`
- [x] Wire up OCR + extraction accuracy metrics (EVALUATION.md)
- [x] CLI: `python -m app extract-questions <run_id>`

### Golden paper verification findings (2026-08-18)

Ran `extract-questions` against all 4 golden paper pages with a real
`ANTHROPIC_API_KEY` (Tesseract for OCR, Claude Sonnet for classification).
Measured against the hand-transcribed fixtures:

| Metric | Main paper | Mental Maths |
|---|---|---|
| Extraction recall | 66.7% (14/21) | 100% (14/14, +8 spurious) |
| Field accuracy — type | 85.7% | 85.7% |
| Field accuracy — marks | 85.7% | 78.6% |
| Field accuracy — topic | 57.1% | 21.4% |
| Field accuracy — difficulty (exact) | 57.1% | 50% |
| OCR character accuracy (page 1 sample) | 56.8% | — |

All below EVALUATION.md's MVP bar (OCR ≥90%, extraction recall ≥90%).
Three distinct root causes, not one bug:

1. **`LayoutAnalysis`'s `^\d{1,2}\.$` regex is both too strict and too
   loose against real OCR noise.** Too strict: Tesseract read "7." as
   "7.." (double period) on the main paper's page 2, so question 7
   (Competency based questions) never opened its own group and its
   content silently merged into question 6's group, which the
   classification prompt then ignored since it was told "this is
   question 6." Same failure dropped question 4 on page 1. Too loose:
   on the Mental Maths page, sentence-ending numbers like "...became
   50." and "...digit is 4." inside question 1f's own text matched the
   same regex and were misread as new top-level questions "50" and "4",
   producing two fabricated garbage entries with `marks: null`. A
   text-only regex can't tell "a question number starting a new line"
   from "a number that happens to end a sentence" — that needs each
   `OCRWord`'s `left`/`top` position (already captured in `OCRResult`,
   just not used by `LayoutAnalysis` yet) to check whether the token is
   the leftmost word on a new line near the page's margin. Not fixed
   here — recorded as the concrete next step before this metric will
   clear 90%.
2. **Real photo OCR quality is moderate in cluttered regions.** 56.8%
   character accuracy on a hand-typed page-1 reference, well under the
   90% bar. Expected given lighting, paper fold, and faint pencil/ink
   remnants Phase 3's cleaning didn't fully remove (see Phase 3's own
   findings above) — this was never going to be a clean scan.
3. **The classification LLM sometimes fabricates plausible-but-wrong
   specifics from corrupted OCR input instead of flagging uncertainty.**
   Mental Maths question 1e's actual text is "57 + 7 = 8 x ___"; badly
   garbled OCR led Sonnet to return an entirely different (but
   internally consistent) fact family, "5 + 3 = 8, 9 - 4 = ___", instead
   of anything resembling the source. The `[0.5x9=4.5]` marks-grid
   question (Q3) shows the opposite, better-behaved failure mode: faced
   with an unreadable digit grid, the model correctly inferred there
   should be 9 sub-items from the marks annotation but returned generic
   placeholder text ("(addition problem with missing digits)") rather
   than invented digits — i.e. it hedged on content it couldn't read
   instead of fabricating numbers. The prompt in
   `questions/extraction.py` has no explicit "say so if you can't read
   part of this" instruction; adding one is a cheap follow-up.

**Metric-implementation note:** `compute_word_accuracy`'s positional
zip-based comparison (matching predicted word *i* against reference word
*i*) desyncs badly once the two texts have a different word count —
which is the normal case here, not the exception. It produced a 4.5%
score on the same page-1 sample that scored 56.8% on character accuracy,
which is not a believable gap. EVALUATION.md specifies "exact word match
rate after tokenization" without saying how to align two differently-
sized word lists; this needs an edit-distance/alignment-based comparison
to be a meaningful number, not the naive zip used here.

Page 3 of the main paper correctly produced 0 question groups — it only
contains continuation letters ("b.", "c.") with no top-level number of
its own, which `LayoutAnalysis` was never designed to handle (see this
phase's plan, Task 9 Step 3 note). Cross-page question continuation is
an open problem for whenever multi-page single-run ingestion lands.

No comparison was possible against a topic taxonomy — "topic accuracy"
is exact-string match against fixture labels I wrote by hand (e.g.
"Addition" vs the model's "Missing number/Equation" for the same
question), so a chunk of that 57%/21% gap is disagreement about label
*wording*, not the model misunderstanding the question. A real fix needs
either a fixed topic taxonomy the model is asked to pick from, or a
looser-than-exact-match grading rule — not yet decided.

## Phase 5 — Structured question models — **done 2026-08-18**

- [x] `app/backend/models/question.py` — `Question`, `QuestionType`,
      `DifficultyFeatures` (DATA_MODEL.md)
- [x] `DifficultyFeatures.score()` implementation + unit tests covering the
      spec §16 easy/medium/harder examples

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

## Phase 11+ — deferred until MVP (Phases 2-10) is solid

- [ ] Basic web UI (wizard, spec §23)
- [ ] Chapter ingestion (Workflow B)
- [ ] Difficulty controls UI
- [ ] Evaluation dashboard

## Open questions for the user (not blocking Phase 1, will block later phases)

- [ ] Which cloud OCR/vision engine (if any) backs the low-confidence
      fallback — decide once golden paper scan quality is known
      (PROJECT_PLAN.md risk 2)
- [ ] Curriculum/board scope beyond CBSE-style Class III Math for Phase 3
