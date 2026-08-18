from app.backend.core.secrets import Secrets


def test_secrets_reads_anthropic_api_key_from_environment(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")

    secrets = Secrets()

    assert secrets.anthropic_api_key == "sk-test-123"


def test_secrets_defaults_to_none_when_env_var_unset(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    # Deleting the process env var isn't enough in isolation — Secrets also
    # reads .env directly off disk, and a real one now legitimately exists
    # in this repo (gitignored, dev-only). _env_file=None skips that file
    # read so this test still proves the "nothing configured" default.
    secrets = Secrets(_env_file=None)

    assert secrets.anthropic_api_key is None
