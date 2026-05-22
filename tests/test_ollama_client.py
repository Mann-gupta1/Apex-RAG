"""Ollama client retry + parsing logic (no live Ollama needed)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import httpx
import pytest

from apex.llm import ollama_client


class _FakeResponse:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self._payload = payload
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=MagicMock(), response=MagicMock(status_code=self.status_code))

    def json(self) -> dict:
        return self._payload


class _FakeClient:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        self.calls = 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def post(self, *_a, **_kw):
        self.calls += 1
        return self._response


def test_generate_extracts_response_field(monkeypatch):
    fake_resp = _FakeResponse({"response": "  hello\n"})
    fake_client = _FakeClient(fake_resp)
    monkeypatch.setattr(ollama_client.httpx, "Client", lambda *a, **k: fake_client)
    out = ollama_client.generate("hi")
    assert out == "hello"
    assert fake_client.calls == 1


def test_generate_uses_default_model(monkeypatch):
    captured = {}
    fake_resp = _FakeResponse({"response": "ok"})

    class C(_FakeClient):
        def post(self, url, json=None, **kw):
            captured["model"] = json["model"]
            return self._response

    monkeypatch.setattr(ollama_client.httpx, "Client", lambda *a, **k: C(fake_resp))
    ollama_client.generate("hi")
    assert "llama3" in captured["model"] or captured["model"]


def test_health_returns_false_on_error(monkeypatch):
    class BadClient:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def get(self, *_a, **_kw):
            raise httpx.ConnectError("boom")

    monkeypatch.setattr(ollama_client.httpx, "Client", lambda *a, **k: BadClient())
    assert ollama_client.health() is False


def test_stream_yields_token_deltas(monkeypatch):
    chunks_iter = iter([
        json.dumps({"response": "Hello"}),
        json.dumps({"response": " world"}),
        json.dumps({"done": True}),
    ])

    class _StreamCtx:
        def __init__(self):
            self.status_code = 200

        def raise_for_status(self):
            return None

        def iter_lines(self):
            yield from chunks_iter

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    class _C:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def stream(self, *_a, **_kw):
            return _StreamCtx()

    monkeypatch.setattr(ollama_client.httpx, "Client", lambda *a, **k: _C())
    out = list(ollama_client.stream("hi", max_tokens=10))
    assert "".join(out) == "Hello world"


def test_generate_includes_system_and_stop(monkeypatch):
    captured = {}
    resp = _FakeResponse({"response": "ok"})

    class C(_FakeClient):
        def post(self, url, json=None, **kw):
            captured["payload"] = json
            return self._response

    monkeypatch.setattr(ollama_client.httpx, "Client", lambda *a, **k: C(resp))
    ollama_client.generate("hi", system="you are helpful", stop=["END"], max_tokens=5, temperature=0.7)
    assert captured["payload"]["system"] == "you are helpful"
    assert captured["payload"]["options"]["stop"] == ["END"]
    assert captured["payload"]["options"]["num_predict"] == 5
    assert captured["payload"]["options"]["temperature"] == pytest.approx(0.7)
