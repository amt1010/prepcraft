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
