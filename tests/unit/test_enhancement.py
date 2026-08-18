import cv2
import numpy as np

from app.backend.preprocessing.enhancement import enhance_image


def test_enhance_image_reduces_brightness_variance_from_a_shadow_gradient():
    width = height = 200
    gradient = np.tile(np.linspace(80, 220, width, dtype=np.uint8), (height, 1))
    shadowed = cv2.cvtColor(gradient, cv2.COLOR_GRAY2BGR)

    result = enhance_image(shadowed)
    result_gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)

    original_row_std = np.std(gradient[0].astype(np.float32))
    corrected_row_std = np.std(result_gray[0].astype(np.float32))
    assert corrected_row_std < original_row_std


def test_enhance_image_increases_or_maintains_contrast_on_a_low_contrast_image():
    low_contrast = np.full((100, 100, 3), 128, dtype=np.uint8)
    low_contrast[40:60, 40:60] = 140  # a faint patch

    result = enhance_image(low_contrast)
    result_gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
    original_gray = cv2.cvtColor(low_contrast, cv2.COLOR_BGR2GRAY)

    assert np.std(result_gray.astype(np.float32)) >= np.std(original_gray.astype(np.float32))


def test_enhance_image_preserves_image_shape_and_dtype():
    image = np.full((50, 60, 3), 200, dtype=np.uint8)

    result = enhance_image(image)

    assert result.shape == image.shape
    assert result.dtype == np.uint8
