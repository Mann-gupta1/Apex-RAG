"""Middleware: JWT tenant resolution + in-memory token bucket rate limit."""
from __future__ import annotations

import time
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from jose import jwt

from apex.api import middleware
from apex.api.main import build_app
from apex.settings import get_settings


def test_jwt_tenant_extracted_from_bearer(monkeypatch):
    settings = get_settings()
    token = jwt.encode(
        {"sub": "user-1", "tenant_id": "acme"},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    req = MagicMock()
    req.headers = {"Authorization": f"Bearer {token}"}
    assert middleware.resolve_tenant(req) == "acme"


def test_jwt_missing_tenant_claim_falls_back_to_default():
    settings = get_settings()
    token = jwt.encode({"sub": "user-1"}, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    req = MagicMock()
    req.headers = {"Authorization": f"Bearer {token}"}
    assert middleware.resolve_tenant(req) == "default"


def test_x_tenant_id_takes_precedence_over_jwt():
    settings = get_settings()
    token = jwt.encode({"tenant_id": "jwt-tenant"}, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    req = MagicMock()
    req.headers = {"X-Tenant-Id": "header-tenant", "Authorization": f"Bearer {token}"}
    assert middleware.resolve_tenant(req) == "header-tenant"


def test_in_memory_rate_limit_triggers_429(monkeypatch):
    # Force redis off so we exercise the in-memory bucket.
    monkeypatch.setattr(middleware, "_get_redis", lambda: None)
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "3")
    from apex.settings import reset_caches

    reset_caches()
    middleware._inmem_counters.clear()  # type: ignore[attr-defined]

    app = build_app()
    tenant = f"rl-test-{int(time.time())}"
    with TestClient(app) as client:
        ok = 0
        limited = 0
        for _ in range(8):
            r = client.get("/api/ready", headers={"X-Tenant-Id": tenant})
            if r.status_code == 200:
                ok += 1
            elif r.status_code == 429:
                limited += 1
        assert ok <= 3, f"expected at most 3 successful calls, got {ok}"
        assert limited >= 4, f"expected at least 4 limited calls, got {limited}"


def test_unprotected_paths_skip_rate_limit(monkeypatch):
    monkeypatch.setattr(middleware, "_get_redis", lambda: None)
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1")
    from apex.settings import reset_caches

    reset_caches()
    middleware._inmem_counters.clear()  # type: ignore[attr-defined]

    app = build_app()
    with TestClient(app) as client:
        # Root and docs are explicitly whitelisted in middleware._check_rate;
        # they MUST never produce a 429 regardless of how many times we hit them.
        for _ in range(5):
            assert client.get("/").status_code == 200
            assert client.get("/openapi.json").status_code == 200
