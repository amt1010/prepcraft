import cv2
import numpy as np


def enhance_image(image: np.ndarray) -> np.ndarray:
    """Corrects uneven lighting/shadows via background-division
    normalization, then boosts contrast with CLAHE on the lightness
    channel."""
    shadow_corrected = _remove_shadows(image)
    return _boost_contrast(shadow_corrected)


def _remove_shadows(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32)
    background = cv2.GaussianBlur(gray, (0, 0), sigmaX=25)
    background = np.maximum(background, 1.0)
    # Normalize toward the image's own mean brightness, not a fixed target —
    # a fixed target (e.g. 200) pushes an already-uniform image toward
    # saturation, which then clips under CLAHE and destroys contrast
    # instead of boosting it.
    target = float(np.mean(gray))
    ratio = target / background
    result = np.clip(image.astype(np.float32) * ratio[:, :, None], 0, 255)
    return result.astype(np.uint8)


def _boost_contrast(image: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_enhanced = clahe.apply(l_channel)
    merged = cv2.merge((l_enhanced, a_channel, b_channel))
    return cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)
