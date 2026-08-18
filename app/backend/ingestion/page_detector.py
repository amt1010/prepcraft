from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class PageDetectionResult:
    image: np.ndarray
    corners: np.ndarray | None
    confidence: float


def detect_page(image: np.ndarray) -> PageDetectionResult:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    edges = cv2.dilate(edges, np.ones((5, 5), np.uint8), iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    image_area = image.shape[0] * image.shape[1]

    best_quad = None
    best_area = 0.0
    for contour in contours:
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(approx) == 4:
            area = cv2.contourArea(approx)
            if area > best_area and area > 0.3 * image_area:
                best_area = area
                best_quad = approx

    if best_quad is None:
        return PageDetectionResult(image=image.copy(), corners=None, confidence=0.5)

    corners = _order_corners(best_quad.reshape(4, 2).astype(np.float32))
    warped = _warp_perspective(image, corners)
    confidence = min(1.0, best_area / image_area)
    return PageDetectionResult(image=warped, corners=corners, confidence=confidence)


def _order_corners(pts: np.ndarray) -> np.ndarray:
    """Returns corners as [top-left, top-right, bottom-right, bottom-left]."""
    total = pts.sum(axis=1)
    diff = np.diff(pts, axis=1).flatten()
    ordered = np.zeros((4, 2), dtype=np.float32)
    ordered[0] = pts[np.argmin(total)]
    ordered[2] = pts[np.argmax(total)]
    ordered[1] = pts[np.argmin(diff)]
    ordered[3] = pts[np.argmax(diff)]
    return ordered


def _warp_perspective(image: np.ndarray, corners: np.ndarray) -> np.ndarray:
    top_left, top_right, bottom_right, bottom_left = corners
    width = int(
        max(np.linalg.norm(bottom_right - bottom_left), np.linalg.norm(top_right - top_left))
    )
    height = int(
        max(np.linalg.norm(top_right - bottom_right), np.linalg.norm(top_left - bottom_left))
    )
    destination = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype=np.float32
    )
    matrix = cv2.getPerspectiveTransform(corners, destination)
    return cv2.warpPerspective(image, matrix, (width, height))
