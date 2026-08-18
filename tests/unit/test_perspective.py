import cv2
import numpy as np

from app.backend.preprocessing.perspective import correct_perspective, estimate_rotation_via_hough


def _line_image(angle_degrees: float) -> np.ndarray:
    """A 300x300 white canvas with one long black line through the center
    at a known angle — Hough should recover exactly this angle, since it's
    computed with the same arctan2 formula the line was drawn from."""
    canvas = np.full((300, 300, 3), 255, dtype=np.uint8)
    length = 250
    angle_rad = np.radians(angle_degrees)
    dx = int(length / 2 * np.cos(angle_rad))
    dy = int(length / 2 * np.sin(angle_rad))
    center = (150, 150)
    p1 = (center[0] - dx, center[1] - dy)
    p2 = (center[0] + dx, center[1] + dy)
    cv2.line(canvas, p1, p2, (0, 0, 0), 3)
    return canvas


def test_estimate_rotation_via_hough_recovers_a_known_line_angle():
    image = _line_image(angle_degrees=8.0)

    angle = estimate_rotation_via_hough(image)

    assert 7.0 < angle < 9.0


def test_estimate_rotation_via_hough_returns_near_zero_for_an_already_horizontal_line():
    image = _line_image(angle_degrees=0.0)

    angle = estimate_rotation_via_hough(image)

    assert abs(angle) < 1.0


def test_estimate_rotation_via_hough_returns_zero_when_no_lines_are_found():
    blank = np.full((100, 100, 3), 255, dtype=np.uint8)

    assert estimate_rotation_via_hough(blank) == 0.0


def test_correct_perspective_leaves_an_already_horizontal_image_unchanged():
    image = _line_image(angle_degrees=0.0)

    result = correct_perspective(image)

    assert np.array_equal(result, image)


def test_correct_perspective_straightens_a_rotated_image():
    image = _line_image(angle_degrees=8.0)

    result = correct_perspective(image)

    corrected_angle = estimate_rotation_via_hough(result)
    assert abs(corrected_angle) < 1.0
