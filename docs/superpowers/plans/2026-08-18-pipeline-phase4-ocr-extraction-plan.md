# Phase 4 — OCR + Question Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn a cleaned golden-paper run (Phase 3's output) into `09_questions.json` — OCR the printed text, group it into per-question chunks, and classify each chunk's type/topic/marks/difficulty — closing PROJECT_PLAN.md's Phase 4 row.

**Architecture:** Two new provider implementations (`TesseractOCRProvider` deterministic, `ClaudeOCRProvider` fallback for low-confidence pages) behind the existing `OCRProvider` protocol from ARCHITECTURE.md; a new `TextGenerationProvider` + `ClaudeTextGenerationProvider` for question classification; a deterministic `LayoutAnalysis` step that groups OCR words by top-level question number (no AI); a `QuestionExtraction` step that hands each group to the text-generation provider to split into lettered sub-parts and classify. Orchestrated by a new `extract-questions` CLI command, writing `07_ocr.json` and `08_layout.json` per page and one run-level `09_questions.json`.

**Tech Stack:** pytesseract (wraps the Tesseract 5.4 binary, now installed at `C:\Program Files\Tesseract-OCR\tesseract.exe`), anthropic SDK (`messages.parse` with `output_format=`), Pydantic v2, Typer.

**Spec:** `PIPELINE.md` (Workflow A steps 8-10: OCR, LayoutAnalysis, QuestionExtraction), `DATA_MODEL.md` (`Question`/`QuestionType`), `ARCHITECTURE.md` ("Provider interfaces", "Model choice per pipeline stage"), `EVALUATION.md` ("Metrics per stage" — OCR + question extraction rows), `PROJECT_PLAN.md` (phase table row 4), master spec §12-13.

## Global Constraints

