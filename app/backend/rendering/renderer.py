"""ReportLab driver (ARCHITECTURE.md's rendering/ module: "PDF templates +
ReportLab renderer"). Deliberately thin — page-size lookup and
SimpleDocTemplate wiring only; all layout decisions live in the template
module. Depends only on app.backend.models and reportlab, never
validation/providers/generation (ARCHITECTURE.md's rendering dependency
rule) — "validated data in" (spec §22) is the caller's contract, not
something this module re-checks."""

from collections.abc import Callable
from pathlib import Path

from reportlab.lib.pagesizes import A4, LETTER
from reportlab.platypus import Flowable, SimpleDocTemplate

from app.backend.models.paper import Paper
from app.backend.models.question import Question
from app.backend.rendering.templates.simple_practice_paper import build_flowables

_PAGE_SIZES = {"A4": A4, "LETTER": LETTER}


def render_question_paper(
    paper: Paper,
    questions: list[Question],
    output_path: Path,
    page_size: str = "A4",
    build_flowables_fn: Callable[[Paper, list[Question]], list[Flowable]] = build_flowables,
) -> Path:
    if page_size not in _PAGE_SIZES:
        raise ValueError(f"unknown page_size: {page_size!r}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(output_path), pagesize=_PAGE_SIZES[page_size])
    doc.build(build_flowables_fn(paper, questions))
    return output_path
