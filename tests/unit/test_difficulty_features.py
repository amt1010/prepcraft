from app.backend.models.question import DifficultyFeatures


def test_easy_addition_with_no_carrying_scores_lowest():
    # spec §16 "Easy": 245 + 123 — no carrying, one operation, one step
    features = DifficultyFeatures(
        digit_count=3,
        operation_count=1,
        requires_carrying=False,
        step_count=1,
        vocabulary_level="basic",
        reasoning_required=False,
    )

    assert features.score() == 1


def test_medium_addition_with_carrying_scores_higher_than_easy():
    # spec §16 "Medium": 378 + 246 — same shape as Easy, but every column carries
    features = DifficultyFeatures(
        digit_count=3,
        operation_count=1,
        requires_carrying=True,
        step_count=1,
        vocabulary_level="basic",
        reasoning_required=False,
    )

    assert features.score() == 2


def test_harder_multi_step_word_problem_scores_highest():
    # spec §16 "Harder": shop has 458 books, receives 267, gives away 125,
    # how many remain — two operations, two steps, reasoning required,
    # word-problem vocabulary
    features = DifficultyFeatures(
        digit_count=3,
        operation_count=2,
        requires_carrying=True,
        step_count=2,
        vocabulary_level="advanced",
        reasoning_required=True,
    )

    assert features.score() == 5


def test_score_never_exceeds_five():
    features = DifficultyFeatures(
        digit_count=6,
        operation_count=4,
        requires_carrying=True,
        step_count=4,
        vocabulary_level="advanced",
        reasoning_required=True,
    )

    assert features.score() == 5


def test_score_treats_a_none_requires_carrying_as_no_bonus():
    # requires_carrying is None for question types where carrying doesn't
    # apply at all (e.g. roman_numeral, true_false) — must not raise and
    # must not be scored as if it were True
    features = DifficultyFeatures(
        operation_count=1,
        requires_carrying=None,
        step_count=1,
        vocabulary_level="basic",
        reasoning_required=False,
    )

    assert features.score() == 1
