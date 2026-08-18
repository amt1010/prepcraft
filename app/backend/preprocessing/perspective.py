import cv2
import numpy as np


def estimate_rotation_via_hough(image: np.ndarray) -> float:
    """Signed rotation angle (degrees) needed to straighten near-horizontal
    lines in the image. Returns 0.0 if no reliable line signal is found."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 180,
        threshold=100,
        minLineLength=image.shape[1] // 4,
        maxLineGap=10,
    )
    if lines is None:
        return 0.0

    angles = []
    for line in lines:
        x1, y1, x2, y2 = line.flatten()
        angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        if abs(angle) < 45:  # only near-horizontal lines are text/edge signal
            angles.append(angle)

    if not angles:
        return 0.0
    return float(np.median(angles))


def correct_perspective(image: np.ndarray) -> np.ndarray:
    """Estimates any residual rotation via Hough line detection and
    straightens it. Works whether or not PageDetector already
    perspective-warped the image — a well-warped page measures ~0
    residual rotation and passes through unchanged."""
    angle = estimate_rotation_via_hough(image)
    if abs(angle) < 0.5:
        return image
    center = (image.shape[1] // 2, image.shape[0] // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(
        image,
        matrix,
        (image.shape[1], image.shape[0]),
        borderValue=(255, 255, 255),
        flags=cv2.INTER_CUBIC,
    )
