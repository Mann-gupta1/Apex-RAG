"""pytest fixtures shared across the test suite."""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Deterministic, side-effect-free defaults for CI and local runs.
os.environ.setdefault("APEX_LOG_LEVEL", "WARNING")
os.environ.setdefault("APEX_OTEL_ENABLED", "false")
os.environ.setdefault("ENABLE_CONTEXTUAL_RETRIEVAL", "false")
os.environ.setdefault("PYTHONHASHSEED", "0")


@pytest.fixture
def settings_reset() -> Iterator[None]:
    """Clear the cached settings singleton for tests that mutate env vars."""
    from apex.settings import reset_caches

    reset_caches()
    yield
    reset_caches()


@pytest.fixture(autouse=True)
def _disable_redis_rate_limit(monkeypatch) -> Iterator[None]:
    """Avoid flaky 429s when the CI Redis service is reachable."""
    try:
        from apex.api import middleware

        monkeypatch.setattr(middleware, "_get_redis", lambda: None)
        middleware._inmem_counters.clear()  # type: ignore[attr-defined]
    except Exception:
        pass
    yield


@pytest.fixture(autouse=True)
def _clear_inmem_rate_counters() -> Iterator[None]:
    """Tests share a process; ensure the in-memory rate-limit bucket is fresh."""
    try:
        from apex.api import middleware

        middleware._inmem_counters.clear()  # type: ignore[attr-defined]
    except Exception:
        pass
    yield
