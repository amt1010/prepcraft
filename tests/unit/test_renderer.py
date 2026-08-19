from datetime import datetime
from pathlib import Path

import pytest

from app.backend.models.answer_key import AnswerKey, AnswerKeyEntry
from app.backend.models.paper import Paper, Section
from app.backend.models.question import DifficultyFeatures, Question, QuestionType
from app.backend.rendering.renderer import render_answer_sheet, render_question_paper


def _difficulty_features() -> DifficultyFeatures:
    return DifficultyFeatures(
        operation_count=1,
        requires_carrying=False,
        step_count=1,
        vocabulary_level="basic",
        reasoning_required=False,
    )


def _question() -> Question:
    return Question(
        id="Q-1",
        paper_id="P-1",
        question_number="1",
        type=QuestionType.ARITHMETIC,
        text="47 + 25 = ?",
        marks=1.0,
        topic="Addition",
        difficulty=1,
        difficulty_features=_difficulty_features(),
        expected_answer="72",
        answer_type="numeric",
        source="existing_paper",
    )


def _paper() -> Paper:
    return Paper(
        id="P-1",
        subject="Mathematics",
        class_standard="III",
        total_marks=1.0,
        duration_minutes=50,
        sections=[Section(name="A", marks=1.0)],
        source="existing_paper",
        created_at=datetime.now(),
    )


def test_renders_a_valid_pdf_file(tmp_path: Path):
    output_path = tmp_path / "question_paper.pdf"

    result = render_question_paper(_paper(), [_question()], output_path)

    assert result == output_path
    content = output_path.read_bytes()
    assert content.startswith(b"%PDF-")
    assert b"%%EOF" in content[-64:]


def test_creates_missing_parent_directories(tmp_path: Path):
    output_path = tmp_path / "nested" / "dir" / "question_paper.pdf"

    render_question_paper(_paper(), [_question()], output_path)

    assert output_path.exists()


def test_unknown_page_size_raises():
    with pytest.raises(ValueError):
        render_question_paper(_paper(), [_question()], Path("unused.pdf"), page_size="A3")


def test_letter_page_size_also_renders(tmp_path: Path):
    output_path = tmp_path / "letter.pdf"

    render_question_paper(_paper(), [_question()], output_path, page_size="LETTER")

    assert output_path.read_bytes().startswith(b"%PDF-")


def _answer_key() -> AnswerKey:
    return AnswerKey(
        id="ANSKEY-1",
        paper_id="P-1",
        entries=[
            AnswerKeyEntry(question_id="Q-1", question_number="1", answer="72", marks=1.0)
        ],
    )


def test_renders_a_valid_answer_sheet_pdf(tmp_path: Path):
    output_path = tmp_path / "answer_sheet.pdf"

    result = render_answer_sheet(_paper(), _answer_key(), output_path)

    assert result == output_path
    content = output_path.read_bytes()
    assert content.startswith(b"%PDF-")
    assert b"%%EOF" in content[-64:]


def test_answer_sheet_creates_missing_parent_directories(tmp_path: Path):
    output_path = tmp_path / "nested" / "dir" / "answer_sheet.pdf"

    render_answer_sheet(_paper(), _answer_key(), output_path)

    assert output_path.exists()


def test_answer_sheet_unknown_page_size_raises():
    with pytest.raises(ValueError):
        render_answer_sheet(_paper(), _answer_key(), Path("unused.pdf"), page_size="A3")
