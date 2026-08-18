from dataclasses import dataclass

import cv2
import numpy as np

from app.backend.providers.vision import VisionProvider


def detect_color_candidates(image: np.ndarray, header_fraction: float = 0.15) -> np.ndarray:
    """Boolean mask of pixels likely to be non-printed ink (colored pen or
    pencil), self-calibrated against the page's own printed header region
    so it adapts to this scan's lighting rather than using fixed
    thresholds (PIPELINE.md's annotation-removal step 1)."""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    _, s_channel, v_channel = cv2.split(hsv)

    header_rows = max(1, int(image.shape[0] * header_fraction))
    header_v = v_channel[:header_rows]
    header_s = s_channel[:header_rows]
    dark_mask = header_v < 128

    if dark_mask.sum() > 0:
        printed_value_threshold = float(np.percentile(header_v[dark_mask], 90))
        printed_sat_threshold = float(np.percentile(header_s[dark_mask], 90))
    else:
        printed_value_threshold = 100.0
        printed_sat_threshold = 60.0

    background = v_channel > 200
    printed_like = (v_channel <= printed_value_threshold) & (s_channel <= printed_sat_threshold)
    colored_ink = (s_channel > printed_sat_threshold + 40) & (v_channel < 220)
    pencil = (
        (s_channel <= printed_sat_threshold)
        & (v_channel > printed_value_threshold)
        & (v_channel < 200)
    )

    return (colored_ink | pencil) & ~background & ~printed_like


def filter_by_stroke_shape(mask: np.ndarray, max_aspect_ratio: float = 15.0) -> np.ndarray:
    """Discards connected components that look like printed rule lines or
    borders (very long, thin, straight) rather than handwriting strokes
    (PIPELINE.md's annotation-removal step 2)."""
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
        mask.astype(np.uint8), connectivity=8
    )
    filtered = np.zeros_like(mask, dtype=bool)
    for label in range(1, num_labels):
        width = stats[label, cv2.CC_STAT_WIDTH]
        height = stats[label, cv2.CC_STAT_HEIGHT]
        aspect_ratio = max(width, height) / max(min(width, height), 1)
        if aspect_ratio <= max_aspect_ratio:
            filtered[labels == label] = True
    return filtered


@dataclass
class AnnotationMaskResult:
    mask: np.ndarray
    confidence: np.ndarray


def _encode_png(image: np.ndarray) -> bytes:
    success, buffer = cv2.imencode(".png", image)
    if not success:
        raise ValueError("failed to encode region as PNG")
    return buffer.tobytes()


def apply_layout_weighting(
    candidates: np.ndarray, layout_regions: list | None = None
) -> np.ndarray:
    """Weights candidates by whether they fall in an expected answer-blank
    region vs overlap a printed glyph's bounding box (PIPELINE.md step 3).
    Needs Phase 4's LayoutAnalysis output (question/glyph bounding boxes)
    to do anything real. Until that exists, this is a documented
    pass-through when no regions are given, and raises rather than
    silently no-op-ing if a caller ever does pass real regions — wire this
    up for real once LayoutAnalysis exists."""
    if layout_regions is not None:
        raise NotImplementedError(
            "layout-region weighting needs Phase 4's LayoutAnalysis output"
        )
    return candidates


def detect_annotations(
    image: np.ndarray,
    vision_provider: VisionProvider | None = None,
    uncertainty_band: tuple[int, int] = (20, 60),
) -> AnnotationMaskResult:
    """Combines color-space candidates + stroke/shape filtering
    (deterministic), then asks vision_provider about small ambiguous
    regions only (PIPELINE.md steps 1, 2, 4). uncertainty_band is the
    connected-component pixel-area range treated as worth a vision call —
    tiny specks and large blobs are decided by the heuristics alone, so
    this stays a handful of cheap targeted calls, never a whole-page
    redraw."""
    color_candidates = detect_color_candidates(image)
    shape_filtered = filter_by_stroke_shape(color_candidates)

    final_mask = shape_filtered.copy()
    confidence = shape_filtered.astype(np.float32)

    if vision_provider is not None:
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
            shape_filtered.astype(np.uint8), connectivity=8
        )
        for label in range(1, num_labels):
            area = stats[label, cv2.CC_STAT_AREA]
            if uncertainty_band[0] <= area <= uncertainty_band[1]:
                x = stats[label, cv2.CC_STAT_LEFT]
                y = stats[label, cv2.CC_STAT_TOP]
                w = stats[label, cv2.CC_STAT_WIDTH]
                h = stats[label, cv2.CC_STAT_HEIGHT]
                crop = image[y : y + h, x : x + w]
                result = vision_provider.analyze_region(
                    _encode_png(crop),
                    "Is this cropped region printed text or a handwritten/"
                    "marked annotation? Answer with your best judgment and "
                    "a confidence score.",
                )
                component_mask = labels == label
                final_mask[component_mask] = result.label == "handwritten_or_marked"
                confidence[component_mask] = result.confidence

    return AnnotationMaskResult(mask=final_mask, confidence=confidence)
