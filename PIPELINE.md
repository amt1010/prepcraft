# Pipeline

Two entry points, converging on the same generation/validation/rendering
tail.

## Workflow A: existing paper -> new paper

```
PaperInput
    |  ImageLoader          load PDF/JPG/PNG/camera image into page images
    v
Pages
    |  PageDetector         find paper boundary in each page
    v
DetectedPages
    |  QualityGate          measure skew angle + blur/sharpness; flag pages
    |                       that shouldn't be auto-processed (see below)
    v
DetectedPages + QualityReport
    |  PerspectiveCorrector fix rotation/perspective/skew
    v
CorrectedPages
    |  ImageEnhancer        fix lighting, shadows, background noise
    v
EnhancedPages
    |  AnnotationDetector   classify pixels: printed vs. handwritten/marked
    v
AnnotationMasks
    |  AnnotationRemover    remove masked regions, inpaint background
    v
CleanPaper
    |  OCR                  extract text (Tesseract, cloud fallback on low confidence)
    v
OCRResult
    |  LayoutAnalysis       group text into questions/sections by position + numbering
    v
LayoutModel
    |  QuestionExtraction   classify each item: type, marks, topic, difficulty
    v
QuestionModel (list[Question] + Paper)
```

Then shared tail (below).

## Workflow B: chapter -> new paper

```
Chapter photos (10-30 images)
    |  ImageLoader + ImageEnhancer   same deskew/lighting correction as Workflow A
    v
Enhanced pages
    |  OCR
    v
OCRResult
    |  Page ordering                 sequence pages (filename hints + content continuity)
    v
Ordered OCR text
    |  Chapter detection             identify chapter title/boundaries
    |  Concept extraction
    |  Learning objective extraction
    |  Example extraction
    |  Exercise extraction
    v
Chapter (structured, see DATA_MODEL.md)
    |  User selects: subject, class, chapter(s), question count, marks,
    |  duration, question types, difficulty
    v
PaperBlueprint
```

Then shared tail (below), starting from blueprint generation instead of
blueprint-from-extracted-structure.

## Shared tail: blueprint -> PDF

```
PaperBlueprint  (from extracted structure, Workflow A; or from user
                 selection, Workflow B)
    |  Template selection      pick QuestionTemplates matching blueprint's
    |                          topics/types/difficulty_range
    |  Variable sampling       generate new values per template's variable spec
    |  Answer computation      evaluate answer_expression in code
    v
Candidate questions (list[Question], source="generated")
    |  Validator               recompute every answer independently; check
    |                          blueprint compliance, duplicates, options
    |                          contain answer, no leakage
    v
Validated questions  --[any failure]--> regenerate candidate or flag for user review
    |
    v
Paper (assembled, source="generated") + AnswerKey (built from Paper, not
                                                      regenerated)
    |  PDF Renderer (ReportLab, template-based, deterministic)
    v
question_paper.pdf + answer_sheet.pdf (+ teacher_marking_scheme.pdf, optional)
```

**Where the LLM is and isn't in this tail:** template selection and
variable sampling can involve an LLM call to draft `text_template` phrasing
for a new question (spec §14 step 5), but variable *values* are sampled by
code against the template's `variables` spec, and the *answer* is always
computed by evaluating `answer_expression` in code — never asked of the
model. See PROJECT_PLAN.md "What's deterministic vs. AI" for the full
split.

## Artifacts per run

Every stage writes its output to `data/processed/<run_id>/`, numbered in
pipeline order, exactly as spec §9 specifies:

```
01_original.png
02_document_detected.png
02b_quality_report.json
03_perspective_corrected.png
04_enhanced.png
05_annotation_mask.png
06_cleaned.png
07_ocr.json
08_layout.json
09_questions.json
```

Generation/validation/rendering artifacts continue the sequence:

```
10_blueprint.json
11_candidates.json
12_validation_report.json
13_paper.json
14_answer_key.json
question_paper.pdf
answer_sheet.pdf
```

