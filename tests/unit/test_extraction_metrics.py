from app.backend.evaluation.extraction_metrics import (
    compute_extraction_recall,
    compute_field_accuracy,
)


def test_extraction_recall_is_one_when_every_expected_question_was_extracted():
    expected = [{"question_number": "1a"}, {"question_number": "1b"}]
    extracted = [{"question_number": "1a"}, {"question_number": "1b"}, {"question_number": "2a"}]

    assert compute_extraction_recall(extracted, expected) == 1.0


def test_extraction_recall_reflects_missing_questions():
    expected = [{"question_number": "1a"}, {"question_number": "1b"}]
    extracted = [{"question_number": "1a"}]

    assert compute_extraction_recall(extracted, expected) == 0.5


def test_extraction_recall_is_one_when_nothing_is_expected():
    assert compute_extraction_recall([], []) == 1.0


def test_field_accuracy_matches_by_question_number_and_compares_one_field():
    expected = [
        {"question_number": "1a", "type": "multiple_choice", "marks": 0.5},
        {"question_number": "1b", "type": "arithmetic", "marks": 0.5},
    ]
    extracted = [
        {"question_number": "1a", "type": "multiple_choice", "marks": 0.5},
        {"question_number": "1b", "type": "fill_in_the_blank", "marks": 0.5},
    ]

    assert compute_field_accuracy(extracted, expected, "type") == 0.5
    assert compute_field_accuracy(extracted, expected, "marks") == 1.0


def test_field_accuracy_ignores_extracted_questions_not_in_expected():
    expected = [{"question_number": "1a", "type": "multiple_choice"}]
    extracted = [
        {"question_number": "1a", "type": "multiple_choice"},
        {"question_number": "9z", "type": "arithmetic"},
    ]

    assert compute_field_accuracy(extracted, expected, "type") == 1.0


def test_field_accuracy_is_zero_when_no_extracted_question_matches_expected():
    expected = [{"question_number": "1a", "type": "multiple_choice"}]
    extracted = [{"question_number": "9z", "type": "arithmetic"}]

    assert compute_field_accuracy(extracted, expected, "type") == 0.0
