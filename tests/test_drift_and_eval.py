"""Eval helpers: drift detector + regression guard + RAGAS fallback."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pytest

from apex.eval import drift, regression_guard
from apex.eval.ragas_runner import _fallback_metrics
from apex.schemas import EvalMetric, EvalRunSummary

TRACKED = ["faithfulness", "context_recall", "answer_relevance"]


def test_regression_guard_passes_within_threshold():
    baseline = {"metrics": {"faithfulness": 0.8, "context_recall": 0.7, "answer_relevance": 0.7}}
    latest = {"metrics": {"faithfulness": 0.79, "context_recall": 0.72, "answer_relevance": 0.72}}
    report = regression_guard.compare(latest, baseline, threshold=0.05, tracked=TRACKED)
    assert report["failures"] == []
    assert "faithfulness" in report["diffs"]


def test_regression_guard_fails_below_threshold():
    baseline = {"metrics": {"faithfulness": 0.9}}
    latest = {"metrics": {"faithfulness": 0.5}}
    report = regression_guard.compare(latest, baseline, threshold=0.05, tracked=TRACKED)
    assert "faithfulness" in report["failures"]
    assert report["diffs"]["faithfulness"]["delta"] < -0.05


def test_regression_guard_handles_missing_metric():
    baseline = {"metrics": {"faithfulness": 0.9, "extra": 0.5}}
    latest = {"metrics": {"faithfulness": 0.9}}
    report = regression_guard.compare(latest, baseline, threshold=0.1, tracked=TRACKED)
    assert report["failures"] == []


def test_drift_ks_statistic_zero_for_same_distribution():
    a = np.tile(np.linspace(0, 1, 100), (4, 1)).T
    b = np.tile(np.linspace(0, 1, 100), (4, 1)).T
    res = drift._ks_test_per_dim(a, b)
    assert res["ks_d_mean"] == pytest.approx(0.0, abs=1e-3)


def test_drift_ks_statistic_high_for_shifted():
    rng = np.random.default_rng(0)
    a = rng.standard_normal((50, 4))
    b = rng.standard_normal((50, 4)) + 10.0
    res = drift._ks_test_per_dim(a, b)
    assert res["ks_d_mean"] > 0.5


def test_ragas_fallback_returns_metrics_list():
    records = [
        {
            "question": "q1",
            "answer": "a1 token",
            "contexts": ["a1 token context"],
            "ground_truth": "a1 token",
            "expected_sources": [],
        },
        {
            "question": "q2",
            "answer": "wrong",
            "contexts": ["other context"],
            "ground_truth": "right",
            "expected_sources": [],
        },
    ]
    metrics = _fallback_metrics(records)
    names = {m.name for m in metrics}
    assert {
        "faithfulness",
        "context_recall",
        "context_precision",
        "answer_relevance",
        "answer_correctness",
    } <= names
    for m in metrics:
        assert 0.0 <= m.value <= 1.0


def test_eval_run_summary_serialises():
    now = datetime.now(timezone.utc)
    summary = EvalRunSummary(
        run_id="abc",
        started_at=now,
        finished_at=now,
        metrics=[EvalMetric(name="faithfulness", value=0.9)],
        variant="apex",
    )
    blob = summary.model_dump()
    assert blob["variant"] == "apex"
    assert blob["metrics"][0]["name"] == "faithfulness"
