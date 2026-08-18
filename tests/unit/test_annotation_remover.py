import numpy as np

from app.backend.preprocessing.annotation_remover import remove_annotations


def test_remove_annotations_replaces_a_marked_region_with_background_colored_pixels():
    page = np.full((100, 100, 3), 255, dtype=np.uint8)
    page[40:60, 40:60] = (30, 30, 200)  # a red mark on white background

    mask = np.zeros((100, 100), dtype=bool)
    mask[40:60, 40:60] = True

    result = remove_annotations(page, mask)

    mean_before = page[40:60, 40:60].mean(axis=(0, 1))
    mean_after = result[40:60, 40:60].mean(axis=(0, 1))

    distance_to_white_before = np.linalg.norm(mean_before - 255)
    distance_to_white_after = np.linalg.norm(mean_after - 255)
    assert distance_to_white_after < distance_to_white_before


def test_remove_annotations_leaves_unmasked_pixels_unchanged():
    page = np.full((50, 50, 3), 255, dtype=np.uint8)
    page[10:20, 10:20] = (0, 0, 0)

    mask = np.zeros((50, 50), dtype=bool)  # nothing masked

    result = remove_annotations(page, mask)

    assert np.array_equal(result, page)
