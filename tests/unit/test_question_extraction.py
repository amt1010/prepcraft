from app.backend.ocr.layout_analysis import LayoutGroup
from app.backend.questions.extraction import (
    ExtractedSubQuestion,
    QuestionGroupExtraction,
    extract_questions,
)


class _FakeTextProvider:
    def __init__(self, response: QuestionGroupExtraction):
        self.response = response
        self.prompts: list[str] = []

    def generate(self, prompt: str, schema):
        self.prompts.append(prompt)
        return self.response


def test_extract_questions_without_a_provider_passes_groups_through_unclassified():
    groups = [LayoutGroup(question_number="1", text="What is 2+2? i.3 ii.4 iii.5")]

    result = extract_questions(groups, text_provider=None)

    assert result == [
        ExtractedSubQuestion(question_number="1", text="What is 2+2? i.3 ii.4 iii.5", type="unknown")
    ]


def test_extract_questions_uses_the_provider_to_split_and_classify_a_group():
    groups = [LayoutGroup(question_number="1", text="a. 405 + 305 = 800 b. 450 [0.5X2=1]")]
    fake_response = QuestionGroupExtraction(
        questions=[
            ExtractedSubQuestion(
                question_number="1a",
                text="405 + 305 = 800. What is the missing number?",
                type="fill_in_the_blank",
                marks=0.5,
                topic="Addition",
                difficulty=2,
            ),
            ExtractedSubQuestion(
                question_number="1b",
                text="What should be added to get 450?",
                type="arithmetic",
                marks=0.5,
                topic="Addition",
                difficulty=2,
            ),
        ]
    )
    provider = _FakeTextProvider(fake_response)

    result = extract_questions(groups, text_provider=provider)

    assert result == fake_response.questions
    assert len(provider.prompts) == 1
    assert "a. 405 + 305 = 800 b. 450 [0.5X2=1]" in provider.prompts[0]


def test_extract_questions_calls_the_provider_once_per_group():
    groups = [
        LayoutGroup(question_number="1", text="first group"),
        LayoutGroup(question_number="2", text="second group"),
    ]
    provider = _FakeTextProvider(QuestionGroupExtraction(questions=[]))

    extract_questions(groups, text_provider=provider)

    assert len(provider.prompts) == 2
