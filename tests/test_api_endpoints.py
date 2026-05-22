"""FastAPI endpoint integration with mocked DB / store / LLM."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apex.api.main import build_app
from apex.schemas import Chunk, Modality, Provenance
from tests.fakes import install_fakes


@pytest.fixture
def client(monkeypatch):
    store = install_fakes(monkeypatch)
    store.upsert(
        [
            Chunk(
                id="c1",
                modality=Modality.TEXT,
                content="Marbury v. Madison established judicial review.",
                provenance=Provenance(source_uri="m.pdf", modality=Modality.TEXT, page=1),
            )
        ]
    )
    monkeypatch.setattr("apex.api.audit.log_event", lambda **k: None)
    monkeypatch.setattr("apex.agent.graph.generate", lambda *a, **k: "Answer with citation [1].")
    monkeypatch.setattr("apex.agent.graph.faithfulness_score", lambda *a, **k: 0.92)
    monkeypatch.setattr(
        "apex.agent.graph.stream", lambda *a, **k: iter(["Answer ", "with ", "citation ", "[1]."])
    )

    app = build_app()
    with TestClient(app) as c:
        yield c


def test_health_endpoint(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok"
    assert "llm_healthy" in body


def test_ready_endpoint(client):
    r = client.get("/api/ready")
    assert r.status_code in (200, 503)


def test_metrics_endpoint(client):
    r = client.get("/api/metrics")
    assert r.status_code == 200


def test_search_endpoint(client):
    r = client.post(
        "/api/search",
        json={"query": "judicial review", "top_k": 3, "use_rerank": False, "use_hyde": False},
    )
    assert r.status_code == 200
    body = r.json()
    assert any("marbury" in res["chunk"]["content"].lower() for res in body["results"])


def test_feedback_endpoint(client, monkeypatch):
    monkeypatch.setattr("apex.feedback.human_loop.record_feedback", lambda req: 1)
    r = client.post(
        "/api/feedback",
        json={"query": "q", "response": "a", "chunk_ids": ["c1"], "rating": 1},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_upload_endpoint_queues_job(client, monkeypatch):
    from apex.api import backpressure as bp

    submitted = {"count": 0}

    async def fake_submit(task):
        submitted["count"] += 1
        return None

    monkeypatch.setattr(bp.queue, "submit", fake_submit)
    files = {"file": ("memo.txt", b"hello world tokens", "text/plain")}
    r = client.post("/api/upload", files=files)
    assert r.status_code in (200, 202), r.text
    assert submitted["count"] == 1


def test_eval_endpoint_queues(client, monkeypatch):
    from apex.api import backpressure as bp

    submitted = {"count": 0}

    async def fake_submit(task):
        submitted["count"] += 1
        return None

    monkeypatch.setattr(bp.queue, "submit", fake_submit)
    r = client.post("/api/eval?variant=apex")
    assert r.status_code == 200
    assert r.json()["status"] == "queued"


def test_chat_stream_returns_sse(client):
    with client.stream("POST", "/api/chat/stream", json={"query": "judicial review"}) as r:
        assert r.status_code == 200
        chunks = list(r.iter_text())
    payload = "".join(chunks)
    assert "data:" in payload
    assert "done" in payload


def test_chat_endpoint_non_streaming(client):
    r = client.post("/api/chat", json={"query": "judicial review"})
    assert r.status_code == 200
    body = r.json()
    assert "answer" in body
    assert isinstance(body.get("citations", []), list)
