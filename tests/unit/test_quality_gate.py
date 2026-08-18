import cv2
import numpy as np

from app.backend.preprocessing.quality_gate import (
    evaluate_quality,
    measure_sharpness,
    measure_skew_degrees,
)


def test_evaluate_quality_passes_when_both_metrics_are_within_tolerance():
    report = evaluate_quality(
        skew_degrees=5, sharpness_score=200, max_skew_degrees=20, min_sharpness=100
    )
    assert report.verdict == "pass"


def test_evaluate_quality_fails_when_both_metrics_are_outside_tolerance():
    report = evaluate_quality(
        skew_degrees=45, sharpness_score=10, max_skew_degrees=20, min_sharpness=100
    )
    assert report.verdict == "fail"


def test_evaluate_quality_flags_when_exactly_one_metric_is_outside_tolerance():
    report = evaluate_quality(
        skew_degrees=45, sharpness_score=200, max_skew_degrees=20, min_sharpness=100
    )
    assert report.verdict == "flagged"
    assert report.skew_within_tolerance is False
    assert report.sharpness_acceptable is True


def test_measure_sharpness_scores_a_sharp_checkerboard_higher_than_a_blurred_one():
    checkerboard = np.indices((100, 100)).sum(axis=0) % 2 * 255
    sharp = checkerboard.astype(np.uint8)
    blurred = cv2.GaussianBlur(sharp, (25, 25), 10)

    assert measure_sharpness(sharp) > measure_sharpness(blurred)


def test_measure_skew_degrees_reads_the_angle_from_the_top_edge():
    # top-left, top-right, bottom-right, bottom-left; top edge rotated ~10 degrees
    corners = np.array([[0, 0], [100, 17.6], [100, 117.6], [0, 100]], dtype=np.float32)

    skew = measure_skew_degrees(corners)

    assert 9.5 < skew < 10.5


def test_measure_skew_degrees_is_zero_when_corners_are_unknown():
    assert measure_skew_degrees(None) == 0.0
