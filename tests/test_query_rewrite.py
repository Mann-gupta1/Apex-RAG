"""Query rewrite fallbacks (no Ollama required)."""
from __future__ import annotations

from apex.retrieval import query_rewrite


def test_hyde_falls_back_to_query_without_llm(monkeypatch):
    monkeypatch.setattr(query_rewrite, "_safe_generate", lambda *a, **k: None)
    assert query_rewrite.hyde("what is judicial review?") == "what is judicial review?"


def test_step_back_falls_back(monkeypatch):
    monkeypatch.setattr(query_rewrite, "_safe_generate", lambda *a, **k: None)
    assert query_rewrite.step_back("what is judicial review?") == "what is judicial review?"


def test_multi_query_falls_back(monkeypatch):
    monkeypatch.setattr(query_rewrite, "_safe_generate", lambda *a, **k: None)
    qs = query_rewrite.multi_query("what is judicial review?")
    assert qs == ["what is judicial review?"]


def test_expand_unique(monkeypatch):
    monkeypatch.setattr(query_rewrite, "_safe_generate", lambda *a, **k: None)
    out = query_rewrite.expand("what is judicial review?")
    assert len(out) == len(set(out))


def test_multi_query_parses_lines(monkeypatch):
    canned = "What did the court rule?\nWhat year was it decided?\nWho was the chief justice?\n"
    monkeypatch.setattr(query_rewrite, "_safe_generate", lambda *a, **k: canned)
    qs = query_rewrite.multi_query("judicial review history", n=3)
    assert len(qs) == 3
    assert all(len(q.split()) >= 3 for q in qs)
