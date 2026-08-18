"""Groups OCR words into per-top-level-question chunks by scanning for
tokens that look like "1.", "2.", ... (PIPELINE.md's LayoutAnalysis:
"group text into questions/sections by position + numbering"). Purely
positional/regex — no AI here. Splitting a chunk into lettered sub-parts
(1a, 1b, ...) and classifying each is QuestionExtraction's job
(questions/extraction.py), which has the judgment (and the marks-annotation
text like "[0.5X4=2]") to do it well; a regex can't tell "1." (a question
number) apart from "1" inside "XVII + V + X = 1" reliably, so this stays
deliberately coarse.

Words come from `OCRResult.words` in Tesseract's native reading order
(top-to-bottom, left-to-right per line) — this module trusts that order
rather than re-sorting by pixel position itself."""

import re

from pydantic import BaseModel

from app.backend.providers.ocr import OCRResult

_TOP_LEVEL_NUMBER = re.compile(r"^(\d{1,2})\.$")


class LayoutGroup(BaseModel):
    question_number: str
    text: str


def group_by_question_number(ocr_result: OCRResult) -> list[LayoutGroup]:
    groups: list[LayoutGroup] = []
    current_number: str | None = None
    current_words: list[str] = []

    for word in ocr_result.words:
        match = _TOP_LEVEL_NUMBER.match(word.text)
        if match:
            if current_number is not None:
                groups.append(LayoutGroup(question_number=current_number, text=" ".join(current_words)))
            current_number = match.group(1)
            current_words = []
        elif current_number is not None:
            current_words.append(word.text)

    if current_number is not None:
        groups.append(LayoutGroup(question_number=current_number, text=" ".join(current_words)))

    return groups
