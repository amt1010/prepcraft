"""Restricted arithmetic expression evaluator (DATA_MODEL.md: "answer_expression
is parsed and evaluated with a restricted expression evaluator (arithmetic
operators only, no eval() on arbitrary strings)"). This is the deterministic
mechanism behind spec §21's example — recomputing 47 + 25 to catch a stated
answer of 73 — and the only thing in this module allowed to touch an
expression string. AST node types are whitelisted explicitly; anything not
listed (calls, attribute access, comparisons, ...) raises ValueError."""

import ast
import operator

_BINARY_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}

_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def evaluate(expression: str, variables: dict[str, float] | None = None) -> float:
    variables = variables or {}
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"not a valid expression: {expression!r}") from exc
    return _eval_node(tree.body, variables)


def _eval_node(node: ast.AST, variables: dict[str, float]) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.Name):
        if node.id not in variables:
            raise ValueError(f"undefined variable: {node.id}")
        return variables[node.id]
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPS:
        left = _eval_node(node.left, variables)
        right = _eval_node(node.right, variables)
        return _BINARY_OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand, variables))
    raise ValueError(f"disallowed expression element: {ast.dump(node)}")
