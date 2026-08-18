# Pipeline Phase 2 — Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Workflow A's ingestion stage — `PaperInput -> ImageLoader ->
PageDetector -> QualityGate` — as a CLI command (`python -m app
ingest-paper <path>`), writing numbered artifacts per page to
`data/processed/<run_id>/page_<n>/` so every page's ingestion result is
visually inspectable, per spec §9 and §31.

**Architecture:** Pure, testable functions per stage
(`ingestion/image_loader.py`, `ingestion/page_detector.py`,
`preprocessing/quality_gate.py`), orchestrated by a thin CLI command in
`app/cli.py` that calls them in sequence and writes artifacts via
`storage/artifact_store.py` — exactly the "explicit function composition"
pattern in ARCHITECTURE.md, no FastAPI/HTTP layer (that's Phase 11,
confirmed out of scope for this plan).

**Tech Stack:** OpenCV (contour detection, perspective warp, Laplacian
sharpness), PyMuPDF (`pymupdf`, imported as `fitz`) for PDF page
rasterization — chosen over `pdf2image` because it has no external
Poppler binary dependency, Pydantic (existing), Typer (existing).

**Spec:** `PIPELINE.md` (Workflow A stages, artifact list, image quality
gate section), `DATA_MODEL.md` (`Paper`/`Section`), `ARCHITECTURE.md`
(module map, function-composition pipeline pattern), `TODO.md` Phase 2.

## Global Constraints

- No FastAPI/HTTP layer in this plan — CLI only, per PROJECT_PLAN.md's
  phase table (API lands at Phase 11) and the user's explicit scope
  choice for this session.
- Every stage's output is a named, numbered artifact file on disk —
  `01_original.png`, `02_document_detected.png`, `02b_quality_report.json`
  — per page, so a bad result is debuggable without re-running anything
  (spec §9, §31).
- Quality gate thresholds come from `config.yaml`'s `quality.*` (already
  written: `max_skew_degrees: 20`, `min_sharpness: 100`) — `AppConfig`
  doesn't expose them yet (Phase 1 left this as a follow-up); this plan's
  first task closes that gap.
- Quality gate verdict rule (resolving PIPELINE.md's prose into exact
  logic): **pass** = both skew and sharpness within tolerance; **fail** =
  both outside tolerance; **flagged** = exactly one outside tolerance.
- No database, no `ProcessingRun` persistence — Phase 2's own TODO.md
  scope is filesystem artifacts only; DB-backed run tracking isn't listed
  there and stays out of scope here.
- `PageDetector` must never crash or hang on an image where no page quad
  is found — it falls back to "the page fills the frame" (confidence 0.5,
  no corners) rather than raising, matching spec §31's "never silently
  fail into garbage, but always produce *something* inspectable."

## File Structure

```
app/backend/
    core/
        config.py        MODIFY — add QualityConfig, AppConfig.quality
    models/
        __init__.py       CREATE
        paper.py          CREATE — Paper, Section
    storage/
        __init__.py       CREATE
        artifact_store.py CREATE — per-page image/JSON artifact writer
    ingestion/
        __init__.py       CREATE
        image_loader.py   CREATE — JPG/PNG/PDF -> list[np.ndarray]
        page_detector.py  CREATE — contour detection, perspective warp
    preprocessing/
        __init__.py       CREATE
        quality_gate.py   CREATE — sharpness/skew measurement + verdict
app/cli.py                MODIFY — add `ingest-paper` command
pyproject.toml            MODIFY — add pymupdf dependency
tests/unit/
    test_config.py         MODIFY — quality config test cases
    test_artifact_store.py CREATE
    test_page_detector.py  CREATE
    test_quality_gate.py   CREATE
tests/integration/
    test_image_loader.py   CREATE
    test_ingest_paper_cli.py CREATE
```

---

### Task 1: Extend AppConfig with quality gate thresholds

**Files:**
- Modify: `app/backend/core/config.py`
- Test: `tests/unit/test_config.py`

**Interfaces:**
- Produces: `QualityConfig` (fields `max_skew_degrees: float = 20.0`,
  `min_sharpness: float = 100.0`), `AppConfig.quality: QualityConfig`.

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/test_config.py`:

