import numpy as np
import pytest

from app.backend.preprocessing.annotation_detector import (
    apply_layout_weighting,
    detect_annotations,
    detect_color_candidates,
    filter_by_stroke_shape,
)
from app.backend.providers.vision import VisionResult


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


def test_discards_a_long_thin_ruled_line_component():
    mask = np.zeros((100, 100), dtype=bool)
    mask[50, 0:95] = True  # 1px-tall, 95px-wide: aspect ratio 95

    filtered = filter_by_stroke_shape(mask)

    assert not filtered.any()


def test_keeps_a_blob_shaped_component():
    mask = np.zeros((100, 100), dtype=bool)
    mask[40:60, 40:60] = True  # 20x20 square: aspect ratio 1

    filtered = filter_by_stroke_shape(mask)

    assert filtered[40:60, 40:60].all()


class _FakeVisionProvider:
    def __init__(self, label: str, confidence: float):
        self.label = label
        self.confidence = confidence
        self.calls = 0

    def analyze_region(self, image: bytes, prompt: str) -> VisionResult:
        self.calls += 1
        return VisionResult(label=self.label, confidence=self.confidence)


def test_apply_layout_weighting_passes_candidates_through_unchanged_when_no_regions_given():
    candidates = np.zeros((10, 10), dtype=bool)
    candidates[3:5, 3:5] = True

    result = apply_layout_weighting(candidates, layout_regions=None)

    assert np.array_equal(result, candidates)


def test_apply_layout_weighting_raises_until_phase_4_layout_analysis_exists():
    candidates = np.zeros((10, 10), dtype=bool)

    with pytest.raises(NotImplementedError):
        apply_layout_weighting(candidates, layout_regions=[{"x": 0, "y": 0, "w": 1, "h": 1}])


def test_detect_annotations_without_a_vision_provider_uses_heuristics_only():
    page = _page_with_marks()

    result = detect_annotations(page, vision_provider=None)

    assert result.mask[105:115, 25:55].any()  # red mark still flagged


def test_detect_annotations_calls_vision_provider_only_for_mid_sized_ambiguous_components():
    page = np.full((200, 200, 3), 255, dtype=np.uint8)
    page[10:20, 10:100] = (20, 20, 20)  # printed header, for calibration
    page[100:105, 100:110] = (150, 150, 150)  # small pencil speck, ~30-50px area

    fake_provider = _FakeVisionProvider(label="printed", confidence=0.7)

    result = detect_annotations(page, vision_provider=fake_provider, uncertainty_band=(10, 80))

    assert fake_provider.calls >= 1
    assert not result.mask[100:105, 100:110].any()  # vision said "printed" -> not flagged
