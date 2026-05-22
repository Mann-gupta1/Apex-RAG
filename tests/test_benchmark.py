"""Benchmark percentile + table renderer."""

from __future__ import annotations

from apex.scripts.benchmark import _percentile, _render_table


def test_percentile_empty():
    assert _percentile([], 50) == 0.0


def test_percentile_single():
    assert _percentile([42.0], 50) == 42.0


def test_percentile_known_distribution():
    values = list(range(1, 101))  # 1..100
    p50 = _percentile(values, 50)
    p95 = _percentile(values, 95)
    p99 = _percentile(values, 99)
    assert 49 <= p50 <= 51
    assert 94 <= p95 <= 96
    assert 98 <= p99 <= 100


def test_render_table_contains_metric_names():
    variants = [
        {"id": "naive"},
        {"id": "apex"},
    ]
    runs = {
        "naive": {
            "metrics": {
                "faithfulness": 0.6,
                "context_recall": 0.7,
                "context_precision": 0.65,
                "answer_relevance": 0.7,
                "answer_correctness": 0.6,
            },
            "latency": {"n": 5, "p50_ms": 100, "p95_ms": 200, "p99_ms": 250, "mean_ms": 150},
        },
        "apex": {
            "metrics": {
                "faithfulness": 0.9,
                "context_recall": 0.85,
                "context_precision": 0.8,
                "answer_relevance": 0.88,
                "answer_correctness": 0.82,
            },
            "latency": {"n": 5, "p50_ms": 200, "p95_ms": 400, "p99_ms": 500, "mean_ms": 250},
        },
    }
    md = _render_table(variants, runs)
    assert "faithfulness" in md
    assert "naive" in md and "apex" in md
    assert "Δ" in md or "delta" in md.lower()
    assert "Latency" in md


def test_render_table_delta_signs():
    variants = [{"id": "n"}, {"id": "a"}]
    runs = {
        "n": {
            "metrics": {
                "faithfulness": 0.5,
                "context_recall": 0.5,
                "context_precision": 0.5,
                "answer_relevance": 0.5,
                "answer_correctness": 0.5,
            },
            "latency": {"n": 0, "p50_ms": 0, "p95_ms": 0, "p99_ms": 0, "mean_ms": 0},
        },
        "a": {
            "metrics": {
                "faithfulness": 0.9,
                "context_recall": 0.9,
                "context_precision": 0.9,
                "answer_relevance": 0.9,
                "answer_correctness": 0.9,
            },
            "latency": {"n": 0, "p50_ms": 0, "p95_ms": 0, "p99_ms": 0, "mean_ms": 0},
        },
    }
    md = _render_table(variants, runs)
    assert "+0.400" in md
