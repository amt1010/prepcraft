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
