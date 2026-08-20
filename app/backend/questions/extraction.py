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

import re

from pydantic import BaseModel

from app.backend.ocr.layout_analysis import LayoutGroup
from app.backend.providers.text_generation import TextGenerationProvider

_CLASSIFICATION_PROMPT = """You are extracting individual questions from a photographed
school exam paper's OCR text.
This is question {question_number} from a CBSE Class III Mathematics paper.

The text may contain multiple lettered sub-parts (a, b, c, ...) and a marks annotation like
"[0.5X4=2]" meaning each of the 4 sub-parts is worth 0.5 marks. Split the text into one
entry per sub-part, numbered "{question_number}a", "{question_number}b", etc. — or just
"{question_number}" if there are no lettered sub-parts.

For each entry determine:
- type: one of multiple_choice, fill_in_the_blank, true_false, arithmetic, roman_numeral,
  predecessor_successor, rounding, word_problem, mental_maths
- options: the answer choices, only when type is multiple_choice
- marks: this sub-part's marks, from the marks annotation
- topic: a short topic label (e.g. "Addition", "Roman numerals")
- difficulty: 1-5 on the CBSE Class III scale (1 = trivial recall, 5 = multi-step reasoning)
- section_name: the section heading this question belongs to, or null if no heading is visible

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
    section_name: str | None = None


class QuestionGroupExtraction(BaseModel):
    questions: list[ExtractedSubQuestion]


_MARKS_PATTERN = re.compile(r"\[\s*(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+)\s*=\s*(\d+(?:\.\d+)?)\s*\]")


def _fallback_classification(
    question: ExtractedSubQuestion, group_text: str
) -> ExtractedSubQuestion:
    text = question.text.lower()
    if question.type == "unknown":
        question_type = "arithmetic"
        if "true" in text or "false" in text:
            question_type = "true_false"
        elif "roman" in text:
            question_type = "roman_numeral"
        elif "round" in text:
            question_type = "rounding"
        elif "predecessor" in text or "successor" in text:
            question_type = "predecessor_successor"
        elif "how many" in text or "altogether" in text:
            question_type = "word_problem"
    else:
        question_type = question.type

    marks = question.marks
    marks_match = _MARKS_PATTERN.search(group_text)
    if marks is None:
        marks = (
            float(marks_match.group(1))
            if marks_match is not None
            else 1.0
        )
    topic = question.topic or (
        "Multiplication" if "multiply" in text or "×" in text else "Mathematics"
    )
    difficulty = question.difficulty or 2
    return question.model_copy(
        update={
            "type": question_type,
            "marks": marks,
            "topic": topic,
            "difficulty": difficulty,
        }
    )


def extract_questions(
    groups: list[LayoutGroup],
    text_provider: TextGenerationProvider | None = None,
) -> list[ExtractedSubQuestion]:
    if text_provider is None:
        return [
            ExtractedSubQuestion(
                question_number=g.question_number,
                text=g.text,
                type="unknown",
                section_name=g.section_name,
            )
            for g in groups
        ]

    extracted: list[ExtractedSubQuestion] = []
    for group in groups:
        prompt = _CLASSIFICATION_PROMPT.format(
            question_number=group.question_number, text=group.text
        )
        result = text_provider.generate(prompt, QuestionGroupExtraction)
        if any(
            question.type == "unknown"
            or question.marks is None
            or question.topic is None
            or question.difficulty is None
            for question in result.questions
        ):
            retry_prompt = (
                f"{prompt}\n\n"
                "Your previous response was incomplete. Return every sub-question with a "
                "supported type, marks, topic, and difficulty. Do not use type=unknown."
            )
            result = text_provider.generate(retry_prompt, QuestionGroupExtraction)
        extracted.extend(
            _fallback_classification(
                question.model_copy(
                    update={"section_name": question.section_name or group.section_name}
                ),
                group.text,
            )
            for question in result.questions
        )
    return extracted
