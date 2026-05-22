"""BGE / sentence-transformers text embedder with batched, normalised output."""
from __future__ import annotations

from collections.abc import Iterable
from functools import lru_cache
from typing import TYPE_CHECKING

import numpy as np

from apex.logging_config import logger
from apex.settings import get_settings

if TYPE_CHECKING:  # avoid heavy import at module load
    from sentence_transformers import SentenceTransformer


class TextEmbedder:
    """Wraps a SentenceTransformer with sensible defaults for retrieval."""

    def __init__(self, model_name: str | None = None, *, normalize: bool = True, batch_size: int = 32) -> None:
        self.model_name = model_name or get_settings().text_embed_model
        self.normalize = normalize
        self.batch_size = batch_size
        self._model: SentenceTransformer | None = None

    def _ensure(self) -> SentenceTransformer:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError(
                    "sentence-transformers not installed. Install the [ingest] extra."
                ) from exc
            logger.info("loading text embedder {}", self.model_name)
            self._model = SentenceTransformer(self.model_name)
        return self._model

    @property
    def dim(self) -> int:
        return int(self._ensure().get_sentence_embedding_dimension())

    def encode(self, texts: Iterable[str]) -> np.ndarray:
        items = list(texts)
        if not items:
            return np.zeros((0, self.dim), dtype=np.float32)
        model = self._ensure()
        vectors = model.encode(
            items,
            batch_size=self.batch_size,
            normalize_embeddings=self.normalize,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vectors.astype(np.float32, copy=False)

    def encode_one(self, text: str) -> np.ndarray:
        return self.encode([text])[0]

    def encode_query(self, query: str) -> np.ndarray:
        """BGE recommends a `query:` prefix for queries; SBERT handles symmetrically."""
        prefix = "query: " if "bge" in self.model_name.lower() else ""
        return self.encode_one(prefix + query)


@lru_cache(maxsize=2)
def get_text_embedder(model_name: str | None = None) -> TextEmbedder:
    return TextEmbedder(model_name=model_name)
