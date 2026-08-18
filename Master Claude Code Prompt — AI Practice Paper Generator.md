# PROJECT: AI Practice Paper Generator

You are the lead software architect and implementation engineer for this project.

I want to build a production-quality application that can ingest real school question papers and textbook/chapter content, understand their structure and difficulty, clean handwritten student/teacher annotations from scanned papers, generate new practice papers with equivalent structure and adjustable difficulty, and produce both the question paper and answer sheet as PDF.

The application should be simple, maintainable, testable, inspectable, and easy for another developer to understand.

Follow an engineering philosophy inspired by Andrej Karpathy:

- Keep the system simple.
- Prefer explicit pipelines over complicated abstractions.
- Build small understandable components.
- Make intermediate outputs visible.
- Avoid unnecessary frameworks.
- Avoid premature microservices.
- Prefer deterministic processing where possible.
- Use AI/LLMs only where they add real value.
- Separate data, processing, generation, validation and presentation.
- Build evaluation into the system from the beginning.
- Every important transformation should be inspectable.
- Do not hide important logic behind large generic helper classes.
- Favor readable Python/TypeScript over clever code.
- Write tests for important transformations.
- Log every pipeline stage.
- Make failures recoverable and debuggable.

---

# 1. PRODUCT VISION

The application will help parents and teachers create customized practice papers from real school material.

There are TWO major input workflows.

## WORKFLOW A — RECREATE / VARIATE AN EXISTING PAPER

Input:

A real question paper, potentially containing:

- Printed questions
- Student handwritten answers
- Pencil markings
- Teacher corrections
- Red-pen markings
- Scores
- Tick marks
- Cross marks
- Circles
- Comments
- Signatures
- Other annotations

The system should:

1. Ingest the paper using:
   - PDF
   - JPG
   - PNG
   - Camera image

2. Detect the paper boundaries.

3. Correct:
   - Rotation
   - Perspective
   - Skew
   - Uneven lighting
   - Shadows
   - Background noise

4. Identify printed content versus handwritten content.

5. Remove:
   - Student pencil writing
   - Student pen writing
   - Teacher red-pen corrections
   - Tick marks
   - Cross marks
   - Circles
   - Scores
   - Handwritten comments
   - The School Name from the paper header

6. Preserve:
   - Printed questions
   - Printed tables
   - Printed borders
   - Printed diagrams
   - Printed headings
   - Printed instructions
   - Printed school information

7. Extract the paper structure.

8. Understand:
   - Subject
   - Class/standard
   - Chapter/topic
   - Question types
   - Marks
   - Number of questions
   - Difficulty
   - Expected answer type
   - Cognitive level
   - Question sequence
   - Distribution of topics

9. Generate a new paper with:
   - Same overall structure (do not include School Name on the page Header) Call it as Sample paper and below it mention the subject name and Class/standard
   - Same style
   - Same marks distribution
   - Same approximate difficulty
   - New values
   - New questions where appropriate
   - No copying of student answers
   - No teacher markings

10. Generate:
   - Clean question paper PDF
   - Answer sheet PDF
   - Optional teacher marking scheme

---

# 2. WORKFLOW B — CHAPTER → PRACTICE PAPER

The second workflow starts from educational content rather than an existing test paper.

Parents/teachers should be able to capture textbook/chapter content using a phone camera.

Example:

Subject:
Mathematics

Class:
III

Chapter:
Addition

Input:
10–30 photographs of textbook pages.

The application should:

1. Ingest images.

2. Clean and deskew them.

3. OCR the content.

4. Identify:
   - Chapter title
   - Concepts
   - Definitions
   - Examples
   - Worked examples
   - Rules
   - Formulae
   - Exercises
   - Important terminology
   - Diagrams
   - Learning objectives

5. Build a structured chapter knowledge representation.

6. Allow the teacher/parent to select:

   Subject
   Class
   Chapter(s)
   Number of questions
   Total marks
   Duration
   Question types
   Difficulty

7. Difficulty should be adjustable.

