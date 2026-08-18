import cv2
import numpy as np


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
