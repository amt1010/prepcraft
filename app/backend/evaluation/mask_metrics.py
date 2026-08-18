import numpy as np


def compute_mask_precision_recall(
    predicted: np.ndarray, ground_truth: np.ndarray
) -> tuple[float, float]:
    """Pixel-level precision/recall of a predicted boolean mask against a
    hand-labeled ground-truth boolean mask (EVALUATION.md's annotation
    mask precision/recall metric)."""
    true_positives = np.logical_and(predicted, ground_truth).sum()
    predicted_positives = predicted.sum()
    actual_positives = ground_truth.sum()

    precision = float(true_positives / predicted_positives) if predicted_positives > 0 else 0.0
    recall = float(true_positives / actual_positives) if actual_positives > 0 else 0.0
    return precision, recall
