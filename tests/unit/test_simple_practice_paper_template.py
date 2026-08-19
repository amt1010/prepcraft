from datetime import datetime

from reportlab.platypus import Paragraph

from app.backend.models.paper import Paper, Section
from app.backend.models.question import DifficultyFeatures, Question, QuestionType
from app.backend.rendering.templates.simple_practice_paper import build_flowables


def _difficulty_features() -> DifficultyFeatures:
    return DifficultyFeatures(
        operation_count=1,
        requires_carrying=False,
        step_count=1,
        vocabulary_level="basic",
        reasoning_required=False,
    )


def _question(**overrides) -> Question:
    fields = {
        "id": "Q-1",
        "paper_id": "P-1",
        "question_number": "1",
        "type": QuestionType.ARITHMETIC,
        "text": "47 + 25 = ?",
        "marks": 1.0,
        "topic": "Addition",
        "difficulty": 1,
        "difficulty_features": _difficulty_features(),
        "expected_answer": "72",
        "answer_type": "numeric",
        "source": "existing_paper",
    }
    fields.update(overrides)
    return Question(**fields)


def _paper() -> Paper:
    return Paper(
        id="P-1",
        subject="Mathematics",
        class_standard="III",
        total_marks=2.0,
        duration_minutes=50,
        sections=[Section(name="A", marks=2.0)],
        source="existing_paper",
        created_at=datetime.now(),
    )


def _paragraph_texts(flowables) -> list[str]:
    return [f.text for f in flowables if isinstance(f, Paragraph)]


def test_title_includes_subject_and_class():
    flowables = build_flowables(_paper(), [])

    title = flowables[0]
    assert isinstance(title, Paragraph)
    assert "Mathematics" in title.text
    assert "III" in title.text


def test_meta_line_includes_total_marks_and_duration():
    flowables = build_flowables(_paper(), [])

    meta = flowables[1]
    assert isinstance(meta, Paragraph)
    assert "2.0" in meta.text
    assert "50" in meta.text


def test_question_number_text_and_marks_appear_together():
    question = _question(question_number="1", text="47 + 25 = ?", marks=1.0)

    texts = _paragraph_texts(build_flowables(_paper(), [question]))

    assert any(t.startswith("1. 47 + 25 = ?") and "[1.0 marks]" in t for t in texts)


def _index_containing(texts: list[str], needle: str) -> int:
    return next(i for i, t in enumerate(texts) if needle in t)


def test_multiple_choice_options_are_lettered_in_order():
    question = _question(
        question_number="1",
        type=QuestionType.MULTIPLE_CHOICE,
        text="Pick the right sum",
        options=["10", "20", "30"],
        expected_answer="20",
        answer_type="choice",
    )

    texts = _paragraph_texts(build_flowables(_paper(), [question]))

    assert any(t.startswith("(a)") and "10" in t for t in texts)
    assert any(t.startswith("(b)") and "20" in t for t in texts)
    assert any(t.startswith("(c)") and "30" in t for t in texts)


def test_non_multiple_choice_question_has_no_option_lines():
    question = _question(type=QuestionType.ARITHMETIC, text="47 + 25 = ?")

    texts = _paragraph_texts(build_flowables(_paper(), [question]))

    assert not any(t.startswith("(a)") for t in texts)


def test_questions_render_in_the_order_given_not_sorted():
    first = _question(question_number="10", text="Second in the list")
    second = _question(question_number="2", text="First in the list")

    texts = _paragraph_texts(build_flowables(_paper(), [first, second]))

    assert _index_containing(texts, "10. Second in the list") < _index_containing(
        texts, "2. First in the list"
    )
