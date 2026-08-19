# Architecture

## Style: modular monolith

One Python process, one deployable, clear module boundaries enforced by
convention (and later, import-linter if it becomes necessary — not before).
No microservices, no message queue, no service mesh. Spec §6, §39 are
explicit about this and the reasoning holds: a solo/small-team project
building a linear pipeline gets nothing from network boundaries between
"OCR" and "question extraction" except latency and deployment complexity.

## Module map

```
app/backend/
    core/          config, logging, run-ID allocation — no pipeline logic
    models/        Pydantic models shared across modules (Paper, Question, ...)
    providers/     VisionProvider, TextGenerationProvider, OCRProvider interfaces + impls
    ingestion/     PaperInput -> ImageLoader -> PageDetector
    preprocessing/ PerspectiveCorrector, ImageEnhancer, AnnotationDetector, AnnotationRemover
    ocr/           OCR orchestration (calls providers.ocr), LayoutAnalysis
    document/      Document understanding: subject/class/topic/difficulty inference
    questions/     QuestionExtraction, QuestionTemplate model + registry
    blueprint/     PaperBlueprint derivation (Workflow A) + blueprint-driven template selection
    knowledge/     Chapter knowledge extraction (Workflow B only)
    generation/    Candidate generation from templates, value sampling
    validation/    Answer recomputation, blueprint compliance, dedup, leakage checks
    rendering/     PDF templates + ReportLab renderer
    storage/       SQLAlchemy models, filesystem artifact read/write
    api/           FastAPI routes (Phase 11) — thin, calls into the modules above
```

**Dependency direction:** `core` and `models` have no dependents' knowledge
of them going the other way — everything depends on `models`, nothing in
`models` imports from a pipeline module. `providers` is depended on by
`preprocessing`, `ocr`, `document`, `generation` — never the reverse.
`rendering` depends only on `models` (validated data in, PDF out) — it must
never import from `providers`, `generation`, or anything upstream of
validation. That's the concrete form of spec §22's "the renderer should
never need to understand the original LLM output."

Each module is a handful of small files, not one big `service.py`. E.g.
`preprocessing/` is `perspective.py`, `enhancement.py`,
`annotation_detector.py`, `annotation_remover.py` — each independently
testable and independently swappable.

## Pipeline as explicit function composition

The pipeline (PIPELINE.md) is not a framework or a DAG engine — it's a
sequence of functions, each taking and returning a Pydantic model or a
`pathlib.Path` to an artifact, called in order by a thin orchestrator in
`core/run.py`. Example shape:

```python
def run_ingestion_and_cleaning(paper_input: PaperInput, run_id: str) -> CleanPaper:
    pages = ImageLoader.load(paper_input)
    detected = [PageDetector.detect(p) for p in pages]
    corrected = [PerspectiveCorrector.correct(p) for p in detected]
    enhanced = [ImageEnhancer.enhance(p) for p in corrected]
    masks = [AnnotationDetector.detect(p) for p in enhanced]
    cleaned = [AnnotationRemover.remove(p, m) for p, m in zip(enhanced, masks)]
    ArtifactStore.save_stage(run_id, "06_cleaned", cleaned)
    return CleanPaper(pages=cleaned, run_id=run_id)
```

Every stage function is pure with respect to its typed input/output;
side-effecting artifact writes happen at the orchestrator level via
`ArtifactStore`, not scattered inside stage functions. This is what makes
each stage independently unit-testable (spec §34) and independently runnable
from the CLI (spec §37) — a CLI command is just "load the input this stage
needs from the last run's artifacts, call the function, save the output."

## Provider interfaces

Kept deliberately tiny — one method each, one job:

```python
class VisionProvider(Protocol):
    def analyze_region(self, image: bytes, prompt: str) -> VisionResult: ...

class TextGenerationProvider(Protocol):
    def generate(self, prompt: str, schema: type[BaseModel]) -> BaseModel: ...

class OCRProvider(Protocol):
    def extract_text(self, image: bytes) -> OCRResult: ...
```

