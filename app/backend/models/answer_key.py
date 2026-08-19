"""AnswerKey model (DATA_MODEL.md's "AnswerKey" core entity; spec §20:
"The answer key should be generated from the structured question model,
not regenerated independently by an LLM. This prevents question/answer
mismatch.")."""

from pydantic import BaseModel


class AnswerKeyEntry(BaseModel):
    question_id: str
    question_number: str
    answer: str
    working: str | None = None
    marks: float


class AnswerKey(BaseModel):
    id: str
    paper_id: str
    entries: list[AnswerKeyEntry]
