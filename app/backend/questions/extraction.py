"""Splits each LayoutGroup's OCR text into lettered sub-parts and classifies
each one (PIPELINE.md's QuestionExtraction: "classify each item: type,
marks, topic, difficulty"). This is judgment over text, not perception, so
it's claude-sonnet-5 territory (ARCHITECTURE.md) via TextGenerationProvider
— never a bespoke regex parser trying to guess where "1a" ends and "1b"
begins, since the marks annotation format ("[0.5X4=2]") and sub-part
boundaries vary paper to paper.

This is deliberately a lighter model than DATA_MODEL.md's full `Question`
(no id/paper_id/expected_answer/difficulty_features/answer_type/source) —
those need a `Paper` to belong to and DifficultyFeatures' full breakdown,
which is Phase 5's job (PROJECT_PLAN.md phase table). Phase 5 builds the
real `Question` model on top of this extraction output."""

from pydantic import BaseModel

from app.backend.ocr.layout_analysis import LayoutGroup
from app.backend.providers.text_generation import TextGenerationProvider

_CLASSIFICATION_PROMPT = """You are extracting individual questions from a photographed school exam paper's OCR text. This is question {question_number} from a CBSE Class III Mathematics paper.

The text may contain multiple lettered sub-parts (a, b, c, ...) and a marks annotation like "[0.5X4=2]" meaning each of the 4 sub-parts is worth 0.5 marks. Split the text into one entry per sub-part, numbered "{question_number}a", "{question_number}b", etc. — or just "{question_number}" if there are no lettered sub-parts.

For each entry determine:
- type: one of multiple_choice, fill_in_the_blank, true_false, arithmetic, roman_numeral, predecessor_successor, rounding, word_problem, mental_maths
- options: the answer choices, only when type is multiple_choice
- marks: this sub-part's marks, from the marks annotation
- topic: a short topic label (e.g. "Addition", "Roman numerals")
- difficulty: 1-5 on the CBSE Class III scale (1 = trivial recall, 5 = multi-step reasoning)

OCR text for question {question_number}:
{text}
"""


class ExtractedSubQuestion(BaseModel):
    question_number: str
    text: str
    type: str
    options: list[str] | None = None
    marks: float | None = None
    topic: str | None = None
    difficulty: int | None = None


class QuestionGroupExtraction(BaseModel):
    questions: list[ExtractedSubQuestion]


def extract_questions(
    groups: list[LayoutGroup],
    text_provider: TextGenerationProvider | None = None,
) -> list[ExtractedSubQuestion]:
    if text_provider is None:
        return [
            ExtractedSubQuestion(question_number=g.question_number, text=g.text, type="unknown")
            for g in groups
        ]

    extracted: list[ExtractedSubQuestion] = []
    for group in groups:
        prompt = _CLASSIFICATION_PROMPT.format(question_number=group.question_number, text=group.text)
        result = text_provider.generate(prompt, QuestionGroupExtraction)
        extracted.extend(result.questions)
    return extracted