Use a simple scale initially:

   Level 1 — Easy
   Level 2 — Standard
   Level 3 — Moderate
   Level 4 — Challenging
   Level 5 — Advanced

For Class III, the system must remain age appropriate.

Do not assume that "advanced" means university-level mathematics.

Advanced should mean challenging within the expected curriculum.

8. Generate the paper.

9. Generate the answer sheet.

10. Validate the generated paper before PDF generation.

---

# 3. CORE PRODUCT CONCEPT

The application should be organized around:

SUBJECT
   ↓
CLASS / STANDARD
   ↓
CHAPTERS
   ↓
SOURCE MATERIAL
   ↓
KNOWLEDGE
   ↓
QUESTION BANK
   ↓
PAPER TEMPLATE
   ↓
PAPER GENERATION
   ↓
VALIDATION
   ↓
PDF
   ↓
ANSWER SHEET

The UI should reflect this pipeline.

Do NOT create a complicated enterprise dashboard.

The primary navigation should be something like:

Home

├── Subjects
│   ├── Mathematics
│   ├── English
│   ├── Science
│   └── Other
│
├── Classes
│   ├── Class I
│   ├── Class II
│   ├── Class III
│   └── ...
│
├── Source Papers
│
├── Chapters
│
├── Question Bank
│
├── Generate Paper
│
└── Generated Papers

---

# 4. FIRST TASK — DO NOT START CODING THE ENTIRE APPLICATION

Before implementing the application, inspect the repository and produce a detailed implementation plan.

The first deliverables must be:

1. README.md
2. PROJECT_PLAN.md
3. ARCHITECTURE.md
4. DATA_MODEL.md
5. PIPELINE.md
6. EVALUATION.md
7. TODO.md

These documents should be created BEFORE substantial implementation.

The README should explain the project to a developer who has never seen it before.

Do not create meaningless boilerplate documentation.

---

# 5. README.md REQUIREMENTS

README.md should contain:

## Project name

Choose a clean working name such as:

AI Practice Paper Generator

Do not over-engineer the branding yet.

## Problem

Explain that parents and teachers currently have to manually:

- Scan papers
- Remove handwritten answers
- Find questions
- Create new questions
- Maintain difficulty
- Format papers
- Create answer sheets

The application automates this workflow.

## Features

Clearly distinguish:

### Existing Paper → New Paper

and

### Chapter Material → New Paper

## Architecture overview

Show a simple ASCII pipeline.

Example:

Camera / PDF / Image
        ↓
Document Ingestion
        ↓
Image Cleanup
        ↓
OCR / Vision
        ↓
Document Understanding
        ↓
Structured Question Model
        ↓
Question Bank
        ↓
Paper Generator
        ↓
Validator
        ↓
PDF Renderer
        ↓
Question Paper + Answer Sheet

## Technology stack

Document the actual selected stack.

Do not invent technologies before evaluating them.

## Local development

Explain exactly how to run the project.

## Testing

Explain how tests are run.

## Project structure

Explain every major directory.

## Roadmap

Separate:

MVP
Phase 2
Phase 3

---

# 6. ARCHITECTURE PRINCIPLE

Use a modular monolith initially.

DO NOT build microservices.

The application should have clear modules:

1. ingestion
2. preprocessing
3. OCR
4. document understanding
5. question extraction
6. knowledge extraction
7. question generation
8. validation
9. paper assembly
10. PDF rendering
11. storage
12. UI

Each module should have a small, explicit responsibility.

---

# 7. RECOMMENDED INITIAL TECHNOLOGY DIRECTION

Evaluate the best practical stack, but strongly consider:

Backend:

Python

FastAPI

Pydantic

OpenCV

Pillow

NumPy

OCR engine abstraction

LLM/Vision model abstraction

ReportLab or another reliable PDF generation library

SQLite for initial development

SQLAlchemy if persistence is needed

Frontend:

Use a lightweight web UI.

Prefer React/Next.js only if it genuinely improves the experience.

