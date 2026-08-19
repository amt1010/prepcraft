"""Candidate question assembly (PIPELINE.md's shared tail: "Variable
sampling ... Answer computation ... Candidate questions (list[Question],
source="generated")"). Selecting *which* QuestionTemplate to use is Phase
8's job (blueprint-driven); this module starts one step later — given an
already-chosen template, sample fresh variables, compute the answer purely
in code (never the LLM, spec §14), render `text_template`, and optionally
ask a TextGenerationProvider to rephrase the *already-computed* text for
naturalness. The provider never sees variables or the answer, so it cannot
introduce an arithmetic error."""

import random

from pydantic import BaseModel

from app.backend.core.ids import new_id
from app.backend.generation.formulas import (
    addition_requires_carrying,
    predecessor,
    round_to_nearest,
    successor,
    to_roman_numeral,
)
from app.backend.generation.variable_sampler import sample_variables
from app.backend.models.question import DifficultyFeatures, Question, QuestionType
from app.backend.models.question_template import QuestionTemplate
from app.backend.providers.text_generation import TextGenerationProvider
from app.backend.validation.answer_engine import evaluate

_PHRASING_PROMPT = """Rewrite this Class III Mathematics question so it reads naturally, without changing any numbers, the blank ("___"), or the underlying meaning. Return only the rewritten question text.

Original: {text}
"""


class _PhrasedText(BaseModel):
    text: str


def _resolve(
    template: QuestionTemplate, variables: dict[str, int], rng: random.Random
) -> tuple[dict[str, int], str]:
    op = template.operation
    if op == "predecessor":
        return variables, str(predecessor(variables["n"]))
    if op == "successor":
        return variables, str(successor(variables["n"]))
    if op == "round_nearest_10":
        return variables, str(round_to_nearest(variables["n"], 10))
    if op == "round_nearest_100":
        return variables, str(round_to_nearest(variables["n"], 100))
    if op == "roman_numeral_conversion":
        return variables, to_roman_numeral(variables["n"])
    if op == "addition_fill_blank":
        total = int(evaluate(template.answer_expression, variables))
        return {**variables, "c": total}, str(variables["b"])
    if op == "true_false_addition":
        correct = int(evaluate(template.answer_expression, variables))
        is_true = rng.random() < 0.5
        shown = correct if is_true else correct + rng.choice([-3, -2, -1, 1, 2, 3])
        return {**variables, "c": shown}, "true" if is_true else "false"
    return variables, str(int(evaluate(template.answer_expression, variables)))


def _build_options(
    template: QuestionTemplate, correct_answer: str, rng: random.Random
) -> list[str] | None:
    if template.question_type != QuestionType.MULTIPLE_CHOICE:
        return None
    if not template.distractor_offsets:
        raise ValueError(f"multiple_choice template {template.id} has no distractor_offsets")
    correct = int(correct_answer)
    values = [correct] + [correct + offset for offset in template.distractor_offsets]
    if len(set(values)) != len(values):
        raise ValueError(f"template {template.id} produced duplicate options: {values}")
    options = [str(v) for v in values]
    rng.shuffle(options)
    return options


def _difficulty_features(template: QuestionTemplate, variables: dict[str, int]) -> DifficultyFeatures:
    requires_carrying = (
        addition_requires_carrying(variables["a"], variables["b"])
        if "a" in variables and "b" in variables
        else None
    )
    is_word_problem = template.question_type == QuestionType.WORD_PROBLEM
    return DifficultyFeatures(
        digit_count=max(len(str(v)) for v in variables.values()),
        operation_count=1,
        requires_carrying=requires_carrying,
        step_count=1,
        vocabulary_level="standard" if is_word_problem else "basic",
        reasoning_required=is_word_problem,
    )


def generate_question(
    template: QuestionTemplate,
    paper_id: str,
    question_number: str,
    rng: random.Random | None = None,
    text_provider: TextGenerationProvider | None = None,
) -> Question:
    rng = rng or random.Random()
    variables = sample_variables(template.variables, rng)
    text_variables, expected_answer = _resolve(template, variables, rng)
    text = template.text_template.format(**text_variables)
    options = _build_options(template, expected_answer, rng)

    if text_provider is not None:
        phrased = text_provider.generate(_PHRASING_PROMPT.format(text=text), _PhrasedText)
        text = phrased.text

    difficulty_features = _difficulty_features(template, variables)

    return Question(
        id=new_id("QUES"),
        paper_id=paper_id,
        question_number=question_number,
        type=template.question_type,
        text=text,
        options=options,
        marks=template.marks,
        topic=template.topic,
        difficulty=difficulty_features.score(),
        difficulty_features=difficulty_features,
        expected_answer=expected_answer,
        answer_type=template.answer_type,
        source="generated",
        template_id=template.id,
    )
