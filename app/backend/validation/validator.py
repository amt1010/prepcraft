"""Question and Paper validation (ARCHITECTURE.md's validation/ module:
"Answer recomputation, blueprint compliance, dedup, leakage checks"). Every
check here is deterministic (PROJECT_PLAN.md's "What's deterministic vs.
AI" list) — this module never calls a provider. Per spec §21: if a
question's stated answer doesn't recompute, it must fail validation and the
PDF must never be generated from it."""

import re

from pydantic import BaseModel

from app.backend.models.paper import Paper
from app.backend.models.question import Question, QuestionType
from app.backend.validation.answer_engine import evaluate

_ARITHMETIC_PATTERN = re.compile(r"(-?\d+(?:\.\d+)?)\s*([+\-*/])\s*(-?\d+(?:\.\d+)?)")


class ValidationIssue(BaseModel):
    code: str
    message: str
    question_number: str | None = None


def validate_question(question: Question) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    if not question.expected_answer.strip():
        issues.append(
            ValidationIssue(
                code="missing_answer",
                message="expected_answer is empty",
                question_number=question.question_number,
            )
        )

    if question.type == QuestionType.MULTIPLE_CHOICE:
        if not question.options:
            issues.append(
                ValidationIssue(
                    code="multiple_choice_missing_options",
                    message="multiple_choice question has no options",
                    question_number=question.question_number,
                )
            )
        elif question.expected_answer not in question.options:
            issues.append(
                ValidationIssue(
                    code="answer_not_in_options",
                    message=(
                        f"expected_answer {question.expected_answer!r} is not "
                        f"among options {question.options!r}"
                    ),
                    question_number=question.question_number,
                )
            )

    if question.type == QuestionType.ARITHMETIC:
        match = _ARITHMETIC_PATTERN.search(question.text)
        if match:
            try:
                stated = float(question.expected_answer)
            except ValueError:
                stated = None
            if stated is not None:
                expression = f"{match.group(1)} {match.group(2)} {match.group(3)}"
                computed = evaluate(expression)
                if computed != stated:
                    issues.append(
                        ValidationIssue(
                            code="arithmetic_mismatch",
                            message=(
                                f"recomputed {expression} = {computed}, but "
                                f"expected_answer states {stated}"
                            ),
                            question_number=question.question_number,
                        )
                    )

    return issues


def validate_paper(paper: Paper, questions: list[Question]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    for question in questions:
        issues.extend(validate_question(question))

    total_marks = sum(question.marks for question in questions)
    if abs(total_marks - paper.total_marks) > 1e-6:
        issues.append(
            ValidationIssue(
                code="marks_mismatch",
                message=(
                    f"questions sum to {total_marks} marks, paper declares "
                    f"{paper.total_marks}"
                ),
            )
        )

    seen_by_text: dict[str, str] = {}
    for question in questions:
        normalized = " ".join(question.text.split()).lower()
        if normalized in seen_by_text:
            issues.append(
                ValidationIssue(
                    code="duplicate_question",
                    message=f"question {question.question_number} duplicates {seen_by_text[normalized]}",
                    question_number=question.question_number,
                )
            )
        else:
            seen_by_text[normalized] = question.question_number

    for question in questions:
        if question.type == QuestionType.MULTIPLE_CHOICE or not question.expected_answer.strip():
            continue
        if re.search(rf"\b{re.escape(question.expected_answer)}\b", question.text, re.IGNORECASE):
            issues.append(
                ValidationIssue(
                    code="answer_leakage",
                    message="expected_answer appears verbatim in question text",
                    question_number=question.question_number,
                )
            )

    return issues
