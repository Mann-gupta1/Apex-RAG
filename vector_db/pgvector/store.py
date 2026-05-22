"""pgvector + PostgreSQL ``VectorStore`` driver.

Hybrid search is implemented as two SQL queries fused in Python by
``apex.retrieval.hybrid``:

* **Dense**:  ``ORDER BY embedding <=> :q`` (cosine distance), HNSW-indexed.
* **Sparse**: ``ts_rank_cd(content_tsv, plainto_tsquery(:q))`` as a BM25-equivalent.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from apex.db import session_scope
from apex.logging_config import logger
from apex.retrieval.vector_store import RetrievalHit
from apex.schemas import Chunk, Modality, Provenance


def _row_to_hit(row: Any, score: float) -> RetrievalHit:
    prov_raw = row.provenance if isinstance(row.provenance, dict) else json.loads(row.provenance or "{}")
    prov = Provenance(**{**prov_raw, "modality": Modality(row.modality), "source_uri": row.source_uri})
    return RetrievalHit(
        chunk_id=str(row.id),
        content=row.content,
        score=float(score),
        provenance=prov,
        modality=Modality(row.modality),
        context_summary=row.context_summary,
    )


def _vec_literal(vec: list[float]) -> str:
    """Format a python list as a pgvector literal."""
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


class PgVectorStore:
    """``VectorStore`` implementation backed by Postgres + pgvector."""

    def upsert(self, chunks: list[Chunk]) -> int:
        if not chunks:
            return 0
        rows: list[dict[str, Any]] = []
        for c in chunks:
            rows.append({
                "tenant_id": c.tenant_id,
                "modality": c.modality.value,
                "source_uri": c.provenance.source_uri,
                "content": c.content,
                "context_summary": c.context_summary,
                "provenance": json.dumps(c.provenance.model_dump(mode="json")),
                "embedding": _vec_literal(c.text_embedding) if c.text_embedding else None,
                "image_embedding": _vec_literal(c.image_embedding) if c.image_embedding else None,
            })

        stmt = text(
            """
            INSERT INTO chunks (tenant_id, modality, source_uri, content, context_summary,
                                provenance, embedding, image_embedding)
            VALUES (:tenant_id, :modality, :source_uri, :content, :context_summary,
                    CAST(:provenance AS jsonb),
                    CAST(:embedding AS vector), CAST(:image_embedding AS vector))
            """
        )
        with session_scope() as session:
            for r in rows:
                session.execute(stmt, r)
        logger.debug("pgvector upserted {} chunks", len(rows))
        return len(rows)

    def dense_search(
        self,
        embedding: list[float],
        *,
        tenant_id: str,
        modalities: list[Modality] | None = None,
        top_k: int = 50,
    ) -> list[RetrievalHit]:
        if not embedding:
            return []
        modality_filter = ""
        params: dict[str, Any] = {
            "tenant_id": tenant_id,
            "q": _vec_literal(embedding),
            "top_k": top_k,
        }
        if modalities:
            modality_filter = "AND modality = ANY(:modalities)"
            params["modalities"] = [m.value for m in modalities]

        sql = text(
            f"""
            SELECT id, modality, source_uri, content, context_summary, provenance,
                   1 - (embedding <=> CAST(:q AS vector)) AS sim
            FROM chunks
            WHERE tenant_id = :tenant_id AND embedding IS NOT NULL {modality_filter}
            ORDER BY embedding <=> CAST(:q AS vector)
            LIMIT :top_k
            """
        )
        with session_scope() as session:
            result = session.execute(sql, params).all()
        return [_row_to_hit(r, r.sim) for r in result]

    def dense_image_search(
        self,
        embedding: list[float],
        *,
        tenant_id: str,
        top_k: int = 50,
    ) -> list[RetrievalHit]:
        if not embedding:
            return []
        sql = text(
            """
            SELECT id, modality, source_uri, content, context_summary, provenance,
                   1 - (image_embedding <=> CAST(:q AS vector)) AS sim
            FROM chunks
            WHERE tenant_id = :tenant_id AND image_embedding IS NOT NULL
            ORDER BY image_embedding <=> CAST(:q AS vector)
            LIMIT :top_k
            """
        )
        with session_scope() as session:
            result = session.execute(
                sql,
                {"tenant_id": tenant_id, "q": _vec_literal(embedding), "top_k": top_k},
            ).all()
        return [_row_to_hit(r, r.sim) for r in result]

    def sparse_search(
        self,
        query: str,
        *,
        tenant_id: str,
        modalities: list[Modality] | None = None,
        top_k: int = 50,
    ) -> list[RetrievalHit]:
        modality_filter = ""
        params: dict[str, Any] = {"tenant_id": tenant_id, "q": query, "top_k": top_k}
        if modalities:
            modality_filter = "AND modality = ANY(:modalities)"
            params["modalities"] = [m.value for m in modalities]

        sql = text(
            f"""
            SELECT id, modality, source_uri, content, context_summary, provenance,
                   ts_rank_cd(content_tsv, plainto_tsquery('english', :q)) AS score
            FROM chunks
            WHERE tenant_id = :tenant_id
              AND content_tsv @@ plainto_tsquery('english', :q) {modality_filter}
            ORDER BY score DESC
            LIMIT :top_k
            """
        )
        with session_scope() as session:
            result = session.execute(sql, params).all()
        return [_row_to_hit(r, r.score) for r in result]

    def get_chunk(self, chunk_id: str, *, tenant_id: str) -> RetrievalHit | None:
        sql = text(
            """
            SELECT id, modality, source_uri, content, context_summary, provenance
            FROM chunks WHERE id = CAST(:cid AS uuid) AND tenant_id = :tenant_id
            """
        )
        with session_scope() as session:
            row = session.execute(sql, {"cid": chunk_id, "tenant_id": tenant_id}).first()
        if not row:
            return None
        return _row_to_hit(row, 1.0)

    def delete_by_tenant(self, tenant_id: str) -> int:
        sql = text("DELETE FROM chunks WHERE tenant_id = :tenant_id RETURNING id")
        with session_scope() as session:
            n = len(session.execute(sql, {"tenant_id": tenant_id}).all())
        return n

    def count(self, tenant_id: str | None = None) -> int:
        sql = text("SELECT COUNT(*) FROM chunks" + (" WHERE tenant_id = :tenant_id" if tenant_id else ""))
        params = {"tenant_id": tenant_id} if tenant_id else {}
        with session_scope() as session:
            return int(session.execute(sql, params).scalar() or 0)
