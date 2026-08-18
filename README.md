# AI Practice Paper Generator

Turn a real school question paper — or a stack of textbook photos — into a fresh practice paper with a matching answer sheet, as a PDF.

## Problem

A parent or teacher who wants extra practice for a kid today has to do this by hand:

- Scan or photograph the paper
- Manually white-out or retype around the student's handwritten answers and the teacher's red-pen marks
- Reinvent new questions that match the original difficulty and topic spread
- Redo the arithmetic to make sure the new answers are actually right
- Format the whole thing into something printable
- Write out an answer key separately, hoping it still matches the questions

This project automates that pipeline end to end, without pretending an LLM can be trusted to do arithmetic, OCR, or image editing reliably on its own. Every step that can be deterministic is deterministic; AI is used only where a deterministic method genuinely can't do the job (reading messy handwriting-adjacent scans, understanding question intent, drafting new question text).

## Features

### Existing Paper → New Paper (Workflow A)

Upload a scanned/photographed paper that has student handwriting, pencil marks, teacher corrections, ticks, crosses, and scores on it. The system:

1. Corrects rotation/perspective/lighting.
2. Separates printed content from handwritten/marked content.
3. Removes the handwritten/marked content, leaving the printed questions, tables, diagrams, and instructions intact.
4. Extracts the paper's structure (questions, marks, types, topics, difficulty).
5. Generates a new paper with the same structure and difficulty, but new question values — never copying a student's answer or a teacher's mark forward.
6. Renders a question paper PDF and an answer sheet PDF.

### Chapter Material → New Paper (Workflow B)

Upload 10-30 photos of textbook pages for a chapter. The system OCRs and structures the chapter (concepts, definitions, examples, exercises), then lets the user pick subject/class/chapter/question count/marks/duration/type/difficulty and generates a paper + answer sheet from that structure.

## Architecture overview

```
Camera / PDF / Image
        |
Document Ingestion
        |
Image Cleanup (deskew, perspective, lighting)
        |
Annotation Detection + Removal   <- hardest step, see PIPELINE.md
        |
OCR / Vision
        |
Document Understanding (structure, question types, difficulty)
        |
Structured Question Model (Pydantic)
        |
Question Bank
        |
Paper Blueprint + Generator (template + LLM-drafted values, code-computed answers)
        |
Validator (recomputes every answer, checks blueprint compliance)
        |
PDF Renderer (deterministic, template-based)
        |
Question Paper + Answer Sheet
```

Full detail: [PIPELINE.md](PIPELINE.md). Module boundaries and data flow: [ARCHITECTURE.md](ARCHITECTURE.md). Data shapes: [DATA_MODEL.md](DATA_MODEL.md).

## Technology stack

Chosen for MVP (see ARCHITECTURE.md §"Stack rationale" for why):

**Backend**
- Python 3.11+
- FastAPI (HTTP API, once the CLI is stable)
- Pydantic v2 (every structured object in the system is a Pydantic model — no raw dicts crossing module boundaries)
- OpenCV + Pillow + NumPy (deterministic image processing: deskew, perspective correction, color-space separation, morphology)
- Tesseract (pytesseract) as the baseline OCR engine, behind an `OCRProvider` interface so a cloud OCR/vision engine can be swapped in per-document when Tesseract's confidence is low
- A small `VisionProvider` / `TextGenerationProvider` interface over the Claude API (default provider) for: reading annotation-heavy regions Tesseract can't, classifying question type/topic/difficulty, and drafting new question text
- ReportLab for PDF rendering (deterministic — it only ever consumes validated structured data, never raw model output)
- SQLite via SQLAlchemy for persistence
- Typer for the CLI

**Frontend**
- Superseded by the SaaS layer (see `docs/superpowers/specs/2026-08-18-saas-tiers-billing-design.md`): Next.js 15 (App Router, TypeScript) at `web/`, chosen for Clerk's best-supported integration once auth/billing/admin were in scope. Its own Postgres via Prisma. The pipeline's review/wizard screens (spec §23, §24) live inside this app rather than a separate server-rendered one.
- The MVP pipeline itself (Phases 2-10) stays CLI-only in the meantime — the CLI plus inspecting `data/processed/<run_id>/` is still how you exercise the pipeline directly, independent of the web app.

