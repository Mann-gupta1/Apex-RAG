"""Adaptive retrieval plan."""
from __future__ import annotations

from apex.retrieval.adaptive import classify, plan


def test_simple_query_short():
    assert classify("What is judicial review?") == "simple"


def test_complex_query_compare():
    assert classify("Compare Marbury and Brown decisions.") == "complex"


def test_plan_simple_skips_rerank():
    p = plan("Define judicial review")
    assert p.use_rerank is False
    assert p.top_k <= 6


def test_plan_complex_enables_features():
    p = plan("Summarise and compare the constitutional reasoning across these decisions in detail.")
    assert p.use_rerank is True
    assert p.use_hyde is True
    assert p.top_k >= 6
