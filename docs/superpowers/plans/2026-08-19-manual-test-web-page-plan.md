# Minimal Manual-Test Web Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the user an actual browser link to click through the Workflow A pipeline manually: upload a scanned paper image, get back a regenerated `question_paper.pdf` + `answer_sheet.pdf`. This is explicitly **not** the production wizard (spec §23's 7-step flow with a Review Screen — spec §24's edit/regenerate/delete/accept) — it's the smallest thing that turns every module built this session into something clickable in a browser, per the user's own choice of "build a minimal local web page" over the CLI-only or CLI-command alternatives offered.

**Architecture:** `app/backend/api/pipeline.py` holds one function, `run_full_pipeline`, composing every already-built, already-tested piece into one call: `ingestion` -> `preprocessing` (perspective/enhancement/annotation removal) -> `ocr` -> `questions/extraction.py` -> `questions/paper_assembly.py` (this session's extraction-gap-closing work) -> `generation/paper_generator.regenerate_paper` (this session's Workflow A fix) -> `answer_key/builder.py` -> `rendering/renderer.py`. `app/backend/api/server.py` is a thin FastAPI app: an upload form, a `POST /generate` route that calls `run_full_pipeline` and returns download links, and a `GET /download/...` route serving the two PDFs. `app/cli.py` gains one `serve` command so there's a single terminal command to start it. No refactor of the existing `ingest-paper`/`clean-paper`/`extract-questions` CLI commands — `run_full_pipeline` calls the same underlying functions those commands call, kept as a separate, self-contained orchestration path so this plan's blast radius stays limited to new files.

