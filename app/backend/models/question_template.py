"""QuestionTemplate model (DATA_MODEL.md's "QuestionTemplate" core entity;
PIPELINE.md's shared tail: "Template selection ... pick QuestionTemplates
matching blueprint's topics/types/difficulty_range"). Extends DATA_MODEL.md's
literal field list with what Phase 7's generator needs to produce a complete
`Question` without a `PaperBlueprint` caller yet (Phase 8) — see the Phase 7
plan's Global Constraints for why each extra field exists."""

from typing import Literal

from pydantic import BaseModel

from app.backend.models.question import QuestionType


class QuestionTemplate(BaseModel):
    id: str
    template_type: str
    question_type: QuestionType
    subject: str
    grade: str
    topic: str
    marks: float
    difficulty_range: tuple[int, int]
    variables: dict[str, str]
    operation: str
    answer_expression: str
    text_template: str
    answer_type: Literal["numeric", "text", "choice", "boolean"]
    distractor_offsets: list[int] | None = None
