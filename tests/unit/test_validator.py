from app.backend.models.question import DifficultyFeatures, Question, QuestionType
from app.backend.validation.validator import validate_question


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
        "text": "47 + 25",
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


def test_a_correct_arithmetic_question_has_no_issues():
    assert validate_question(_question()) == []


def test_spec_47_plus_25_stated_as_73_fails_validation():
    question = _question(text="47 + 25", expected_answer="73")

    issues = validate_question(question)

    assert len(issues) == 1
    assert issues[0].code == "arithmetic_mismatch"
    assert issues[0].question_number == "1"


def test_missing_expected_answer_is_flagged():
    question = _question(expected_answer="")

    issues = validate_question(question)

    assert any(issue.code == "missing_answer" for issue in issues)


def test_multiple_choice_without_options_is_flagged():
    question = _question(
        type=QuestionType.MULTIPLE_CHOICE, text="Pick one", expected_answer="A", options=None
    )

    issues = validate_question(question)

    assert any(issue.code == "multiple_choice_missing_options" for issue in issues)


def test_multiple_choice_answer_not_in_options_is_flagged():
    question = _question(
        type=QuestionType.MULTIPLE_CHOICE,
        text="Pick one",
        expected_answer="D",
        options=["A", "B", "C"],
    )

    issues = validate_question(question)

    assert any(issue.code == "answer_not_in_options" for issue in issues)


def test_multiple_choice_answer_in_options_has_no_issues():
    question = _question(
        type=QuestionType.MULTIPLE_CHOICE,
        text="Pick one",
        expected_answer="B",
        options=["A", "B", "C"],
    )

    assert validate_question(question) == []


def test_arithmetic_question_with_unparseable_text_is_skipped_not_flagged():
    question = _question(
        type=QuestionType.ARITHMETIC,
        text="A shopkeeper sold some items",
        expected_answer="unknown",
    )

    assert validate_question(question) == []
