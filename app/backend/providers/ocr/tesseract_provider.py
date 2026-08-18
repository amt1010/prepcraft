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
