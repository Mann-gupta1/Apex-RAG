"""Hybrid retrieval: dense + sparse (BM25-equivalent) fused via Reciprocal Rank Fusion.

RRF: ``score(d) = Σ_r 1 / (k + rank_r(d))``  where k defaults to 60.
This is a strong, parameter-light fusion and works whenever the two lists are
ranked but have incomparable score scales (which is exactly our case).
"""
from __future__ import annotations

from collections.abc import Iterable

from apex.embedding.text import get_text_embedder
from apex.logging_config import logger
from apex.retrieval.store_factory import get_vector_store
from apex.retrieval.vector_store import RetrievalHit
from apex.schemas import Modality
from apex.settings import load_yaml_config


def reciprocal_rank_fusion(
    ranked_lists: Iterable[list[RetrievalHit]],
    *,
    k: int = 60,
    top_k: int | None = None,
) -> list[RetrievalHit]:
    """Fuse multiple ranked lists into a single list ordered by RRF score."""
    score_by_id: dict[str, float] = {}
    hit_by_id: dict[str, RetrievalHit] = {}
    for ranked in ranked_lists:
        for rank, hit in enumerate(ranked):
            cid = hit.chunk_id
            score_by_id[cid] = score_by_id.get(cid, 0.0) + 1.0 / (k + rank + 1)
            hit_by_id.setdefault(cid, hit)
    fused = [
        RetrievalHit(
            chunk_id=cid,
            content=hit_by_id[cid].content,
            score=score,
            provenance=hit_by_id[cid].provenance,
            modality=hit_by_id[cid].modality,
            context_summary=hit_by_id[cid].context_summary,
        )
        for cid, score in score_by_id.items()
    ]
    fused.sort(key=lambda h: h.score, reverse=True)
    return fused[:top_k] if top_k else fused


def hybrid_search(
    query: str,
    *,
    tenant_id: str = "default",
    modalities: list[Modality] | None = None,
    dense_top_k: int | None = None,
    sparse_top_k: int | None = None,
    final_top_k: int | None = None,
    rrf_k: int | None = None,
) -> list[RetrievalHit]:
    """Run dense + sparse retrieval and fuse with RRF. Modality-aware."""
    cfg = load_yaml_config("retrieval").get("hybrid", {})
    dense_top_k = dense_top_k or int(cfg.get("dense_top_k", 50))
    sparse_top_k = sparse_top_k or int(cfg.get("sparse_top_k", 50))
    final_top_k = final_top_k or int(cfg.get("final_top_k", 20))
    rrf_k = rrf_k or int(cfg.get("rrf_k", 60))

    store = get_vector_store()
    embedder = get_text_embedder()

    embedding = embedder.encode_query(query).tolist()
    dense = store.dense_search(embedding, tenant_id=tenant_id, modalities=modalities, top_k=dense_top_k)
    sparse = store.sparse_search(query, tenant_id=tenant_id, modalities=modalities, top_k=sparse_top_k)

    image_results: list[RetrievalHit] = []
    if modalities and (Modality.IMAGE in modalities or Modality.VIDEO in modalities):
        try:
            from apex.embedding.image import get_image_embedder

            clip_vec = get_image_embedder().encode_text([query])[0].tolist()
            image_results = store.dense_image_search(clip_vec, tenant_id=tenant_id, top_k=dense_top_k)
        except Exception as exc:
            logger.debug("image-modality dense search skipped: {}", exc)

    logger.debug("hybrid: dense={} sparse={} image={}", len(dense), len(sparse), len(image_results))
    return reciprocal_rank_fusion([dense, sparse, image_results], k=rrf_k, top_k=final_top_k)
