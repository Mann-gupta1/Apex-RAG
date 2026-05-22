"""Feedback export pipelines (reranker pairs + DPO)."""

from __future__ import annotations

import json

from apex.feedback import human_loop


def _fake_rows():
    return [
        {
            "id": 1,
            "tenant_id": "t1",
            "query": "what year?",
            "response": "1803",
            "chunk_ids": ["c1"],
            "rating": 1,
            "comment": None,
            "created_at": None,
        },
        {
            "id": 2,
            "tenant_id": "t1",
            "query": "what year?",
            "response": "1804",
            "chunk_ids": ["c2"],
            "rating": -1,
            "comment": None,
            "created_at": None,
        },
        {
            "id": 3,
            "tenant_id": "t1",
            "query": "what year?",
            "response": "1803 confirmed",
            "chunk_ids": ["c1", "c3"],
            "rating": 1,
            "comment": None,
            "created_at": None,
        },
        {
            "id": 4,
            "tenant_id": "t1",
            "query": "who decided?",
            "response": "Marshall",
            "chunk_ids": ["c4"],
            "rating": 1,
            "comment": None,
            "created_at": None,
        },
        {
            "id": 5,
            "tenant_id": "t1",
            "query": "who decided?",
            "response": "Taney",
            "chunk_ids": ["c5"],
            "rating": -1,
            "comment": None,
            "created_at": None,
        },
    ]


def test_export_reranker_pairs(tmp_path, monkeypatch):
    monkeypatch.setattr(human_loop, "_iter_feedback", lambda: iter(_fake_rows()))
    out = tmp_path / "reranker.jsonl"
    n = human_loop.export_reranker_pairs(out)
    assert n == 2  # two distinct queries with mixed feedback
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    parsed = [json.loads(ln) for ln in lines]
    by_query = {p["query"]: p for p in parsed}
    assert "c1" in by_query["what year?"]["positive"]
    assert "c2" in by_query["what year?"]["negative"]


def test_export_dpo_dataset(tmp_path, monkeypatch):
    monkeypatch.setattr(human_loop, "_iter_feedback", lambda: iter(_fake_rows()))
    out = tmp_path / "dpo.jsonl"
    n = human_loop.export_dpo_dataset(out)
    # year query has 2 chosen and 1 rejected (2 pairs); decided query has 1 chosen and 1 rejected (1 pair)
    assert n == 3
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    parsed = [json.loads(ln) for ln in lines]
    assert all({"prompt", "chosen", "rejected"} <= set(p) for p in parsed)


def test_export_no_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(human_loop, "_iter_feedback", lambda: iter([]))
    rr = tmp_path / "rr.jsonl"
    dpo = tmp_path / "dpo.jsonl"
    assert human_loop.export_reranker_pairs(rr) == 0
    assert human_loop.export_dpo_dataset(dpo) == 0
    # both files are written, empty
    assert rr.exists()
    assert dpo.exists()


def test_export_datasets_returns_counts(tmp_path, monkeypatch):
    monkeypatch.setattr(human_loop, "_iter_feedback", lambda: iter(_fake_rows()))
    result = human_loop.export_datasets(tmp_path / "rr.jsonl", tmp_path / "dpo.jsonl")
    assert result["reranker_pairs"] == 2
    assert result["dpo_pairs"] == 3
    assert "ran_at" in result
