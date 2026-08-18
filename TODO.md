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

## Phase 5 — Structured question models

- [ ] `app/backend/models/question.py` — `Question`, `QuestionType`,
      `DifficultyFeatures` (DATA_MODEL.md)
- [ ] `DifficultyFeatures.score()` implementation + unit tests covering the
      spec §16 easy/medium/harder examples

## Phase 6 — Validation

- [ ] `validation/answer_engine.py` — restricted expression evaluator
- [ ] `validation/validator.py` — recompute, blueprint compliance, dedup,
      options-contain-answer, no leakage
- [ ] Unit test: deliberately wrong answer_expression fixture must fail
      validation (spec §21's 47+25=73 example, literally)

## Phase 7 — Question generation

- [ ] `app/backend/models/question_template.py`
- [ ] Seed template set for MVP types (addition word problem, arithmetic,
      Roman numeral, predecessor/successor, rounding, mental maths,
      fill-in-blank, multiple choice, true/false)
- [ ] `generation/variable_sampler.py`
- [ ] `providers/text/` — `TextGenerationProvider` + Claude implementation,
      used for `text_template` phrasing only

## Phase 8 — Paper blueprint

- [ ] `app/backend/models/blueprint.py`
- [ ] Blueprint derivation from extracted `Paper` structure (Workflow A)

## Phase 9-10 — PDF + answer sheet

- [ ] `rendering/templates/simple_practice_paper.py` (ReportLab)
- [ ] `rendering/renderer.py`
- [ ] `app/backend/models/answer_key.py` + builder from `Paper`
- [ ] CLI: `render-paper`, `generate-answer-key`

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
