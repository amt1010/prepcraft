import pytest

from app.backend.validation.answer_engine import evaluate


def test_evaluates_simple_addition():
    assert evaluate("47 + 25") == 72


def test_evaluates_subtraction():
    assert evaluate("100 - 37") == 63


def test_evaluates_multiplication():
    assert evaluate("6 * 7") == 42


def test_evaluates_division():
    assert evaluate("20 / 4") == 5


def test_respects_operator_precedence():
    assert evaluate("2 + 3 * 4") == 14


def test_respects_parentheses():
    assert evaluate("(2 + 3) * 4") == 20


def test_supports_unary_negation():
    assert evaluate("-5 + 10") == 5


def test_substitutes_variables():
    assert evaluate("a + b", {"a": 3, "b": 4}) == 7


def test_raises_on_undefined_variable():
    with pytest.raises(ValueError, match="undefined variable"):
        evaluate("a + 1")


def test_raises_on_function_call():
    with pytest.raises(ValueError):
        evaluate("__import__('os').system('ls')")


def test_raises_on_attribute_access():
    with pytest.raises(ValueError):
        evaluate("a.b", {"a": 1})


def test_raises_on_syntax_error():
    with pytest.raises(ValueError):
        evaluate("47 +")
