"""Audit log helper — verify it never raises and constructs the right SQL params."""

from __future__ import annotations

from apex.api import audit


def test_log_event_swallows_db_errors(monkeypatch):
    def boom(*_a, **_kw):
        raise RuntimeError("db down")

    monkeypatch.setattr(audit, "session_scope", boom)
    # must not propagate; otherwise a transient DB outage would break the API
    audit.log_event(tenant_id="t1", action="search", request={"q": "x"})


def test_log_event_passes_params_to_session(monkeypatch):
    captured: dict = {}

    class _Session:
        def execute(self, _stmt, params):
            captured.update(params)

    class _Ctx:
        def __enter__(self):
            return _Session()

        def __exit__(self, *_):
            return False

    monkeypatch.setattr(audit, "session_scope", lambda: _Ctx())

    audit.log_event(
        tenant_id="alpha",
        action="chat",
        request={"q": "what?"},
        response_summary={"n": 3},
        source_chunk_ids=["c1", "c2"],
        latency_ms=42,
        user_id="u1",
    )

    assert captured["tenant_id"] == "alpha"
    assert captured["action"] == "chat"
    assert captured["latency_ms"] == 42
    assert captured["user_id"] == "u1"
    # JSON-serialised payloads
    assert '"q"' in captured["request"]
    assert "c1" in captured["source_chunk_ids"]


def test_log_event_defaults_no_payloads(monkeypatch):
    captured: dict = {}

    class _Session:
        def execute(self, _stmt, params):
            captured.update(params)

    class _Ctx:
        def __enter__(self):
            return _Session()

        def __exit__(self, *_):
            return False

    monkeypatch.setattr(audit, "session_scope", lambda: _Ctx())
    audit.log_event(tenant_id="t", action="x")
    assert captured["request"] == "{}"
    assert captured["response_summary"] == "{}"
    assert captured["source_chunk_ids"] == "[]"
    assert captured["latency_ms"] is None
