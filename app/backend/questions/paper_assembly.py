"""Turns Phase 4 extraction output into Phase 5's real Question/Paper
models — the conversion questions/extraction.py's own docstring calls
"Phase 5's job" but Phase 5 never actually wrote (TODO.md's generate_paper
orchestrator section: "Two new gaps surfaced while scoping this"). See this
plan's header for the judgment calls this file has to make about data
extraction genuinely doesn't produce (expected_answer, difficulty_features,
section grouping, paper-level metadata)."""

import re
from datetime import datetime

from app.backend.core.ids import new_id
from app.backend.models.paper import Paper, Section
from app.backend.models.question import DifficultyFeatures, Question, QuestionType
from app.backend.questions.extraction import ExtractedSubQuestion

_ANSWER_TYPE_BY_QUESTION_TYPE = {
    QuestionType.MULTIPLE_CHOICE: "choice",
    QuestionType.TRUE_FALSE: "boolean",
    QuestionType.ROMAN_NUMERAL: "text",
}
_DEFAULT_ANSWER_TYPE = "numeric"
_QUESTION_NUMBER_PATTERN = re.compile(r"(\d+)([a-z]*)", re.IGNORECASE)


def _question_number_key(question_number: str) -> tuple[int, str]:
    match = _QUESTION_NUMBER_PATTERN.fullmatch(question_number.strip())
    if match is None:
        return (10**9, question_number)
    return (int(match.group(1)), match.group(2).lower())


def _placeholder_difficulty_features(question_type: QuestionType) -> DifficultyFeatures:
    """Best-effort structural guess only — NOT the source of truth for this
    question's difficulty (extraction's own LLM-judged `difficulty` int is).
    There is nothing in extraction output to compute operation_count/
    requires_carrying/step_count from without re-parsing question text,
    which is out of scope here."""
    reasoning_required = question_type in (QuestionType.WORD_PROBLEM, QuestionType.MENTAL_MATHS)
    return DifficultyFeatures(
        operation_count=1,
        requires_carrying=None,
        step_count=1,
        vocabulary_level="standard",
        reasoning_required=reasoning_required,
    )


def question_from_extracted(extracted: ExtractedSubQuestion, paper_id: str) -> Question:
    if extracted.marks is None or extracted.topic is None or extracted.difficulty is None:
        raise ValueError(
            f"question {extracted.question_number!r} is missing marks/topic/difficulty — "
            "was it extracted without a text_provider, leaving it unclassified "
            "('type=unknown')?"
        )
    question_type = QuestionType(extracted.type)

    return Question(
        id=new_id("QUES"),
        paper_id=paper_id,
        question_number=extracted.question_number,
        type=question_type,
        text=extracted.text,
        options=extracted.options,
        marks=extracted.marks,
        topic=extracted.topic,
        difficulty=extracted.difficulty,
        difficulty_features=_placeholder_difficulty_features(question_type),
        expected_answer="",
        answer_type=_ANSWER_TYPE_BY_QUESTION_TYPE.get(question_type, _DEFAULT_ANSWER_TYPE),
        source="existing_paper",
    )


def assemble_paper_from_extracted(
    subject: str,
    class_standard: str,
    duration_minutes: int,
    extracted_questions: list[ExtractedSubQuestion],
) -> tuple[Paper, list[Question]]:
    paper_id = new_id("PAPER")
    has_sections = any(item.section_name for item in extracted_questions)
    if has_sections:
        ordered_extracted = list(extracted_questions)
    else:
        ordered_extracted = sorted(
            extracted_questions, key=lambda item: _question_number_key(item.question_number)
        )
    questions = [question_from_extracted(extracted, paper_id) for extracted in ordered_extracted]
    section_groups: list[tuple[str, list[Question]]] = []
    for extracted, question in zip(ordered_extracted, questions, strict=True):
        section_name = extracted.section_name or "All Questions"
        if not section_groups or section_groups[-1][0] != section_name:
            section_groups.append((section_name, []))
        section_groups[-1][1].append(question)
    if not section_groups:
        section_groups.append(("All Questions", []))
    total_marks = sum(question.marks for question in questions)

    paper = Paper(
        id=paper_id,
        subject=subject,
        class_standard=class_standard,
        total_marks=total_marks,
        duration_minutes=duration_minutes,
        sections=[
            Section(
                name=name,
                marks=sum(question.marks for question in section_questions),
                question_count=len(section_questions),
            )
            for name, section_questions in section_groups
        ],
        source="existing_paper",
        created_at=datetime.now(),
    )
    return paper, questions