Do not introduce a large frontend architecture unnecessarily.

The application must work well on:

Desktop

Tablet

Mobile browser

The mobile workflow should support camera uploads.

---

# 8. IMPORTANT — AI MODEL ABSTRACTION

Do NOT hard-code the application around one AI provider.

Create a small provider interface.

For example:

VisionProvider

TextGenerationProvider

EmbeddingProvider

But keep these interfaces extremely small.

The application should allow future providers such as:

Claude

OpenAI

Gemini

Local models

Do not create a massive "AI framework".

---

# 9. PAPER INGESTION PIPELINE

Create an explicit pipeline:

PaperInput
   ↓
ImageLoader
   ↓
PageDetector
   ↓
PerspectiveCorrector
   ↓
ImageEnhancer
   ↓
AnnotationDetector
   ↓
AnnotationRemover
   ↓
CleanPaper
   ↓
OCR
   ↓
LayoutAnalysis
   ↓
QuestionExtraction
   ↓
QuestionModel

Each stage should produce an inspectable artifact.

For example:

01_original.png

02_document_detected.png

03_perspective_corrected.png

04_enhanced.png

05_annotation_mask.png

06_cleaned.png

07_ocr.json

08_layout.json

09_questions.json

This is extremely important.

The user must be able to debug why a paper was processed incorrectly.

---

# 10. HANDWRITING / TEACHER MARK REMOVAL

This is one of the hardest parts.

Do NOT assume that simple color thresholding will solve it.

Build this as a dedicated image-processing pipeline.

The system should attempt to identify:

- Blue/black student ink
- Pencil
- Red teacher ink
- Green ink
- Other annotation colors

Use a combination of:

- Color-space analysis
- HSV/LAB separation
- Stroke detection
- Morphological operations
- Connected components
- OCR
- Layout awareness
- Vision model assistance where required

CRITICAL:

Printed text must not be accidentally removed.

For example:

Printed:

"47 + 25 = ______"

Student writes:

"72"

Teacher writes:

✓

The output should preserve:

"47 + 25 = ______"

and remove:

"72"

and:

"✓"

The system should create an annotation mask.

Never directly modify the original input.

Always retain:

original image

cleaned image

mask

---

# 11. DO NOT USE GENERATIVE IMAGE CREATION FOR DOCUMENT RECONSTRUCTION BY DEFAULT

For exam papers, accuracy matters more than artistic quality.

Do NOT use an image-generation model to redraw an entire paper.

Use deterministic image processing and document reconstruction.

Generative AI may be used for:

- Understanding questions
- Extracting structure
- Generating new questions
- Classifying difficulty
- Understanding textbook content

But the actual paper rendering should be deterministic.

This prevents:

- Changed numbers
- Incorrect symbols
- Altered diagrams
- Misspelled words
- Fake school logos
- Changed mathematical notation

---

# 12. DOCUMENT UNDERSTANDING

Convert an existing paper into structured JSON.

Create a canonical model.

Example:

Paper:

{
  "subject": "Mathematics",
  "class": "III",
  "total_marks": 20,
  "duration_minutes": 50,
  "sections": [...]
}

Question:

{
  "id": "...",
  "question_number": "1a",
  "type": "multiple_choice",
  "text": "...",
  "options": [...],
  "marks": 0.5,
  "topic": "Addition",
  "difficulty": 2,
  "expected_answer": "...",
  "answer_type": "numeric",
  "source": "existing_paper"
}

Use Pydantic models.

Do not pass uncontrolled dictionaries throughout the application.

---

# 13. QUESTION TYPES

The initial system should support:

Multiple choice

Fill in the blanks

True/False

Predecessor/successor

Roman numerals

Arithmetic

Column addition/subtraction

Word problems

Estimation

Rounding

Match the following

Short answer

Mental maths

Diagram-based questions where feasible

Do not attempt every possible question type in MVP.

Start with the question types that can be validated reliably.

---

# 14. QUESTION GENERATION