**Tech Stack:** Two new dependencies: `uvicorn` (ASGI server to actually run the FastAPI app — `fastapi` has been a listed dependency since Phase 1 but nothing has ever served it) and `python-multipart` (FastAPI's file-upload parsing requires it; omitting it produces a runtime error the moment a form with a file field is submitted). Everything else reuses modules already built and tested this session and in Phases 2-10.

**Spec:** `ARCHITECTURE.md` (module map's `api/` entry: "FastAPI routes (Phase 11) — thin, calls into the modules above"; "Pipeline as explicit function composition" — this plan's `run_full_pipeline` is exactly that pattern, one call site combining stages instead of a framework), `PIPELINE.md` (Workflow A's full stage list — every stage this plan's orchestrator calls, in the same order `app/cli.py`'s three existing commands already use), `app/cli.py` (the literal reference implementation for ingest/clean/extract — this plan's `run_full_pipeline` mirrors its exact call sequence, verified stage-by-stage against the current file), this session's conversation (the `regenerate_paper` fix and the request for "a link to test" this pipeline).

## Global Constraints

- `run_full_pipeline` handles exactly one uploaded page (matches `ingestion/image_loader.load_pages`'s existing single-file-per-call contract — multi-page papers already require multiple `ingest-paper` invocations under one `run_id` today; this plan doesn't change that).
- API routes stay thin: `server.py` only parses the HTTP request, calls `run_full_pipeline`, and formats the HTML response — no pipeline logic lives in a route handler (ARCHITECTURE.md's `api/` constraint).
- `GET /download/{paper_id}/{filename}` sanitizes both path segments with `Path(...).name` before touching the filesystem — untrusted URL path segments must never be concatenated directly into a filesystem path (path traversal).
- Every module boundary crosses with a Pydantic model, never a raw dict (DATA_MODEL.md line 3-4, spec §12, §35) — unchanged, this plan only adds a thin HTTP layer on top of code that already honors this.
- No automated test in this plan makes a real Claude API call — that would make `pytest -q` slow and non-free on every run. The "does the real pipeline actually work end to end with real classification" proof is Task 5's manual browser verification, not an automated test (same reasoning Phase 9/10 used for "render a PDF and read it back," not "assert every glyph position").

---

### Task 1: Add `uvicorn` and `python-multipart`

**Files:**
- Modify: `pyproject.toml`

**Interfaces:** None — dependency setup only.

- [ ] **Step 1: Add the two dependencies**

In `pyproject.toml`'s `dependencies` list, add after `"fastapi>=0.115",`:

```toml
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "python-multipart>=0.0.12",
```

- [ ] **Step 2: Install them into the existing venv**

Run: `.venv/Scripts/python.exe -m pip install -e ".[dev]"`
Expected: installs `uvicorn` and `python-multipart` (and their transitive deps) without touching already-satisfied requirements.

- [ ] **Step 3: Verify the imports resolve**

Run: `.venv/Scripts/python.exe -c "import uvicorn, multipart; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "add uvicorn and python-multipart for the manual-test web page"
```

---

### Task 2: `api/pipeline.py` — `run_full_pipeline`

**Files:**
- Create: `app/backend/api/__init__.py` (empty, package marker)
- Create: `app/backend/api/pipeline.py`
- Test: `tests/unit/test_pipeline_orchestration.py`

**Interfaces:**
- Consumes: `load_pages` (`ingestion/image_loader.py`), `detect_page` (`ingestion/page_detector.py`), `correct_perspective` (`preprocessing/perspective.py`), `enhance_image` (`preprocessing/enhancement.py`), `detect_annotations`/`remove_annotations` (`preprocessing/annotation_detector.py`/`annotation_remover.py`), `extract_text_with_fallback` (`ocr/orchestrator.py`), `group_by_question_number` (`ocr/layout_analysis.py`), `extract_questions` (`questions/extraction.py`), `assemble_paper_from_extracted` (`questions/paper_assembly.py`), `regenerate_paper` (`generation/paper_generator.py`), `build_answer_key` (`answer_key/builder.py`), `render_question_paper`/`render_answer_sheet` (`rendering/renderer.py`), `TesseractOCRProvider`/`ClaudeOCRProvider`/`ClaudeVisionProvider`/`ClaudeTextGenerationProvider` (`providers/`), `Secrets` (`core/secrets.py`), `load_config` (`core/config.py`).
- Produces: `run_full_pipeline(image_path: Path, subject: str, class_standard: str, duration_minutes: int, output_root: Path = Path("data/generated"), config_path: Path = Path("config.yaml"), use_real_providers: bool = True) -> tuple[Path, Path]` — returns `(question_paper_path, answer_sheet_path)`. `use_real_providers` defaults to `True` for production/`server.py`'s use (build vision/OCR-fallback/classification providers from `Secrets()` when a key is configured); tests pass `False` to force the no-provider path deterministically, since this repo's own `.env` has a real key configured — an automated test cannot assume a key is *absent* just because it wants the free/fast path. Task 3 imports `run_full_pipeline` directly: `from app.backend.api.pipeline import run_full_pipeline`.

- [ ] **Step 1: Write the failing test**

This repo's `.env` has a real `ANTHROPIC_API_KEY` configured (confirmed earlier this session), so a test can't rely on "no key present" happening naturally — it has to force the no-provider path explicitly via `use_real_providers=False`, then assert the same already-established failure mode `questions/paper_assembly.py` documents for unclassified extraction.

```python
# tests/unit/test_pipeline_orchestration.py
"""Exercises run_full_pipeline's real wiring (real Tesseract OCR, real
OpenCV image processing — no network calls) against the golden mental_maths
fixture, with use_real_providers=False forcing the no-classification path
regardless of this repo's own configured ANTHROPIC_API_KEY. This suite
must stay free and fast; Task 5's manual browser verification (real
providers, real classification) is what proves the happy-path end-to-end
result. This test proves the unclassified-fallback path fails the way
questions/paper_assembly.py documents (ValueError on marks/topic/
difficulty missing) rather than silently producing a garbage Paper."""

from pathlib import Path

import pytest

from app.backend.api.pipeline import run_full_pipeline


def test_run_full_pipeline_raises_on_unclassified_extraction(tmp_path):
    with pytest.raises(ValueError):
        run_full_pipeline(
            Path("tests/fixtures/existing_paper/mental_maths/page_1.jpg"),
            subject="Mathematics",
            class_standard="III",
            duration_minutes=20,
            output_root=tmp_path,
            use_real_providers=False,
        )
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_pipeline_orchestration.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backend.api'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/backend/api/__init__.py
```

```python
# app/backend/api/pipeline.py
"""End-to-end pipeline orchestration for the minimal manual-testing web
page (api/server.py). Thin composition of already-built, already-tested
modules — mirrors app/cli.py's ingest-paper/clean-paper/extract-questions
stage sequence exactly (verified against that file), then adds
Workflow A's 1:1 regeneration and rendering. No new pipeline logic."""

import random
from pathlib import Path

import cv2

from app.backend.answer_key.builder import build_answer_key
from app.backend.core.config import load_config
from app.backend.core.secrets import Secrets
from app.backend.generation.paper_generator import regenerate_paper
from app.backend.ingestion.image_loader import load_pages
from app.backend.ingestion.page_detector import detect_page
from app.backend.ocr.layout_analysis import group_by_question_number
from app.backend.ocr.orchestrator import extract_text_with_fallback
from app.backend.preprocessing.annotation_detector import detect_annotations
from app.backend.preprocessing.annotation_remover import remove_annotations
from app.backend.preprocessing.enhancement import enhance_image
from app.backend.preprocessing.perspective import correct_perspective
from app.backend.providers.ocr.claude_provider import ClaudeOCRProvider
from app.backend.providers.ocr.tesseract_provider import TesseractOCRProvider
from app.backend.providers.text_generation import ClaudeTextGenerationProvider
from app.backend.providers.vision import ClaudeVisionProvider
from app.backend.questions.extraction import extract_questions
from app.backend.questions.paper_assembly import assemble_paper_from_extracted
from app.backend.rendering.renderer import render_answer_sheet, render_question_paper


def _build_providers(
    config_path: Path,
) -> tuple[ClaudeVisionProvider | None, ClaudeOCRProvider | None, ClaudeTextGenerationProvider | None]:
    cfg = load_config(config_path) if config_path.exists() else None
    secrets = Secrets()
    if not secrets.anthropic_api_key:
        return None, None, None
    vision_provider = ClaudeVisionProvider(api_key=secrets.anthropic_api_key)
    ocr_fallback = ClaudeOCRProvider(
        api_key=secrets.anthropic_api_key,
        model=cfg.models.ocr_fallback if cfg else "claude-haiku-4-5",
    )
    text_provider = ClaudeTextGenerationProvider(
        api_key=secrets.anthropic_api_key,
        model=cfg.models.question_classification if cfg else "claude-sonnet-5",
    )
    return vision_provider, ocr_fallback, text_provider


def run_full_pipeline(
    image_path: Path,
    subject: str,
    class_standard: str,
    duration_minutes: int,
    output_root: Path = Path("data/generated"),
    config_path: Path = Path("config.yaml"),
    use_real_providers: bool = True,
) -> tuple[Path, Path]:
    if use_real_providers:
        vision_provider, ocr_fallback, text_provider = _build_providers(config_path)
    else:
        vision_provider = ocr_fallback = text_provider = None

    pages = load_pages(image_path)
    detection = detect_page(pages[0])
    corrected = correct_perspective(detection.image)
    enhanced = enhance_image(corrected)
    annotation_result = detect_annotations(enhanced, vision_provider=vision_provider)
    cleaned = remove_annotations(enhanced, annotation_result.mask)

    success, buffer = cv2.imencode(".png", cleaned)
    if not success:
        raise ValueError("failed to encode cleaned page as PNG")
    ocr_result = extract_text_with_fallback(
        buffer.tobytes(), TesseractOCRProvider(), ocr_fallback
    )
    groups = group_by_question_number(ocr_result)
    extracted = extract_questions(groups, text_provider=text_provider)

    source_paper, source_questions = assemble_paper_from_extracted(
        subject=subject,
        class_standard=class_standard,
        duration_minutes=duration_minutes,
        extracted_questions=extracted,
    )
    generated_paper, generated_questions = regenerate_paper(
        source_paper, source_questions, rng=random.Random(), text_provider=text_provider
    )
    answer_key = build_answer_key(generated_paper, generated_questions)

    paper_dir = output_root / generated_paper.id
    question_paper_path = render_question_paper(
        generated_paper, generated_questions, paper_dir / "question_paper.pdf"
    )
    answer_sheet_path = render_answer_sheet(
        generated_paper, answer_key, paper_dir / "answer_sheet.pdf"
    )
    return question_paper_path, answer_sheet_path
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_pipeline_orchestration.py -v`
Expected: PASS (1 test) — Tesseract runs for real (no network call), extraction falls back to `type="unknown"` with no `text_provider` configured, and `assemble_paper_from_extracted` raises `ValueError` exactly as `questions/paper_assembly.py` documents.

- [ ] **Step 5: Commit**

```bash
git add app/backend/api/__init__.py app/backend/api/pipeline.py tests/unit/test_pipeline_orchestration.py
git commit -m "add run_full_pipeline orchestrator for the manual-test web page"
```

---

### Task 3: `api/server.py` — FastAPI routes

**Files:**
- Create: `app/backend/api/server.py`

**Interfaces:**
- Consumes: `run_full_pipeline` (Task 2).
- Produces: a FastAPI app object `app` at module level (`app.backend.api.server:app`), with `GET /`, `POST /generate`, `GET /download/{paper_id}/{filename}`. Task 4's `serve` CLI command references this module path directly.

- [ ] **Step 1: Write the server**

No TDD cycle here — this is a thin HTTP layer over Task 2's already-tested function; its only real verification is Task 5's manual browser run, which needs the server to exist first.

```python
# app/backend/api/server.py
"""Minimal FastAPI page for manually testing the full Workflow A pipeline
in a browser: upload a scanned paper image, get back a regenerated
question paper + answer sheet PDF. Routes stay thin (ARCHITECTURE.md's
api/ constraint) — all real work is in api/pipeline.py's run_full_pipeline.
Not the production wizard (spec §23/§24) — no difficulty selection, no
Review Screen edit/regenerate/delete, no Workflow B. Scoped only to "click
through the pipeline once and get real PDFs back," per the user's explicit
choice of this over a CLI-only or CLI-command approach."""

from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from app.backend.api.pipeline import run_full_pipeline

app = FastAPI(title="AI Practice Paper Generator — manual test page")

_UPLOAD_DIR = Path("data/uploads")
_GENERATED_DIR = Path("data/generated")

_FORM_HTML = """<!doctype html>
<html><head><title>AI Practice Paper Generator</title></head>
<body style="font-family: sans-serif; max-width: 640px; margin: 40px auto;">
<h1>AI Practice Paper Generator — manual test</h1>
<p>Upload a scanned exam page (JPG/PNG/PDF, one page). Runs the full
Workflow A pipeline: ingest, clean, OCR, extract, regenerate 1:1
(same type, same marks, new values), render.</p>
<form action="/generate" method="post" enctype="multipart/form-data">
  <p><label>Paper image/PDF: <input type="file" name="file" required></label></p>
  <p><label>Subject: <input type="text" name="subject" value="Mathematics"></label></p>
  <p><label>Class: <input type="text" name="class_standard" value="III"></label></p>
  <p><label>Duration (minutes):
    <input type="number" name="duration_minutes" value="50"></label></p>
  <p><button type="submit">Generate</button></p>
</form>
</body></html>
"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return _FORM_HTML


@app.post("/generate", response_class=HTMLResponse)
async def generate(
    file: UploadFile,
    subject: str = Form("Mathematics"),
    class_standard: str = Form("III"),
    duration_minutes: int = Form(50),
) -> str:
    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    upload_path = _UPLOAD_DIR / Path(file.filename).name
    upload_path.write_bytes(await file.read())

    question_paper_path, answer_sheet_path = run_full_pipeline(
        upload_path,
        subject=subject,
        class_standard=class_standard,
        duration_minutes=duration_minutes,
        output_root=_GENERATED_DIR,
    )

    paper_id = question_paper_path.parent.name
    return f"""<!doctype html>
<html><head><title>Generated</title></head>
<body style="font-family: sans-serif; max-width: 640px; margin: 40px auto;">
<h1>Done</h1>
<p><a href="/download/{paper_id}/question_paper.pdf">Download question_paper.pdf</a></p>
<p><a href="/download/{paper_id}/answer_sheet.pdf">Download answer_sheet.pdf</a></p>
<p><a href="/">Generate another</a></p>
</body></html>
"""


@app.get("/download/{paper_id}/{filename}")
def download(paper_id: str, filename: str) -> FileResponse:
    safe_paper_id = Path(paper_id).name
    safe_filename = Path(filename).name
    path = _GENERATED_DIR / safe_paper_id / safe_filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="not found")
    return FileResponse(path, media_type="application/pdf", filename=safe_filename)
```

- [ ] **Step 2: Import-check the module**

Run: `.venv/Scripts/python.exe -c "from app.backend.api.server import app; print(app.title)"`
Expected: `AI Practice Paper Generator — manual test page` — proves the module and every import resolve before Task 4 wires a CLI command to it.

- [ ] **Step 3: Commit**

```bash
git add app/backend/api/server.py
git commit -m "add FastAPI server for the manual-test web page"
```

---

### Task 4: `serve` CLI command

**Files:**
- Modify: `app/cli.py`

**Interfaces:**
- Consumes: `app.backend.api.server:app` (Task 3, referenced by import path string, not imported directly — keeps `uvicorn`'s import lazy so every other CLI command's startup stays fast).
- Produces: `python -m app serve [--host HOST] [--port PORT]`.

- [ ] **Step 1: Add the command**

Add to `app/cli.py`, after the `extract_questions_cmd` function and before `if __name__ == "__main__":`:

```python
@app.command(name="serve")
def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Run the minimal manual-testing web page (upload a paper, get back
    a regenerated question paper + answer sheet PDF)."""
    import uvicorn

    typer.echo(f"Serving at http://{host}:{port} — Ctrl+C to stop")
    uvicorn.run("app.backend.api.server:app", host=host, port=port, reload=False)
```

- [ ] **Step 2: Verify the command is registered**

Run: `.venv/Scripts/python.exe -m app --help`
Expected: the `Commands` panel now lists `serve` alongside `version`/`ingest-paper`/`clean-paper`/`extract-questions`.

- [ ] **Step 3: Commit**

```bash
git add app/cli.py
git commit -m "add serve CLI command for the manual-test web page"
```

---

### Task 5: Manual browser verification

**Files:** None (manual step, no code changes)

This is the actual "test this pipeline manually" the user asked for — start the real server, upload the real golden paper through a real browser, confirm two real PDFs come back and open correctly. Task 2's automated test only proves the unclassified-fallback path fails correctly (no API key assumed); this step is what proves the classified, happy path genuinely works, matching this codebase's established pattern of manual verification for anything that needs a real provider call or visual confirmation (Phase 3's mask inspection, Phase 9/10's rendered-PDF read-back).

- [ ] **Step 1: Start the server in the background**

```bash
.venv/Scripts/python.exe -m app serve
```

- [ ] **Step 2: Open it in a browser and upload the golden paper**

Navigate to `http://127.0.0.1:8000/`, upload `tests/fixtures/existing_paper/mental_maths/page_1.jpg`, leave Subject/Class/Duration at their defaults, submit. Wait for the response page — this repeats the same real Claude vision/OCR-fallback/classification calls Task 5 of the earlier "let's test the application" session took ~2 minutes for, so expect a comparable wait with no visible progress indicator (this minimal page doesn't have one — a known, acceptable limitation for a manual-test-only page).

- [ ] **Step 3: Download and open both PDFs**

Click both download links. Confirm `question_paper.pdf` shows regenerated questions (new values, same types/marks as the golden `mental_maths` questions) and `answer_sheet.pdf` lists a matching answer per question, mirroring Phase 9/10's own visual-inspection checks.

- [ ] **Step 4: Stop the server and record findings**

Note what was confirmed (or any real issue found and fixed) for Task 6's TODO.md entry.

---

### Task 6: Update TODO.md

**Files:**
- Modify: `TODO.md`

**Interfaces:** None — documentation only.

- [ ] **Step 1: Run the full test suite and ruff as a pre-flight check**

Run: `.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m ruff check app/backend/api tests/unit/test_pipeline_orchestration.py app/cli.py`
Expected: all tests pass; ruff reports no issues in the files this plan touched.

- [ ] **Step 2: Record the addition, right after the Workflow A regeneration section**

Insert a new section in `TODO.md` immediately after the `Workflow A: 1:1 question regeneration` section (before `## Phase 11+`):

```markdown
## Minimal manual-test web page — **done 2026-08-19**

Not Phase 11's production wizard (spec §23/§24 — difficulty selection,
Review Screen edit/regenerate/delete, Workflow B) — a deliberately small
FastAPI page so the pipeline built across this session has an actual
browser link to click through, per explicit user request ("I want to test
this pipeline manually, help me with the link to test").

- [x] `app/backend/api/pipeline.py` — `run_full_pipeline`: one function
      chaining ingestion -> cleaning -> OCR -> extraction ->
      `assemble_paper_from_extracted` -> `regenerate_paper` (Workflow A
      1:1) -> `build_answer_key` -> both renderers. Mirrors
      `app/cli.py`'s existing ingest/clean/extract call sequence exactly
      (no CLI refactor — this is a separate, self-contained path)
- [x] `app/backend/api/server.py` — `GET /` (upload form), `POST
      /generate` (runs the pipeline, returns download links), `GET
      /download/{paper_id}/{filename}` (path-sanitized file serving)
- [x] `python -m app serve [--host] [--port]` — new CLI command, lazy
      `uvicorn` import so every other command's startup stays fast
- [x] New dependencies: `uvicorn`, `python-multipart` (file upload
      parsing — `fastapi` needs it and has never actually needed it
      before, since nothing served the app until now)
- [x] Automated test: `run_full_pipeline` against the real golden
      `mental_maths` fixture (real Tesseract, no network calls) correctly
      raises when extraction is unclassified (no API key) — the
      classified happy path is proven manually instead, to keep the test
      suite free and fast
- [x] Manual verification: [fill in what Task 5 actually confirmed —
      uploaded the golden paper through a real browser session, both
      PDFs downloaded and opened, regenerated content matched the
      source's types/marks with new values]
```

- [ ] **Step 3: Commit**

```bash
git add TODO.md
git commit -m "add minimal manual-test web page"
```
