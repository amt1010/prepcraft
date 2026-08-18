import logging

from app.backend.core.logging import configure_logging, get_logger


def test_configure_logging_sets_root_logger_level():
    configure_logging("DEBUG")

    assert logging.getLogger().level == logging.DEBUG


def test_configure_logging_accepts_lowercase_level_names():
    configure_logging("warning")

    assert logging.getLogger().level == logging.WARNING


def test_get_logger_returns_logger_with_given_name():
    logger = get_logger("app.backend.ingestion")

    assert logger.name == "app.backend.ingestion"
