"""Deterministic "the spec gives a formula" computations (PROJECT_PLAN.md's
"What's deterministic vs. AI" list: "Roman numeral conversion, arithmetic
evaluation, rounding, predecessor/successor — anywhere the spec gives a
formula"). Plain arithmetic already has a home in
validation/answer_engine.py's restricted evaluator; this module holds the
formulas that aren't a bare arithmetic expression over declared variables."""

_ROMAN_NUMERAL_VALUES: list[tuple[int, str]] = [
    (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
    (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
    (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
]


def to_roman_numeral(n: int) -> str:
    if not 1 <= n <= 3999:
        raise ValueError(f"roman numeral conversion only supports 1-3999, got {n}")
    symbols = []
    remaining = n
    for value, symbol in _ROMAN_NUMERAL_VALUES:
        while remaining >= value:
            symbols.append(symbol)
            remaining -= value
    return "".join(symbols)


def round_to_nearest(n: int, base: int) -> int:
    """Round-half-up, matching classroom convention (Python's round() uses
    round-half-to-even, which would round 25 to the nearest 10 down to 20)."""
    quotient, remainder = divmod(n, base)
    if remainder * 2 >= base:
        quotient += 1
    return quotient * base


def predecessor(n: int) -> int:
    return n - 1


def successor(n: int) -> int:
    return n + 1


def addition_requires_carrying(a: int, b: int) -> bool:
    x, y = abs(a), abs(b)
    while x or y:
        if (x % 10) + (y % 10) >= 10:
            return True
        x //= 10
        y //= 10
    return False
