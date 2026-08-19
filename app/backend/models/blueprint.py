"""PaperBlueprint model (DATA_MODEL.md's "PaperBlueprint" core entity;
PIPELINE.md's shared tail: "PaperBlueprint (from extracted structure,
Workflow A; or from user selection, Workflow B)"). Fields match DATA_MODEL.md
literally — every field already has a real caller this phase, unlike Phase
7's QuestionTemplate extension."""

from pydantic import BaseModel

from app.backend.models.question import QuestionType


class BlueprintSection(BaseModel):
    name: str
    marks: float
    question_count: int | None = None
    allowed_types: list[QuestionType] | None = None


class PaperBlueprint(BaseModel):
    id: str
    subject: str
    class_standard: str
    total_marks: float
    duration_minutes: int
    sections: list[BlueprintSection]
    difficulty_level: int
    derived_from_paper_id: str | None = None