```python
def test_load_config_reads_nested_quality_thresholds(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("quality:\n  max_skew_degrees: 15\n  min_sharpness: 80\n")

    config = load_config(config_file)

    assert config.quality.max_skew_degrees == 15
    assert config.quality.min_sharpness == 80


def test_load_config_defaults_quality_thresholds_when_omitted(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("ai_provider: openai\n")

    config = load_config(config_file)

    assert config.quality.max_skew_degrees == 20.0
    assert config.quality.min_sharpness == 100.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_config.py -v`
Expected: FAIL with `AttributeError: 'AppConfig' object has no attribute 'quality'`

- [ ] **Step 3: Write minimal implementation**

In `app/backend/core/config.py`, add above `AppConfig`:

```python
class QualityConfig(BaseModel):
    max_skew_degrees: float = 20.0
    min_sharpness: float = 100.0
```

Add field to `AppConfig`:

```python
    quality: QualityConfig = QualityConfig()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_config.py -v`
Expected: PASS (6 tests — 4 existing + 2 new)

- [ ] **Step 5: Commit**

```bash
git add app/backend/core/config.py tests/unit/test_config.py
git commit -m "extend AppConfig with quality gate thresholds"
```

---

### Task 2: Paper and Section models

**Files:**
- Create: `app/backend/models/__init__.py`, `app/backend/models/paper.py`
- Test: `tests/unit/test_paper_model.py`

**Interfaces:**
- Produces: `Section(name: str, marks: float, question_count: int | None)`,
  `Paper(id, subject, class_standard, curriculum, total_marks,
  duration_minutes, sections, source, source_paper_id, created_at)` —
  exact fields from DATA_MODEL.md, used by every later phase that
  constructs a `Paper`.

- [ ] **Step 1: Write the failing test**

```python
from datetime import datetime

from app.backend.models.paper import Paper, Section


def test_paper_round_trips_through_the_model_without_data_loss():
    paper = Paper(
        id="PAPER-01",
        subject="Mathematics",
        class_standard="III",
        curriculum="CBSE",
        total_marks=20,
        duration_minutes=50,
        sections=[Section(name="MCQ", marks=2, question_count=4)],
        source="existing_paper",
        source_paper_id=None,
        created_at=datetime(2026, 8, 18),
    )

    restored = Paper.model_validate(paper.model_dump())

    assert restored == paper


def test_paper_rejects_an_invalid_source_value():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Paper(
            id="PAPER-01",
            subject="Mathematics",
            class_standard="III",
            total_marks=20,
            duration_minutes=50,
            sections=[],
            source="not_a_real_source",
            created_at=datetime(2026, 8, 18),
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_paper_model.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backend.models'`

- [ ] **Step 3: Write minimal implementation**

`app/backend/models/__init__.py`: empty file.

`app/backend/models/paper.py`:

```python
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class Section(BaseModel):
    name: str
    marks: float
    question_count: int | None = None


class Paper(BaseModel):
    id: str
    subject: str
    class_standard: str
    curriculum: str | None = None
    total_marks: float
    duration_minutes: int
    sections: list[Section]
    source: Literal["existing_paper", "chapter", "generated"]
    source_paper_id: str | None = None
    created_at: datetime
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_paper_model.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add app/backend/models/ tests/unit/test_paper_model.py
git commit -m "add Paper and Section Pydantic models"
```

---

### Task 3: ArtifactStore — per-page artifact writer

**Files:**
- Create: `app/backend/storage/__init__.py`, `app/backend/storage/artifact_store.py`
- Test: `tests/unit/test_artifact_store.py`

**Interfaces:**
- Consumes: nothing new (stdlib `pathlib`, `json`; `numpy`, `Pillow`).
- Produces: `ArtifactStore(root: Path, run_id: str)` with
  `.run_dir: Path`, `.save_image(page: int, stage_name: str, image:
  np.ndarray) -> Path`, `.save_json(page: int, stage_name: str, data:
  dict) -> Path`. Layout: `<root>/<run_id>/page_<NN>/<stage_name>.<ext>`
  (page number zero-padded to 2 digits).

- [ ] **Step 1: Write the failing test**

