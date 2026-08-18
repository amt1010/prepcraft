import numpy as np

from app.backend.preprocessing.annotation_detector import detect_color_candidates


def _page_with_marks() -> np.ndarray:
    """White page, a black 'printed' text block in the header (used for
    self-calibration), a red pen mark, and a pencil-gray mark, elsewhere
    on the page. Colors are BGR (OpenCV convention)."""
    page = np.full((200, 200, 3), 255, dtype=np.uint8)
    page[10:20, 10:100] = (20, 20, 20)      # printed black header text
    page[100:120, 20:60] = (30, 30, 200)    # red pen mark
    page[150:170, 20:60] = (150, 150, 150)  # pencil-gray mark
    return page


def test_flags_red_ink_and_pencil_marks_as_candidates():
    page = _page_with_marks()

    candidates = detect_color_candidates(page)

    assert candidates[105:115, 25:55].mean() > 0.8
    assert candidates[155:165, 25:55].mean() > 0.5


def test_does_not_flag_the_calibrated_printed_header_as_a_candidate():
    page = _page_with_marks()

    candidates = detect_color_candidates(page)

    assert candidates[10:20, 10:100].mean() < 0.2


def test_does_not_flag_plain_background_as_a_candidate():
    page = _page_with_marks()

    candidates = detect_color_candidates(page)

    assert candidates[0:5, 150:195].mean() < 0.1
