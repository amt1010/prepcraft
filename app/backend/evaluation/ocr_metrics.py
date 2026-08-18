"""EVALUATION.md's OCR row: character accuracy (1 - normalized Levenshtein
distance) and word accuracy (exact word match rate after tokenization),
both against a hand-transcribed reference page of text."""


def _levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    previous_row = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        current_row = [i] + [0] * len(b)
        for j, char_b in enumerate(b, start=1):
            insert_cost = current_row[j - 1] + 1
            delete_cost = previous_row[j] + 1
            substitute_cost = previous_row[j - 1] + (char_a != char_b)
            current_row[j] = min(insert_cost, delete_cost, substitute_cost)
        previous_row = current_row
    return previous_row[-1]


def compute_character_accuracy(predicted: str, reference: str) -> float:
    if not reference:
        return 1.0 if not predicted else 0.0
    distance = _levenshtein(predicted, reference)
    return max(0.0, 1.0 - distance / len(reference))


def compute_word_accuracy(predicted: str, reference: str) -> float:
    predicted_words = predicted.split()
    reference_words = reference.split()
    if not reference_words:
        return 1.0 if not predicted_words else 0.0
    matches = sum(1 for p, r in zip(predicted_words, reference_words) if p == r)
    return matches / len(reference_words)
