""""Simple practice paper" PDF template (spec §22's template list: "School
exam style / Simple practice paper / Worksheet / Mental Maths" — this is
the one MVP template). Pure function: Paper + list[Question] in, a flat
list of ReportLab Flowables out, no I/O, no randomness (spec §22: "PDF
rendering should be deterministic"). Renders questions in the order given,
not grouped by Paper.sections — Question has no section field to group by
(the same gap Phase 6's and Phase 8's TODO.md notes flagged)."""

from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Flowable, Paragraph, Spacer

from app.backend.models.paper import Paper
from app.backend.models.question import Question, QuestionType

_STYLES = getSampleStyleSheet()
_TITLE_STYLE = ParagraphStyle("PaperTitle", parent=_STYLES["Title"])
_META_STYLE = ParagraphStyle("PaperMeta", parent=_STYLES["Normal"], alignment=1)
_QUESTION_STYLE = ParagraphStyle(
    "Question", parent=_STYLES["Normal"], spaceBefore=10, spaceAfter=4
)
_SECTION_STYLE = ParagraphStyle("Section", parent=_STYLES["Heading2"], spaceBefore=14)
_OPTION_STYLE = ParagraphStyle("Option", parent=_STYLES["Normal"], leftIndent=18)
_OPTION_LABELS = "abcdefgh"


def _question_flowables(question: Question) -> list[Flowable]:
    flowables: list[Flowable] = [
        Paragraph(
            f"{question.question_number}. {question.text} <i>[{question.marks} marks]</i>",
            _QUESTION_STYLE,
        )
    ]
    if question.type == QuestionType.MULTIPLE_CHOICE and question.options:
        for label, option in zip(_OPTION_LABELS, question.options, strict=False):
            flowables.append(Paragraph(f"({label}) {option}", _OPTION_STYLE))
    return flowables


def build_flowables(paper: Paper, questions: list[Question]) -> list[Flowable]:
    flowables: list[Flowable] = [
        Paragraph(f"{paper.subject} — Class {paper.class_standard}", _TITLE_STYLE),
        Paragraph(
            f"Total Marks: {paper.total_marks} Duration: {paper.duration_minutes} minutes",
            _META_STYLE,
        ),
        Spacer(1, 0.5 * cm),
    ]
    section_question_total = sum(section.question_count or 0 for section in paper.sections)
    if section_question_total != len(questions):
        for question in questions:
            flowables.extend(_question_flowables(question))
        return flowables

    question_index = 0
    for section in paper.sections:
        if section.name != "All Questions":
            flowables.append(Paragraph(section.name, _SECTION_STYLE))
        section_questions = questions[
            question_index : question_index + (section.question_count or 0)
        ]
        question_index += len(section_questions)
        for question in section_questions:
            flowables.extend(_question_flowables(question))
    return flowables
