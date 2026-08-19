"""Closes the gap Phase 6's TODO.md note left open: "nothing produces a full
generated Paper + Question set until Phase 7/8 ... they become validator
work again once Phase 7/8 give them a caller." This generates one candidate
per seed template and runs Phase 6's validate_paper against the result."""

import random
from datetime import datetime

from app.backend.generation.question_generator import generate_question
from app.backend.models.paper import Paper, Section
from app.backend.questions.template_registry import TEMPLATES
from app.backend.validation.validator import validate_paper


def test_one_candidate_per_seed_template_passes_validation():
    rng = random.Random(42)
    questions = [
        generate_question(template, paper_id="P-1", question_number=str(i), rng=rng)
        for i, template in enumerate(TEMPLATES, start=1)
    ]
    total_marks = sum(question.marks for question in questions)
    paper = Paper(
        id="P-1",
        subject="Mathematics",
        class_standard="III",
        total_marks=total_marks,
        duration_minutes=50,
        sections=[Section(name="A", marks=total_marks)],
        source="generated",
        created_at=datetime.now(),
    )

    issues = validate_paper(paper, questions)

    assert issues == []
