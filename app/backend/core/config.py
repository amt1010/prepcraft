"""Non-secret application settings, loaded from config.yaml.

Secrets (API keys) never live here — see core/secrets.py, which reads
.env instead. Keeping the two apart is what makes "no API keys in source
code, no API keys in config.yaml" checkable by just not putting a secret
field on this model.
"""

from pathlib import Path

import yaml
from pydantic import BaseModel


class QualityConfig(BaseModel):
    max_skew_degrees: float = 20.0
    min_sharpness: float = 100.0


class AppConfig(BaseModel):
    ai_provider: str = "claude"
    ai_model: str = "claude-sonnet-5"
    ocr_provider: str = "tesseract"
    storage_root: Path = Path("data")
    log_level: str = "INFO"
    pdf_page_size: str = "A4"
    generation_max_regenerate_attempts: int = 3
    quality: QualityConfig = QualityConfig()


def load_config(path: Path) -> AppConfig:
    if not path.exists():
        raise FileNotFoundError(f"config file not found: {path}")
    data = yaml.safe_load(path.read_text()) or {}
    return AppConfig(**data)
