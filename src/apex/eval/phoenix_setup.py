"""Phoenix OpenTelemetry initialisation.

Called from the FastAPI lifespan; safe to import without arize-phoenix
installed (no-op in that case).
"""
from __future__ import annotations

import os

from apex.logging_config import logger
from apex.settings import get_settings


def maybe_init_phoenix() -> None:
    settings = get_settings()
    if not settings.apex_otel_enabled:
        return
    try:
        from phoenix.otel import register

        os.environ.setdefault("PHOENIX_COLLECTOR_ENDPOINT", settings.phoenix_collector_endpoint)
        register(project_name="apex-rag")
        logger.info("phoenix tracing initialised → {}", settings.phoenix_collector_endpoint)
    except Exception as exc:
        logger.debug("phoenix not initialised: {}", exc)


def launch_phoenix_inline() -> None:
    """Launch Phoenix in-process for ad-hoc local exploration (notebooks)."""
    try:
        import phoenix as px

        session = px.launch_app()
        logger.info("phoenix UI available at {}", session.url)
    except Exception as exc:
        logger.warning("could not launch phoenix inline: {}", exc)
