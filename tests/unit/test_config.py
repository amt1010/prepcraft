from pathlib import Path

import pytest

from app.backend.core.config import AppConfig, load_config


def test_load_config_reads_values_from_yaml_file(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("ai_provider: openai\nlog_level: DEBUG\n")

    config = load_config(config_file)

    assert config.ai_provider == "openai"
    assert config.log_level == "DEBUG"


def test_load_config_uses_defaults_for_fields_missing_from_yaml(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("ai_provider: openai\n")

    config = load_config(config_file)

    assert config.ocr_provider == AppConfig().ocr_provider


def test_load_config_raises_when_file_does_not_exist(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "missing.yaml")


def test_load_config_treats_empty_file_as_all_defaults(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("")

    config = load_config(config_file)

    assert config == AppConfig()


def test_load_config_reads_nested_quality_thresholds(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("quality:\n  max_skew_degrees: 15\n  min_sharpness: 80\n")

    config = load_config(config_file)

    assert config.quality.max_skew_degrees == 15
    assert config.quality.min_sharpness == 80


def test_load_config_defaults_quality_thresholds_when_omitted(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("ai_provider: openai\n")

    config = load_config(config_file)

    assert config.quality.max_skew_degrees == 20.0
    assert config.quality.min_sharpness == 100.0


def test_load_config_reads_nested_model_routing(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "models:\n  ocr_fallback: claude-haiku-4-5\n  question_classification: claude-opus-5\n"
    )

    config = load_config(config_file)

    assert config.models.ocr_fallback == "claude-haiku-4-5"
    assert config.models.question_classification == "claude-opus-5"


def test_load_config_defaults_model_routing_when_omitted(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("ai_provider: openai\n")

    config = load_config(config_file)

    assert config.models.annotation_vision == "claude-haiku-4-5"
    assert config.models.ocr_fallback == "claude-haiku-4-5"
    assert config.models.question_classification == "claude-sonnet-5"
    assert config.models.question_generation == "claude-sonnet-5"