- Every module boundary crosses with a Pydantic model, never a raw dict (DATA_MODEL.md line 3-4, spec §12, §35).
- `OCRProvider.extract_text(self, image: bytes) -> OCRResult` and `TextGenerationProvider.generate(self, prompt: str, schema: type[T]) -> T` are the exact protocol shapes from ARCHITECTURE.md — don't drift from them.
- OCR fallback uses `claude-haiku-4-5`; question classification uses `claude-sonnet-5` (ARCHITECTURE.md's per-stage model table) — both already have `config.yaml` entries (`models.ocr_fallback`, `models.question_classification`) that just aren't wired into `AppConfig` yet.
- Every stage's artifact goes to `data/processed/<run_id>/` per PIPELINE.md's numbered list — `07_ocr.json` and `08_layout.json` are per-page (like `06_cleaned.png`); `09_questions.json` is one file for the whole run (a `Paper` spans every page).
- No AI framework, no hand-rolled agent loop — a provider call is a function call that returns a typed object or raises (ARCHITECTURE.md).
- MVP question types only (DATA_MODEL.md's `QuestionType` enum, 9 values) — don't build classification for the commented-out types (match_the_following, short_answer, etc).

---

### Task 1: OCR provider contracts + TesseractOCRProvider

**Files:**
- Create: `app/backend/providers/ocr/__init__.py`
- Create: `app/backend/providers/ocr/tesseract_provider.py`
- Test: `tests/unit/test_tesseract_provider.py`
- Test: `tests/integration/test_tesseract_ocr_real.py`

**Interfaces:**
- Produces: `OCRWord(BaseModel)` with fields `text: str`, `confidence: float`, `left: int`, `top: int`, `width: int`, `height: int`; `OCRResult(BaseModel)` with `words: list[OCRWord]`, `full_text: str`; `OCRProvider(Protocol)` with `extract_text(self, image: bytes) -> OCRResult`; `TesseractOCRProvider(tesseract_cmd: str | None = None)` implementing it.

- [x] **Step 1: Write the failing test — parsing logic (mocked)**

```python
# tests/unit/test_tesseract_provider.py
from unittest.mock import patch

from app.backend.providers.ocr import OCRResult
from app.backend.providers.ocr.tesseract_provider import TesseractOCRProvider


def _fake_tesseract_data():
    return {
        "text": ["", "Hello", "world", ""],
        "conf": ["-1", "92.5", "88.0", "-1"],
        "left": [0, 10, 60, 0],
        "top": [0, 5, 5, 0],
        "width": [0, 40, 45, 0],
        "height": [0, 12, 12, 0],
    }


def test_extract_text_builds_ocr_result_from_tesseract_data():
    with patch("pytesseract.image_to_data", return_value=_fake_tesseract_data()):
        with patch("PIL.Image.open"):
            provider = TesseractOCRProvider(tesseract_cmd="fake-tesseract")
            result = provider.extract_text(image=b"fake-png-bytes")

    assert result == OCRResult(
        words=[
            {"text": "Hello", "confidence": 92.5, "left": 10, "top": 5, "width": 40, "height": 12},
            {"text": "world", "confidence": 88.0, "left": 60, "top": 5, "width": 45, "height": 12},
        ],
        full_text="Hello world",
    )


def test_extract_text_skips_blank_and_whitespace_only_entries():
    data = _fake_tesseract_data()
    data["text"][1] = "   "

    with patch("pytesseract.image_to_data", return_value=data):
        with patch("PIL.Image.open"):
            provider = TesseractOCRProvider(tesseract_cmd="fake-tesseract")
            result = provider.extract_text(image=b"fake-png-bytes")

    assert [w.text for w in result.words] == ["world"]


def test_constructor_uses_explicit_tesseract_cmd_when_given():
    import pytesseract

    TesseractOCRProvider(tesseract_cmd=r"C:\custom\tesseract.exe")

    assert pytesseract.pytesseract.tesseract_cmd == r"C:\custom\tesseract.exe"
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_tesseract_provider.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backend.providers.ocr'`

- [x] **Step 3: Write minimal implementation**

```python
# app/backend/providers/ocr/__init__.py
from typing import Protocol

from pydantic import BaseModel


class OCRWord(BaseModel):
    text: str
    confidence: float
    left: int
    top: int
    width: int
    height: int


class OCRResult(BaseModel):
    words: list[OCRWord]
    full_text: str


class OCRProvider(Protocol):
    def extract_text(self, image: bytes) -> OCRResult: ...
```

```python
# app/backend/providers/ocr/tesseract_provider.py
"""Deterministic, local, offline OCR via the Tesseract binary (PIPELINE.md's
OCR step, primary provider — PROJECT_PLAN.md risk 2's ocr_provider=tesseract
default). No AI call, no network — this only degrades to ClaudeOCRProvider
(claude_provider.py) when confidence is low, via ocr/orchestrator.py."""

import io
import shutil
from pathlib import Path

import pytesseract
from PIL import Image
from pytesseract import Output

from app.backend.providers.ocr import OCRResult, OCRWord

_WINDOWS_INSTALL_PATHS = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
)


def _resolve_tesseract_cmd(explicit: str | None) -> str | None:
    if explicit:
        return explicit
    found_on_path = shutil.which("tesseract")
    if found_on_path:
        return found_on_path
    for candidate in _WINDOWS_INSTALL_PATHS:
        if Path(candidate).exists():
            return candidate
    return None


class TesseractOCRProvider:
    def __init__(self, tesseract_cmd: str | None = None) -> None:
        resolved = _resolve_tesseract_cmd(tesseract_cmd)
        if resolved:
            pytesseract.pytesseract.tesseract_cmd = resolved

    def extract_text(self, image: bytes) -> OCRResult:
        pil_image = Image.open(io.BytesIO(image))
        data = pytesseract.image_to_data(pil_image, output_type=Output.DICT)

        words: list[OCRWord] = []
        for i, text in enumerate(data["text"]):
            if not text.strip():
                continue
            words.append(
                OCRWord(
                    text=text,
                    confidence=float(data["conf"][i]),
                    left=int(data["left"][i]),
                    top=int(data["top"][i]),
                    width=int(data["width"][i]),
                    height=int(data["height"][i]),
                )
            )

        return OCRResult(words=words, full_text=" ".join(w.text for w in words))
```

- [x] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_tesseract_provider.py -v`
Expected: PASS (3 tests)

- [x] **Step 5: Write a real end-to-end integration test against the installed binary**

```python
# tests/integration/test_tesseract_ocr_real.py
"""Proves the actually-installed Tesseract binary works end to end, not
just the parsing logic around it (that's test_tesseract_provider.py)."""

import io

from PIL import Image, ImageDraw, ImageFont

from app.backend.providers.ocr.tesseract_provider import TesseractOCRProvider


def test_extracts_real_text_from_a_rendered_image():
    image = Image.new("RGB", (400, 100), color="white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 36)
    draw.text((10, 20), "Hello world", fill="black", font=font)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")

    provider = TesseractOCRProvider()
    result = provider.extract_text(buffer.getvalue())

    assert "Hello" in result.full_text
    assert "world" in result.full_text
    assert all(w.confidence > 0 for w in result.words)
```

- [x] **Step 6: Run the integration test**

Run: `.venv/Scripts/python.exe -m pytest tests/integration/test_tesseract_ocr_real.py -v`
Expected: PASS — confirms the installed binary is actually reachable and working, not just mocked

- [x] **Step 7: Commit**

```bash
git add app/backend/providers/ocr/ tests/unit/test_tesseract_provider.py tests/integration/test_tesseract_ocr_real.py
git commit -m "add OCRProvider contract and TesseractOCRProvider"
```

---

### Task 2: ClaudeOCRProvider (fallback) + confidence-based orchestrator

**Files:**
- Create: `app/backend/providers/ocr/claude_provider.py`
- Create: `app/backend/ocr/__init__.py`
- Create: `app/backend/ocr/orchestrator.py`
- Test: `tests/unit/test_claude_ocr_provider.py`
- Test: `tests/unit/test_ocr_orchestrator.py`

**Interfaces:**
- Consumes: `OCRResult`, `OCRWord`, `OCRProvider` from Task 1.
- Produces: `ClaudeOCRProvider(api_key: str, model: str = "claude-haiku-4-5")` implementing `OCRProvider`; `extract_text_with_fallback(image: bytes, primary: OCRProvider, fallback: OCRProvider | None, confidence_threshold: float = 60.0) -> OCRResult`.

- [x] **Step 1: Write the failing test — ClaudeOCRProvider**

```python
# tests/unit/test_claude_ocr_provider.py
from unittest.mock import MagicMock, patch

from app.backend.providers.ocr import OCRResult
from app.backend.providers.ocr.claude_provider import ClaudeOCRProvider, _OCRTranscription


def test_extract_text_returns_the_transcribed_text():
    with patch("anthropic.Anthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.parsed_output = _OCRTranscription(text="Hello world")
        mock_client.messages.parse.return_value = mock_response

        provider = ClaudeOCRProvider(api_key="fake-key")
        result = provider.extract_text(image=b"fake-png-bytes")

        assert result == OCRResult(words=[], full_text="Hello world")
        mock_client.messages.parse.assert_called_once()


def test_extract_text_uses_the_configured_model_and_sends_image_as_base64():
    with patch("anthropic.Anthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.parsed_output = _OCRTranscription(text="x")
        mock_client.messages.parse.return_value = mock_response

        provider = ClaudeOCRProvider(api_key="fake-key", model="claude-haiku-4-5")
        provider.extract_text(image=b"abc")

        call_kwargs = mock_client.messages.parse.call_args.kwargs
        assert call_kwargs["model"] == "claude-haiku-4-5"
        content = call_kwargs["messages"][0]["content"]
        assert content[0]["type"] == "image"
        assert content[0]["source"]["type"] == "base64"
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_claude_ocr_provider.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backend.providers.ocr.claude_provider'`

- [x] **Step 3: Write minimal implementation — ClaudeOCRProvider**

```python
# app/backend/providers/ocr/claude_provider.py
"""OCR fallback for pages Tesseract transcribes with low confidence
(PIPELINE.md's "cloud fallback on low confidence"). Vision-based, so it
returns full-text only — no per-word bounding boxes, since the model
doesn't give pixel coordinates back. LayoutAnalysis still works on this
because it only needs word order, and this always replaces a whole page's
OCRResult rather than patching individual words (see orchestrator.py)."""

import base64

import anthropic
from pydantic import BaseModel

from app.backend.providers.ocr import OCRResult


class _OCRTranscription(BaseModel):
    text: str


class ClaudeOCRProvider:
    def __init__(self, api_key: str, model: str = "claude-haiku-4-5") -> None:
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def extract_text(self, image: bytes) -> OCRResult:
        image_data = base64.standard_b64encode(image).decode("utf-8")
        response = self._client.messages.parse(
            model=self._model,
            max_tokens=2048,
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
                        {
                            "type": "text",
                            "text": (
                                "Transcribe all printed text visible in this image, "
                                "exactly as written, preserving line breaks. Ignore "
                                "any handwritten annotations."
                            ),
                        },
                    ],
                }
            ],
            output_format=_OCRTranscription,
        )
        return OCRResult(words=[], full_text=response.parsed_output.text)
```

- [x] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_claude_ocr_provider.py -v`
Expected: PASS (2 tests)

- [x] **Step 5: Write the failing test — orchestrator**

```python
# tests/unit/test_ocr_orchestrator.py
from app.backend.ocr.orchestrator import extract_text_with_fallback
from app.backend.providers.ocr import OCRResult, OCRWord


class _FakeProvider:
    def __init__(self, result: OCRResult):
        self.result = result
        self.calls = 0

    def extract_text(self, image: bytes) -> OCRResult:
        self.calls += 1
        return self.result


def test_returns_primary_result_when_confidence_is_high():
    primary = _FakeProvider(
        OCRResult(words=[OCRWord(text="a", confidence=95, left=0, top=0, width=1, height=1)], full_text="a")
    )
    fallback = _FakeProvider(OCRResult(words=[], full_text="fallback"))

    result = extract_text_with_fallback(b"img", primary, fallback)

    assert result.full_text == "a"
    assert fallback.calls == 0


def test_calls_fallback_when_mean_confidence_is_below_threshold():
    primary = _FakeProvider(
        OCRResult(words=[OCRWord(text="a", confidence=10, left=0, top=0, width=1, height=1)], full_text="a")
    )
    fallback = _FakeProvider(OCRResult(words=[], full_text="fallback"))

    result = extract_text_with_fallback(b"img", primary, fallback, confidence_threshold=60.0)

    assert result.full_text == "fallback"
    assert fallback.calls == 1


def test_returns_primary_result_when_no_fallback_is_configured():
    primary = _FakeProvider(
        OCRResult(words=[OCRWord(text="a", confidence=5, left=0, top=0, width=1, height=1)], full_text="a")
    )

    result = extract_text_with_fallback(b"img", primary, fallback=None)

    assert result.full_text == "a"


def test_returns_primary_result_unchanged_when_it_found_no_words_at_all():
    primary = _FakeProvider(OCRResult(words=[], full_text=""))
    fallback = _FakeProvider(OCRResult(words=[], full_text="fallback"))

    result = extract_text_with_fallback(b"img", primary, fallback)

    assert result.full_text == ""
    assert fallback.calls == 0
```

- [x] **Step 6: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_ocr_orchestrator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backend.ocr'`

- [x] **Step 7: Write minimal implementation — orchestrator**

```python
# app/backend/ocr/__init__.py
```

```python
# app/backend/ocr/orchestrator.py
"""Chooses between the primary (Tesseract) and fallback (Claude vision) OCR
provider per page, based on mean word confidence (PIPELINE.md's "extract
text (Tesseract, cloud fallback on low confidence)"). A page either gets
Tesseract's per-word result, or gets fully re-transcribed by the fallback —
never a per-word patch, since the fallback provider has no bounding boxes
to align against Tesseract's."""

from app.backend.providers.ocr import OCRProvider, OCRResult


def extract_text_with_fallback(
    image: bytes,
    primary: OCRProvider,
    fallback: OCRProvider | None,
    confidence_threshold: float = 60.0,
) -> OCRResult:
    result = primary.extract_text(image)
    if fallback is None or not result.words:
        return result

    mean_confidence = sum(w.confidence for w in result.words) / len(result.words)
    if mean_confidence >= confidence_threshold:
        return result

    return fallback.extract_text(image)
```

- [x] **Step 8: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_ocr_orchestrator.py tests/unit/test_claude_ocr_provider.py -v`
Expected: PASS (6 tests)

- [x] **Step 9: Commit**

```bash
git add app/backend/providers/ocr/claude_provider.py app/backend/ocr/ tests/unit/test_claude_ocr_provider.py tests/unit/test_ocr_orchestrator.py
git commit -m "add Claude OCR fallback and confidence-based orchestrator"
```

---

### Task 3: TextGenerationProvider + ClaudeTextGenerationProvider

**Files:**
- Create: `app/backend/providers/text_generation.py`
- Test: `tests/unit/test_text_generation_provider.py`

**Interfaces:**
- Produces: `TextGenerationProvider(Protocol)` with `generate(self, prompt: str, schema: type[T]) -> T`; `ClaudeTextGenerationProvider(api_key: str, model: str = "claude-sonnet-5")` implementing it. This is the provider Task 6 (QuestionExtraction) calls for classification, and the one Phase 7 (question generation) will reuse.

- [x] **Step 1: Write the failing test**

```python
# tests/unit/test_text_generation_provider.py
from unittest.mock import MagicMock, patch

from pydantic import BaseModel

from app.backend.providers.text_generation import ClaudeTextGenerationProvider


class _FakeSchema(BaseModel):
    value: str


def test_generate_returns_the_parsed_structured_output():
    with patch("anthropic.Anthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.parsed_output = _FakeSchema(value="classified")
        mock_client.messages.parse.return_value = mock_response

        provider = ClaudeTextGenerationProvider(api_key="fake-key")
        result = provider.generate(prompt="classify this", schema=_FakeSchema)

        assert result == _FakeSchema(value="classified")
        mock_client.messages.parse.assert_called_once()


def test_generate_uses_the_configured_model_and_the_given_schema():
    with patch("anthropic.Anthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.parsed_output = _FakeSchema(value="x")
        mock_client.messages.parse.return_value = mock_response

        provider = ClaudeTextGenerationProvider(api_key="fake-key", model="claude-sonnet-5")
        provider.generate(prompt="classify this", schema=_FakeSchema)

        call_kwargs = mock_client.messages.parse.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-5"
        assert call_kwargs["output_format"] is _FakeSchema
        assert call_kwargs["messages"][0]["content"] == "classify this"
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_text_generation_provider.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backend.providers.text_generation'`

- [x] **Step 3: Write minimal implementation**

```python
# app/backend/providers/text_generation.py
"""Judgment-over-text AI call site (ARCHITECTURE.md's model-choice table):
question classification now (Task 6), question-draft generation in Phase
7. Both are `claude-sonnet-5` because they need actual reasoning about
curriculum/topic/phrasing, unlike the cheap perception calls in
providers/vision.py and providers/ocr/claude_provider.py."""

from typing import Protocol, TypeVar

import anthropic
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class TextGenerationProvider(Protocol):
    def generate(self, prompt: str, schema: type[T]) -> T: ...


class ClaudeTextGenerationProvider:
    def __init__(self, api_key: str, model: str = "claude-sonnet-5") -> None:
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def generate(self, prompt: str, schema: type[T]) -> T:
        response = self._client.messages.parse(
            model=self._model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
            output_format=schema,
        )
        return response.parsed_output
```

- [x] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_text_generation_provider.py -v`
Expected: PASS (2 tests)

- [x] **Step 5: Commit**

```bash
git add app/backend/providers/text_generation.py tests/unit/test_text_generation_provider.py
git commit -m "add TextGenerationProvider and ClaudeTextGenerationProvider"
```

---

### Task 4: Wire `models.*` into AppConfig

**Files:**
- Modify: `app/backend/core/config.py`
- Test: `tests/unit/test_config.py`

**Interfaces:**
- Produces: `ModelsConfig(BaseModel)` with `annotation_vision: str = "claude-haiku-4-5"`, `ocr_fallback: str = "claude-haiku-4-5"`, `question_classification: str = "claude-sonnet-5"`, `question_generation: str = "claude-sonnet-5"`; `AppConfig.models: ModelsConfig`.

- [x] **Step 1: Write the failing test**

```python
# append to tests/unit/test_config.py
def test_load_config_reads_nested_model_routing(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "models:\n  ocr_fallback: claude-haiku-4-5\n  question_classification: claude-opus-5\n"
    )

    config = load_config(config_file)

    assert config.models.ocr_fallback == "claude-haiku-4-5"
    assert config.models.question_classification == "claude-opus-5"


def test_load_config_defaults_model_routing_when_omitted(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("ai_provider: openai\n")

    config = load_config(config_file)

    assert config.models.annotation_vision == "claude-haiku-4-5"
    assert config.models.ocr_fallback == "claude-haiku-4-5"
    assert config.models.question_classification == "claude-sonnet-5"
    assert config.models.question_generation == "claude-sonnet-5"
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_config.py -k model_routing -v`
Expected: FAIL — `AttributeError: 'AppConfig' object has no attribute 'models'`

- [x] **Step 3: Write minimal implementation**

In `app/backend/core/config.py`, add after `QualityConfig`:

```python
class ModelsConfig(BaseModel):
    annotation_vision: str = "claude-haiku-4-5"
    ocr_fallback: str = "claude-haiku-4-5"
    question_classification: str = "claude-sonnet-5"
    question_generation: str = "claude-sonnet-5"
```

And add a field to `AppConfig`:

```python
    quality: QualityConfig = QualityConfig()
    models: ModelsConfig = ModelsConfig()
```

- [x] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_config.py -v`
Expected: PASS (all tests in the file)

- [x] **Step 5: Update config.yaml's comment — it's no longer a future-phase placeholder**

In `config.yaml`, the file header comment says `quality.* and models.* below are the target Phase 3/7 shape ... extend it when those phases land`. Update it since Phase 3 and this Phase 4 both now read `models.*` for real:

```yaml
# Non-secret application settings. Loaded by app/backend/core/config.py.
# Secrets (API keys) go in .env, never here — see .env.example.
```

(Delete the two "target Phase 3/7 shape" lines — both `quality` and `models` are wired into `AppConfig` now.)

- [x] **Step 6: Commit**

```bash
git add app/backend/core/config.py config.yaml tests/unit/test_config.py
git commit -m "wire models.* per-stage routing into AppConfig"
```

---

### Task 5: LayoutAnalysis — group OCR words by top-level question number

**Files:**
- Create: `app/backend/ocr/layout_analysis.py`
- Test: `tests/unit/test_layout_analysis.py`

**Interfaces:**
- Consumes: `OCRResult`, `OCRWord` from Task 1.
- Produces: `LayoutGroup(BaseModel)` with `question_number: str`, `text: str`; `group_by_question_number(ocr_result: OCRResult) -> list[LayoutGroup]`. Task 6 consumes this list directly.

- [x] **Step 1: Write the failing test**

```python
# tests/unit/test_layout_analysis.py
from app.backend.ocr.layout_analysis import group_by_question_number
from app.backend.providers.ocr import OCRResult, OCRWord


def _word(text: str, index: int) -> OCRWord:
    return OCRWord(text=text, confidence=90, left=index * 10, top=0, width=8, height=10)


def test_groups_words_after_a_top_level_number():
    words = [_word(w, i) for i, w in enumerate(["1.", "What", "is", "2+2?"])]
    ocr_result = OCRResult(words=words, full_text="1. What is 2+2?")

    groups = group_by_question_number(ocr_result)

    assert groups == [{"question_number": "1", "text": "What is 2+2?"}]


def test_starts_a_new_group_at_the_next_top_level_number():
    words = [_word(w, i) for i, w in enumerate(["1.", "a", "b", "2.", "c", "d"])]
    ocr_result = OCRResult(words=words, full_text="1. a b 2. c d")

    groups = group_by_question_number(ocr_result)

    assert [g.question_number for g in groups] == ["1", "2"]
    assert groups[0].text == "a b"
    assert groups[1].text == "c d"


def test_ignores_words_before_the_first_top_level_number():
    words = [_word(w, i) for i, w in enumerate(["Series:", "DWPS", "1.", "a"])]
    ocr_result = OCRResult(words=words, full_text="Series: DWPS 1. a")

    groups = group_by_question_number(ocr_result)

    assert len(groups) == 1
    assert groups[0].question_number == "1"


def test_returns_empty_list_when_no_top_level_numbers_found():
    words = [_word(w, i) for i, w in enumerate(["Series:", "DWPS"])]
    ocr_result = OCRResult(words=words, full_text="Series: DWPS")

    groups = group_by_question_number(ocr_result)

    assert groups == []


def test_does_not_treat_a_lettered_sub_part_marker_as_a_new_top_level_group():
    words = [_word(w, i) for i, w in enumerate(["1.", "a.", "405", "b.", "450"])]
    ocr_result = OCRResult(words=words, full_text="1. a. 405 b. 450")

    groups = group_by_question_number(ocr_result)

    assert len(groups) == 1
    assert groups[0].question_number == "1"
    assert groups[0].text == "a. 405 b. 450"
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_layout_analysis.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backend.ocr.layout_analysis'`

- [x] **Step 3: Write minimal implementation**

```python
# app/backend/ocr/layout_analysis.py
"""Groups OCR words into per-top-level-question chunks by scanning for
tokens that look like "1.", "2.", ... (PIPELINE.md's LayoutAnalysis:
"group text into questions/sections by position + numbering"). Purely
positional/regex — no AI here. Splitting a chunk into lettered sub-parts
(1a, 1b, ...) and classifying each is QuestionExtraction's job (Task 6),
which has the judgment (and the marks-annotation text like "[0.5X4=2]")
to do it well; a regex can't tell "1." (a question number) apart from "1"
inside "XVII + V + X = 1" reliably, so this stays deliberately coarse.

Words come from `OCRResult.words` in Tesseract's native reading order
(top-to-bottom, left-to-right per line) — this module trusts that order
rather than re-sorting by pixel position itself."""

import re

from pydantic import BaseModel

from app.backend.providers.ocr import OCRResult

_TOP_LEVEL_NUMBER = re.compile(r"^(\d{1,2})\.$")


class LayoutGroup(BaseModel):
    question_number: str
    text: str


def group_by_question_number(ocr_result: OCRResult) -> list[LayoutGroup]:
    groups: list[LayoutGroup] = []
    current_number: str | None = None
    current_words: list[str] = []

    for word in ocr_result.words:
        match = _TOP_LEVEL_NUMBER.match(word.text)
        if match:
            if current_number is not None:
                groups.append(LayoutGroup(question_number=current_number, text=" ".join(current_words)))
            current_number = match.group(1)
            current_words = []
        elif current_number is not None:
            current_words.append(word.text)

    if current_number is not None:
        groups.append(LayoutGroup(question_number=current_number, text=" ".join(current_words)))

    return groups
```

- [x] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_layout_analysis.py -v`
Expected: PASS (5 tests)

- [x] **Step 5: Commit**

```bash
git add app/backend/ocr/layout_analysis.py tests/unit/test_layout_analysis.py
git commit -m "add LayoutAnalysis: group OCR words by top-level question number"
```

---

### Task 6: QuestionExtraction — split + classify each group

**Files:**
- Create: `app/backend/questions/__init__.py`
- Create: `app/backend/questions/extraction.py`
- Test: `tests/unit/test_question_extraction.py`

**Interfaces:**
- Consumes: `LayoutGroup` from Task 5; `TextGenerationProvider` from Task 3.
- Produces: `ExtractedSubQuestion(BaseModel)` with `question_number: str`, `text: str`, `type: str`, `options: list[str] | None = None`, `marks: float | None = None`, `topic: str | None = None`, `difficulty: int | None = None`; `QuestionGroupExtraction(BaseModel)` with `questions: list[ExtractedSubQuestion]`; `extract_questions(groups: list[LayoutGroup], text_provider: TextGenerationProvider | None = None) -> list[ExtractedSubQuestion]`. Task 7's CLI command calls this directly.

- [x] **Step 1: Write the failing test**

```python
# tests/unit/test_question_extraction.py
from app.backend.ocr.layout_analysis import LayoutGroup
from app.backend.questions.extraction import (
    ExtractedSubQuestion,
    QuestionGroupExtraction,
    extract_questions,
)


class _FakeTextProvider:
    def __init__(self, response: QuestionGroupExtraction):
        self.response = response
        self.prompts: list[str] = []

    def generate(self, prompt: str, schema):
        self.prompts.append(prompt)
        return self.response


def test_extract_questions_without_a_provider_passes_groups_through_unclassified():
    groups = [LayoutGroup(question_number="1", text="What is 2+2? i.3 ii.4 iii.5")]

    result = extract_questions(groups, text_provider=None)

    assert result == [
        ExtractedSubQuestion(question_number="1", text="What is 2+2? i.3 ii.4 iii.5", type="unknown")
    ]


def test_extract_questions_uses_the_provider_to_split_and_classify_a_group():
    groups = [LayoutGroup(question_number="1", text="a. 405 + 305 = 800 b. 450 [0.5X2=1]")]
    fake_response = QuestionGroupExtraction(
        questions=[
            ExtractedSubQuestion(
                question_number="1a",
                text="405 + 305 = 800. What is the missing number?",
                type="fill_in_the_blank",
                marks=0.5,
                topic="Addition",
                difficulty=2,
            ),
            ExtractedSubQuestion(
                question_number="1b",
                text="What should be added to get 450?",
                type="arithmetic",
                marks=0.5,
                topic="Addition",
                difficulty=2,
            ),
        ]
    )
    provider = _FakeTextProvider(fake_response)

    result = extract_questions(groups, text_provider=provider)

    assert result == fake_response.questions
    assert len(provider.prompts) == 1
    assert "a. 405 + 305 = 800 b. 450 [0.5X2=1]" in provider.prompts[0]


def test_extract_questions_calls_the_provider_once_per_group():
    groups = [
        LayoutGroup(question_number="1", text="first group"),
        LayoutGroup(question_number="2", text="second group"),
    ]
    provider = _FakeTextProvider(QuestionGroupExtraction(questions=[]))

    extract_questions(groups, text_provider=provider)

    assert len(provider.prompts) == 2
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_question_extraction.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backend.questions'`

- [x] **Step 3: Write minimal implementation**

```python
# app/backend/questions/__init__.py
```

```python
# app/backend/questions/extraction.py
"""Splits each LayoutGroup's OCR text into lettered sub-parts and classifies
each one (PIPELINE.md's QuestionExtraction: "classify each item: type,
marks, topic, difficulty"). This is judgment over text, not perception, so
it's claude-sonnet-5 territory (ARCHITECTURE.md) via TextGenerationProvider
— never a bespoke regex parser trying to guess where "1a" ends and "1b"
begins, since the marks annotation format ("[0.5X4=2]") and sub-part
boundaries vary paper to paper.

This is deliberately a lighter model than DATA_MODEL.md's full `Question`
(no id/paper_id/expected_answer/difficulty_features/answer_type/source) —
those need a `Paper` to belong to and DifficultyFeatures' full breakdown,
which is Phase 5's job (PROJECT_PLAN.md phase table). Phase 5 builds the
real `Question` model on top of this extraction output."""

from pydantic import BaseModel

from app.backend.ocr.layout_analysis import LayoutGroup
from app.backend.providers.text_generation import TextGenerationProvider

_CLASSIFICATION_PROMPT = """You are extracting individual questions from a photographed school exam paper's OCR text. This is question {question_number} from a CBSE Class III Mathematics paper.

The text may contain multiple lettered sub-parts (a, b, c, ...) and a marks annotation like "[0.5X4=2]" meaning each of the 4 sub-parts is worth 0.5 marks. Split the text into one entry per sub-part, numbered "{question_number}a", "{question_number}b", etc. — or just "{question_number}" if there are no lettered sub-parts.

For each entry determine:
- type: one of multiple_choice, fill_in_the_blank, true_false, arithmetic, roman_numeral, predecessor_successor, rounding, word_problem, mental_maths
- options: the answer choices, only when type is multiple_choice
- marks: this sub-part's marks, from the marks annotation
- topic: a short topic label (e.g. "Addition", "Roman numerals")
- difficulty: 1-5 on the CBSE Class III scale (1 = trivial recall, 5 = multi-step reasoning)

OCR text for question {question_number}:
{text}
"""


class ExtractedSubQuestion(BaseModel):
    question_number: str
    text: str
    type: str
    options: list[str] | None = None
    marks: float | None = None
    topic: str | None = None
    difficulty: int | None = None


class QuestionGroupExtraction(BaseModel):
    questions: list[ExtractedSubQuestion]


def extract_questions(
    groups: list[LayoutGroup],
    text_provider: TextGenerationProvider | None = None,
) -> list[ExtractedSubQuestion]:
    if text_provider is None:
        return [
            ExtractedSubQuestion(question_number=g.question_number, text=g.text, type="unknown")
            for g in groups
        ]

    extracted: list[ExtractedSubQuestion] = []
    for group in groups:
        prompt = _CLASSIFICATION_PROMPT.format(question_number=group.question_number, text=group.text)
        result = text_provider.generate(prompt, QuestionGroupExtraction)
        extracted.extend(result.questions)
    return extracted
```

- [x] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_question_extraction.py -v`
Expected: PASS (3 tests)

- [x] **Step 5: Commit**

```bash
git add app/backend/questions/ tests/unit/test_question_extraction.py
git commit -m "add QuestionExtraction: split and classify layout groups"
```

---

### Task 7: ArtifactStore run-level JSON + `extract-questions` CLI command

**Files:**
- Modify: `app/backend/storage/artifact_store.py`
- Modify: `app/cli.py`
- Test: `tests/unit/test_artifact_store.py`
- Test: `tests/integration/test_extract_questions_cli.py`

**Interfaces:**
- Consumes: `extract_text_with_fallback` (Task 2), `group_by_question_number`/`LayoutGroup` (Task 5), `extract_questions`/`ExtractedSubQuestion` (Task 6), `TesseractOCRProvider` (Task 1), `ClaudeOCRProvider` (Task 2), `ClaudeTextGenerationProvider` (Task 3), `AppConfig.models` (Task 4).
- Produces: `ArtifactStore.save_run_json(stage_name: str, data: dict) -> Path`, `ArtifactStore.load_run_json(stage_name: str) -> dict`; CLI command `python -m app extract-questions <run_id>`.

- [x] **Step 1: Write the failing test — ArtifactStore additions**

```python
# append to tests/unit/test_artifact_store.py
def test_save_run_json_writes_to_the_run_root_not_a_page_dir(tmp_path):
    store = ArtifactStore(tmp_path, "RUN-001")

    path = store.save_run_json("09_questions", {"questions": []})

    assert path == tmp_path / "RUN-001" / "09_questions.json"
    assert json.loads(path.read_text()) == {"questions": []}


def test_load_run_json_round_trips_a_saved_run_json(tmp_path):
    store = ArtifactStore(tmp_path, "RUN-001")
    store.save_run_json("09_questions", {"questions": [{"question_number": "1a"}]})

    loaded = store.load_run_json("09_questions")

    assert loaded == {"questions": [{"question_number": "1a"}]}
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_artifact_store.py -k run_json -v`
Expected: FAIL — `AttributeError: 'ArtifactStore' object has no attribute 'save_run_json'`

- [x] **Step 3: Write minimal implementation — ArtifactStore**

Add to `app/backend/storage/artifact_store.py`, inside the `ArtifactStore` class:

```python
    def save_run_json(self, stage_name: str, data: dict) -> Path:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        path = self.run_dir / f"{stage_name}.json"
        path.write_text(json.dumps(data, indent=2, default=str))
        return path

    def load_run_json(self, stage_name: str) -> dict:
        path = self.run_dir / f"{stage_name}.json"
        return json.loads(path.read_text())
```

- [x] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_artifact_store.py -v`
Expected: PASS (all tests in the file)

- [x] **Step 5: Write the failing test — `extract-questions` CLI**

```python
# tests/integration/test_extract_questions_cli.py
import numpy as np
from typer.testing import CliRunner

from app.backend.storage.artifact_store import ArtifactStore
from app.cli import app

runner = CliRunner()


def test_extract_questions_writes_all_expected_artifacts(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    store = ArtifactStore(tmp_path, "RUN-TEST")
    page = np.full((200, 800, 3), 255, dtype=np.uint8)
    store.save_image(1, "06_cleaned", page)

    result = runner.invoke(app, ["extract-questions", "RUN-TEST", "--storage-root", str(tmp_path)])

    assert result.exit_code == 0, result.output
    page_dir = tmp_path / "RUN-TEST" / "page_01"
    assert (page_dir / "07_ocr.json").exists()
    assert (page_dir / "08_layout.json").exists()
    assert (tmp_path / "RUN-TEST" / "09_questions.json").exists()


def test_extract_questions_exits_with_an_error_when_the_run_has_no_pages(tmp_path):
    result = runner.invoke(app, ["extract-questions", "RUN-MISSING", "--storage-root", str(tmp_path)])

    assert result.exit_code == 1
```

- [x] **Step 6: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/integration/test_extract_questions_cli.py -v`
Expected: FAIL — `AssertionError` (no such command `extract-questions`)

- [x] **Step 7: Write minimal implementation — CLI**

Add these imports to `app/cli.py` (alongside the existing Phase 2/3 imports):

```python
import cv2

from app.backend.core.config import load_config
from app.backend.ocr.layout_analysis import LayoutGroup, group_by_question_number
from app.backend.ocr.orchestrator import extract_text_with_fallback
from app.backend.providers.ocr.claude_provider import ClaudeOCRProvider
from app.backend.providers.ocr.tesseract_provider import TesseractOCRProvider
from app.backend.providers.text_generation import ClaudeTextGenerationProvider
from app.backend.questions.extraction import extract_questions
```

(`load_config` is already imported in `app/cli.py` from Phase 2 — don't duplicate the import line, just reuse it.)

Add the command:

```python
@app.command(name="extract-questions")
def extract_questions_cmd(
    run_id: str,
    storage_root: Path = Path("data/processed"),
    config_path: Path = Path("config.yaml"),
) -> None:
    """OCR each cleaned page, group text into per-question chunks, and
    classify each chunk's type/marks/topic/difficulty."""
    store = ArtifactStore(storage_root, run_id)
    pages = store.list_pages()
    if not pages:
        typer.echo(f"No pages found for run {run_id} under {storage_root}")
        raise typer.Exit(code=1)

    cfg = load_config(config_path) if config_path.exists() else None
    secrets = Secrets()

    tesseract = TesseractOCRProvider()
    ocr_fallback = (
        ClaudeOCRProvider(
            api_key=secrets.anthropic_api_key,
            model=cfg.models.ocr_fallback if cfg else "claude-haiku-4-5",
        )
        if secrets.anthropic_api_key
        else None
    )
    text_provider = (
        ClaudeTextGenerationProvider(
            api_key=secrets.anthropic_api_key,
            model=cfg.models.question_classification if cfg else "claude-sonnet-5",
        )
        if secrets.anthropic_api_key
        else None
    )

    all_groups: list[LayoutGroup] = []
    for index in pages:
        cleaned = store.load_image(index, "06_cleaned")
        success, buffer = cv2.imencode(".png", cleaned)
        if not success:
            raise ValueError(f"failed to encode page {index} as PNG")
        image_bytes = buffer.tobytes()

        ocr_result = extract_text_with_fallback(image_bytes, tesseract, ocr_fallback)
        store.save_json(index, "07_ocr", ocr_result.model_dump())

        groups = group_by_question_number(ocr_result)
        store.save_json(index, "08_layout", {"groups": [g.model_dump() for g in groups]})
        all_groups.extend(groups)

        typer.echo(f"[{index}] OCR: {len(ocr_result.words)} word(s), {len(groups)} question group(s)")

    questions = extract_questions(all_groups, text_provider=text_provider)
    store.save_run_json("09_questions", {"questions": [q.model_dump() for q in questions]})

    typer.echo(f"Extracted {len(questions)} question(s)")
    typer.echo(f"Artifacts written to {store.run_dir}")
```

- [x] **Step 8: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/integration/test_extract_questions_cli.py -v`
Expected: PASS (2 tests)

- [x] **Step 9: Run the full test suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: All tests pass, no regressions in Phase 1-3 tests

- [x] **Step 10: Commit**

```bash
git add app/backend/storage/artifact_store.py app/cli.py tests/unit/test_artifact_store.py tests/integration/test_extract_questions_cli.py
git commit -m "add extract-questions CLI command and run-level artifact storage"
```

---

### Task 8: OCR + extraction accuracy metrics

**Files:**
- Create: `app/backend/evaluation/ocr_metrics.py`
- Create: `app/backend/evaluation/extraction_metrics.py`
- Test: `tests/unit/test_ocr_metrics.py`
- Test: `tests/unit/test_extraction_metrics.py`

**Interfaces:**
- Produces: `compute_character_accuracy(predicted: str, reference: str) -> float`, `compute_word_accuracy(predicted: str, reference: str) -> float` (EVALUATION.md's OCR row); `compute_extraction_recall(extracted: list[dict], expected: list[dict]) -> float`, `compute_field_accuracy(extracted: list[dict], expected: list[dict], field: str) -> float` (EVALUATION.md's question extraction row), matched by `question_number`.

- [x] **Step 1: Write the failing test — OCR metrics**

```python
# tests/unit/test_ocr_metrics.py
from app.backend.evaluation.ocr_metrics import compute_character_accuracy, compute_word_accuracy


def test_character_accuracy_is_one_for_an_exact_match():
    assert compute_character_accuracy("hello world", "hello world") == 1.0


def test_character_accuracy_reflects_edit_distance():
    # "hello" -> "hallo" is 1 substitution out of 11 reference characters
    accuracy = compute_character_accuracy("hallo world", "hello world")
    assert accuracy == 1.0 - 1 / 11


def test_character_accuracy_does_not_go_below_zero_for_a_very_wrong_prediction():
    accuracy = compute_character_accuracy("completely different text here", "a")
    assert accuracy == 0.0


def test_word_accuracy_is_one_for_an_exact_match():
    assert compute_word_accuracy("hello world", "hello world") == 1.0


def test_word_accuracy_counts_only_position_matched_words():
    # "hello" matches, "there" != "world"
    accuracy = compute_word_accuracy("hello there", "hello world")
    assert accuracy == 0.5


def test_word_accuracy_is_zero_when_reference_is_empty_and_prediction_is_not():
    assert compute_word_accuracy("extra", "") == 0.0


def test_word_accuracy_is_one_when_both_are_empty():
    assert compute_word_accuracy("", "") == 1.0
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_ocr_metrics.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backend.evaluation.ocr_metrics'`

- [x] **Step 3: Write minimal implementation — OCR metrics**

```python
# app/backend/evaluation/ocr_metrics.py
"""EVALUATION.md's OCR row: character accuracy (1 - normalized Levenshtein
distance) and word accuracy (exact word match rate after tokenization),
both against a hand-transcribed reference page of text."""


def _levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    previous_row = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        current_row = [i] + [0] * len(b)
        for j, char_b in enumerate(b, start=1):
            insert_cost = current_row[j - 1] + 1
            delete_cost = previous_row[j] + 1
            substitute_cost = previous_row[j - 1] + (char_a != char_b)
            current_row[j] = min(insert_cost, delete_cost, substitute_cost)
        previous_row = current_row
    return previous_row[-1]


def compute_character_accuracy(predicted: str, reference: str) -> float:
    if not reference:
        return 1.0 if not predicted else 0.0
    distance = _levenshtein(predicted, reference)
    return max(0.0, 1.0 - distance / len(reference))


def compute_word_accuracy(predicted: str, reference: str) -> float:
    predicted_words = predicted.split()
    reference_words = reference.split()
    if not reference_words:
        return 1.0 if not predicted_words else 0.0
    matches = sum(1 for p, r in zip(predicted_words, reference_words) if p == r)
    return matches / len(reference_words)
```

- [x] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_ocr_metrics.py -v`
Expected: PASS (7 tests)

- [x] **Step 5: Write the failing test — extraction metrics**

```python
# tests/unit/test_extraction_metrics.py
from app.backend.evaluation.extraction_metrics import (
    compute_extraction_recall,
    compute_field_accuracy,
)


def test_extraction_recall_is_one_when_every_expected_question_was_extracted():
    expected = [{"question_number": "1a"}, {"question_number": "1b"}]
    extracted = [{"question_number": "1a"}, {"question_number": "1b"}, {"question_number": "2a"}]

    assert compute_extraction_recall(extracted, expected) == 1.0


def test_extraction_recall_reflects_missing_questions():
    expected = [{"question_number": "1a"}, {"question_number": "1b"}]
    extracted = [{"question_number": "1a"}]

    assert compute_extraction_recall(extracted, expected) == 0.5


def test_extraction_recall_is_one_when_nothing_is_expected():
    assert compute_extraction_recall([], []) == 1.0


def test_field_accuracy_matches_by_question_number_and_compares_one_field():
    expected = [
        {"question_number": "1a", "type": "multiple_choice", "marks": 0.5},
        {"question_number": "1b", "type": "arithmetic", "marks": 0.5},
    ]
    extracted = [
        {"question_number": "1a", "type": "multiple_choice", "marks": 0.5},
        {"question_number": "1b", "type": "fill_in_the_blank", "marks": 0.5},
    ]

    assert compute_field_accuracy(extracted, expected, "type") == 0.5
    assert compute_field_accuracy(extracted, expected, "marks") == 1.0


def test_field_accuracy_ignores_extracted_questions_not_in_expected():
    expected = [{"question_number": "1a", "type": "multiple_choice"}]
    extracted = [
        {"question_number": "1a", "type": "multiple_choice"},
        {"question_number": "9z", "type": "arithmetic"},
    ]

    assert compute_field_accuracy(extracted, expected, "type") == 1.0


def test_field_accuracy_is_zero_when_no_extracted_question_matches_expected():
    expected = [{"question_number": "1a", "type": "multiple_choice"}]
    extracted = [{"question_number": "9z", "type": "arithmetic"}]

    assert compute_field_accuracy(extracted, expected, "type") == 0.0
```

- [x] **Step 6: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_extraction_metrics.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backend.evaluation.extraction_metrics'`

- [x] **Step 7: Write minimal implementation — extraction metrics**

```python
# app/backend/evaluation/extraction_metrics.py
"""EVALUATION.md's question extraction row: extraction recall (questions
correctly extracted / questions expected) and per-field accuracy (type,
marks, question_number, ...), both matched by question_number against
tests/fixtures/expected/<doc>/questions.json."""


def compute_extraction_recall(extracted: list[dict], expected: list[dict]) -> float:
    if not expected:
        return 1.0
    expected_numbers = {q["question_number"] for q in expected}
    extracted_numbers = {q["question_number"] for q in extracted}
    matched = expected_numbers & extracted_numbers
    return len(matched) / len(expected_numbers)


def compute_field_accuracy(extracted: list[dict], expected: list[dict], field: str) -> float:
    expected_by_number = {q["question_number"]: q for q in expected}
    matched_extracted = [q for q in extracted if q["question_number"] in expected_by_number]
    if not matched_extracted:
        return 0.0
    correct = sum(
        1
        for q in matched_extracted
        if q.get(field) == expected_by_number[q["question_number"]].get(field)
    )
    return correct / len(matched_extracted)
```

- [x] **Step 8: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_extraction_metrics.py -v`
Expected: PASS (6 tests)

- [x] **Step 9: Commit**

```bash
git add app/backend/evaluation/ocr_metrics.py app/backend/evaluation/extraction_metrics.py tests/unit/test_ocr_metrics.py tests/unit/test_extraction_metrics.py
git commit -m "add OCR and question-extraction accuracy metrics (EVALUATION.md)"
```

---

### Task 9: Golden paper hand-transcription + verification

**Files:**
- Create: `tests/fixtures/expected/main/questions.json`
- Create: `tests/fixtures/expected/mental_maths/questions.json`
- Modify: `TODO.md`

**Interfaces:**
- Consumes: everything above. `extract-questions` CLI (Task 7), `compute_character_accuracy`/`compute_word_accuracy` (Task 8), `compute_extraction_recall`/`compute_field_accuracy` (Task 8).

The golden paper is two documents: `main` (3 pages, 20 marks, questions 1-8 with lettered sub-parts) and `mental_maths` (1 page, 10 marks, questions 1-3). Both were viewed in full during Phase 3 verification (`data/processed/RUN-01M09YVNWB94A6Y8RV41R60JSK/page_01/04_enhanced.png` = main p1, `RUN-01M09YVQC6ZQBJXW5HGKZB55J7/page_01/04_enhanced.png` = main p2, `RUN-01M09YVRT0H0G92892W1RDHJCP/page_01/04_enhanced.png` = main p3, `RUN-01M09YVT6BVQCTSRYE02V2MRRM/page_01/04_enhanced.png` = mental_maths p1 — re-view them if those runs have been cleaned up).

- [x] **Step 1: Transcribe `tests/fixtures/expected/main/questions.json`**

Per EVALUATION.md's golden dataset instructions: use the *printed* question text and the school's own red-circled per-question marks — not the student's handwritten answers. Schema (deliberately the subset of DATA_MODEL.md's `Question` that Task 6's `ExtractedSubQuestion` produces, plus `expected_answer` for reuse by Phase 5/6 — `id`/`paper_id`/`difficulty_features`/`answer_type`/`source` are out of scope until Phase 5 builds the full model):

```json
{
  "questions": [
    {
      "question_number": "1a",
      "text": "500 + 305 = 800. What is the missing number?",
      "type": "multiple_choice",
      "options": ["405", "450", "500", "495"],
      "marks": 0.5,
      "topic": "Addition",
      "difficulty": 2,
      "expected_answer": "500"
    }
  ]
}
```

Write one entry per lettered sub-part for every question on all 3 main-paper pages (1a-1d, 2a-2b, 3a-3b, 4a-4c, 5a-5b, 6a-6c, 7a-7b, 8a-8c — verify the exact split against the images, this list is a guide from Phase 3's viewing, not a substitute for looking again). Difficulty: use the 1-5 scale, judged by step count and reasoning required (DifficultyFeatures' intent in DATA_MODEL.md, even though the full feature breakdown isn't computed until Phase 5) — a single-step recall question is 1-2, a multi-step word problem is 3-4.

- [x] **Step 2: Transcribe `tests/fixtures/expected/mental_maths/questions.json`**

Same schema and rules. Question 3 ("Fill in the missing digits") is three column-addition grids worth 1.5 marks each (the red-circled `1.5` next to each grid, matching `[0.5x9=4.5]` / 3 grids) — treat each grid as one question (`"3a"`, `"3b"`, `"3c"`), `type: "fill_in_the_blank"`, and record `expected_answer` as the complete set of digits that make the addition correct (e.g. `"5,7,4"` for the three blank cells in the first grid, reading top-to-bottom in the blank column(s) — verify against the image, don't guess).

- [x] **Step 3: Run `extract-questions` against all 4 golden pages**

Reuse the run_ids from Phase 3 if `data/processed/RUN-*` still exists, or re-run `ingest-paper` then `clean-paper` first:

```bash
.venv/Scripts/python.exe -m app.cli extract-questions <main_page1_run_id>
.venv/Scripts/python.exe -m app.cli extract-questions <main_page2_run_id>
.venv/Scripts/python.exe -m app.cli extract-questions <main_page3_run_id>
.venv/Scripts/python.exe -m app.cli extract-questions <mental_maths_run_id>
```

Note: each golden paper page was ingested as a separate one-page run in Phase 3 (see TODO.md's Phase 3 findings), so `extract-questions` runs once per page here too, each producing its own `09_questions.json` — there's no single multi-page run to point it at. Read all 4 pages' `07_ocr.json`, `08_layout.json`, `09_questions.json` for the inspection step below.

- [x] **Step 4: Inspect the OCR and extraction output**

For each run, check:
- Does `07_ocr.json`'s `full_text` roughly match what's printed on the page (garbled words are expected on real photos, but it shouldn't be nonsense)?
- Does `08_layout.json` split into roughly the right number of top-level groups (1-8 for main pages, 1-3 for mental_maths)?
- Does `09_questions.json` have a `type`/`topic`/`difficulty` per sub-question that looks reasonable, or is everything `"unknown"` (meaning no `ANTHROPIC_API_KEY` was picked up — check `.env` exists and has the key)?

Note anything that looks wrong.

- [x] **Step 5: Compute the metrics against the golden fixtures**

Write a short throwaway script (not committed — this is a manual check, not a permanent CLI command; Phase 14's evaluation dashboard is where `python -m app evaluate` becomes a real command per PROJECT_PLAN.md) that, for each of the 4 runs:
- loads that run's `09_questions.json` questions and the matching `expected/<doc>/questions.json` questions (main pages 1-3 all compare against the same `expected/main/questions.json`, since they're one paper split across 3 photos — merge all 3 pages' extracted questions before comparing)
- calls `compute_extraction_recall`, and `compute_field_accuracy` for `"type"`, `"marks"`, `"topic"`, `"difficulty"`
- loads `07_ocr.json`'s `full_text` per page and a hand-typed reference string for that page (type out what the page actually says — this is the "hand-transcribed text per page" EVALUATION.md's OCR row needs) and calls `compute_character_accuracy`/`compute_word_accuracy`

Print the results.

- [x] **Step 6: Record findings in TODO.md under Phase 4**, same style as Phase 2 and Phase 3's findings sections — the actual numbers from Step 5, what worked, what didn't, and why (e.g. if OCR accuracy is low because of photo quality, or extraction recall is low because a section's marks annotation format didn't match what the classification prompt expected). Mark the Phase 4 checklist items done.

- [x] **Step 7: Commit**

```bash
git add tests/fixtures/expected/ TODO.md
git commit -m "hand-transcribe golden paper fixtures and record Phase 4 verification findings"
```

---

## Self-Review Notes

- **Spec coverage:** §12 (Question/Paper JSON shape) → Task 6's `ExtractedSubQuestion` (deliberately a subset, documented why). §13 (question types) → Task 6's `type` literal list matches DATA_MODEL.md's 9 MVP `QuestionType` values. PIPELINE.md's OCR/LayoutAnalysis/QuestionExtraction steps → Tasks 1-2, 5, 6 respectively. ARCHITECTURE.md's provider protocols → Tasks 1-3 match the exact signatures. ARCHITECTURE.md's model-choice table → Task 4 wires the config, Task 7's CLI reads it. EVALUATION.md's OCR + extraction metrics → Task 8. EVALUATION.md's golden dataset transcription requirement → Task 9.
- **Deferred, not forgotten:** the full `Question` Pydantic model (`id`, `paper_id`, `difficulty_features`, `answer_type`, `source`, `template_id`) is Phase 5's job per PROJECT_PLAN.md's phase table ("Every extracted question round-trips through the model without data loss") — Task 6's `ExtractedSubQuestion` is intentionally lighter, and Task 9's fixture schema matches that scope rather than over-building ahead of Phase 5.
- **Type consistency:** `LayoutGroup` (Task 5) is consumed unchanged by Task 6 and Task 7. `ExtractedSubQuestion`/`QuestionGroupExtraction` (Task 6) are consumed unchanged by Task 7's CLI. `OCRResult`/`OCRWord` (Task 1) are consumed unchanged by Tasks 2, 5, 7.
