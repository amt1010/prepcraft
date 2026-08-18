"""API keys and other secrets, read from environment variables / .env.

Kept separate from AppConfig (core/config.py) so secrets can never end up
in config.yaml, which is meant to be committed.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Secrets(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str | None = None
