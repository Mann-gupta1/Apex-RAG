"""Top-level retrieval orchestrator.

This is the function the API and the agent both call. It encapsulates:

1. Adaptive plan selection (complexity → top_k, rerank flag).
2. Query rewriting (HyDE / step-back / multi-query).
3. Hybrid search per rewritten query.
4. RRF fusion across all per-query ranked lists.
5. Optional cross-encoder rerank of the fused list.
6. Optional ColBERT-style late-interaction rescoring (gated by config).
"""

from __future__ import annotations

import time

from apex.logging_config import logger
from apex.retrieval import adaptive
from apex.retrieval import contextual as late_interaction
from apex.retrieval.hybrid import hybrid_search, reciprocal_rank_fusion
from apex.retrieval.query_rewrite import expand
from apex.retrieval.rerank import get_reranker
from apex.retrieval.vector_store import RetrievalHit
from apex.schemas import Chunk, Modality, RetrievedChunk, SearchRequest, SearchResponse
from apex.settings import get_settings, load_yaml_config


def _hit_to_retrieved(hit: RetrievalHit, *, rank: int) -> RetrievedChunk:
    return RetrievedChunk(
        chunk=Chunk(
            id=hit.chunk_id,
            modality=hit.modality,
            content=hit.content,
            provenance=hit.provenance,
            context_summary=hit.context_summary,
        ),
        score=hit.score,
        fusion_rank=rank,
    )


def run_search(req: SearchRequest) -> SearchResponse:
    settings = get_settings()
    started = time.perf_counter()

    plan = adaptive.plan(req.query)
    use_rerank = (
        req.use_rerank
        if req.use_rerank is not None
        else (plan.use_rerank and settings.enable_reranker)
    )
    use_hyde = (
        req.use_hyde if req.use_hyde is not None else (plan.use_hyde and settings.enable_hyde)
    )
    final_top_k = req.top_k or plan.top_k

    queries = [req.query]
    if use_hyde or req.use_multi_query is None:
        queries = expand(req.query)
    if not use_hyde:
        queries = [req.query]

    modalities: list[Modality] | None = req.modalities or None

    ranked_lists: list[list[RetrievalHit]] = []
    cfg = load_yaml_config("retrieval").get("hybrid", {})
    per_query_top_k = max(final_top_k * 3, int(cfg.get("final_top_k", 20)))
    for q in queries:
        try:
            ranked_lists.append(
                hybrid_search(
                    q,
                    tenant_id=req.tenant_id,
                    modalities=modalities,
                    final_top_k=per_query_top_k,
                )
            )
        except Exception as exc:
            logger.warning("hybrid retrieval failed for {!r}: {}", q, exc)

    fused = reciprocal_rank_fusion(ranked_lists, top_k=max(final_top_k * 2, 20))

    if use_rerank and fused:
        try:
            fused = get_reranker().rerank(req.query, fused, top_k=final_top_k)
        except Exception as exc:
            logger.warning("rerank failed; using fused list: {}", exc)

    if late_interaction.is_enabled() and fused:
        try:
            fused = late_interaction.get_late_interaction_scorer().rerank(
                req.query, fused, top_k=final_top_k
            )
        except Exception as exc:
            logger.warning("late-interaction rescoring skipped: {}", exc)

    fused = fused[:final_top_k]
    latency_ms = int((time.perf_counter() - started) * 1000)
    return SearchResponse(
        query=req.query,
        rewritten_queries=[q for q in queries if q != req.query],
        results=[_hit_to_retrieved(h, rank=i) for i, h in enumerate(fused)],
        latency_ms=latency_ms,
    )
