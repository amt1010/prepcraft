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
