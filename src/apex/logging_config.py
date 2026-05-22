"""Structured logging with loguru. Every module should do ``from apex.logging_config import logger``."""
from __future__ import annotations

import sys

from loguru import logger as _logger

from apex.settings import get_settings


def _configure() -> None:
    settings = get_settings()
    _logger.remove()
    _logger.add(
        sys.stderr,
        level=settings.apex_log_level,
        backtrace=False,
        diagnose=False,
        enqueue=False,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> "
            "<level>{level: <8}</level> "
            "<cyan>{name}:{function}:{line}</cyan> "
            "- <level>{message}</level>"
        ),
    )


_configure()
logger = _logger
__all__ = ["logger"]
