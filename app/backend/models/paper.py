from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class Section(BaseModel):
    name: str
    marks: float
    question_count: int | None = None


class Paper(BaseModel):
    id: str
    subject: str
    class_standard: str
    curriculum: str | None = None
    total_marks: float
    duration_minutes: int
    sections: list[Section]
    source: Literal["existing_paper", "chapter", "generated"]
    source_paper_id: str | None = None
    created_at: datetime
