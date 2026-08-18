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

## Phase 2 — Ingestion

- [ ] `app/backend/models/paper.py` — `Paper`, `Section` (DATA_MODEL.md)
- [ ] `app/backend/ingestion/image_loader.py` — PDF/JPG/PNG -> page images
- [ ] `app/backend/ingestion/page_detector.py` — boundary detection
- [ ] `app/backend/storage/artifact_store.py` — `data/processed/<run_id>/`
      read/write, stage numbering
- [ ] CLI: `python -m app ingest-paper <path>`
- [ ] Unit tests: image_loader on each input format; page_detector on a
      deliberately skewed fixture image
- [ ] Run against golden paper, inspect `01_original.png` /
      `02_document_detected.png` manually

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
