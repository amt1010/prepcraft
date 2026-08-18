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