Question generation must NOT simply ask an LLM:

"Create a maths paper."

Instead:

1. Understand curriculum.
2. Understand source paper.
3. Extract question templates.
4. Identify variables.
5. Generate candidate questions.
6. Calculate answers programmatically where possible.
7. Validate.
8. Reject invalid candidates.
9. Assemble final paper.

For example:

Template:

A shopkeeper sold X items on Monday and Y items on Tuesday.

Question:

How many items did the shopkeeper sell altogether?

Generated:

X = 468
Y = 257

Answer:

725

The answer should be calculated by code.

Do NOT trust the LLM to perform arithmetic when deterministic code can do it.

---

# 15. QUESTION TEMPLATE MODEL

Build a question template representation.

Example:

{
  "template_type": "addition_word_problem",
  "topic": "addition",
  "grade": 3,
  "difficulty": 2,
  "variables": {
    "a": "3_digit_number",
    "b": "3_digit_number"
  },
  "operation": "addition",
  "answer_expression": "a + b"
}

This allows new values to be generated safely.

---

# 16. DIFFICULTY ENGINE

Do not make difficulty merely an arbitrary number.

Create measurable difficulty features.

Examples:

- Number of digits
- Number of operations
- Carrying required
- Number of steps
- Familiarity of vocabulary
- Distractor similarity
- Abstractness
- Word-problem complexity
- Reasoning requirement

For example:

Easy:

245 + 123

Medium:

378 + 246

Harder:

A shop had 458 books and received 267 more books. Then 125 books were given away. How many remain?

The system should record why a question has a particular difficulty.

---

# 17. CHAPTER INGESTION

The user should be able to upload:

- Camera photographs
- PDF textbook pages
- JPG
- PNG

Pipeline:

Chapter images
    ↓
Image cleanup
    ↓
OCR
    ↓
Page ordering
    ↓
Chapter detection
    ↓
Concept extraction
    ↓
Learning objective extraction
    ↓
Example extraction
    ↓
Exercise extraction
    ↓
Knowledge representation
    ↓
Question generation

Create:

chapter.json

Example:

{
  "subject": "Mathematics",
  "class": "III",
  "chapter": "Addition",
  "concepts": [
    "3-digit addition",
    "regrouping",
    "estimation"
  ],
  "examples": [...],
  "learning_objectives": [...],
  "difficulty_range": [...]
}

---

# 18. CURRICULUM / CLASS ISOLATION

Everything must be scoped by:

Subject

Class

Chapter

Academic year

Curriculum/board where possible.

Example:

Mathematics
→ Class III
→ CBSE
→ Addition

must not accidentally mix with:

Mathematics
→ Class V
→ CBSE
→ Addition

Create clear IDs for these entities.

---

# 19. PAPER BLUEPRINT

Before generating a paper, create a blueprint.

Example:

{
  "subject": "Mathematics",
  "class": "III",
  "total_marks": 20,
  "duration_minutes": 50,
  "sections": [
    {
      "name": "Multiple Choice",
      "marks": 2,
      "question_count": 4
    },
    {
      "name": "Number Concepts",
      "marks": 3
    },
    {
      "name": "Arithmetic",
      "marks": 6
    },
    {
      "name": "Word Problems",
      "marks": 6
    }
  ]
}

The generator must satisfy the blueprint.

---

# 20. ANSWER SHEET

Every generated paper must have an answer sheet.

The answer sheet should include:

Question number

Correct answer

Expected working where relevant

Marks

For example:

1(a) 300 — 0.5 mark

1(b) 500 — 0.5 mark

2(a) 5,607 / 5,609 — etc.

For mathematical questions, optionally show:

Question

Working

Final answer

The answer key should be generated from the structured question model, not regenerated independently by an LLM.

This prevents question/answer mismatch.

---

# 21. VALIDATION ENGINE

This is a critical component.

Before generating the PDF:

Validate:

- Total marks
- Number of questions
- Missing answers
- Arithmetic correctness
- Roman numeral correctness
- Multiple-choice answer exists
- Correct answer belongs to options
- Difficulty within requested range
- Question belongs to selected chapter
- No duplicate questions
- No contradictory instructions
- No impossible questions
- No accidental answer leakage

Example:

If generated:

47 + 25

the validator must calculate:

72

If the generated answer says:

73

the question must fail validation.

Do not generate the PDF.

---

# 22. PDF GENERATION

PDF rendering should be deterministic.

Create templates for:

- School exam style
- Simple practice paper
- Worksheet
- Mental Maths

The renderer should accept structured paper JSON and produce:

question_paper.pdf

answer_sheet.pdf

Optionally:

teacher_marking_scheme.pdf

The renderer should never need to understand the original LLM output.

It should only consume validated structured data.

---

# 23. UI DESIGN

Keep the UI extremely simple.

Main screen:

--------------------------------
AI PRACTICE PAPER
--------------------------------

Select Class

[ Class III ▼ ]

Select Subject

[ Mathematics ▼ ]

--------------------------------

What would you like to do?

[ Create from Existing Paper ]

[ Create from Chapter ]

--------------------------------

Recent Papers

...

--------------------------------

For "Create from Existing Paper":

STEP 1
Upload Paper

STEP 2
Clean Paper

STEP 3
Review Extracted Questions

STEP 4
Choose Difficulty

STEP 5
Generate Paper

STEP 6
Review

STEP 7
Download PDF

For "Create from Chapter":

STEP 1
Upload Chapter Photos

STEP 2
Extract Chapter Knowledge

STEP 3
Select Topics

STEP 4
Choose Difficulty

STEP 5
Create Blueprint

STEP 6
Generate Paper

STEP 7
Review

STEP 8
Download Question Paper + Answer Sheet

---

# 24. REVIEW SCREEN

Do NOT make the system completely automatic.

The user should be able to inspect:

Original image

Clean image

Detected questions

Extracted question text

Question type

Topic

Difficulty

Expected answer

Generated question

Generated answer

Allow:

Edit

Regenerate

Delete

Accept

This human-in-the-loop approach is important.

---

# 25. PROJECT STRUCTURE

Start with something approximately like:

app/

    backend/

        api/

        core/

        models/

        ingestion/

        preprocessing/

        ocr/

        document/

        questions/

        knowledge/

        generation/

        validation/

        rendering/

        storage/

        providers/

    frontend/

        ...

tests/

    unit/

    integration/

    fixtures/

data/

    samples/

    processed/

    generated/

docs/

scripts/

README.md
PROJECT_PLAN.md
ARCHITECTURE.md
DATA_MODEL.md
PIPELINE.md
EVALUATION.md
TODO.md

Adjust this structure if your analysis shows a better simple structure.

Do not create directories just for the sake of architecture.

---

# 26. DATA STORAGE

For MVP:

SQLite is sufficient.

Store:

subjects

classes

chapters

source_documents

pages

questions

question_templates

question_banks

paper_blueprints

generated_papers

answer_keys

processing_runs

evaluation_results

Store images/files on filesystem initially.

Design storage so it can later move to object storage.

---

# 27. LOGGING

Every pipeline run should have a run ID.

Example:

RUN-2026-000001

Log:

input

stage

start time

end time

status

errors

output artifact

model used

prompt version where applicable

This is essential for debugging AI systems.

---

# 28. PROMPT VERSIONING

AI prompts must NOT be scattered throughout the code.

Store them separately.

For example:

prompts/

    extract_questions_v1.txt

    classify_question_v1.txt

    extract_chapter_v1.txt

    generate_question_v1.txt

    review_question_v1.txt

This allows prompts to evolve independently.

---

# 29. EVALUATION

Create an evaluation framework from the beginning.

Build a small golden dataset using the provided Class III Mathematics paper.

Measure:

OCR accuracy

Question extraction accuracy

Annotation removal quality

Question classification accuracy

Generated question validity

Answer correctness

Difficulty accuracy

