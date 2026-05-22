"""Critical security test: tenant resolution + isolation contract.

We don't have a live DB in CI, but we can lock down the contract that
* the middleware never lets a request through without a resolved tenant,
* and the resolved tenant is reflected in the response header.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from apex.api.main import build_app


def test_default_tenant_when_no_header():
    app = build_app()
    with TestClient(app) as client:
        r = client.get("/api/ready")
        assert r.status_code == 200
        assert r.headers["X-Tenant-Id"] == "default"


def test_explicit_tenant_header_used():
    app = build_app()
    with TestClient(app) as client:
        r = client.get("/api/ready", headers={"X-Tenant-Id": "alice"})
        assert r.headers["X-Tenant-Id"] == "alice"
        r = client.get("/api/ready", headers={"X-Tenant-Id": "bob"})
        assert r.headers["X-Tenant-Id"] == "bob"


def test_invalid_jwt_falls_back_to_default():
    app = build_app()
    with TestClient(app) as client:
        r = client.get("/api/ready", headers={"Authorization": "Bearer not-a-jwt"})
        assert r.status_code == 200
        assert r.headers["X-Tenant-Id"] == "default"