`TextGenerationProvider.generate` takes a Pydantic model class and returns
an instance of it (structured output / tool-use under the hood) — nothing
downstream ever parses free-text LLM output by hand. Concrete
implementations (`ClaudeVisionProvider`, `TesseractOCRProvider`, etc.) live
in `providers/`, selected by `config.yaml`. Swapping providers is a config
change, not a code change, per spec §8.

No "AI framework," no agent loop, no orchestration library. A provider call
is a function call that returns a typed object or raises.

## Model choice per pipeline stage

The four AI call sites in the pipeline (PROJECT_PLAN.md's "what's
deterministic vs. AI" table) split into two different kinds of task, and
they don't need the same model:

| Call site | Kind of task | Model |
|---|---|---|
| Annotation region check ("printed or handwritten?") | Perception on a small image crop | `claude-haiku-4-5` |
| OCR fallback (transcribe low-confidence crop) | Perception on a small image crop | `claude-haiku-4-5` |
| Question classification (topic/type/difficulty) | Judgment over extracted text | `claude-sonnet-5` |
| Question generation (draft new question text) | Judgment + generation | `claude-sonnet-5` |

The first two are cheap, high-volume, narrow classification calls on a
small crop — Haiku is accurate enough and meaningfully cheaper per call.
The last two need actual reasoning about curriculum, topic, and phrasing —
worth Sonnet's cost. This is a `config.yaml` setting per stage
(`models.annotation_vision`, `models.ocr_fallback`,
`models.question_classification`, `models.question_generation`), not a
single global `ai_model` — swapping one stage to a different model (e.g.
trying Haiku for classification once there's an accuracy baseline to test
against, per EVALUATION.md) never touches the others. Every provider call
still goes through the same `VisionProvider`/`TextGenerationProvider`
interface regardless of which model backs a given stage — the provider
doesn't know or care that different stages ask for different models.

## Storage design

SQLite via SQLAlchemy for structured records (see DATA_MODEL.md for the
table list). Binary artifacts (images, PDFs, JSON snapshots) go on the
filesystem under `data/processed/<run_id>/` and `data/generated/<paper_id>/`,
with the DB row holding the path, not the bytes. This keeps the DB small and
the artifacts trivially inspectable with a file browser — no BLOB
extraction step needed to debug a run. `storage/artifact_store.py` is the
only module that knows the on-disk layout; a later move to object storage
(spec §26) means changing that one file's implementation, not every caller.

## Stack rationale

- **FastAPI over Flask/Django:** Pydantic-native request/response models,
  which matters here because Pydantic models are already the system's
  lingua franca — no second serialization layer.
- **ReportLab over HTML-to-PDF:** direct control over layout without a
  headless-browser dependency; PDF generation is deterministic template
  code, not a rendering pipeline of its own.
- **Tesseract as OCR baseline, not the only OCR:** free, offline, good
  enough for clean printed text (most of the page once annotations are
  removed); the `OCRProvider` swap point exists specifically because
  handwriting-adjacent regions will need something stronger, and which
  engine that should be is an open question until real scans are tested
  (PROJECT_PLAN.md, risk 2).
- **SQLite over Postgres for MVP:** single-process, zero ops, matches
  spec §26. Move to Postgres if/when multi-user concurrent access is
  actually needed — not before.
- **Server-rendered wizard (FastAPI+Jinja2/HTMX) over a SPA for the
  eventual UI:** the UI is a linear 7-8 step wizard (spec §23), not an
  app with complex client state. A SPA framework buys nothing here and
  costs a build pipeline, a second dependency tree, and a second set of
  conventions.

## What this architecture explicitly avoids

Per spec §39 and §41: no Kubernetes, no microservices, no Kafka/queues, no
Redis cluster, no vector database (no semantic search requirement exists
yet), no multi-agent framework (every AI call here is a single
request/response, not an agent with tools and a loop), no fine-tuning, no
SPA framework until the wizard genuinely needs one.
