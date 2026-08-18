from unittest.mock import MagicMock, patch

from pydantic import BaseModel

from app.backend.providers.text_generation import ClaudeTextGenerationProvider


class _FakeSchema(BaseModel):
    value: str


def test_generate_returns_the_parsed_structured_output():
    with patch("anthropic.Anthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.parsed_output = _FakeSchema(value="classified")
        mock_client.messages.parse.return_value = mock_response

        provider = ClaudeTextGenerationProvider(api_key="fake-key")
        result = provider.generate(prompt="classify this", schema=_FakeSchema)

        assert result == _FakeSchema(value="classified")
        mock_client.messages.parse.assert_called_once()


def test_generate_uses_the_configured_model_and_the_given_schema():
    with patch("anthropic.Anthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.parsed_output = _FakeSchema(value="x")
        mock_client.messages.parse.return_value = mock_response

        provider = ClaudeTextGenerationProvider(api_key="fake-key", model="claude-sonnet-5")
        provider.generate(prompt="classify this", schema=_FakeSchema)

        call_kwargs = mock_client.messages.parse.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-5"
        assert call_kwargs["output_format"] is _FakeSchema
        assert call_kwargs["messages"][0]["content"] == "classify this"
