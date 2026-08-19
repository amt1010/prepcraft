import pytest

from app.backend.generation.formulas import (
    addition_requires_carrying,
    predecessor,
    round_to_nearest,
    successor,
    to_roman_numeral,
)


@pytest.mark.parametrize(
    "n, roman",
    [
        (1, "I"),
        (4, "IV"),
        (9, "IX"),
        (14, "XIV"),
        (40, "XL"),
        (90, "XC"),
        (400, "CD"),
        (900, "CM"),
        (1994, "MCMXCIV"),
        (3999, "MMMCMXCIX"),
    ],
)
def test_to_roman_numeral_known_values(n, roman):
    assert to_roman_numeral(n) == roman


def test_to_roman_numeral_rejects_zero():
    with pytest.raises(ValueError):
        to_roman_numeral(0)


def test_to_roman_numeral_rejects_above_3999():
    with pytest.raises(ValueError):
        to_roman_numeral(4000)


def test_round_to_nearest_rounds_down_below_half():
    assert round_to_nearest(24, 10) == 20


def test_round_to_nearest_rounds_half_up():
    # Python's round() uses round-half-to-even (25 -> 20); classroom
    # convention is round-half-up (25 -> 30).
    assert round_to_nearest(25, 10) == 30


def test_round_to_nearest_hundred():
    assert round_to_nearest(449, 100) == 400
    assert round_to_nearest(450, 100) == 500


def test_predecessor_and_successor():
    assert predecessor(24) == 23
    assert successor(24) == 25


def test_addition_requires_carrying_spec_easy_example():
    # spec §16 "Easy": 245 + 123 — no column carries
    assert addition_requires_carrying(245, 123) is False


def test_addition_requires_carrying_spec_medium_example():
    # spec §16 "Medium": 378 + 246 — every column carries
    assert addition_requires_carrying(378, 246) is True
