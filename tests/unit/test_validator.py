from app.backend.models.paper import Paper, Section
from app.backend.models.question import DifficultyFeatures, Question, QuestionType
from app.backend.validation.validator import validate_paper, validate_question


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


def _paper(total_marks: float) -> Paper:
    return Paper(
        id="P-1",
        subject="Mathematics",
        class_standard="III",
        total_marks=total_marks,
        duration_minutes=50,
        sections=[Section(name="A", marks=total_marks)],
        source="existing_paper",
        created_at="2026-08-19T00:00:00",
    )


def test_paper_with_marks_not_summing_to_total_is_flagged():
    paper = _paper(total_marks=5.0)
    questions = [_question(marks=1.0)]

    issues = validate_paper(paper, questions)

    assert any(issue.code == "marks_mismatch" for issue in issues)


def test_paper_with_matching_marks_has_no_marks_issue():
    paper = _paper(total_marks=1.0)
    questions = [_question(marks=1.0)]

    issues = validate_paper(paper, questions)

    assert not any(issue.code == "marks_mismatch" for issue in issues)


def test_duplicate_question_text_is_flagged():
    paper = _paper(total_marks=2.0)
    questions = [
        _question(question_number="1", marks=1.0),
        _question(question_number="2", marks=1.0),
    ]

    issues = validate_paper(paper, questions)

    assert any(
        issue.code == "duplicate_question" and issue.question_number == "2"
        for issue in issues
    )


def test_answer_leaked_into_question_text_is_flagged():
    paper = _paper(total_marks=1.0)
    questions = [
        _question(
            type=QuestionType.FILL_BLANK,
            text="The answer is 72, what is 47 + 25?",
            expected_answer="72",
            marks=1.0,
        )
    ]

    issues = validate_paper(paper, questions)

    assert any(issue.code == "answer_leakage" for issue in issues)


def test_multiple_choice_options_are_not_treated_as_leakage():
    paper = _paper(total_marks=1.0)
    questions = [
        _question(
            type=QuestionType.MULTIPLE_CHOICE,
            text="Pick one: A, B, C",
            expected_answer="A",
            options=["A", "B", "C"],
            marks=1.0,
        )
    ]

    issues = validate_paper(paper, questions)

    assert not any(issue.code == "answer_leakage" for issue in issues)
