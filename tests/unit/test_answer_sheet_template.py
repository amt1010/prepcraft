from datetime import datetime

from reportlab.platypus import Paragraph

from app.backend.models.answer_key import AnswerKey, AnswerKeyEntry
from app.backend.models.paper import Paper, Section
from app.backend.rendering.templates.answer_sheet import build_flowables


def _entry(**overrides) -> AnswerKeyEntry:
    fields = {
        "question_id": "Q-1",
        "question_number": "1",
        "answer": "72",
        "marks": 1.0,
    }
    fields.update(overrides)
    return AnswerKeyEntry(**fields)


def _paper() -> Paper:
    return Paper(
        id="P-1",
        subject="Mathematics",
        class_standard="III",
        total_marks=1.0,
        duration_minutes=50,
        sections=[Section(name="A", marks=1.0)],
        source="existing_paper",
        created_at=datetime.now(),
    )


def _paragraph_texts(flowables) -> list[str]:
    return [f.text for f in flowables if isinstance(f, Paragraph)]


def _index_containing(texts: list[str], needle: str) -> int:
    return next(i for i, t in enumerate(texts) if needle in t)


def test_title_includes_subject_class_and_answer_key_label():
    key = AnswerKey(id="ANSKEY-1", paper_id="P-1", entries=[])

    title = build_flowables(_paper(), key)[0]

    assert isinstance(title, Paragraph)
    assert "Mathematics" in title.text
    assert "III" in title.text
    assert "Answer Key" in title.text


def test_entry_line_includes_number_answer_and_marks():
    key = AnswerKey(
        id="ANSKEY-1",
        paper_id="P-1",
        entries=[_entry(question_number="1", answer="72", marks=1.0)],
    )

    texts = _paragraph_texts(build_flowables(_paper(), key))

    assert any(t.startswith("1. 72") and "[1.0 marks]" in t for t in texts)


def test_working_line_appears_when_present():
    key = AnswerKey(
        id="ANSKEY-1",
        paper_id="P-1",
        entries=[_entry(working="47 + 25 = 72")],
    )

    texts = _paragraph_texts(build_flowables(_paper(), key))

    assert any("Working: 47 + 25 = 72" in t for t in texts)


def test_no_working_line_when_absent():
    key = AnswerKey(id="ANSKEY-1", paper_id="P-1", entries=[_entry()])

    texts = _paragraph_texts(build_flowables(_paper(), key))

    assert not any("Working:" in t for t in texts)


def test_entries_render_in_the_order_given():
    key = AnswerKey(
        id="ANSKEY-1",
        paper_id="P-1",
        entries=[
            _entry(question_number="10", answer="second"),
            _entry(question_number="2", answer="first"),
        ],
    )

    texts = _paragraph_texts(build_flowables(_paper(), key))

    assert _index_containing(texts, "10. second") < _index_containing(texts, "2. first")
