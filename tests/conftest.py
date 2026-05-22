"""pytest fixtures shared across the test suite."""
from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

# Make sure tests use deterministic, side-effect-free defaults.
os.environ.setdefault("APEX_LOG_LEVEL", "WARNING")
os.environ.setdefault("APEX_OTEL_ENABLED", "false")
os.environ.setdefault("ENABLE_CONTEXTUAL_RETRIEVAL", "false")


@pytest.fixture
def settings_reset() -> Iterator[None]:
    """Clear the cached settings singleton for tests that mutate env vars."""
    from apex.settings import reset_caches

    reset_caches()
    yield
    reset_caches()


@pytest.fixture(autouse=True)
def _clear_inmem_rate_counters() -> Iterator[None]:
    """Tests share a process; ensure the in-memory rate-limit bucket is fresh."""
    try:
        from apex.api import middleware

        middleware._inmem_counters.clear()  # type: ignore[attr-defined]
    except Exception:
        pass
    yield
