# Project Plan

## Repository inspection (as of this plan)

The repository contained exactly one file: the master spec
(`Master Claude Code Prompt — AI Practice Paper Generator.md`). No code, no
dependencies, no sample paper, no git history. This plan and the other six
Phase 0 documents are the first commit.

**Consequence:** there are no existing components to reuse and no existing
conventions to follow. Every architectural choice below is a fresh decision,
made against the constraints in the spec (modular monolith, deterministic
where possible, small provider interfaces, no over-engineering).

## Golden dataset: received

The spec repeatedly (§29, §30, §33, §43-12) treats "the provided Class III
Mathematics paper" as the first golden test case. The photos are now in
`tests/fixtures/existing_paper/` (source: `C:\prepcraft\GoldenPaper`).

One correction to the spec's framing: this is **two separate exam
documents** photographed together, not one 4-page paper —

- `main_page_1.jpg` – `main_page_3.jpg`: Delhi World Public School, Noida
  Extension, Class III-A, Mathematics, 20 marks, 50 minutes, dated
  28-07-2026. Student "Abhyudhay", roll 006, scored 15/20 overall. Covers
  MCQs, predecessor/successor, Roman numerals, break-to-ten addition,
  ascending/descending Roman numeral ordering, column addition (Th/H/T/O
  grids), rounding/estimation, and multi-step word problems. Ends
  "END OF EXAMINATION" on page 3.
- `mental_maths_page_1.jpg`: a separate "Mental Maths" paper, same
  school/student/roll, 10 marks, 20 minutes, dated 29-07-2026. Short-answer
  number facts, tick-the-correct-option, and missing-digit column addition.
  Scored 8.5/10.

Both carry real annotation noise the spec describes: blue/graphite student
pencil-and-pen work, red teacher ink (ticks, crosses, circled per-question
scores, a "good" comment), roll number box, invigilator and checker
signatures, a school crest/header banner. This is good coverage for
Workflow A — it exercises annotation removal against two different papers'
worth of marking style from the same teacher, not just one.

They're stored as two golden fixtures, not one padded-out one:
`tests/fixtures/existing_paper/main/page_1-3.jpg` (20-mark paper) and
`tests/fixtures/existing_paper/mental_maths/page_1.jpg` (10-mark paper) —
so the pipeline and evaluation code never have to guess which pages belong
to which `Paper`.

## Risks and unknowns

1. **Handwriting/mark removal accuracy (spec §10)** — the hardest single
   component. Color-space thresholding alone will not reliably distinguish
   "printed black text" from "student pen that happens to be dark" under
   uneven scan lighting. Plan: build it as its own inspectable stage with a
   mask artifact, evaluate precision/recall of removal against the golden
   dataset (EVALUATION.md), and accept that MVP quality here will be
   "flag uncertain regions for the user to review," not "perfect automatic
   removal." The spec agrees (§31: "if annotation removal is uncertain, show
   the user the image").

2. **OCR quality on real scans.** Tesseract is free and offline but weak on
   noisy scans and handwriting-adjacent regions. The `OCRProvider`
   abstraction lets a cloud OCR/vision engine take over per-page when
   Tesseract's confidence is low, but that adds cost and an external
   dependency. Decision on which cloud engine (if any) is deferred to when
   real scan quality is known — i.e., after the golden dataset arrives.

3. **AI provider cost and latency.** Vision/text generation calls happen at
   several stages (annotation-uncertain OCR, question classification,
   question drafting). Framework config (`config.yaml`) should let each
   stage's model be tuned independently so cost can be controlled without
   code changes.

