from dataclasses import dataclass
from typing import Literal

import cv2
import numpy as np

Verdict = Literal["pass", "flagged", "fail"]


@dataclass
class QualityReport:
    skew_degrees: float
    skew_within_tolerance: bool
    sharpness_score: float
    sharpness_acceptable: bool
    verdict: Verdict


def measure_sharpness(image: np.ndarray) -> float:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def measure_skew_degrees(corners: np.ndarray | None) -> float:
    if corners is None:
        return 0.0
    top_left, top_right = corners[0], corners[1]
    delta = top_right - top_left
    return float(abs(np.degrees(np.arctan2(delta[1], delta[0]))))


def evaluate_quality(
    skew_degrees: float,
    sharpness_score: float,
    max_skew_degrees: float,
    min_sharpness: float,
) -> QualityReport:
    skew_ok = skew_degrees <= max_skew_degrees
    sharpness_ok = sharpness_score >= min_sharpness

    if skew_ok and sharpness_ok:
        verdict: Verdict = "pass"
    elif not skew_ok and not sharpness_ok:
        verdict = "fail"
    else:
        verdict = "flagged"

    return QualityReport(
        skew_degrees=skew_degrees,
        skew_within_tolerance=skew_ok,
        sharpness_score=sharpness_score,
        sharpness_acceptable=sharpness_ok,
        verdict=verdict,
    )
