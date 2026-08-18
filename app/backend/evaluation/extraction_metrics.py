"""EVALUATION.md's question extraction row: extraction recall (questions
correctly extracted / questions expected) and per-field accuracy (type,
marks, question_number, ...), both matched by question_number against
tests/fixtures/expected/<doc>/questions.json."""


def compute_extraction_recall(extracted: list[dict], expected: list[dict]) -> float:
    if not expected:
        return 1.0
    expected_numbers = {q["question_number"] for q in expected}
    extracted_numbers = {q["question_number"] for q in extracted}
    matched = expected_numbers & extracted_numbers
    return len(matched) / len(expected_numbers)


def compute_field_accuracy(extracted: list[dict], expected: list[dict], field: str) -> float:
    expected_by_number = {q["question_number"]: q for q in expected}
    matched_extracted = [q for q in extracted if q["question_number"] in expected_by_number]
    if not matched_extracted:
        return 0.0
    correct = sum(
        1
        for q in matched_extracted
        if q.get(field) == expected_by_number[q["question_number"]].get(field)
    )
    return correct / len(matched_extracted)
