""""Answer Key" PDF template (spec §20: "Question number / Correct answer /
Expected working where relevant / Marks"). Pure function, no I/O — mirrors
simple_practice_paper.py's shape, swapping list[Question] for an
already-built AnswerKey (spec §20: the key is built from the structured
question model; this template never regenerates it)."""

from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Flowable, Paragraph

from app.backend.models.answer_key import AnswerKey, AnswerKeyEntry
from app.backend.models.paper import Paper

_STYLES = getSampleStyleSheet()
_TITLE_STYLE = ParagraphStyle("AnswerSheetTitle", parent=_STYLES["Title"])
_ENTRY_STYLE = ParagraphStyle(
    "AnswerEntry", parent=_STYLES["Normal"], spaceBefore=6, spaceAfter=2
)
_WORKING_STYLE = ParagraphStyle("Working", parent=_STYLES["Normal"], leftIndent=18)


def _entry_flowables(entry: AnswerKeyEntry) -> list[Flowable]:
    flowables: list[Flowable] = [
        Paragraph(
            f"{entry.question_number}. {entry.answer} <i>[{entry.marks} marks]</i>",
            _ENTRY_STYLE,
        )
    ]
    if entry.working:
        flowables.append(Paragraph(f"Working: {entry.working}", _WORKING_STYLE))
    return flowables


def build_flowables(paper: Paper, answer_key: AnswerKey) -> list[Flowable]:
    flowables: list[Flowable] = [
        Paragraph(
            f"{paper.subject} — Class {paper.class_standard} Answer Key", _TITLE_STYLE
        ),
    ]
    for entry in answer_key.entries:
        flowables.extend(_entry_flowables(entry))
    return flowables