Blueprint compliance

PDF rendering correctness

Do not claim the system is accurate without measurable evaluation.

---

# 30. GOLDEN DATASET

Create:

tests/fixtures/

existing_paper/

    page_1.png

    page_2.png

    page_3.png

    page_4.png

expected/

    cleaned_page_1.png

    questions.json

    answer_key.json

This dataset should become a regression test.

Whenever the pipeline changes:

run the dataset again.

Compare results.

---

# 31. IMPORTANT SAFETY / QUALITY RULES

Never silently change extracted source content.

If OCR confidence is low:

flag it.

If question understanding is uncertain:

flag it.

If annotation removal is uncertain:

show the user the image.

If generated question validation fails:

regenerate or ask the user to review.

Never present an unvalidated generated answer as authoritative.

---

# 32. MVP SCOPE

Do NOT attempt to build everything immediately.

The first MVP should support:

### MVP 1

Existing Paper → Clean → Extract Questions → Generate Similar Paper → Answer Sheet

Support initially:

Class III

Mathematics

Image/PDF input

Multiple choice

Fill blanks

Arithmetic

Roman numerals

Predecessor/successor

Rounding

Addition

Word problems

Mental maths

PDF output

Answer key

The architecture must remain extensible for:

English

Science

Hindi

Social Studies

Other classes

Other boards

---

# 33. MVP DEMO

The first end-to-end demo should use the provided sample Class III Mathematics paper.

The demo should perform:

INPUT:

4-page scanned mathematics paper with handwritten student answers and teacher red-pen corrections.

↓

CLEAN:

Remove annotations.

↓

UNDERSTAND:

Extract:

questions

marks

question types

topics

difficulty

↓

GENERATE:

Create a new paper with different numbers and equivalent question structures.

↓

VALIDATE:

Verify answers programmatically.

↓

OUTPUT:

new_question_paper.pdf

answer_sheet.pdf

---

# 34. TESTING REQUIREMENTS

Use:

pytest

Unit tests for:

image preprocessing

number generation

Roman numeral conversion

arithmetic

question validation

blueprint validation

difficulty scoring

PDF data model

Integration tests for:

paper ingestion

question extraction

generation pipeline

answer generation

End-to-end test:

sample paper → generated PDF

---

# 35. CODE QUALITY

Use:

Type hints

Pydantic models

Docstrings where useful

Small functions

Meaningful names

Structured logging

Configuration files

Environment variables for secrets

No API keys in source code.

No giant 1,000-line files.

No "utils.py" dumping ground.

No unnecessary inheritance.

No global mutable state.

No magic numbers.

No hard-coded prompts.

No hard-coded API credentials.

No hidden network calls.

---

# 36. CONFIGURATION

Create:

.env.example

config.yaml

Configuration should include:

AI provider

model

OCR provider

image processing settings

PDF settings

storage paths

logging level

generation settings

Do not commit .env.

---

# 37. CLI

Before building the full UI, create a CLI.

Example:

python -m app ingest-paper input/paper.pdf

python -m app clean-paper input/paper.pdf

python -m app extract-questions input/paper.pdf

python -m app generate-paper --source paper.json

python -m app validate-paper generated.json

python -m app render-paper generated.json

python -m app generate-answer-key generated.json

This makes every pipeline stage testable independently.

---

# 38. OBSERVABILITY

Create a simple processing viewer or CLI output showing:

[1/8] Loading document
[2/8] Detecting page
[3/8] Cleaning annotations
[4/8] OCR
[5/8] Extracting questions
[6/8] Generating questions
[7/8] Validating
[8/8] Rendering PDF

Example:

✓ Page detection
✓ Perspective correction
✓ Annotation mask
✓ OCR
✓ 12 questions extracted
✓ 12 questions generated
✓ 12/12 validated
✓ PDF generated

This should be one of the core UX principles.

---

# 39. DO NOT OVER-ENGINEER THE FIRST VERSION

Avoid initially:

Kubernetes

Microservices

Kafka

