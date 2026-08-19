import random

import pytest

from app.backend.generation.variable_sampler import sample_variables


def test_samples_one_value_per_declared_variable():
    variables = sample_variables({"a": "3_digit_number", "b": "2_digit_number"}, random.Random(1))

    assert set(variables) == {"a", "b"}


@pytest.mark.parametrize(
    "kind, low, high",
    [
        ("1_digit_number", 1, 9),
        ("2_digit_number", 10, 99),
        ("3_digit_number", 100, 999),
        ("4_digit_number", 1000, 9999),
        ("small_number_1_50", 1, 50),
    ],
)
def test_each_kind_samples_within_its_range(kind, low, high):
    rng = random.Random(7)
    for _ in range(50):
        value = sample_variables({"x": kind}, rng)["x"]
        assert low <= value <= high


def test_unknown_kind_raises_value_error():
    with pytest.raises(ValueError, match="unknown variable kind"):
        sample_variables({"a": "not_a_real_kind"}, random.Random(1))


def test_same_seed_produces_the_same_values():
    spec = {"a": "3_digit_number", "b": "3_digit_number"}

    first = sample_variables(spec, random.Random(99))
    second = sample_variables(spec, random.Random(99))

    assert first == second