The original input file is never modified in place — `01_original.png` is a
copy/conversion of the input, not a pointer to it, so a bug anywhere
downstream can never corrupt the user's source paper.

## Image quality gate

Added stage, between `PageDetector` and `PerspectiveCorrector`. Before any
correction is attempted, measure two things on the detected page region:

- **Skew severity** — the rotation angle `PerspectiveCorrector` would need
  to apply, as a percentage of the configured maximum tolerable rotation
  (`quality.max_skew_degrees` in `config.yaml`, default **20°**, i.e. a page
  needing more than 20° of correction fails this check).
- **Sharpness** — a Laplacian-variance blur score (`quality.min_sharpness`,
  default tuned against a deliberately-blurred fixture once one exists);
  below the threshold, the page is too blurry for OCR to be reliable
  regardless of correction.

Both thresholds are `config.yaml` values, not hard-coded, since "acceptable"
depends on the phone/scanner mix real users bring — expect to retune once
usage data exists.

`QualityGate` writes `02b_quality_report.json` per page:

```json
{
  "page": 1,
  "skew_degrees": 4.2,
  "skew_within_tolerance": true,
  "sharpness_score": 812.4,
  "sharpness_acceptable": true,
  "verdict": "pass"
}
```

`verdict` is `"pass"`, `"flagged"` (one metric outside tolerance — pipeline
continues, but the page is marked for user review before it's trusted), or
`"fail"` (skew or blur severe enough that correction/OCR would likely
produce garbage — pipeline stops for this page and asks the user to
re-capture it, per spec §31's "never silently accept" rule). A `fail`
never proceeds to `PerspectiveCorrector` automatically; a `flagged` page
proceeds but its downstream artifacts carry a `low_confidence: true` note
so the eventual review screen highlights it.

## Annotation removal detail (spec §10 — the hard part)

`AnnotationDetector` doesn't use a single technique; it combines signals and
only removes a region when confidence is high, otherwise flags it:

1. **Color-space candidates:** convert to HSV and LAB, threshold for
   red/blue/green ink ranges and graphite-gray pencil ranges, separately
   from "printed black/dark-gray text" ranges calibrated from the paper's
   own printed-header region (self-calibrating per scan, since lighting
   varies).
2. **Stroke/shape filtering:** connected-component analysis on candidate
   regions — handwriting strokes have different width variance and
   curvature statistics than printed glyphs at the same DPI. Discard
   candidates that look printed.
3. **Layout awareness:** candidates inside the printed question's expected
   answer-blank/margin region are weighted toward "remove"; candidates
   overlapping printed glyph bounding boxes are weighted toward "keep,
   flag" rather than auto-removed, since a false removal (deleting part of
   a printed question) is worse than a false keep (leaving a mark behind
   for the user to see and remove manually).
4. **Vision model assist:** for regions where steps 1-3 disagree or
   confidence is below threshold, crop the region and ask
   `VisionProvider.analyze_region` "is this printed text or a handwritten
   mark" as a targeted, cheap, structured-output call — not a
   whole-page redraw.
5. **Inpainting:** approved-for-removal regions are filled using OpenCV
   inpainting against the local background, not deleted to blank/white,
   so paper texture and printed borders that partially underlap a mark stay
   visually consistent.

Output is always three artifacts, never just the cleaned image (spec §10):
`original`, `05_annotation_mask.png` (what was identified, visually), and
`06_cleaned.png` (result). The mask is what a human reviews when removal
quality is in doubt.

## Failure handling

Every stage function can raise a typed exception (`StageError` subtypes per
module). The CLI orchestrator catches these, writes the error into that
stage's `ProcessingRun` row (spec §27), prints `[n/8] stage name ✗ <reason>`,
and stops the pipeline rather than passing a partial/garbage artifact to the
next stage. Nothing downstream of a failed stage runs. This is what makes
"failures recoverable and debuggable" (spec's engineering philosophy) concrete
rather than aspirational: the run's artifact directory shows exactly how far
processing got and what the input to the failing stage looked like.
