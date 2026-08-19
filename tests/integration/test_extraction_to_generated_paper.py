"""Closes the loop TODO.md's generate_paper orchestrator section left open:
realistic extraction output (the ExtractedSubQuestion shape
questions/extraction.py actually produces, echoing the golden paper's
hand-transcribed content) now has a real path all the way to a validated
generated Paper, with no fixture-only Question/Paper construction in
between."""

import random

from app.backend.generation.paper_generator import generate_paper
from app.backend.questions.extraction import ExtractedSubQuestion
from app.backend.questions.paper_assembly import assemble_paper_from_extracted
from app.backend.validation.validator import validate_paper


def _extracted_questions() -> list[ExtractedSubQuestion]:
    # All three at marks=1.0 and difficulty=2 so the single auto-generated
    # "All Questions" section (marks=3.0, question_count=3) lands on
    # per_question_marks=1.0 — a value questions/template_registry.py's
    # TPL-ARITHMETIC-ADD/TPL-FILL-BLANK-ADD/TPL-MULTIPLE-CHOICE-ADD/
    # TPL-TRUE-FALSE-ADD all match at difficulty_level=2, so template
    # selection (Phase 8's marks-exact-match rule, no packing solver)
    # succeeds deterministically regardless of which of those it picks.
    return [
        ExtractedSubQuestion(
            question_number="1a",
            text="___ + 305 = 800. What is the missing number?",
            type="multiple_choice",
            options=["405", "450", "500", "495"],
            marks=1.0,
            topic="Addition",
            difficulty=2,
        ),
        ExtractedSubQuestion(
            question_number="2a",
            text="Write the predecessor and successor of 4759.",
            type="fill_in_the_blank",
            marks=1.0,
            topic="Predecessor and successor",
            difficulty=2,
        ),
        ExtractedSubQuestion(
            question_number="4a",
            text="Solve by breaking up to make ten: 7 + 8",
            type="arithmetic",
            marks=1.0,
            topic="Addition",
            difficulty=2,
        ),
    ]


def test_extracted_questions_assemble_and_generate_a_valid_paper():
    source_paper, source_questions = assemble_paper_from_extracted(
        subject="Mathematics",
        class_standard="III",
        duration_minutes=50,
        extracted_questions=_extracted_questions(),
    )

    assert source_paper.total_marks == 3.0
    assert len(source_questions) == 3
    assert all(q.paper_id == source_paper.id for q in source_questions)

    generated_paper, generated_questions = generate_paper(
        source_paper, source_questions, rng=random.Random(11)
    )

    assert validate_paper(generated_paper, generated_questions) == []
    assert generated_paper.source_paper_id == source_paper.id
