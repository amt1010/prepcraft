"""Judgment-over-text AI call site (ARCHITECTURE.md's model-choice table):
question classification now (questions/extraction.py), question-draft
generation in Phase 7. Both are claude-sonnet-5 because they need actual
reasoning about curriculum/topic/phrasing, unlike the cheap perception
calls in providers/vision.py and providers/ocr/claude_provider.py."""

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
