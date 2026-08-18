from datetime import datetime

import pytest
from pydantic import ValidationError

from app.backend.models.paper import Paper, Section


def test_paper_round_trips_through_the_model_without_data_loss():
    paper = Paper(
        id="PAPER-01",
        subject="Mathematics",
        class_standard="III",
        curriculum="CBSE",
        total_marks=20,
        duration_minutes=50,
        sections=[Section(name="MCQ", marks=2, question_count=4)],
        source="existing_paper",
        source_paper_id=None,
        created_at=datetime(2026, 8, 18),
    )

    restored = Paper.model_validate(paper.model_dump())

    assert restored == paper


def test_paper_rejects_an_invalid_source_value():
    with pytest.raises(ValidationError):
        Paper(
            id="PAPER-01",
            subject="Mathematics",
            class_standard="III",
            total_marks=20,
            duration_minutes=50,
            sections=[],
            source="not_a_real_source",
            created_at=datetime(2026, 8, 18),
        )
