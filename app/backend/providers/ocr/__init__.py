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
