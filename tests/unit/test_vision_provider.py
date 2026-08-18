from unittest.mock import MagicMock, patch

from app.backend.providers.vision import ClaudeVisionProvider, VisionResult


def test_analyze_region_returns_the_parsed_structured_output():
    with patch("anthropic.Anthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.parsed_output = VisionResult(label="handwritten_or_marked", confidence=0.9)
        mock_client.messages.parse.return_value = mock_response

        provider = ClaudeVisionProvider(api_key="fake-key")
        result = provider.analyze_region(
            image=b"fake-png-bytes", prompt="is this printed or handwritten?"
        )

        assert result == VisionResult(label="handwritten_or_marked", confidence=0.9)
        mock_client.messages.parse.assert_called_once()


def test_analyze_region_sends_the_image_as_base64_and_uses_the_configured_model():
    with patch("anthropic.Anthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.parsed_output = VisionResult(label="printed", confidence=0.6)
        mock_client.messages.parse.return_value = mock_response

        provider = ClaudeVisionProvider(api_key="fake-key", model="claude-haiku-4-5")
        provider.analyze_region(image=b"abc", prompt="classify this")

        call_kwargs = mock_client.messages.parse.call_args.kwargs
        assert call_kwargs["model"] == "claude-haiku-4-5"
        content = call_kwargs["messages"][0]["content"]
        assert content[0]["type"] == "image"
        assert content[0]["source"]["type"] == "base64"
