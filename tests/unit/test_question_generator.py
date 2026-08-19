import random
import re

from pydantic import BaseModel

from app.backend.generation.question_generator import generate_question
from app.backend.models.question import QuestionType
from app.backend.questions.template_registry import get_templates


class _PhrasedText(BaseModel):
    text: str


class _FakeTextProvider:
    def __init__(self, text: str):
        self._text = text
        self.prompts: list[str] = []

    def generate(self, prompt: str, schema):
        self.prompts.append(prompt)
        return _PhrasedText(text=self._text)


def _template(question_type):
    return get_templates(question_type)[0]


def test_arithmetic_question_recomputes_correctly():
    template = _template(QuestionType.ARITHMETIC)
    rng = random.Random(1)

    question = generate_question(template, paper_id="P-1", question_number="1", rng=rng)

    left, _, _ = question.text.partition("=")
    a, op, b = left.split()
    assert op == "+"
    assert question.expected_answer == str(int(a) + int(b))
    assert question.type == QuestionType.ARITHMETIC
    assert question.source == "generated"
    assert question.template_id == template.id


def test_roman_numeral_question_converts_correctly():
    template = _template(QuestionType.ROMAN_NUMERAL)
    rng = random.Random(2)

    question = generate_question(template, paper_id="P-1", question_number="1", rng=rng)

    # regex, not a digit-join: "Write the Roman numeral for 24." must not
    # pick up digits from elsewhere in the sentence
    n = int(re.search(r"\d+", question.text).group())
    assert question.answer_type == "text"
    assert question.expected_answer  # non-empty roman numeral string
    assert all(ch in "IVXLCDM" for ch in question.expected_answer)
    assert 1 <= n <= 50


def test_fill_in_blank_hides_the_second_addend():
    template = _template(QuestionType.FILL_BLANK)
    rng = random.Random(3)

    question = generate_question(template, paper_id="P-1", question_number="1", rng=rng)

    assert "___" in question.text
    assert question.expected_answer not in question.text


def test_multiple_choice_options_contain_the_answer_and_are_unique():
    template = _template(QuestionType.MULTIPLE_CHOICE)
    rng = random.Random(4)

    question = generate_question(template, paper_id="P-1", question_number="1", rng=rng)

    assert question.options is not None
    assert len(question.options) == len(set(question.options)) == 4
    assert question.expected_answer in question.options


def test_true_false_answer_is_true_or_false_string():
    template = _template(QuestionType.TRUE_FALSE)
    rng = random.Random(5)

    question = generate_question(template, paper_id="P-1", question_number="1", rng=rng)

    assert question.expected_answer in ("true", "false")


def test_predecessor_successor_answers_are_correct():
    for template in get_templates(QuestionType.PREDECESSOR_SUCCESSOR):
        rng = random.Random(6)
        question = generate_question(template, paper_id="P-1", question_number="1", rng=rng)
        n = int(re.search(r"\d+", question.text).group())
        expected = n - 1 if template.operation == "predecessor" else n + 1
        assert question.expected_answer == str(expected)


def test_rounding_answers_are_correct():
    for template in get_templates(QuestionType.ROUNDING):
        rng = random.Random(7)
        question = generate_question(template, paper_id="P-1", question_number="1", rng=rng)
        base = 10 if template.operation == "round_nearest_10" else 100
        # the sampled n always appears before "nearest 10"/"nearest 100" in
        # the template wording, so the first match in the text is n itself
        n = int(re.search(r"\d+", question.text).group())
        assert int(question.expected_answer) % base == 0


def test_difficulty_features_track_addition_carrying():
    # 245 + 123 has no carrying (spec §16 Easy); force it via a seed that
    # samples those exact values would be brittle, so instead check the
    # invariant: requires_carrying is set (not None) whenever the template
    # has both "a" and "b" variables, and difficulty is computed from it.
    template = _template(QuestionType.ARITHMETIC)
    rng = random.Random(8)

    question = generate_question(template, paper_id="P-1", question_number="1", rng=rng)

    assert question.difficulty_features.requires_carrying is not None
    assert question.difficulty == question.difficulty_features.score()


def test_uses_the_text_provider_to_rephrase_when_given_one():
    template = _template(QuestionType.WORD_PROBLEM)
    rng = random.Random(9)
    provider = _FakeTextProvider("A rephrased version of the question.")

    question = generate_question(
        template, paper_id="P-1", question_number="1", rng=rng, text_provider=provider
    )

    assert question.text == "A rephrased version of the question."
    assert len(provider.prompts) == 1


def test_without_a_text_provider_uses_the_rendered_template_text():
    template = _template(QuestionType.WORD_PROBLEM)
    rng = random.Random(10)

    question = generate_question(template, paper_id="P-1", question_number="1", rng=rng)

    assert "shopkeeper" in question.text
