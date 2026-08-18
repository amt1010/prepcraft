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

- [ ] `preprocessing/perspective.py`, `enhancement.py`
- [ ] `preprocessing/annotation_detector.py` — color-space + stroke +
      layout heuristics (PIPELINE.md detail)
- [ ] `preprocessing/annotation_remover.py` — inpainting
- [ ] `providers/vision/` — `VisionProvider` interface + Claude
      implementation, used for low-confidence annotation regions
- [ ] Hand-label a mask for golden paper page 1, wire up the precision/
      recall check from EVALUATION.md
- [ ] CLI: `python -m app clean-paper <run_id>`

## Phase 4 — OCR + extraction

- [ ] `providers/ocr/tesseract_provider.py`
- [ ] `ocr/layout_analysis.py`
- [ ] `questions/extraction.py`
- [ ] Hand-transcribe `tests/fixtures/expected/main/questions.json` and
      `tests/fixtures/expected/mental_maths/questions.json`
- [ ] Wire up OCR + extraction accuracy metrics (EVALUATION.md)
- [ ] CLI: `python -m app extract-questions <run_id>`

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
