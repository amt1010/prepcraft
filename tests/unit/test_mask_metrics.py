import numpy as np

from app.backend.evaluation.mask_metrics import compute_mask_precision_recall


def test_perfect_match_gives_precision_and_recall_of_one():
    mask = np.zeros((10, 10), dtype=bool)
    mask[2:5, 2:5] = True

    precision, recall = compute_mask_precision_recall(mask, mask)

    assert precision == 1.0
    assert recall == 1.0


def test_no_overlap_gives_zero_precision_and_recall():
    predicted = np.zeros((10, 10), dtype=bool)
    predicted[0:2, 0:2] = True
    ground_truth = np.zeros((10, 10), dtype=bool)
    ground_truth[8:10, 8:10] = True

    precision, recall = compute_mask_precision_recall(predicted, ground_truth)

    assert precision == 0.0
    assert recall == 0.0


def test_partial_overlap_computes_correct_ratios():
    predicted = np.zeros((10, 10), dtype=bool)
    predicted[0:4, 0:1] = True  # 4 predicted-positive pixels
    ground_truth = np.zeros((10, 10), dtype=bool)
    ground_truth[0:2, 0:1] = True  # 2 actual-positive pixels, both inside predicted

    precision, recall = compute_mask_precision_recall(predicted, ground_truth)

    assert precision == 0.5  # 2 true positives / 4 predicted positives
    assert recall == 1.0     # 2 true positives / 2 actual positives


def test_empty_prediction_gives_zero_precision_not_a_division_error():
    predicted = np.zeros((10, 10), dtype=bool)
    ground_truth = np.zeros((10, 10), dtype=bool)
    ground_truth[0:2, 0:2] = True

    precision, recall = compute_mask_precision_recall(predicted, ground_truth)

    assert precision == 0.0
    assert recall == 0.0