```python
import json

import numpy as np

from app.backend.storage.artifact_store import ArtifactStore


def test_save_image_writes_to_the_page_scoped_path(tmp_path):
    store = ArtifactStore(tmp_path, "RUN-001")
    image = np.zeros((10, 10, 3), dtype=np.uint8)

    path = store.save_image(1, "01_original", image)

    assert path == tmp_path / "RUN-001" / "page_01" / "01_original.png"
    assert path.exists()


def test_save_json_writes_readable_json_to_the_page_scoped_path(tmp_path):
    store = ArtifactStore(tmp_path, "RUN-001")

    path = store.save_json(2, "02b_quality_report", {"verdict": "pass"})

    assert path == tmp_path / "RUN-001" / "page_02" / "02b_quality_report.json"
    assert json.loads(path.read_text()) == {"verdict": "pass"}


def test_different_pages_get_separate_directories(tmp_path):
    store = ArtifactStore(tmp_path, "RUN-001")
    image = np.zeros((5, 5, 3), dtype=np.uint8)

    store.save_image(1, "01_original", image)
    store.save_image(2, "01_original", image)

    assert (tmp_path / "RUN-001" / "page_01" / "01_original.png").exists()
    assert (tmp_path / "RUN-001" / "page_02" / "01_original.png").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_artifact_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backend.storage'`

- [ ] **Step 3: Write minimal implementation**

`app/backend/storage/__init__.py`: empty file.

`app/backend/storage/artifact_store.py`:

```python
import json
from pathlib import Path

import numpy as np
from PIL import Image


class ArtifactStore:
    def __init__(self, root: Path, run_id: str) -> None:
        self.run_dir = Path(root) / run_id

    def _page_dir(self, page: int) -> Path:
        page_dir = self.run_dir / f"page_{page:02d}"
        page_dir.mkdir(parents=True, exist_ok=True)
        return page_dir

    def save_image(self, page: int, stage_name: str, image: np.ndarray) -> Path:
        path = self._page_dir(page) / f"{stage_name}.png"
        Image.fromarray(image[:, :, ::-1] if image.ndim == 3 else image).save(path)
        return path

    def save_json(self, page: int, stage_name: str, data: dict) -> Path:
        path = self._page_dir(page) / f"{stage_name}.json"
        path.write_text(json.dumps(data, indent=2, default=str))
        return path
```

Note: `image[:, :, ::-1]` converts OpenCV's BGR channel order to RGB for
correct-looking PNGs — every image this store receives comes from
OpenCV (`image_loader.py`, `page_detector.py`), so this conversion lives
here once rather than at every call site.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_artifact_store.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add app/backend/storage/ tests/unit/test_artifact_store.py
git commit -m "add per-page ArtifactStore for pipeline stage outputs"
```

---

### Task 4: ImageLoader — JPG/PNG/PDF to page images

**Files:**
- Add dependency: `pymupdf>=1.24` in `pyproject.toml`
- Create: `app/backend/ingestion/__init__.py`, `app/backend/ingestion/image_loader.py`
- Test: `tests/integration/test_image_loader.py`

**Interfaces:**
- Produces: `load_pages(path: Path) -> list[np.ndarray]` (BGR images,
  OpenCV convention) — raises `ValueError` for unsupported extensions or
  unreadable files.

- [ ] **Step 1: Add the dependency and install**

Add `"pymupdf>=1.24",` to `pyproject.toml`'s `dependencies` list.

Run: `.venv/Scripts/python.exe -m pip install -e ".[dev]"`
Expected: installs `pymupdf` cleanly.

- [ ] **Step 2: Write the failing test**

```python
from pathlib import Path

import pytest
from reportlab.pdfgen import canvas

from app.backend.ingestion.image_loader import load_pages

FIXTURE_JPG = Path("tests/fixtures/existing_paper/main/page_1.jpg")


def test_loads_a_single_page_from_a_jpg():
    pages = load_pages(FIXTURE_JPG)

    assert len(pages) == 1
    assert pages[0].ndim == 3  # H, W, channels


