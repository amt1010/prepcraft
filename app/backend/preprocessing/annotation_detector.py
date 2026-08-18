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
    # Exclude near-pure-black pixels from calibration. Real printed ink in a
    # photograph is essentially never pure 0-value black; only a solid
    # graphic fill (e.g. a school-name banner) is. Including those pulls
    # the calibrated "printed" threshold too low, which then makes normal
    # printed text elsewhere in the page look like pencil by comparison —
    # this was confirmed against the real golden paper photos, where a
    # dark banner in the header caused the detector to flag nearly all
    # printed text as candidates.
    dark_mask = (header_v < 128) & (header_v > 10)

    if dark_mask.sum() > 0:
        printed_value_threshold = float(np.percentile(header_v[dark_mask], 90))
        printed_sat_threshold = float(np.percentile(header_s[dark_mask], 90))
    else:
        printed_value_threshold = 100.0
        printed_sat_threshold = 60.0

    # Bright colored ink (e.g. a vibrant red pen circle under good lighting)
    # can have v > 200 too, so brightness alone isn't enough to call
    # something background paper — it also needs to be low-saturation.
    # Confirmed against the golden paper: a red score circle's ink pixels
    # were ~90% v>200, and were being wrongly zeroed out here before this
    # fix.
    background = (v_channel > 200) & (s_channel < 40)
    printed_like = (v_channel <= printed_value_threshold) & (s_channel <= printed_sat_threshold)
    # No upper bound on v_channel here: the background mask above already
    # excludes low-saturation bright pixels (actual white paper), so a high
    # saturation value alone is enough to call something colored ink even
    # when it's also bright (e.g. a vivid red pen mark under good light).
    colored_ink = s_channel > printed_sat_threshold + 40
    # A clear margin above the calibrated printed-ink range, not immediately
    # above it — real printed text has natural brightness variation
    # (anti-aliasing, JPEG artifacts, uneven photo lighting) that would
    # otherwise get misread as pencil.
    pencil_margin = 25.0
    pencil = (
        (s_channel <= printed_sat_threshold)
        & (v_channel > printed_value_threshold + pencil_margin)
        & (v_channel < 200)
    )

    candidates = (colored_ink | pencil) & ~background & ~printed_like
    # The header region is the calibration source for "what printed looks
    # like" on this page, so it's excluded from the output entirely rather
    # than needing to also pass the colored-ink test itself. Pre-printed
    # letterhead graphics (school crest, colored banner blocks) are often
    # more saturated than plain black text and would otherwise look like
    # colored ink — confirmed against the golden paper's school banner.
    candidates[:header_rows] = False
    return candidates


def filter_by_stroke_shape(
    mask: np.ndarray, max_aspect_ratio: float = 15.0, min_area: int = 20
) -> np.ndarray:
    """Discards connected components that look like printed rule lines or
    borders (very long, thin, straight) rather than handwriting strokes
    (PIPELINE.md's annotation-removal step 2), and components too small to
    be a real stroke. The min_area cutoff matters on real photographed
    pages: anti-aliased/JPEG-compressed edges around ordinary printed
    glyphs land in the same brightness range as light pencil marks and
    produce thousands of 1-6px specks (confirmed against the golden
    paper), while genuine pencil/pen marks are much larger connected
    blobs."""
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
        mask.astype(np.uint8), connectivity=8
    )
    filtered = np.zeros_like(mask, dtype=bool)
    for label in range(1, num_labels):
        area = stats[label, cv2.CC_STAT_AREA]
        width = stats[label, cv2.CC_STAT_WIDTH]
        height = stats[label, cv2.CC_STAT_HEIGHT]
        aspect_ratio = max(width, height) / max(min(width, height), 1)
        if area >= min_area and aspect_ratio <= max_aspect_ratio:
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
