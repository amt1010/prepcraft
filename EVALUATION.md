# Evaluation

No accuracy claim ships without a number behind it (spec §29, §45). This
document defines what's measured at each stage, against what reference, and
how it gets worse or better over time.

## Golden dataset

```
tests/fixtures/
    existing_paper/
        main/
            page_1.jpg
            page_2.jpg
            page_3.jpg
        mental_maths/
            page_1.jpg
    expected/
        main/
            cleaned_page_1.png
            ...
            questions.json
            answer_key.json
        mental_maths/
            cleaned_page_1.png
            questions.json
            answer_key.json
```

Source: two real Delhi World Public School, Noida Extension, Class III-A
Mathematics papers (see PROJECT_PLAN.md for the full description — a
20-mark main paper and a separate 10-mark Mental Maths paper, same
student, both with real student pencil/pen work and teacher red-pen
marking). Raw images are in the repo under `existing_paper/`. Still to do,
per document, before metrics are meaningful:

1. Manually produce `expected/<doc>/cleaned_page_*.png` (hand-clean each
   page in an image editor — this is the ground truth AnnotationRemover is
   graded against).
2. Manually transcribe `expected/<doc>/questions.json` against the
   `Question` model in DATA_MODEL.md — every question, its type, marks,
   topic, expected answer. Use the printed question text and the school's
   own mark scheme (visible in the red circled per-question scores), not
   the student's handwritten answer.
3. Derive `expected/<doc>/answer_key.json` from `questions.json`.

This is a regression fixture, not a training set: it never changes once
established, except by deliberate, reviewed update when the paper itself
was mistranscribed. Every pipeline change re-runs against it
(`pytest tests/e2e`) and the metrics below are compared to the previous
commit's numbers, not just checked against a fixed threshold — a metric
that quietly regresses 5% per commit is as bad as one that fails outright.

## Metrics per stage

| Stage | Metric | Computed as | Reference |
|---|---|---|---|
| OCR | Character accuracy | 1 - (Levenshtein distance / reference length), per page | Hand-transcribed text per page |
| OCR | Word accuracy | Exact word match rate after tokenization | Hand-transcribed text per page |
| Annotation removal | Mask precision/recall | Compare `05_annotation_mask.png` against a hand-labeled mask (pixels correctly flagged as annotation vs. printed) | Hand-labeled mask |
| Annotation removal | Printed-content preservation | SSIM between `06_cleaned.png` and `expected/cleaned_page_N.png`, restricted to printed-text bounding boxes | `expected/cleaned_page_*.png` |
| Question extraction | Extraction recall | (questions correctly extracted) / (questions in `expected/questions.json`) | `expected/questions.json` |
| Question extraction | Field accuracy | Per-field exact/near match rate: type, marks, question_number | `expected/questions.json` |
| Question classification | Topic accuracy | Exact match rate against expected topic | `expected/questions.json` |
| Question classification | Difficulty accuracy | Within ±1 of expected level (spec's 5-level scale is coarse; exact match is too strict a bar) | `expected/questions.json` |
| Generated question validity | Validator pass rate | (candidates passing validation) / (candidates generated) | N/A — measures generation quality, not correctness against a fixture |
| Answer correctness | Recomputation match rate | (answers where validator's independent computation matches template's stated answer) / (total) — **must be 100%**; anything less means a template bug, not a tolerance to tune | N/A |
| Difficulty accuracy (generated) | Requested-vs-delivered level match | Compare `DifficultyFeatures.score()` of generated questions against the blueprint's requested `difficulty_level` | N/A |
| Blueprint compliance | Section/marks/count match rate | (generated paper's sections match blueprint exactly) — **must be 100%**; partial compliance means don't render, per spec §21 | N/A |
| PDF rendering | Structural correctness | Automated check: page count reasonable, every question_id in `Paper` appears exactly once in the rendered PDF's text layer, total marks printed matches `Paper.total_marks` | Generated `Paper` model |

Two rows above are marked "must be 100%" deliberately: answer correctness
and blueprint compliance are not statistical quality metrics, they're
correctness gates. Spec §21's example (47+25 validator must compute 72, not
accept 73) means a sub-100% pass rate here is a bug, and the validator's
job is specifically to make sure a wrong answer never reaches a PDF — so
this number should always read 100% in CI, and a drop means stop and fix,
not "acceptable variance."

## How results are surfaced

`python -m app evaluate --dataset golden` runs the full pipeline against
the golden dataset and writes `evaluation_results` rows (see
DATA_MODEL.md) plus a human-readable summary:

```
OCR character accuracy:        94.2%  (prev: 93.8%)
Annotation mask precision:     88.1%  (prev: n/a — first run)
Annotation mask recall:        91.4%  (prev: n/a)
Question extraction recall:    11/12  (prev: n/a)
Answer recomputation match:    100%   (prev: n/a)
Blueprint compliance:          100%   (prev: n/a)
```

Phase 14 (evaluation dashboard, PROJECT_PLAN.md) turns this into a
browsable view over `evaluation_results` history instead of a CLI printout,
once there's enough run history for a trend to be worth looking at.

## What "MVP successful" means quantitatively

Restating spec §44's success criteria as numbers this framework can check:

- OCR character accuracy ≥ 90% on the golden paper
- Annotation mask precision ≥ 85%, recall ≥ 85% (favor precision if forced
  to choose — a missed mark the user can still see and object to; a wrongly
  removed printed character is silently wrong)
- Question extraction recall ≥ 90% on the golden paper's question count
- Answer recomputation match = 100% (gate, not target)
- Blueprint compliance = 100% (gate, not target)
- PDF renders and opens without manual repair

These thresholds are starting points based on what "reasonable accuracy"
(spec §44) should mean for a first MVP, not measured values — there's
nothing to measure them against yet without the golden paper. Revisit once
real numbers come in from the first `evaluate` run.
