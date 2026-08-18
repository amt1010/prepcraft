# Data Model

All structured data crossing a module boundary is a Pydantic v2 model. No
raw dicts, no `Any`-typed payloads between pipeline stages (spec §12, §35).

## Core entities

### Paper

```python
class Section(BaseModel):
    name: str
    marks: float
    question_count: int | None = None

class Paper(BaseModel):
    id: str                          # e.g. "PAPER-2026-000123"
    subject: str
    class_standard: str               # "III", not an int — some boards use non-numeric labels
    curriculum: str | None = None     # e.g. "CBSE"; None until Phase 3 board support lands
    total_marks: float
    duration_minutes: int
    sections: list[Section]
    source: Literal["existing_paper", "chapter", "generated"]
    source_paper_id: str | None = None   # set when source == "generated"
    created_at: datetime
```

### Question

```python
class Question(BaseModel):
    id: str
    paper_id: str
    question_number: str              # "1a", "2", "3b" — matches source numbering scheme
    type: QuestionType                 # enum, see below
    text: str
    options: list[str] | None = None   # multiple_choice only
    marks: float
    topic: str
    difficulty: int                    # 1-5, spec §16 scale
    difficulty_features: DifficultyFeatures
    expected_answer: str
    answer_type: Literal["numeric", "text", "choice", "boolean"]
    source: Literal["existing_paper", "generated"]
    template_id: str | None = None     # set when source == "generated"

class QuestionType(str, Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    FILL_BLANK = "fill_in_the_blank"
    TRUE_FALSE = "true_false"
    ARITHMETIC = "arithmetic"
    ROMAN_NUMERAL = "roman_numeral"
    PREDECESSOR_SUCCESSOR = "predecessor_successor"
    ROUNDING = "rounding"
    WORD_PROBLEM = "word_problem"
    MENTAL_MATHS = "mental_maths"
    # Phase 2+: MATCH_THE_FOLLOWING, SHORT_ANSWER, COLUMN_ARITHMETIC, ESTIMATION, DIAGRAM_BASED
```

MVP implements the first 9; the commented-out set needs free-text or
matching validation logic that doesn't exist yet (PROJECT_PLAN.md MVP
scope) and is deliberately deferred rather than half-built.

### DifficultyFeatures

Concrete, measurable, not a bare int (spec §16 is explicit that difficulty
must be explainable):

```python
class DifficultyFeatures(BaseModel):
    digit_count: int | None = None
    operation_count: int
    requires_carrying: bool | None = None
    step_count: int
    vocabulary_level: Literal["basic", "standard", "advanced"]
    reasoning_required: bool

    def score(self) -> int:
        """Maps features to the 1-5 scale. Pure function, unit-tested directly —
        this is the one place 'difficulty' gets computed, so every question's
        level traces back to it."""
```

### QuestionTemplate

```python
class QuestionTemplate(BaseModel):
    id: str
    template_type: str                 # "addition_word_problem"
    topic: str
    grade: str
    difficulty_range: tuple[int, int]  # which difficulty levels this template can serve
    variables: dict[str, str]          # {"a": "3_digit_number", "b": "3_digit_number"}
    operation: str
    answer_expression: str             # "a + b" — evaluated by code, never by the LLM
    text_template: str                 # "A shopkeeper sold {a} items on Monday and {b} on Tuesday..."
```

`answer_expression` is parsed and evaluated with a restricted expression
evaluator (arithmetic operators only, no `eval()` on arbitrary strings) in
`generation/answer_engine.py`. This is the concrete mechanism behind spec
§14's "answer should be calculated by code."

### PaperBlueprint

```python
class BlueprintSection(BaseModel):
    name: str
    marks: float
    question_count: int | None = None
    allowed_types: list[QuestionType] | None = None

class PaperBlueprint(BaseModel):
    id: str
    subject: str
    class_standard: str
    total_marks: float
    duration_minutes: int
    sections: list[BlueprintSection]
    difficulty_level: int               # 1-5, spec §16
    derived_from_paper_id: str | None = None   # set for Workflow A
```

### Chapter (Workflow B)

```python
class ChapterExample(BaseModel):
    text: str
    worked_solution: str | None = None

class Chapter(BaseModel):
    id: str
    subject: str
    class_standard: str
    title: str
    concepts: list[str]
    definitions: dict[str, str]
    examples: list[ChapterExample]
    learning_objectives: list[str]
    exercises: list[str]
    difficulty_range: tuple[int, int]
    source_image_ids: list[str]
```

### AnswerKey

```python
class AnswerKeyEntry(BaseModel):
    question_id: str
    question_number: str
    answer: str
    working: str | None = None
    marks: float

class AnswerKey(BaseModel):
    id: str
    paper_id: str
    entries: list[AnswerKeyEntry]
```

Built directly from the `Paper`'s `Question.expected_answer` fields, never
regenerated independently — this is the concrete mechanism behind spec
§20's "generated from the structured question model, not regenerated
independently by an LLM," which is what prevents question/answer mismatch.

### ProcessingRun

```python
class ProcessingRun(BaseModel):
    id: str                            # "RUN-2026-000001"
    input_ref: str
    stage: str
    status: Literal["pending", "running", "succeeded", "failed"]
    started_at: datetime
    ended_at: datetime | None = None
    errors: list[str] = []
    output_artifact_path: str | None = None
    model_used: str | None = None
    prompt_version: str | None = None
```

One row per stage per run (spec §27) — not one row per run — so a failure
at stage 4 of 8 is visible as exactly that, not as a generic "run failed."

## Database tables (SQLite via SQLAlchemy)

Mirrors spec §26 directly:

`subjects, classes, chapters, source_documents, pages, questions,
question_templates, question_banks, paper_blueprints, generated_papers,
answer_keys, processing_runs, evaluation_results`

Each table's columns are the corresponding Pydantic model's fields, plus
`created_at`/`updated_at`. Binary content (images, PDFs) is never stored in
these tables — see ARCHITECTURE.md "Storage design" for the filesystem
split. IDs are ULIDs (sortable, unlike UUID4) generated in `core/ids.py`,
not autoincrement — so an ID is stable before the row is committed, which
matters when the same ID needs to name a directory of artifact files before
the DB write happens.

## Scoping invariant

Every `Question`, `Chapter`, `QuestionTemplate`, and `PaperBlueprint` row
carries `subject` + `class_standard` (+ `curriculum` once boards are
supported). Query helpers in `storage/` take these as required, not
optional, arguments — there is no "get all questions" function, only
"get questions for (subject, class, chapter)". This is the concrete
mechanism behind spec §18's isolation requirement; it's enforced by the
query layer's function signatures, not by convention.
