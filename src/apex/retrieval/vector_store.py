"""Pluggable VectorStore protocol.

Both the pgvector and Weaviate drivers implement this surface so the rest of
the codebase never depends on a specific backend.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from apex.schemas import Chunk, Modality, Provenance


@dataclass
class RetrievalHit:
    chunk_id: str
    content: str
    score: float
    provenance: Provenance
    modality: Modality
    context_summary: str | None = None


@runtime_checkable
class VectorStore(Protocol):
    """Common interface for vector storage drivers."""

    def upsert(self, chunks: list[Chunk]) -> int:
        """Insert/update chunks; returns the number written."""

    def dense_search(
        self,
        embedding: list[float],
        *,
        tenant_id: str,
        modalities: list[Modality] | None = None,
        top_k: int = 50,
    ) -> list[RetrievalHit]:
        """Dense vector similarity (cosine) over the text embedding."""

    def dense_image_search(
        self,
        embedding: list[float],
        *,
        tenant_id: str,
        top_k: int = 50,
    ) -> list[RetrievalHit]:
        """Dense similarity over the CLIP image-embedding column (image+video)."""

    def sparse_search(
        self,
        query: str,
        *,
        tenant_id: str,
        modalities: list[Modality] | None = None,
        top_k: int = 50,
    ) -> list[RetrievalHit]:
        """Lexical BM25-equivalent search."""

    def get_chunk(self, chunk_id: str, *, tenant_id: str) -> RetrievalHit | None: ...

    def delete_by_tenant(self, tenant_id: str) -> int: ...

    def count(self, tenant_id: str | None = None) -> int: ...