def test_loads_one_page_per_pdf_page(tmp_path):
    pdf_path = tmp_path / "two_pages.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=(200, 300))
    c.drawString(10, 150, "page one")
    c.showPage()
    c.drawString(10, 150, "page two")
    c.showPage()
    c.save()

    pages = load_pages(pdf_path)

    assert len(pages) == 2
    assert all(page.ndim == 3 for page in pages)


def test_raises_on_an_unsupported_extension(tmp_path):
    bad_file = tmp_path / "notes.txt"
    bad_file.write_text("not an image")

    with pytest.raises(ValueError, match="unsupported"):
        load_pages(bad_file)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/integration/test_image_loader.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backend.ingestion'`

- [ ] **Step 4: Write minimal implementation**

`app/backend/ingestion/__init__.py`: empty file.

`app/backend/ingestion/image_loader.py`:

```python
from pathlib import Path

import cv2
import fitz
import numpy as np

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


def load_pages(path: Path) -> list[np.ndarray]:
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return _load_pdf(path)
    if suffix in _IMAGE_SUFFIXES:
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError(f"could not read image: {path}")
        return [image]
    raise ValueError(f"unsupported file type: {suffix}")


def _load_pdf(path: Path, dpi: int = 200) -> list[np.ndarray]:
    pages: list[np.ndarray] = []
    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)

    with fitz.open(path) as doc:
        for page in doc:
            pix = page.get_pixmap(matrix=matrix)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            if pix.n == 4:
                img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
            else:
                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            pages.append(img)

    return pages
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/integration/test_image_loader.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml app/backend/ingestion/__init__.py app/backend/ingestion/image_loader.py tests/integration/test_image_loader.py
git commit -m "add ImageLoader for JPG/PNG/PDF page extraction"
```

---

### Task 5: PageDetector — boundary detection + perspective warp

**Files:**
- Create: `app/backend/ingestion/page_detector.py`
- Test: `tests/unit/test_page_detector.py`

**Interfaces:**
- Consumes: `numpy.ndarray` images (BGR, from Task 4).
- Produces: `PageDetectionResult(image: np.ndarray, corners:
  np.ndarray | None, confidence: float)`, `detect_page(image:
  np.ndarray) -> PageDetectionResult`.

- [ ] **Step 1: Write the failing test**

```python
import cv2
import numpy as np

from app.backend.ingestion.page_detector import detect_page


def _synthetic_page(rotation_degrees: float = 0.0) -> np.ndarray:
    """A black 300x300 canvas with a white 220x160 rectangle (the 'page'),
    rotated in-place, centered — a controlled fixture instead of a real
    photo, so the expected corners are known exactly. Sized to ~39% of
    the canvas area, comfortably above detect_page's 30% area cutoff —
    not right at the boundary, where contour rounding could flip a test."""
    canvas = np.zeros((300, 300, 3), dtype=np.uint8)
    rect = ((150, 150), (220, 160), rotation_degrees)
    box = cv2.boxPoints(rect).astype(np.int32)
    cv2.fillPoly(canvas, [box], (255, 255, 255))
    return canvas


def test_detects_an_unrotated_page_with_high_confidence():
    result = detect_page(_synthetic_page(rotation_degrees=0.0))

    assert result.corners is not None
    assert result.confidence > 0.5
    # Warped output should be roughly the rectangle's own aspect ratio
    height, width = result.image.shape[:2]
    assert 1.2 < width / height < 1.6  # ~220/160 = 1.375


def test_detects_a_rotated_page_and_returns_four_corners():
    result = detect_page(_synthetic_page(rotation_degrees=15.0))

    assert result.corners is not None
    assert result.corners.shape == (4, 2)


def test_falls_back_to_the_full_frame_when_no_quad_is_found():
    blank = np.full((100, 100, 3), 255, dtype=np.uint8)  # no edges at all

    result = detect_page(blank)

    assert result.corners is None
    assert result.confidence == 0.5
    assert result.image.shape == blank.shape
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_page_detector.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backend.ingestion.page_detector'`

- [ ] **Step 3: Write minimal implementation**

`app/backend/ingestion/page_detector.py`:

