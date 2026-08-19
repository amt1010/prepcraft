from app.backend.models.answer_key import AnswerKey, AnswerKeyEntry


def _entry(**overrides) -> AnswerKeyEntry:
    fields = {
        "question_id": "Q-1",
        "question_number": "1",
        "answer": "72",
        "marks": 1.0,
    }
    fields.update(overrides)
    return AnswerKeyEntry(**fields)


def test_builds_a_valid_answer_key():
    key = AnswerKey(id="ANSKEY-1", paper_id="PAPER-1", entries=[_entry()])

    assert key.paper_id == "PAPER-1"
    assert key.entries[0].answer == "72"


def test_entry_working_defaults_to_none_but_can_be_set():
    default_entry = _entry()
    entry_with_working = _entry(working="47 + 25 = 72")

    assert default_entry.working is None
    assert entry_with_working.working == "47 + 25 = 72"


def test_answer_key_can_have_no_entries():
    key = AnswerKey(id="ANSKEY-1", paper_id="PAPER-1", entries=[])

    assert key.entries == []
