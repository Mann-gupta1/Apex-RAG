"""Weaviate OSS driver.

Mirrors ``PgVectorStore`` so callers can switch drivers via ``VECTOR_STORE_DRIVER``.
Falls back to a clear ``RuntimeError`` if the weaviate-client SDK is missing.
"""
from __future__ import annotations

import uuid
from typing import Any

from apex.logging_config import logger
from apex.retrieval.vector_store import RetrievalHit
from apex.schemas import Chunk, Modality, Provenance
from apex.settings import get_settings

_CLASS = "ApexChunk"


def _hit_from_obj(obj: Any, score: float) -> RetrievalHit:
    props = obj.properties if hasattr(obj, "properties") else obj
    prov_raw = props.get("provenance") or {}
    prov = Provenance(**{**prov_raw, "modality": Modality(props["modality"]), "source_uri": props["source_uri"]})
    return RetrievalHit(
        chunk_id=str(obj.uuid if hasattr(obj, "uuid") else props.get("id")),
        content=props["content"],
        score=float(score),
        provenance=prov,
        modality=Modality(props["modality"]),
        context_summary=props.get("context_summary"),
    )


class WeaviateStore:
    def __init__(self) -> None:
        try:
            import weaviate
            from weaviate.classes.config import Configure, Property, DataType
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("weaviate-client not installed (need [retrieval] extra)") from exc

        settings = get_settings()
        self._client = weaviate.connect_to_local(
            host=settings.weaviate_url.replace("http://", "").split(":")[0],
            port=int(settings.weaviate_url.split(":")[-1].rstrip("/")) or 8080,
        )
        if not self._client.collections.exists(_CLASS):
            logger.info("creating weaviate collection {}", _CLASS)
            self._client.collections.create(
                name=_CLASS,
                vectorizer_config=Configure.Vectorizer.none(),
                properties=[
                    Property(name="tenant_id", data_type=DataType.TEXT),
                    Property(name="modality", data_type=DataType.TEXT),
                    Property(name="source_uri", data_type=DataType.TEXT),
                    Property(name="content", data_type=DataType.TEXT),
                    Property(name="context_summary", data_type=DataType.TEXT),
                    Property(name="provenance", data_type=DataType.OBJECT, nested_properties=[]),
                ],
            )
        self._coll = self._client.collections.get(_CLASS)

    def upsert(self, chunks: list[Chunk]) -> int:
        if not chunks:
            return 0
        with self._coll.batch.dynamic() as batch:
            for c in chunks:
                vec = c.text_embedding or c.image_embedding
                batch.add_object(
                    properties={
                        "tenant_id": c.tenant_id,
                        "modality": c.modality.value,
                        "source_uri": c.provenance.source_uri,
                        "content": c.content,
                        "context_summary": c.context_summary,
                        "provenance": c.provenance.model_dump(mode="json"),
                    },
                    uuid=uuid.uuid4(),
                    vector=vec,
                )
        return len(chunks)

    def _filter(self, tenant_id: str, modalities: list[Modality] | None) -> Any:
        from weaviate.classes.query import Filter

        f = Filter.by_property("tenant_id").equal(tenant_id)
        if modalities:
            f = f & Filter.by_property("modality").contains_any([m.value for m in modalities])
        return f

    def dense_search(self, embedding, *, tenant_id, modalities=None, top_k=50):
        res = self._coll.query.near_vector(
            near_vector=embedding,
            filters=self._filter(tenant_id, modalities),
            limit=top_k,
            return_metadata=["distance"],
        )
        return [_hit_from_obj(o, 1.0 - (o.metadata.distance or 0.0)) for o in res.objects]

    def dense_image_search(self, embedding, *, tenant_id, top_k=50):
        return self.dense_search(embedding, tenant_id=tenant_id, modalities=None, top_k=top_k)

    def sparse_search(self, query, *, tenant_id, modalities=None, top_k=50):
        res = self._coll.query.bm25(
            query=query,
            filters=self._filter(tenant_id, modalities),
            limit=top_k,
            return_metadata=["score"],
        )
        return [_hit_from_obj(o, o.metadata.score or 0.0) for o in res.objects]

    def get_chunk(self, chunk_id, *, tenant_id):  # noqa: ARG002
        try:
            obj = self._coll.query.fetch_object_by_id(chunk_id)
            return _hit_from_obj(obj, 1.0) if obj else None
        except Exception:  # noqa: BLE001
            return None

    def delete_by_tenant(self, tenant_id):
        from weaviate.classes.query import Filter

        res = self._coll.data.delete_many(where=Filter.by_property("tenant_id").equal(tenant_id))
        return int(getattr(res, "successful", 0))

    def count(self, tenant_id=None):
        if tenant_id is None:
            return int(self._coll.aggregate.over_all(total_count=True).total_count or 0)
        from weaviate.classes.query import Filter

        return int(
            self._coll.aggregate.over_all(
                filters=Filter.by_property("tenant_id").equal(tenant_id),
                total_count=True,
            ).total_count
            or 0
        )