```python
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class PageDetectionResult:
    image: np.ndarray
    corners: np.ndarray | None
    confidence: float


def detect_page(image: np.ndarray) -> PageDetectionResult:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    edges = cv2.dilate(edges, np.ones((5, 5), np.uint8), iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    image_area = image.shape[0] * image.shape[1]

    best_quad = None
    best_area = 0.0
    for contour in contours:
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(approx) == 4:
            area = cv2.contourArea(approx)
            if area > best_area and area > 0.3 * image_area:
                best_area = area
                best_quad = approx

    if best_quad is None:
        return PageDetectionResult(image=image.copy(), corners=None, confidence=0.5)

    corners = _order_corners(best_quad.reshape(4, 2).astype(np.float32))
    warped = _warp_perspective(image, corners)
    confidence = min(1.0, best_area / image_area)
    return PageDetectionResult(image=warped, corners=corners, confidence=confidence)


def _order_corners(pts: np.ndarray) -> np.ndarray:
    """Returns corners as [top-left, top-right, bottom-right, bottom-left]."""
    total = pts.sum(axis=1)
    diff = np.diff(pts, axis=1).flatten()
    ordered = np.zeros((4, 2), dtype=np.float32)
    ordered[0] = pts[np.argmin(total)]
    ordered[2] = pts[np.argmax(total)]
    ordered[1] = pts[np.argmin(diff)]
    ordered[3] = pts[np.argmax(diff)]
    return ordered


def _warp_perspective(image: np.ndarray, corners: np.ndarray) -> np.ndarray:
    top_left, top_right, bottom_right, bottom_left = corners
    width = int(max(np.linalg.norm(bottom_right - bottom_left), np.linalg.norm(top_right - top_left)))
    height = int(max(np.linalg.norm(top_right - bottom_right), np.linalg.norm(top_left - bottom_left)))
    destination = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype=np.float32
    )
    matrix = cv2.getPerspectiveTransform(corners, destination)
    return cv2.warpPerspective(image, matrix, (width, height))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_page_detector.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add app/backend/ingestion/page_detector.py tests/unit/test_page_detector.py
git commit -m "add PageDetector: contour-based boundary detection + perspective warp"
```

---

### Task 6: QualityGate — sharpness/skew measurement and verdict

**Files:**
- Create: `app/backend/preprocessing/__init__.py`, `app/backend/preprocessing/quality_gate.py`
- Test: `tests/unit/test_quality_gate.py`

**Interfaces:**
- Consumes: `PageDetectionResult.corners` shape (Task 5).
- Produces: `QualityReport(skew_degrees, skew_within_tolerance,
  sharpness_score, sharpness_acceptable, verdict)`,
  `measure_sharpness(image: np.ndarray) -> float`,
  `measure_skew_degrees(corners: np.ndarray | None) -> float`,
  `evaluate_quality(skew_degrees, sharpness_score, max_skew_degrees,
  min_sharpness) -> QualityReport`.

- [ ] **Step 1: Write the failing test**

```python
import cv2
import numpy as np

from app.backend.preprocessing.quality_gate import (
    evaluate_quality,
    measure_skew_degrees,
    measure_sharpness,
)


def test_evaluate_quality_passes_when_both_metrics_are_within_tolerance():
    report = evaluate_quality(skew_degrees=5, sharpness_score=200, max_skew_degrees=20, min_sharpness=100)
    assert report.verdict == "pass"


def test_evaluate_quality_fails_when_both_metrics_are_outside_tolerance():
    report = evaluate_quality(skew_degrees=45, sharpness_score=10, max_skew_degrees=20, min_sharpness=100)
    assert report.verdict == "fail"


def test_evaluate_quality_flags_when_exactly_one_metric_is_outside_tolerance():
    report = evaluate_quality(skew_degrees=45, sharpness_score=200, max_skew_degrees=20, min_sharpness=100)
    assert report.verdict == "flagged"
    assert report.skew_within_tolerance is False
    assert report.sharpness_acceptable is True


def test_measure_sharpness_scores_a_sharp_checkerboard_higher_than_a_blurred_one():
    checkerboard = np.indices((100, 100)).sum(axis=0) % 2 * 255
    sharp = checkerboard.astype(np.uint8)
    blurred = cv2.GaussianBlur(sharp, (25, 25), 10)

    assert measure_sharpness(sharp) > measure_sharpness(blurred)


def test_measure_skew_degrees_reads_the_angle_from_the_top_edge():
    # top-left, top-right, bottom-right, bottom-left; top edge rotated ~10 degrees
    corners = np.array([[0, 0], [100, 17.6], [100, 117.6], [0, 100]], dtype=np.float32)

    skew = measure_skew_degrees(corners)

    assert 9.5 < skew < 10.5


def test_measure_skew_degrees_is_zero_when_corners_are_unknown():
    assert measure_skew_degrees(None) == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_quality_gate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backend.preprocessing'`

