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
_SECTION_HEADING = re.compile(r"^([A-Z])\.$")
_TEXT_QUESTION = re.compile(r"^(\d{1,2})\.\s+(.+)$")
_TEXT_SECTION = re.compile(r"^([A-Z])\.\s+(.+)$")


class LayoutGroup(BaseModel):
    question_number: str
    text: str
    section_name: str | None = None


def group_by_question_number(ocr_result: OCRResult) -> list[LayoutGroup]:
    groups: list[LayoutGroup] = []
    current_number: str | None = None
    current_words: list[str] = []
    current_section: str | None = None

    for word in ocr_result.words:
        section_match = _SECTION_HEADING.match(word.text)
        if section_match:
            if current_number is not None:
                groups.append(
                    LayoutGroup(
                        question_number=current_number,
                        text=" ".join(current_words),
                        section_name=current_section,
                    )
                )
                current_number = None
                current_words = []
            current_section = section_match.group(1)
            continue
        match = _TOP_LEVEL_NUMBER.match(word.text)
        if match:
            if current_number is not None:
                groups.append(
                    LayoutGroup(
                        question_number=current_number,
                        text=" ".join(current_words),
                        section_name=current_section,
                    )
                )
            current_number = match.group(1)
            current_words = []
        elif current_number is not None:
            current_words.append(word.text)

    if current_number is not None:
        groups.append(
            LayoutGroup(
                question_number=current_number,
                text=" ".join(current_words),
                section_name=current_section,
            )
        )

    return groups


def group_text_by_question_number(text: str) -> list[LayoutGroup]:
    """Parse a text-layer PDF while retaining section headings and line order."""
    groups: list[LayoutGroup] = []
    current_number: str | None = None
    current_words: list[str] = []
    current_section: str | None = None

    def flush() -> None:
        nonlocal current_number, current_words
        if current_number is not None:
            groups.append(
                LayoutGroup(
                    question_number=current_number,
                    text=" ".join(current_words).strip(),
                    section_name=current_section,
                )
            )
        current_number = None
        current_words = []

    for line in text.splitlines():
        line = " ".join(line.split())
        if not line:
            continue
        section_match = _TEXT_SECTION.match(line)
        if section_match:
            flush()
            current_section = f"{section_match.group(1)}. {section_match.group(2)}"
            continue
        question_match = _TEXT_QUESTION.match(line)
        if question_match:
            flush()
            current_number = question_match.group(1)
            current_words = [question_match.group(2)]
        elif current_number is not None:
            current_words.append(line)
    flush()
    return groups
