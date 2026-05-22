"""FastAPI smoke tests — exercise the wiring without DB / LLM dependencies."""
from __future__ import annotations

from fastapi.testclient import TestClient

from apex.api.main import build_app


def test_root_and_health():
    app = build_app()
    with TestClient(app) as client:
        r = client.get("/")
        assert r.status_code == 200
        assert r.json()["name"] == "apex-rag"
        r = client.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"


def test_metrics_exposes_queue():
    app = build_app()
    with TestClient(app) as client:
        r = client.get("/api/metrics")
        assert r.status_code == 200
        body = r.json()
        assert "queue_size" in body
        assert "queue_max" in body


def test_ready_endpoint():
    app = build_app()
    with TestClient(app) as client:
        r = client.get("/api/ready")
        assert r.status_code == 200
        assert r.json()["ready"] is True


def test_tenant_header_round_trips():
    app = build_app()
    with TestClient(app) as client:
        r = client.get("/api/ready", headers={"X-Tenant-Id": "alpha"})
        assert r.status_code == 200
        assert r.headers["X-Tenant-Id"] == "alpha"