- [ ] **Step 3: Write minimal implementation**

`app/backend/preprocessing/__init__.py`: empty file.

`app/backend/preprocessing/quality_gate.py`:

```python
from dataclasses import dataclass
from typing import Literal

import cv2
import numpy as np

Verdict = Literal["pass", "flagged", "fail"]


@dataclass
class QualityReport:
    skew_degrees: float
    skew_within_tolerance: bool
    sharpness_score: float
    sharpness_acceptable: bool
    verdict: Verdict


def measure_sharpness(image: np.ndarray) -> float:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def measure_skew_degrees(corners: np.ndarray | None) -> float:
    if corners is None:
        return 0.0
    top_left, top_right = corners[0], corners[1]
    delta = top_right - top_left
    return float(abs(np.degrees(np.arctan2(delta[1], delta[0]))))


def evaluate_quality(
    skew_degrees: float,
    sharpness_score: float,
    max_skew_degrees: float,
    min_sharpness: float,
) -> QualityReport:
    skew_ok = skew_degrees <= max_skew_degrees
    sharpness_ok = sharpness_score >= min_sharpness

    if skew_ok and sharpness_ok:
        verdict: Verdict = "pass"
    elif not skew_ok and not sharpness_ok:
        verdict = "fail"
    else:
        verdict = "flagged"

    return QualityReport(
        skew_degrees=skew_degrees,
        skew_within_tolerance=skew_ok,
        sharpness_score=sharpness_score,
        sharpness_acceptable=sharpness_ok,
        verdict=verdict,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_quality_gate.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add app/backend/preprocessing/ tests/unit/test_quality_gate.py
git commit -m "add QualityGate: sharpness/skew measurement and pass/flagged/fail verdict"
```

---

### Task 7: CLI — `ingest-paper` command

**Files:**
- Modify: `app/cli.py`
- Test: `tests/integration/test_ingest_paper_cli.py`

**Interfaces:**
- Consumes: `load_pages` (Task 4), `detect_page` (Task 5),
  `measure_sharpness`/`measure_skew_degrees`/`evaluate_quality` (Task 6),
  `ArtifactStore` (Task 3), `load_config` (Task 1), `new_id` (Phase 1
  `core/ids.py`).
- Produces: `python -m app ingest-paper <path> [--storage-root PATH]`
  command; writes `01_original`, `02_document_detected`,
  `02b_quality_report` artifacts per page.

- [ ] **Step 1: Write the failing test**

```python
import json
from pathlib import Path

from typer.testing import CliRunner

from app.cli import app

runner = CliRunner()
FIXTURE_JPG = Path("tests/fixtures/existing_paper/main/page_1.jpg").resolve()


def test_ingest_paper_writes_artifacts_for_a_single_page_jpg(tmp_path):
    result = runner.invoke(
        app, ["ingest-paper", str(FIXTURE_JPG), "--storage-root", str(tmp_path)]
    )

    assert result.exit_code == 0, result.output

    run_dirs = list(tmp_path.iterdir())
    assert len(run_dirs) == 1
    page_dir = run_dirs[0] / "page_01"

    assert (page_dir / "01_original.png").exists()
    assert (page_dir / "02_document_detected.png").exists()

    report = json.loads((page_dir / "02b_quality_report.json").read_text())
    assert report["verdict"] in ("pass", "flagged", "fail")


def test_ingest_paper_prints_observability_output_per_page(tmp_path):
    result = runner.invoke(
        app, ["ingest-paper", str(FIXTURE_JPG), "--storage-root", str(tmp_path)]
    )

    assert "Page 1" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/integration/test_ingest_paper_cli.py -v`