No provider is hard-coded. `VisionProvider`, `TextGenerationProvider`, and `OCRProvider` are small interfaces (see ARCHITECTURE.md) so Claude, OpenAI, Gemini, or a local model can sit behind them later without touching pipeline code.

## Local development

```bash
python -m venv .venv
.venv\Scripts\activate         # Windows
pip install -e ".[dev]"
copy .env.example .env         # fill in ANTHROPIC_API_KEY
python -m app --help
python -m app version
```

Settings live in `config.yaml` (committed, no secrets); API keys live in
`.env` (gitignored, never committed) — see `app/backend/core/config.py`
and `core/secrets.py`.

## Testing

```bash
pytest                       # everything
pytest tests/unit            # pure-function tests: ids, config, logging, CLI wiring
pytest tests/integration     # pipeline-stage tests (added from Phase 2 onward)
pytest tests/e2e             # sample paper -> generated PDF, run against the golden dataset
ruff check .                 # lint
```

See [EVALUATION.md](EVALUATION.md) for what "correct" means at each stage and how it's measured, not just pass/fail.

## Project structure

```
app/
    backend/
        api/            FastAPI routes (added Phase 11)
        core/            config loading, logging, run-ID management
        models/          Pydantic models: Paper, Question, Chapter, Blueprint, etc.
        ingestion/       PaperInput -> ImageLoader -> PageDetector
        preprocessing/   PerspectiveCorrector, ImageEnhancer, AnnotationDetector, AnnotationRemover
        ocr/             OCRProvider interface + Tesseract implementation
        document/        LayoutAnalysis, document understanding (structure/topic/difficulty)
        questions/       QuestionExtraction, question template model
        knowledge/       Chapter knowledge extraction (Workflow B)
        generation/      Candidate question generation from templates + LLM
        validation/      Answer recomputation, blueprint compliance, duplicate/leakage checks
        rendering/       PDF templates + renderer (ReportLab)
        storage/         SQLite models, filesystem artifact storage
        providers/       VisionProvider, TextGenerationProvider, OCRProvider interfaces + implementations
web/                     Next.js SaaS shell (auth, quota, billing, admin) — see the SaaS spec/plan under docs/superpowers/
tests/
    unit/
    integration/
    e2e/
    fixtures/            Golden dataset (existing_paper/, expected/) — see EVALUATION.md
data/
    samples/             Raw uploaded input, untouched
    processed/           Per-run inspectable artifacts (01_original.png ... 09_questions.json)
    generated/           Output PDFs
docs/                    Design notes below the top-level docs
prompts/                 Versioned prompt files (extract_questions_v1.txt, etc.) — never inline in code
scripts/
README.md
PROJECT_PLAN.md
ARCHITECTURE.md
DATA_MODEL.md
PIPELINE.md
EVALUATION.md
TODO.md
```

## Roadmap

**MVP** — Workflow A only, Class III Mathematics, image/PDF input, question types: multiple choice, fill-in-blank, arithmetic, roman numerals, predecessor/successor, rounding, addition word problems, mental maths. CLI-driven. Output: question paper PDF + answer sheet PDF. See PROJECT_PLAN.md for the phase-by-phase build order and TODO.md for the current task list.

**Phase 2** — Workflow B (chapter → paper). Basic web UI (wizard, matches spec §23). More question types (match-the-following, short answer, word problems with multiple steps).

**Phase 3** — More subjects (English, Science, Hindi, Social Studies), more classes, more boards, evaluation dashboard, teacher marking scheme output.

Deliberately out of scope until there's a concrete need: microservices, Kubernetes, message queues, vector databases, multi-agent orchestration, fine-tuning, a full SPA frontend.
