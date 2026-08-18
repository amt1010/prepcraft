from app.backend.evaluation.ocr_metrics import compute_character_accuracy, compute_word_accuracy


def test_character_accuracy_is_one_for_an_exact_match():
    assert compute_character_accuracy("hello world", "hello world") == 1.0


def test_character_accuracy_reflects_edit_distance():
    # "hello" -> "hallo" is 1 substitution out of 11 reference characters
    accuracy = compute_character_accuracy("hallo world", "hello world")
    assert accuracy == 1.0 - 1 / 11


def test_character_accuracy_does_not_go_below_zero_for_a_very_wrong_prediction():
    accuracy = compute_character_accuracy("completely different text here", "a")
    assert accuracy == 0.0


def test_word_accuracy_is_one_for_an_exact_match():
    assert compute_word_accuracy("hello world", "hello world") == 1.0


def test_word_accuracy_counts_only_position_matched_words():
    # "hello" matches, "there" != "world"
    accuracy = compute_word_accuracy("hello there", "hello world")
    assert accuracy == 0.5


def test_word_accuracy_is_zero_when_reference_is_empty_and_prediction_is_not():
    assert compute_word_accuracy("extra", "") == 0.0


def test_word_accuracy_is_one_when_both_are_empty():
    assert compute_word_accuracy("", "") == 1.0
