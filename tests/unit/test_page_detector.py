import cv2
import numpy as np

from app.backend.ingestion.page_detector import detect_page


def _synthetic_page(rotation_degrees: float = 0.0) -> np.ndarray:
    """A black 300x300 canvas with a white 220x160 rectangle (the 'page'),
    rotated in-place, centered — a controlled fixture instead of a real
    photo, so the expected corners are known exactly. Sized to ~39% of
    the canvas area, comfortably above detect_page's 30% area cutoff —
    not right at the boundary, where contour rounding could flip a test."""
    canvas = np.zeros((300, 300, 3), dtype=np.uint8)
    rect = ((150, 150), (220, 160), rotation_degrees)
    box = cv2.boxPoints(rect).astype(np.int32)
    cv2.fillPoly(canvas, [box], (255, 255, 255))
    return canvas


def test_detects_an_unrotated_page_with_high_confidence():
    result = detect_page(_synthetic_page(rotation_degrees=0.0))

    assert result.corners is not None
    # confidence = detected_area / image_area; the fixture rectangle is
    # ~39% of the canvas, so a correct detection lands close to that,
    # comfortably above the 30% area cutoff detect_page itself applies.
    assert result.confidence > 0.35
    # Warped output should be roughly the rectangle's own aspect ratio
    height, width = result.image.shape[:2]
    assert 1.2 < width / height < 1.6  # ~220/160 = 1.375


def test_detects_a_rotated_page_and_returns_four_corners():
    result = detect_page(_synthetic_page(rotation_degrees=15.0))

    assert result.corners is not None
    assert result.corners.shape == (4, 2)


def test_falls_back_to_the_full_frame_when_no_quad_is_found():
    blank = np.full((100, 100, 3), 255, dtype=np.uint8)  # no edges at all

    result = detect_page(blank)

    assert result.corners is None
    assert result.confidence == 0.5
    assert result.image.shape == blank.shape
