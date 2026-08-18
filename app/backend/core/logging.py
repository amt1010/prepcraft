"""Structured logging setup.

Every stage of the pipeline logs through get_logger(__name__); the format
below always includes the logger name so a log line is traceable back to
the module (and, once run-scoped logging is added in Phase 2, the run ID)
that produced it.
"""

import logging

_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(level=level.upper(), format=_FORMAT, force=True)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
