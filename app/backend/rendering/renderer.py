"""ReportLab driver (ARCHITECTURE.md's rendering/ module: "PDF templates +
ReportLab renderer"). Deliberately thin — page-size lookup and
SimpleDocTemplate wiring only; all layout decisions live in the template
modules. Depends only on app.backend.models and reportlab, never
validation/providers/generation/answer_key (ARCHITECTURE.md's rendering
dependency rule) — "validated data in" (spec §22) and an already-built
AnswerKey (spec §20) are the caller's contract, not something this module
builds or re-checks."""

from collections.abc import Callable
from pathlib import Path

from reportlab.lib.pagesizes import A4, LETTER
from reportlab.platypus import Flowable, SimpleDocTemplate

from app.backend.models.answer_key import AnswerKey
from app.backend.models.paper import Paper
from app.backend.models.question import Question
from app.backend.rendering.templates.answer_sheet import (
    build_flowables as build_answer_sheet_flowables,
)
from app.backend.rendering.templates.simple_practice_paper import (
    build_flowables as build_question_paper_flowables,
)

_PAGE_SIZES = {"A4": A4, "LETTER": LETTER}


def _write_pdf(flowables: list[Flowable], output_path: Path, page_size: str) -> Path:
    if page_size not in _PAGE_SIZES:
        raise ValueError(f"unknown page_size: {page_size!r}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(output_path), pagesize=_PAGE_SIZES[page_size])
    doc.build(flowables)
    return output_path


def render_question_paper(
    paper: Paper,
    questions: list[Question],
    output_path: Path,
    page_size: str = "A4",
    build_flowables_fn: Callable[
        [Paper, list[Question]], list[Flowable]
    ] = build_question_paper_flowables,
) -> Path:
    return _write_pdf(build_flowables_fn(paper, questions), output_path, page_size)


def render_answer_sheet(
    paper: Paper,
    answer_key: AnswerKey,
    output_path: Path,
    page_size: str = "A4",
    build_flowables_fn: Callable[
        [Paper, AnswerKey], list[Flowable]
    ] = build_answer_sheet_flowables,
) -> Path:
    return _write_pdf(build_flowables_fn(paper, answer_key), output_path, page_size)
