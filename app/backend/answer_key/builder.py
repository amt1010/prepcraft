"""Builds an AnswerKey directly from a Paper's already-computed
Question.expected_answer fields (spec §20: "generated from the structured
question model, not regenerated independently by an LLM" — this prevents
question/answer mismatch). One AnswerKeyEntry per question, in the order
given, so PROJECT_PLAN.md's Phase 10 acceptance bar ("answer_sheet.pdf
matches generated paper's questions 1:1") holds by construction. `working`
is always None — no Question field holds step-by-step working yet (spec
§20's "Expected working where relevant" is optional), so there is nothing
to populate it from."""

from app.backend.core.ids import new_id
from app.backend.models.answer_key import AnswerKey, AnswerKeyEntry
from app.backend.models.paper import Paper
from app.backend.models.question import Question


def build_answer_key(paper: Paper, questions: list[Question]) -> AnswerKey:
    entries = [
        AnswerKeyEntry(
            question_id=question.id,
            question_number=question.question_number,
            answer=question.expected_answer,
            marks=question.marks,
        )
        for question in questions
    ]
    return AnswerKey(id=new_id("ANSKEY"), paper_id=paper.id, entries=entries)
