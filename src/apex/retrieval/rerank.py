"""Cross-encoder reranker (BGE-reranker by default).

Takes top-N hybrid results and re-scores them with a query+passage cross-encoder.
A monotonic relevance-aware score is appended (``rerank_score``) and used to
reorder the list.
"""
from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from apex.logging_config import logger
from apex.retrieval.vector_store import RetrievalHit
from apex.settings import get_settings, load_yaml_config

if TYPE_CHECKING:
    from sentence_transformers import CrossEncoder


class Reranker:
    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or get_settings().reranker_model
        self._model: CrossEncoder | None = None

    def _ensure(self) -> CrossEncoder:
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError("sentence-transformers not installed (need [ingest] extra)") from exc
            logger.info("loading reranker {}", self.model_name)
            self._model = CrossEncoder(self.model_name)
        return self._model

    def rerank(
        self,
        query: str,
        hits: list[RetrievalHit],
        *,
        top_k: int | None = None,
        batch_size: int | None = None,
    ) -> list[RetrievalHit]:
        if not hits:
            return hits
        cfg = load_yaml_config("retrieval").get("rerank", {})
        top_k = top_k or int(cfg.get("top_k_output", 6))
        batch_size = batch_size or int(cfg.get("batch_size", 16))
        try:
            model = self._ensure()
        except RuntimeError as exc:
            logger.warning("reranker unavailable: {}; passing through", exc)
            return hits[:top_k]

        pairs = [[query, h.content] for h in hits]
        scores = model.predict(pairs, batch_size=batch_size, show_progress_bar=False).tolist()
        reranked = [
            RetrievalHit(
                chunk_id=h.chunk_id,
                content=h.content,
                score=float(scores[i]),
                provenance=h.provenance,
                modality=h.modality,
                context_summary=h.context_summary,
            )
            for i, h in enumerate(hits)
        ]
        reranked.sort(key=lambda h: h.score, reverse=True)
        return reranked[:top_k]


@lru_cache(maxsize=1)
def get_reranker() -> Reranker:
    return Reranker()
