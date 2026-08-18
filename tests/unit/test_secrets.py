from app.backend.core.secrets import Secrets


def test_secrets_reads_anthropic_api_key_from_environment(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")

    secrets = Secrets()

    assert secrets.anthropic_api_key == "sk-test-123"


def test_secrets_defaults_to_none_when_env_var_unset(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    secrets = Secrets()

    assert secrets.anthropic_api_key is None