Redis clusters

Complex event systems

Vector databases unless actually required

Complex agent frameworks

Multi-agent architecture

Fine-tuning

Custom neural networks

Huge frontend frameworks

The first version should be understandable by one developer.

---

# 40. FUTURE ARCHITECTURE

Document future possibilities but do not implement them unless necessary:

- Multiple boards
- Multiple languages
- NCERT integration
- Curriculum mapping
- Student profiles
- Performance tracking
- Adaptive difficulty
- Question recommendation
- Teacher sharing
- Parent accounts
- Cloud storage
- Mobile application
- School administration
- Analytics
- Question-bank marketplace
- Local/offline AI

---

# 41. IMPORTANT DESIGN PRINCIPLE

The system should NOT be:

"Upload paper → AI magically creates another paper."

It should be:

"Upload paper → understand paper → create structured representation → create blueprint → generate candidates → validate candidates → assemble paper → render PDF."

Every stage should be inspectable.

---

# 42. IMPLEMENTATION ORDER

Follow this order.

PHASE 0

Repository inspection.

Create:

README.md

PROJECT_PLAN.md

ARCHITECTURE.md

DATA_MODEL.md

PIPELINE.md

EVALUATION.md

TODO.md

Do not start large implementation before these exist.

PHASE 1

Create project skeleton.

Set up:

Python environment

dependency management

linting

formatting

pytest

logging

configuration

CLI

basic README instructions

PHASE 2

Implement image/document ingestion.

PHASE 3

Implement image cleaning.

PHASE 4

Implement OCR and question extraction.

PHASE 5

Implement structured question models.

PHASE 6

Implement question validation.

PHASE 7

Implement question generation.

PHASE 8

Implement paper blueprint.

PHASE 9

Implement PDF generation.

PHASE 10

Implement answer sheet generation.

PHASE 11

Build basic UI.

PHASE 12

Implement chapter ingestion.

PHASE 13

Implement difficulty controls.

PHASE 14

Implement evaluation dashboard.

---

# 43. FIRST RESPONSE REQUIRED FROM YOU

Before writing substantial application code, do the following:

1. Inspect the repository.

2. Identify existing files.

3. Identify existing dependencies.

4. Identify reusable components.

5. Identify risks.

6. Identify unknowns.

7. Propose the architecture.

8. Create:

README.md

PROJECT_PLAN.md

ARCHITECTURE.md

DATA_MODEL.md

PIPELINE.md

EVALUATION.md

TODO.md

9. Explain the MVP.

10. Explain exactly how the first end-to-end demo will work.

11. Explain which parts are deterministic and which parts use AI.

12. Explain how the supplied Class III Mathematics paper will be used as the first golden test case.

13. Do NOT start implementing the complete application yet.

Wait for approval after presenting the implementation plan.

---

# 44. SUCCESS CRITERIA FOR MVP

The MVP will be considered successful when:

A real scanned paper can be uploaded.

The system can clean student/teacher handwriting with reasonable accuracy.

The original printed questions remain intact.

Questions can be extracted into structured data.

The system understands question types.

The system generates equivalent new questions.

Numbers/values are different.

Difficulty remains comparable.

Answers are calculated and validated.

A new PDF is generated.

An answer sheet is generated.

The parent/teacher can inspect the generated paper.

The system can repeat the process for another paper.

Most importantly:

The entire pipeline should be understandable and debuggable.

---

# 45. FINAL INSTRUCTION

Think like a senior engineer building a real product, not a demo.

Prefer simple working software over impressive architecture.

Prefer deterministic algorithms wherever possible.

Use AI where deterministic algorithms are insufficient.

Keep all intermediate artifacts.

Make failures visible.

Make generated content testable.

Make answers independently verifiable.

Do not blindly trust LLM output.

Do not blindly trust OCR.

Do not blindly trust image processing.

Build confidence through validation and evaluation.

Start by inspecting the repository and creating the implementation documentation.

Do not begin the complete implementation until the plan has been presented.