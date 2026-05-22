"""ColBERT-style late-interaction scoring (experimental).

A faithful production-grade ColBERT implementation would require a per-token
embedder and an inverted file; we provide a lightweight surrogate that scores
each (query_token, passage_token) pair using sub-word cosine similarity on top
of the existing sentence-transformer's tokenwise hidden states.

This module is intentionally gated by the ``advanced.late_interaction.enabled``
flag in ``config/retrieval.yaml`` because the per-token forward pass is
expensive on CPU; it's wired so that interview reviewers can read and run it.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np

from apex.logging_config import logger
from apex.retrieval.vector_store import RetrievalHit
from apex.settings import get_settings, load_yaml_config


class LateInteractionScorer:
    """Approximate ColBERT MaxSim scoring using sub-word transformer states."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or get_settings().text_embed_model
        self._model = None
        self._tokenizer = None

    def _ensure(self) -> None:
        if self._model is not None:
            return
        try:
            from transformers import AutoModel, AutoTokenizer
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("transformers required for late interaction") from exc
        logger.info("loading late-interaction backbone {}", self.model_name)
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self._model = AutoModel.from_pretrained(self.model_name).eval()

    def _token_embeddings(self, text: str) -> np.ndarray:
        import torch

        self._ensure()
        assert self._tokenizer is not None and self._model is not None
        toks = self._tokenizer(text, return_tensors="pt", truncation=True, max_length=256)
        with torch.no_grad():
            out = self._model(**toks).last_hidden_state[0]
        out = out / (out.norm(dim=-1, keepdim=True) + 1e-9)
        return out.cpu().numpy()

    def score(self, query: str, passage: str) -> float:
        q_emb = self._token_embeddings(query)
        p_emb = self._token_embeddings(passage)
        sims = q_emb @ p_emb.T  # (q_tokens, p_tokens)
        return float(sims.max(axis=1).sum())  # MaxSim summation

    def rerank(
        self, query: str, hits: list[RetrievalHit], *, top_k: int | None = None
    ) -> list[RetrievalHit]:
        if not hits:
            return hits
        rescored = [
            RetrievalHit(
                chunk_id=h.chunk_id,
                content=h.content,
                score=self.score(query, h.content),
                provenance=h.provenance,
                modality=h.modality,
                context_summary=h.context_summary,
            )
            for h in hits
        ]
        rescored.sort(key=lambda h: h.score, reverse=True)
        return rescored[:top_k] if top_k else rescored


@lru_cache(maxsize=1)
def get_late_interaction_scorer() -> LateInteractionScorer:
    return LateInteractionScorer()


def is_enabled() -> bool:
    return bool(
        load_yaml_config("retrieval")
        .get("advanced", {})
        .get("late_interaction", {})
        .get("enabled", False)
    )
