"""Adaptive retrieval depth.

Heuristic + LLM-light classifier that chooses ``top_k`` and whether to rerank
based on the query's complexity. Cheap queries skip the rerank entirely.
"""

from __future__ import annotations

from dataclasses import dataclass

from apex.logging_config import logger
from apex.settings import load_yaml_config


@dataclass
class RetrievalPlan:
    top_k: int
    use_rerank: bool
    use_hyde: bool
    complexity: str  # "simple" | "complex"


SIMPLE_MARKERS = {"what is", "who is", "define", "when was", "where is"}
COMPLEX_MARKERS = {
    "compare",
    "contrast",
    "summarise",
    "summarize",
    "across",
    "between",
    "trade-off",
    "tradeoff",
}


def classify(query: str) -> str:
    q = query.lower()
    if any(m in q for m in COMPLEX_MARKERS) or q.count("?") > 1 or len(q.split()) > 18:
        return "complex"
    if any(q.startswith(m) for m in SIMPLE_MARKERS) or len(q.split()) < 6:
        return "simple"
    return "complex"


def plan(query: str) -> RetrievalPlan:
    cfg = load_yaml_config("retrieval").get("advanced", {}).get("adaptive_depth", {})
    simple_k = int(cfg.get("simple_top_k", 3))
    complex_k = int(cfg.get("complex_top_k", 20))
    complexity = classify(query)
    p = RetrievalPlan(
        top_k=simple_k if complexity == "simple" else complex_k,
        use_rerank=complexity == "complex",
        use_hyde=complexity == "complex",
        complexity=complexity,
    )
    logger.debug("adaptive plan for {!r}: {}", query, p)
    return p