Expected: FAIL — `RuntimeError`/`UsageError`: no such command `ingest-paper`

- [ ] **Step 3: Write minimal implementation**

Add to `app/cli.py` (alongside the existing `version` command):

```python
from dataclasses import asdict
from pathlib import Path as _Path

from app.backend.core.config import load_config
from app.backend.core.ids import new_id
from app.backend.ingestion.image_loader import load_pages
from app.backend.ingestion.page_detector import detect_page
from app.backend.preprocessing.quality_gate import (
    evaluate_quality,
    measure_skew_degrees,
    measure_sharpness,
)
from app.backend.storage.artifact_store import ArtifactStore


@app.command(name="ingest-paper")
def ingest_paper(
    path: _Path,
    storage_root: _Path = _Path("data/processed"),
    config_path: _Path = _Path("config.yaml"),
) -> None:
    """Ingest a paper (PDF/JPG/PNG): load pages, detect page boundaries,
    run the image quality gate, and write inspectable artifacts."""
    cfg = load_config(config_path) if config_path.exists() else None
    max_skew = cfg.quality.max_skew_degrees if cfg else 20.0
    min_sharpness = cfg.quality.min_sharpness if cfg else 100.0

    run_id = new_id("RUN")
    store = ArtifactStore(storage_root, run_id)
    pages = load_pages(path)
    typer.echo(f"[1/2] Loaded {len(pages)} page(s)  run_id={run_id}")

    for index, page in enumerate(pages, start=1):
        store.save_image(index, "01_original", page)
        detection = detect_page(page)
        store.save_image(index, "02_document_detected", detection.image)

        sharpness = measure_sharpness(detection.image)
        skew = measure_skew_degrees(detection.corners)
        report = evaluate_quality(skew, sharpness, max_skew, min_sharpness)
        store.save_json(index, "02b_quality_report", asdict(report) | {"page": index})

        symbol = {"pass": "OK", "flagged": "~", "fail": "X"}[report.verdict]
        typer.echo(
            f"[2/2] Page {index}: quality {symbol} ({report.verdict}, "
            f"skew={skew:.1f} deg, sharpness={sharpness:.0f})"
        )

    typer.echo(f"Artifacts written to {store.run_dir}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/integration/test_ingest_paper_cli.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the full test suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all pass (Phase 1's 17 + this plan's new tests)

- [ ] **Step 6: Commit**

```bash
git add app/cli.py tests/integration/test_ingest_paper_cli.py
git commit -m "add ingest-paper CLI command wiring ImageLoader/PageDetector/QualityGate"
```

---

### Task 8: Run against the golden paper and inspect manually

Not a coded task — a verification step, per TODO.md Phase 2's own
acceptance criterion ("Run against golden paper, inspect
`01_original.png` / `02_document_detected.png` manually").

- [ ] Run: `.venv/Scripts/python.exe -m app ingest-paper tests/fixtures/existing_paper/main/page_1.jpg`
- [ ] Read the resulting `02_document_detected.png` and
      `02b_quality_report.json` and confirm the detected page looks
      reasonable (page boundary correctly found, or a sensible fallback)
      and the quality verdict matches what the image actually looks like.
- [ ] Repeat for `main/page_2.jpg`, `main/page_3.jpg`, and
      `mental_maths/page_1.jpg`.
- [ ] Note in `TODO.md` under Phase 2 whether `PageDetector`'s contour
      approach holds up on these real (not synthetic) photos, or whether
      it needs tuning before Phase 3 builds on top of it — this is exactly
      the kind of finding EVALUATION.md expects to be recorded, not
      silently absorbed.

## Explicitly not in this plan

- FastAPI/HTTP layer (Phase 11, and out of scope per this session's
  explicit scope choice)
- `PerspectiveCorrector` / `ImageEnhancer` (Phase 3 — image cleaning)
- `AnnotationDetector` / `AnnotationRemover` (Phase 3 — the hard part,
  PIPELINE.md's dedicated section)
- OCR, question extraction, generation, validation, rendering (Phases
  4-10)
- `ProcessingRun` database persistence (not in TODO.md's Phase 2 scope)
