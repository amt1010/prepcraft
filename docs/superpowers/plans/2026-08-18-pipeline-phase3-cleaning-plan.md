# Pipeline Phase 3 — Image Cleaning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Workflow A's image-cleaning stage —
`PerspectiveCorrector -> ImageEnhancer -> AnnotationDetector ->
AnnotationRemover -> CleanPaper` — as a CLI command (`python -m app
clean-paper <run_id>`) that continues from Phase 2's saved artifacts and
writes `03_perspective_corrected.png` through `06_cleaned.png` per page.

**Architecture:** Same pattern as Phase 2 — pure, testable functions per
stage, orchestrated by a thin CLI command via `ArtifactStore`.
`AnnotationDetector` combines three deterministic/AI-assisted signals per
PIPELINE.md's "Annotation removal detail" section: color-space candidates,
stroke/shape filtering, and a targeted `VisionProvider` call only for
small ambiguous regions — never a whole-page redraw.

**Tech Stack:** OpenCV (Hough transform, CLAHE, connected components,
inpainting), `anthropic` SDK for `ClaudeVisionProvider` (existing
dependency), Pydantic (`VisionResult`).

**Spec:** `PIPELINE.md`'s "Annotation removal detail" and shared-tail
sections, `ARCHITECTURE.md`'s `VisionProvider` protocol, `EVALUATION.md`'s
annotation-mask precision/recall metric, `TODO.md` Phase 3.

## Global Constraints

- Never delete/blank a masked region — always inpaint against the local
  background (spec §10), and always keep the mask itself as its own
  artifact (`05_annotation_mask.png`) so a human can review removal
  quality when in doubt (spec §31).
- Printed content must never be silently removed: a false keep (leaving a
  mark) is acceptable; a false removal (deleting part of a printed
  question) is not — bias every heuristic toward "flag, don't remove" on
  ambiguity (PIPELINE.md).
- The vision-model assist is for small ambiguous regions only, never a
  whole-page call — cheap, targeted, structured-output calls (PIPELINE.md
  step 4).
- No `ANTHROPIC_API_KEY` is configured in this environment — every task
  must be buildable and testable with `vision_provider=None` (heuristics
  only); `ClaudeVisionProvider`'s own unit test mocks the `anthropic`
  client rather than making a real call, matching how `NotConfiguredProvider`
  was tested in the SaaS plan.
- **Design resolution (not explicit in PIPELINE.md, decided here):**
  `PerspectiveCorrector` does not take Phase 2's `corners` as input.
  Phase 2's CLI only persists the (possibly already-warped) image, not
  the `corners`/`confidence` metadata — so Phase 3, working from saved
  artifacts alone, has no way to know whether Phase 2 warped the page or
  fell back. Instead, `correct_perspective` always independently
  estimates residual rotation via Hough line detection and corrects if
  needed; an already-warped page measures ~0 residual rotation and passes
  through unchanged. Simpler than threading corner metadata across a
  process boundary, and self-correcting regardless of what Phase 2 did.
