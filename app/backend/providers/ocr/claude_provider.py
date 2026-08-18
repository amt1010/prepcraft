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
