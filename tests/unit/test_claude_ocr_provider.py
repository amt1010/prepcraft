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