- **Design resolution — layout awareness (PIPELINE.md step 3):** needs
  Phase 4's `LayoutAnalysis` output (question/glyph bounding boxes),
  which doesn't exist yet. `apply_layout_weighting` is a documented
  pass-through for now (raises `NotImplementedError` if ever called with
  real regions, so a future caller can't silently get a no-op) — not
  silently faked.
- **Design resolution — true hand-labeled precision/recall (EVALUATION.md):**
  requires a human to hand-annotate a ground-truth mask in an image
  editor, which isn't something this plan's execution can fabricate. This
  plan builds the metric *function* (tested) and does a qualitative visual
  check against the golden paper (Task 9) — real hand-labeling is a
  follow-up, recorded honestly in `TODO.md`, not skipped silently.

## File Structure

```
app/backend/
    preprocessing/
        perspective.py          CREATE — Hough-based rotation estimate + correction
        enhancement.py           CREATE — shadow removal + CLAHE contrast
        annotation_detector.py   CREATE — color candidates, stroke filter, orchestration
        annotation_remover.py    CREATE — inpainting
    providers/
        __init__.py              CREATE
        vision.py                CREATE — VisionProvider, VisionResult, ClaudeVisionProvider
    storage/
        artifact_store.py        MODIFY — add load_image(), list_pages()
    evaluation/
        __init__.py              CREATE
        mask_metrics.py          CREATE — compute_mask_precision_recall()
app/cli.py                       MODIFY — add `clean-paper` command
tests/unit/
    test_perspective.py          CREATE
    test_enhancement.py          CREATE
    test_annotation_detector.py  CREATE
    test_vision_provider.py      CREATE
    test_annotation_remover.py   CREATE
    test_mask_metrics.py         CREATE
    test_artifact_store.py       MODIFY — load_image/list_pages cases
tests/integration/
    test_clean_paper_cli.py      CREATE
```

---

### Task 1: PerspectiveCorrector — residual-rotation correction

**Files:**
- Create: `app/backend/preprocessing/perspective.py`
- Test: `tests/unit/test_perspective.py`

**Interfaces:**
- Produces: `estimate_rotation_via_hough(image: np.ndarray) -> float`
  (signed degrees, 0.0 if no reliable line signal), `correct_perspective(image: np.ndarray) -> np.ndarray`.

- [ ] **Step 1: Write the failing test**

```python
import cv2
import numpy as np

from app.backend.preprocessing.perspective import correct_perspective, estimate_rotation_via_hough


def _line_image(angle_degrees: float) -> np.ndarray:
    """A 300x300 white canvas with one long black line through the center
    at a known angle — Hough should recover exactly this angle, since it's
    computed with the same arctan2 formula the line was drawn from."""
    canvas = np.full((300, 300, 3), 255, dtype=np.uint8)
    length = 250
    angle_rad = np.radians(angle_degrees)
    dx = int(length / 2 * np.cos(angle_rad))
    dy = int(length / 2 * np.sin(angle_rad))
    center = (150, 150)
    p1 = (center[0] - dx, center[1] - dy)
    p2 = (center[0] + dx, center[1] + dy)
    cv2.line(canvas, p1, p2, (0, 0, 0), 3)
    return canvas


def test_estimate_rotation_via_hough_recovers_a_known_line_angle():
    image = _line_image(angle_degrees=8.0)

    angle = estimate_rotation_via_hough(image)

    assert 7.0 < angle < 9.0


def test_estimate_rotation_via_hough_returns_near_zero_for_an_already_horizontal_line():
    image = _line_image(angle_degrees=0.0)

    angle = estimate_rotation_via_hough(image)

    assert abs(angle) < 1.0


def test_estimate_rotation_via_hough_returns_zero_when_no_lines_are_found():
    blank = np.full((100, 100, 3), 255, dtype=np.uint8)

    assert estimate_rotation_via_hough(blank) == 0.0


def test_correct_perspective_leaves_an_already_horizontal_image_unchanged():
    image = _line_image(angle_degrees=0.0)

    result = correct_perspective(image)

    assert np.array_equal(result, image)


def test_correct_perspective_straightens_a_rotated_image():
    image = _line_image(angle_degrees=8.0)

    result = correct_perspective(image)

    corrected_angle = estimate_rotation_via_hough(result)
    assert abs(corrected_angle) < 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_perspective.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backend.preprocessing.perspective'`

- [ ] **Step 3: Write minimal implementation**

```python
import cv2
import numpy as np


def estimate_rotation_via_hough(image: np.ndarray) -> float:
    """Signed rotation angle (degrees) needed to straighten near-horizontal
    lines in the image. Returns 0.0 if no reliable line signal is found."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180, threshold=100,
        minLineLength=image.shape[1] // 4, maxLineGap=10,
    )
    if lines is None:
        return 0.0

    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        if abs(angle) < 45:  # only near-horizontal lines are text/edge signal
            angles.append(angle)

    if not angles:
        return 0.0
    return float(np.median(angles))


def correct_perspective(image: np.ndarray) -> np.ndarray:
    """Estimates any residual rotation via Hough line detection and
    straightens it. Works whether or not PageDetector already
    perspective-warped the image — a well-warped page measures ~0
    residual rotation and passes through unchanged."""
    angle = estimate_rotation_via_hough(image)
    if abs(angle) < 0.5:
        return image
    center = (image.shape[1] // 2, image.shape[0] // 2)
    matrix = cv2.getRotationMatrix2D(center, -angle, 1.0)
    return cv2.warpAffine(
        image, matrix, (image.shape[1], image.shape[0]),
        borderValue=(255, 255, 255), flags=cv2.INTER_CUBIC,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_perspective.py -v`
Expected: PASS (5 tests). If `correct_perspective`'s rotation direction is
backwards (the corrected angle test fails with a *doubled* residual angle
instead of near-zero), flip the sign: `cv2.getRotationMatrix2D(center,
angle, 1.0)` instead of `-angle` — confirm empirically here, don't guess.

- [ ] **Step 5: Commit**

```bash
git add app/backend/preprocessing/perspective.py tests/unit/test_perspective.py
git commit -m "add PerspectiveCorrector: Hough-based residual rotation correction"
```

---

### Task 2: ImageEnhancer — shadow removal + contrast boost

**Files:**
- Create: `app/backend/preprocessing/enhancement.py`
- Test: `tests/unit/test_enhancement.py`

**Interfaces:**
- Produces: `enhance_image(image: np.ndarray) -> np.ndarray`.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_enhancement.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backend.preprocessing.enhancement'`

- [ ] **Step 3: Write minimal implementation**

```python
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
    ratio = 200.0 / background
    result = np.clip(image.astype(np.float32) * ratio[:, :, None], 0, 255)
    return result.astype(np.uint8)


def _boost_contrast(image: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_enhanced = clahe.apply(l_channel)
    merged = cv2.merge((l_enhanced, a_channel, b_channel))
    return cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_enhancement.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add app/backend/preprocessing/enhancement.py tests/unit/test_enhancement.py
git commit -m "add ImageEnhancer: shadow removal + CLAHE contrast boost"
```

---

### Task 3: AnnotationDetector — color-space candidates

**Files:**
- Create: `app/backend/preprocessing/annotation_detector.py`
- Test: `tests/unit/test_annotation_detector.py`

**Interfaces:**
- Produces: `detect_color_candidates(image: np.ndarray, header_fraction:
  float = 0.15) -> np.ndarray` (boolean mask, same H×W as input).

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_annotation_detector.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backend.preprocessing.annotation_detector'`

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_annotation_detector.py -v`
Expected: PASS (3 tests). If a threshold is off (e.g. the pencil mark not
flagged), adjust the `+ 40` saturation margin or the percentile — tune
against this concrete synthetic fixture, not blindly.

- [ ] **Step 5: Commit**

```bash
git add app/backend/preprocessing/annotation_detector.py tests/unit/test_annotation_detector.py
git commit -m "add AnnotationDetector: self-calibrated color-space ink candidates"
```

---

### Task 4: AnnotationDetector — stroke/shape filtering

**Files:**
- Modify: `app/backend/preprocessing/annotation_detector.py`
- Test: `tests/unit/test_annotation_detector.py`

**Interfaces:**
- Consumes: a boolean mask (e.g. from Task 3's `detect_color_candidates`).
- Produces: `filter_by_stroke_shape(mask: np.ndarray, max_aspect_ratio:
  float = 15.0) -> np.ndarray`.

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/test_annotation_detector.py`:

```python
from app.backend.preprocessing.annotation_detector import filter_by_stroke_shape


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_annotation_detector.py -v`
Expected: FAIL — `ImportError: cannot import name 'filter_by_stroke_shape'`

- [ ] **Step 3: Write minimal implementation**

Add to `app/backend/preprocessing/annotation_detector.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_annotation_detector.py -v`
Expected: PASS (5 tests — 3 from Task 3 + 2 new)

- [ ] **Step 5: Commit**

```bash
git add app/backend/preprocessing/annotation_detector.py tests/unit/test_annotation_detector.py
git commit -m "add AnnotationDetector: discard rule-line-shaped components"
```

---

### Task 5: VisionProvider + ClaudeVisionProvider

**Files:**
- Create: `app/backend/providers/__init__.py`, `app/backend/providers/vision.py`
- Test: `tests/unit/test_vision_provider.py`

**Interfaces:**
- Produces: `VisionResult(label: Literal["printed",
  "handwritten_or_marked"], confidence: float)` (Pydantic model),
  `VisionProvider` (`Protocol`, `analyze_region(image: bytes, prompt:
  str) -> VisionResult`), `ClaudeVisionProvider(api_key: str, model: str
  = "claude-haiku-4-5")` implementing it — matches
  ARCHITECTURE.md's `VisionProvider` protocol exactly, and the
  Haiku-for-perception-tasks choice from ARCHITECTURE.md's "Model choice
  per pipeline stage" section.

- [ ] **Step 1: Write the failing test**

```python
from unittest.mock import MagicMock, patch

from app.backend.providers.vision import ClaudeVisionProvider, VisionResult


def test_analyze_region_returns_the_parsed_structured_output():
    with patch("anthropic.Anthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.parsed_output = VisionResult(label="handwritten_or_marked", confidence=0.9)
        mock_client.messages.parse.return_value = mock_response

        provider = ClaudeVisionProvider(api_key="fake-key")
        result = provider.analyze_region(
            image=b"fake-png-bytes", prompt="is this printed or handwritten?"
        )

        assert result == VisionResult(label="handwritten_or_marked", confidence=0.9)
        mock_client.messages.parse.assert_called_once()


def test_analyze_region_sends_the_image_as_base64_and_uses_the_configured_model():
    with patch("anthropic.Anthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.parsed_output = VisionResult(label="printed", confidence=0.6)
        mock_client.messages.parse.return_value = mock_response

        provider = ClaudeVisionProvider(api_key="fake-key", model="claude-haiku-4-5")
        provider.analyze_region(image=b"abc", prompt="classify this")

        call_kwargs = mock_client.messages.parse.call_args.kwargs
        assert call_kwargs["model"] == "claude-haiku-4-5"
        content = call_kwargs["messages"][0]["content"]
        assert content[0]["type"] == "image"
        assert content[0]["source"]["type"] == "base64"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_vision_provider.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backend.providers'`

- [ ] **Step 3: Write minimal implementation**

`app/backend/providers/__init__.py`: empty file.

`app/backend/providers/vision.py`:

```python
import base64
from typing import Literal, Protocol

import anthropic
from pydantic import BaseModel


class VisionResult(BaseModel):
    label: Literal["printed", "handwritten_or_marked"]
    confidence: float


class VisionProvider(Protocol):
    def analyze_region(self, image: bytes, prompt: str) -> VisionResult: ...


class ClaudeVisionProvider:
    def __init__(self, api_key: str, model: str = "claude-haiku-4-5") -> None:
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def analyze_region(self, image: bytes, prompt: str) -> VisionResult:
        image_data = base64.standard_b64encode(image).decode("utf-8")
        response = self._client.messages.parse(
            model=self._model,
            max_tokens=256,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": image_data,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            output_format=VisionResult,
        )
        return response.parsed_output
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_vision_provider.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add app/backend/providers/ tests/unit/test_vision_provider.py
git commit -m "add VisionProvider interface and ClaudeVisionProvider"
```

---

### Task 6: AnnotationDetector — orchestration

**Files:**
- Modify: `app/backend/preprocessing/annotation_detector.py`
- Test: `tests/unit/test_annotation_detector.py`

**Interfaces:**
- Consumes: `detect_color_candidates`, `filter_by_stroke_shape` (Tasks
  3-4), `VisionProvider`/`VisionResult` (Task 5).
- Produces: `AnnotationMaskResult(mask: np.ndarray, confidence:
  np.ndarray)`, `apply_layout_weighting(candidates: np.ndarray,
  layout_regions: list | None = None) -> np.ndarray`,
  `detect_annotations(image: np.ndarray, vision_provider: VisionProvider
  | None = None, uncertainty_band: tuple[int, int] = (20, 60)) ->
  AnnotationMaskResult`.

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/test_annotation_detector.py`:

```python
from app.backend.preprocessing.annotation_detector import (
    apply_layout_weighting,
    detect_annotations,
)
from app.backend.providers.vision import VisionResult


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
```

Add `import pytest` to the top of `tests/unit/test_annotation_detector.py`
if not already present.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_annotation_detector.py -v`
Expected: FAIL — `ImportError: cannot import name 'detect_annotations'`

- [ ] **Step 3: Write minimal implementation**

Add to `app/backend/preprocessing/annotation_detector.py`:

```python
from dataclasses import dataclass

from app.backend.providers.vision import VisionProvider


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_annotation_detector.py -v`
Expected: PASS (9 tests total)

- [ ] **Step 5: Commit**

```bash
git add app/backend/preprocessing/annotation_detector.py tests/unit/test_annotation_detector.py
git commit -m "add AnnotationDetector orchestration: heuristics + targeted vision assist"
```

---

### Task 7: AnnotationRemover — inpainting

**Files:**
- Create: `app/backend/preprocessing/annotation_remover.py`
- Test: `tests/unit/test_annotation_remover.py`

**Interfaces:**
- Produces: `remove_annotations(image: np.ndarray, mask: np.ndarray) -> np.ndarray`.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_annotation_remover.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backend.preprocessing.annotation_remover'`

- [ ] **Step 3: Write minimal implementation**

```python
import cv2
import numpy as np


def remove_annotations(image: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Inpaints masked regions against the local background (PIPELINE.md
    step 5) rather than deleting to blank/white, so paper texture and
    printed borders that partially underlap a mark stay visually
    consistent."""
    mask_uint8 = mask.astype(np.uint8) * 255
    return cv2.inpaint(image, mask_uint8, inpaintRadius=3, flags=cv2.INPAINT_TELEA)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_annotation_remover.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add app/backend/preprocessing/annotation_remover.py tests/unit/test_annotation_remover.py
git commit -m "add AnnotationRemover: background-aware inpainting"
```

---

### Task 8: ArtifactStore loading + `clean-paper` CLI command

**Files:**
- Modify: `app/backend/storage/artifact_store.py`, `app/cli.py`
- Test: `tests/unit/test_artifact_store.py`, `tests/integration/test_clean_paper_cli.py`

**Interfaces:**
- Consumes: `correct_perspective` (Task 1), `enhance_image` (Task 2),
  `detect_annotations` (Task 6), `remove_annotations` (Task 7),
  `ClaudeVisionProvider` (Task 5), `Secrets` (Phase 1
  `core/secrets.py`).
- Produces: `ArtifactStore.load_image(page: int, stage_name: str) ->
  np.ndarray`, `ArtifactStore.list_pages() -> list[int]`; CLI command
  `python -m app clean-paper <run_id> [--storage-root PATH]`.

- [ ] **Step 1: Write the failing test — ArtifactStore additions**

Add to `tests/unit/test_artifact_store.py`:

```python
def test_load_image_round_trips_a_saved_image(tmp_path):
    store = ArtifactStore(tmp_path, "RUN-001")
    image = np.zeros((10, 10, 3), dtype=np.uint8)
    image[:, :, 2] = 200  # a distinct tint in the red channel (BGR)

    store.save_image(1, "01_original", image)
    loaded = store.load_image(1, "01_original")

    assert loaded.shape == image.shape
    assert np.array_equal(loaded, image)


def test_list_pages_returns_sorted_page_numbers(tmp_path):
    store = ArtifactStore(tmp_path, "RUN-001")
    image = np.zeros((5, 5, 3), dtype=np.uint8)

    store.save_image(2, "01_original", image)
    store.save_image(1, "01_original", image)

    assert store.list_pages() == [1, 2]


def test_list_pages_returns_empty_list_for_a_run_that_does_not_exist(tmp_path):
    store = ArtifactStore(tmp_path, "RUN-MISSING")

    assert store.list_pages() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_artifact_store.py -v`
Expected: FAIL — `AttributeError: 'ArtifactStore' object has no attribute 'load_image'`

- [ ] **Step 3: Write minimal implementation — ArtifactStore**

Add to `app/backend/storage/artifact_store.py`:

```python
    def load_image(self, page: int, stage_name: str) -> np.ndarray:
        path = self._page_dir(page) / f"{stage_name}.png"
        pil_image = Image.open(path).convert("RGB")
        return np.array(pil_image)[:, :, ::-1]  # RGB -> BGR

    def list_pages(self) -> list[int]:
        if not self.run_dir.exists():
            return []
        pages = [
            int(child.name.removeprefix("page_"))
            for child in self.run_dir.iterdir()
            if child.is_dir() and child.name.startswith("page_")
        ]
        return sorted(pages)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_artifact_store.py -v`
Expected: PASS (6 tests — 3 existing + 3 new)

- [ ] **Step 5: Write the failing test — `clean-paper` CLI**

```python
import numpy as np
from typer.testing import CliRunner

from app.backend.storage.artifact_store import ArtifactStore
from app.cli import app

runner = CliRunner()


def test_clean_paper_writes_all_expected_artifacts_for_each_page(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    store = ArtifactStore(tmp_path, "RUN-TEST")
    page = np.full((100, 100, 3), 255, dtype=np.uint8)
    page[40:60, 40:60] = (30, 30, 200)  # a red mark to clean up
    store.save_image(1, "02_document_detected", page)

    result = runner.invoke(app, ["clean-paper", "RUN-TEST", "--storage-root", str(tmp_path)])

    assert result.exit_code == 0, result.output

    page_dir = tmp_path / "RUN-TEST" / "page_01"
    assert (page_dir / "03_perspective_corrected.png").exists()
    assert (page_dir / "04_enhanced.png").exists()
    assert (page_dir / "05_annotation_mask.png").exists()
    assert (page_dir / "06_cleaned.png").exists()


def test_clean_paper_exits_with_an_error_when_the_run_has_no_pages(tmp_path):
    result = runner.invoke(app, ["clean-paper", "RUN-MISSING", "--storage-root", str(tmp_path)])

    assert result.exit_code == 1
```

- [ ] **Step 6: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/integration/test_clean_paper_cli.py -v`
Expected: FAIL — `No such command 'clean-paper'`

- [ ] **Step 7: Write minimal implementation — CLI**

Add to `app/cli.py`:

```python
from app.backend.core.secrets import Secrets
from app.backend.preprocessing.annotation_detector import detect_annotations
from app.backend.preprocessing.annotation_remover import remove_annotations
from app.backend.preprocessing.enhancement import enhance_image
from app.backend.preprocessing.perspective import correct_perspective
from app.backend.providers.vision import ClaudeVisionProvider


@app.command(name="clean-paper")
def clean_paper(run_id: str, storage_root: Path = Path("data/processed")) -> None:
    """Load a previously ingested run's detected pages, correct residual
    rotation, fix lighting, detect and remove handwritten/marked
    annotations, and write the cleaned artifacts."""
    store = ArtifactStore(storage_root, run_id)
    pages = store.list_pages()
    if not pages:
        typer.echo(f"No pages found for run {run_id} under {storage_root}")
        raise typer.Exit(code=1)

    secrets = Secrets()
    vision_provider = (
        ClaudeVisionProvider(api_key=secrets.anthropic_api_key)
        if secrets.anthropic_api_key
        else None
    )

    for index in pages:
        detected = store.load_image(index, "02_document_detected")

        corrected = correct_perspective(detected)
        store.save_image(index, "03_perspective_corrected", corrected)

        enhanced = enhance_image(corrected)
        store.save_image(index, "04_enhanced", enhanced)

        annotation_result = detect_annotations(enhanced, vision_provider=vision_provider)
        mask_image = (annotation_result.mask * 255).astype("uint8")
        store.save_image(index, "05_annotation_mask", mask_image)

        cleaned = remove_annotations(enhanced, annotation_result.mask)
        store.save_image(index, "06_cleaned", cleaned)

        typer.echo(
            f"[{index}] cleaned — {int(annotation_result.mask.sum())} annotation pixels removed"
        )

    typer.echo(f"Cleaned artifacts written to {store.run_dir}")
```

- [ ] **Step 8: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/integration/test_clean_paper_cli.py -v`
Expected: PASS (2 tests)

- [ ] **Step 9: Run the full test suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all pass

- [ ] **Step 10: Commit**

```bash
git add app/backend/storage/artifact_store.py app/cli.py tests/unit/test_artifact_store.py tests/integration/test_clean_paper_cli.py
git commit -m "add ArtifactStore loading and clean-paper CLI command"
```

---

### Task 9: Mask precision/recall metric + golden paper verification

**Files:**
- Create: `app/backend/evaluation/__init__.py`, `app/backend/evaluation/mask_metrics.py`
- Test: `tests/unit/test_mask_metrics.py`

**Interfaces:**
- Produces: `compute_mask_precision_recall(predicted: np.ndarray,
  ground_truth: np.ndarray) -> tuple[float, float]` — EVALUATION.md's
  annotation-mask precision/recall metric.

- [ ] **Step 1: Write the failing test**

```python
import numpy as np

from app.backend.evaluation.mask_metrics import compute_mask_precision_recall


def test_perfect_match_gives_precision_and_recall_of_one():
    mask = np.zeros((10, 10), dtype=bool)
    mask[2:5, 2:5] = True

    precision, recall = compute_mask_precision_recall(mask, mask)

    assert precision == 1.0
    assert recall == 1.0


def test_no_overlap_gives_zero_precision_and_recall():
    predicted = np.zeros((10, 10), dtype=bool)
    predicted[0:2, 0:2] = True
    ground_truth = np.zeros((10, 10), dtype=bool)
    ground_truth[8:10, 8:10] = True

    precision, recall = compute_mask_precision_recall(predicted, ground_truth)

    assert precision == 0.0
    assert recall == 0.0


def test_partial_overlap_computes_correct_ratios():
    predicted = np.zeros((10, 10), dtype=bool)
    predicted[0:4, 0:1] = True  # 4 predicted-positive pixels
    ground_truth = np.zeros((10, 10), dtype=bool)
    ground_truth[0:2, 0:1] = True  # 2 actual-positive pixels, both inside predicted

    precision, recall = compute_mask_precision_recall(predicted, ground_truth)

    assert precision == 0.5  # 2 true positives / 4 predicted positives
    assert recall == 1.0     # 2 true positives / 2 actual positives


def test_empty_prediction_gives_zero_precision_not_a_division_error():
    predicted = np.zeros((10, 10), dtype=bool)
    ground_truth = np.zeros((10, 10), dtype=bool)
    ground_truth[0:2, 0:2] = True

    precision, recall = compute_mask_precision_recall(predicted, ground_truth)

    assert precision == 0.0
    assert recall == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_mask_metrics.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backend.evaluation'`

- [ ] **Step 3: Write minimal implementation**

`app/backend/evaluation/__init__.py`: empty file.

`app/backend/evaluation/mask_metrics.py`:

```python
import numpy as np


def compute_mask_precision_recall(
    predicted: np.ndarray, ground_truth: np.ndarray
) -> tuple[float, float]:
    """Pixel-level precision/recall of a predicted boolean mask against a
    hand-labeled ground-truth boolean mask (EVALUATION.md's annotation
    mask precision/recall metric)."""
    true_positives = np.logical_and(predicted, ground_truth).sum()
    predicted_positives = predicted.sum()
    actual_positives = ground_truth.sum()

    precision = float(true_positives / predicted_positives) if predicted_positives > 0 else 0.0
    recall = float(true_positives / actual_positives) if actual_positives > 0 else 0.0
    return precision, recall
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_mask_metrics.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add app/backend/evaluation/ tests/unit/test_mask_metrics.py
git commit -m "add mask precision/recall metric (EVALUATION.md)"
```

- [ ] **Step 6: Run the full pipeline against the golden paper**

Run `ingest-paper` then `clean-paper` for each golden paper page (reuse
the `run_id` printed by `ingest-paper`):

```bash
.venv/Scripts/python.exe -m app ingest-paper tests/fixtures/existing_paper/main/page_1.jpg
.venv/Scripts/python.exe -m app clean-paper <run_id_from_output>
```

- [ ] **Step 7: Inspect `05_annotation_mask.png` and `06_cleaned.png` for
      each page.** Check specifically: did it catch the blue pencil/pen
      student answers and red teacher ticks/circles/scores? Did it leave
      the printed questions, tables, and headers intact? Note anything
      that looks wrong (over-removal of printed content, or marks left
      behind) — this is exactly what spec §31 means by "inspectable."

- [ ] **Step 8: Record the finding in `TODO.md` under Phase 3**, same
      style as Phase 2's Task 8 — what was actually observed on the real
      golden paper (not a synthetic fixture), and explicitly note that
      `compute_mask_precision_recall` has no real ground-truth mask to
      run against yet (that needs a human hand-labeling a page in an
      image editor, which is a follow-up, not something to fabricate).

## Explicitly not in this plan

- `LayoutAnalysis` / real layout-aware weighting (Phase 4) —
  `apply_layout_weighting` stays a documented pass-through until then.
- OCR, question extraction, generation, validation, rendering (Phases
  4-10).
- A real hand-labeled ground-truth mask for the golden paper — the
  metric function is built and tested; producing actual ground truth is
  manual image-editing work outside what this plan's execution can do.
- Live `ClaudeVisionProvider` calls against the golden paper — no
  `ANTHROPIC_API_KEY` is configured in this environment; the provider is
  built and unit-tested with a mocked client.
