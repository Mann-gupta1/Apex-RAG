"""Query router: classify a query into one of {factual, analytical, visual, deep_research}."""
from __future__ import annotations

from dataclasses import dataclass

from apex.logging_config import logger
from apex.schemas import Modality


@dataclass
class RouteDecision:
    kind: str  # factual | analytical | visual | deep_research
    modalities: list[Modality] | None
    reason: str


_VISUAL_TOKENS = {"image", "photo", "picture", "exhibit", "video", "deposition", "screenshot", "timestamp"}
_DEEP_RESEARCH_MARKERS = {
    "summarise", "summarize", "memo", "comprehensive", "across", "trends", "synthesise",
    "synthesize", "report on", "compile", "literature review", "case law", "compare and contrast",
}
_ANALYTICAL_MARKERS = {
    "compare", "contrast", "why", "how does", "explain", "tradeoff", "trade-off", "impact",
    "implication", "consequence", "vs ", " versus ", "relationship between",
}


def classify(query: str) -> RouteDecision:
    q = query.lower().strip()

    visual_hit = any(tok in q for tok in _VISUAL_TOKENS)
    deep_hit = any(m in q for m in _DEEP_RESEARCH_MARKERS) or len(q.split()) > 32
    analytical_hit = any(m in q for m in _ANALYTICAL_MARKERS)

    if deep_hit:
        return RouteDecision(
            kind="deep_research",
            modalities=None,
            reason="long-form or synthesis verbs detected",
        )
    if visual_hit:
        mods = [Modality.IMAGE, Modality.VIDEO]
        if "video" in q or "deposition" in q or "timestamp" in q:
            mods = [Modality.VIDEO]
        return RouteDecision(kind="visual", modalities=mods, reason="visual keywords detected")
    if analytical_hit:
        return RouteDecision(kind="analytical", modalities=None, reason="analytical keywords detected")
    return RouteDecision(kind="factual", modalities=None, reason="default factual")


def explain(query: str) -> RouteDecision:
    d = classify(query)
    logger.debug("router: {!r} -> {}", query, d)
    return d