4. **PDF layout fidelity.** Reproducing "same overall structure and style"
   (spec §9-9) as the source paper in ReportLab is a real design task, not
   just a rendering task — tables, diagrams, multi-column layouts. MVP
   scopes this down to a single clean template (spec §22: "Simple practice
   paper") rather than attempting to mimic arbitrary source layouts; layout
   cloning is a Phase 3+ concern.

5. **Answer correctness is only as good as the template's
   `answer_expression`.** The validator recomputes answers from the
   structured model, not from the LLM's stated answer — but if a template's
   expression is wrong, validation will consistently pass a wrong answer.
   Mitigation: unit test every question template's answer expression against
   known cases (spec §34).

6. **Curriculum accuracy for "age-appropriate advanced" (spec §17-7).**
   There's no curriculum reference data in the repo. MVP hard-codes
   difficulty bounds per topic for Class III Mathematics based on the golden
   paper and common CBSE material; this is a known simplification the
   architecture must not calcify — see DATA_MODEL.md's `difficulty_range`
   design.

## What's deterministic vs. AI

Deterministic (no model call, same input -> same output, unit-testable):

- Image geometry: rotation, perspective correction, deskew, lighting
  normalization (OpenCV)
- Color-space separation for candidate annotation regions (HSV/LAB
  thresholds, morphology, connected components)
- Roman numeral conversion, arithmetic evaluation, rounding, predecessor/
  successor — anywhere the spec gives a formula
- Answer computation from a question template's `answer_expression`
- Validation: recomputing every answer, checking blueprint compliance
  (marks/question counts add up), duplicate detection, options-contain-
  answer checks
- PDF rendering from validated structured data

AI-assisted (a `VisionProvider`/`TextGenerationProvider` call, non-
deterministic, evaluated for quality not correctness):

- Distinguishing printed vs. handwritten content in ambiguous regions the
  color-space heuristics can't resolve confidently
- OCR fallback for low-confidence regions
- Classifying question type, topic, and cognitive level from extracted text
- Drafting new question text from a template (values are still generated and
  computed by code — see spec §14, the LLM never does the arithmetic)
- Chapter concept/example/exercise extraction from OCR'd textbook text

Every AI call sits behind a small provider interface (ARCHITECTURE.md) and
every one of its outputs is either validated deterministically before use
(question drafts) or surfaced to the user for review (annotation removal
uncertainty, low-confidence OCR) rather than trusted outright — per spec §31
and §45.

## MVP definition

Workflow A only. Scope:

- Input: image or PDF, one paper at a time
- Subject: Mathematics. Class: III.
- Question types: multiple choice, fill-in-the-blank, arithmetic, Roman
  numerals, predecessor/successor, rounding, addition word problems, mental
  maths (spec §32 list, trimmed to types with a clear deterministic answer
  check — "short answer" and "match the following" need free-text or
  matching validation that's out of scope for MVP)
- Interface: CLI only (spec §37) — every stage runnable and inspectable
  independently
- Output: question paper PDF + answer sheet PDF
- Human-in-the-loop: not a UI review screen yet, but every stage's artifact
  is written to disk under `data/processed/<run_id>/` for inspection (spec
  §9's `01_original.png` ... `09_questions.json` list)

## First end-to-end demo

1. `python -m app ingest-paper data/samples/<golden_paper>.pdf` — loads
   pages, detects boundaries, writes `01_original.png`,
   `02_document_detected.png`.
2. `python -m app clean-paper <run_id>` — perspective/lighting correction,
   annotation mask + removal, writes `03_perspective_corrected.png` through
   `06_cleaned.png`.
3. `python -m app extract-questions <run_id>` — OCR + layout analysis +
   question extraction, writes `07_ocr.json`, `08_layout.json`,
   `09_questions.json`.
4. `python -m app generate-paper --source <run_id> --difficulty 2` — builds
   a blueprint from the extracted structure, generates candidate questions
   with new values, computes answers.
5. `python -m app validate-paper <generated_id>` — recomputes every answer,
   checks blueprint compliance; fails loudly if anything doesn't check out.
6. `python -m app render-paper <generated_id>` — writes
   `question_paper.pdf` and `answer_sheet.pdf` to `data/generated/`.

Each command prints the observability output from spec §38
(`[n/8] stage name`, `✓`/`✗` per check) and exits non-zero on validation
failure rather than silently producing a bad PDF.

## Phase-by-phase build order

Following spec §42, with acceptance criteria per phase so "done" is
checkable, not a feeling:

| Phase | Deliverable | Done when |
|---|---|---|
| 0 | This plan + 6 docs | This commit exists, user has approved |
| 1 | Project skeleton: venv, deps, lint/format, pytest, logging, config, CLI stub | `python -m app --help` runs; `pytest` runs (0 tests, 0 errors) |
| 2 | Ingestion: `PaperInput`, `ImageLoader`, `PageDetector` | Golden paper's 4 pages load and boundaries detect; artifacts written |
| 3 | Image cleaning: perspective, enhancement, annotation mask + removal | Cleaned golden paper preserves printed text (manual check) and removes obvious student/teacher marks |
| 4 | OCR + question extraction | `09_questions.json` for golden paper matches `tests/fixtures/expected/questions.json` within the accuracy bar set in EVALUATION.md |
| 5 | Structured question models (Pydantic) | Every extracted question round-trips through the model without data loss |
| 6 | Question validation | Validator catches a deliberately-broken fixture (wrong answer, marks mismatch) in a unit test |
| 7 | Question generation | Generated paper from golden source has new values, same structure, answers computed by code |
| 8 | Paper blueprint | Blueprint from golden paper's structure is satisfied by generated paper |
| 9 | PDF generation | `question_paper.pdf` renders and opens |
| 10 | Answer sheet generation | `answer_sheet.pdf` matches generated paper's questions 1:1 |
| 11 | Basic UI | Wizard flow from spec §23 works end-to-end in a browser for Workflow A |
| 12 | Chapter ingestion (Workflow B) | `chapter.json` produced from a sample set of textbook photos |
| 13 | Difficulty controls | Difficulty engine (spec §16) produces measurably different question sets at levels 1 vs 5 |
| 14 | Evaluation dashboard | Metrics from EVALUATION.md computed and viewable, not just logged |

Phases 2-10 constitute the MVP (spec §32-33). Phases 11-14 are Phase 2/3 of
the roadmap (README.md).

## Immediate next step

Waiting on: (a) approval of this plan, (b) the golden Class III Mathematics
paper. Phase 1 (skeleton) can start on approval alone; Phase 2 needs the
paper.
