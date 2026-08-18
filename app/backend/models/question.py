"""Question and difficulty models (DATA_MODEL.md's "Question" and
"DifficultyFeatures" sections). DifficultyFeatures.score() is the one place
"difficulty" gets computed (spec §16: "record why a question has a
particular difficulty") — every question's 1-5 level must trace back to
this method, never be assigned as a bare number elsewhere."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel


class QuestionType(str, Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    FILL_BLANK = "fill_in_the_blank"
    TRUE_FALSE = "true_false"
    ARITHMETIC = "arithmetic"
    ROMAN_NUMERAL = "roman_numeral"
    PREDECESSOR_SUCCESSOR = "predecessor_successor"
    ROUNDING = "rounding"
    WORD_PROBLEM = "word_problem"
    MENTAL_MATHS = "mental_maths"


class DifficultyFeatures(BaseModel):
    digit_count: int | None = None
    operation_count: int
    requires_carrying: bool | None = None
    step_count: int
    vocabulary_level: Literal["basic", "standard", "advanced"]
    reasoning_required: bool

    def score(self) -> int:
        points = 1
        if self.requires_carrying:
            points += 1
        if self.operation_count >= 2:
            points += 1
        if self.step_count >= 2:
            points += 1
        if self.reasoning_required:
            points += 1
        if self.vocabulary_level == "advanced":
            points += 1
        return min(points, 5)
