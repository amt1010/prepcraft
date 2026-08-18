import cv2
import numpy as np


def remove_annotations(image: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Inpaints masked regions against the local background (PIPELINE.md
    step 5) rather than deleting to blank/white, so paper texture and
    printed borders that partially underlap a mark stay visually
    consistent."""
    mask_uint8 = mask.astype(np.uint8) * 255
    return cv2.inpaint(image, mask_uint8, inpaintRadius=3, flags=cv2.INPAINT_TELEA)
