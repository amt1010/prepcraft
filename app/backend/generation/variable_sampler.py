"""Samples fresh variable values for a QuestionTemplate (PIPELINE.md's
shared tail: "Variable sampling — generate new values per template's
variable spec"). Each template declares variables as {"a": "3_digit_number"}
(DATA_MODEL.md); this module is the only place that maps a variable "kind"
string to a concrete numeric range, so adding a new kind means editing one
dict, not hunting through every template. Callers pass their own
random.Random so generation is reproducible under a seed — never the
module-level random.* functions."""

import random

_KIND_RANGES: dict[str, tuple[int, int]] = {
    "1_digit_number": (1, 9),
    "2_digit_number": (10, 99),
    "3_digit_number": (100, 999),
    "4_digit_number": (1000, 9999),
    "small_number_1_50": (1, 50),
}


def sample_variables(spec: dict[str, str], rng: random.Random) -> dict[str, int]:
    variables: dict[str, int] = {}
    for name, kind in spec.items():
        if kind not in _KIND_RANGES:
            raise ValueError(f"unknown variable kind: {kind!r}")
        low, high = _KIND_RANGES[kind]
        variables[name] = rng.randint(low, high)
    return variables
