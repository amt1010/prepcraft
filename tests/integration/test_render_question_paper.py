"""Closes PROJECT_PLAN.md's Phase 9 acceptance bar: "question_paper.pdf
renders and opens." Builds a realistic multi-type Class III paper (echoing
the golden paper's hand-transcribed content style from
tests/fixtures/expected/main/questions.json), validates it with Phase 6's
validate_paper the way a real caller must before rendering (spec §21: "Do
not generate the PDF" on a validation failure), then renders it and checks
the output is a well-formed, non-trivial PDF file."""

from datetime import datetime
from pathlib import Path

from app.backend.models.paper import Paper, Section
from app.backend.models.question import DifficultyFeatures, Question, QuestionType
from app.backend.rendering.renderer import render_question_paper
from app.backend.validation.validator import validate_paper


def _difficulty_features(**overrides) -> DifficultyFeatures:
    fields = {
        "operation_count": 1,
        "requires_carrying": False,
        "step_count": 1,
        "vocabulary_level": "basic",
        "reasoning_required": False,
    }
    fields.update(overrides)
    return DifficultyFeatures(**fields)


def _questions() -> list[Question]:
    return [
        Question(
            id="Q-1",
            paper_id="PAPER-1",
            question_number="1",
            type=QuestionType.MULTIPLE_CHOICE,
            text="___ + 305 = 800. What is the missing number?",
            options=["405", "450", "500", "495"],
            marks=0.5,
            topic="Addition",
            difficulty=2,
            difficulty_features=_difficulty_features(),
            expected_answer="495",
            answer_type="choice",
            source="existing_paper",
        ),
        Question(
            id="Q-2",
            paper_id="PAPER-1",
            question_number="2",
            type=QuestionType.FILL_BLANK,
            text="Write the predecessor and successor of 4759.",
            marks=1.0,
            topic="Predecessor and successor",
            difficulty=1,
            difficulty_features=_difficulty_features(),
            expected_answer="4758, 4760",
            answer_type="text",
            source="existing_paper",
        ),
        Question(
            id="Q-3",
            paper_id="PAPER-1",
            question_number="3",
            type=QuestionType.ROMAN_NUMERAL,
            text="Write the roman number for 27.",
            marks=0.5,
            topic="Roman numerals",
            difficulty=2,
            difficulty_features=_difficulty_features(),
            expected_answer="XXVII",
            answer_type="text",
            source="existing_paper",
        ),
        Question(
            id="Q-4",
            paper_id="PAPER-1",
            question_number="4",
            type=QuestionType.WORD_PROBLEM,
            text=(
                "The cost of two toys is Rs 47 and Rs 64. Find the exact total cost "
                "by adding the two amounts."
            ),
            marks=2.0,
            topic="Addition word problem",
            difficulty=3,
            difficulty_features=_difficulty_features(
                reasoning_required=True, vocabulary_level="standard"
            ),
            expected_answer="111",
            answer_type="numeric",
            source="existing_paper",
        ),
    ]


def _paper(total_marks: float) -> Paper:
    return Paper(
        id="PAPER-1",
        subject="Mathematics",
        class_standard="III",
        total_marks=total_marks,
        duration_minutes=50,
        sections=[Section(name="Practice", marks=total_marks, question_count=4)],
        source="existing_paper",
        created_at=datetime.now(),
    )


def test_a_realistic_validated_paper_renders_to_a_well_formed_pdf(tmp_path: Path):
    questions = _questions()
    paper = _paper(total_marks=sum(q.marks for q in questions))

    assert validate_paper(paper, questions) == []

    output_path = render_question_paper(paper, questions, tmp_path / "question_paper.pdf")

    content = output_path.read_bytes()
    assert content.startswith(b"%PDF-")
    assert b"%%EOF" in content[-64:]
    assert len(content) > 1000  # more than an empty/near-empty document
