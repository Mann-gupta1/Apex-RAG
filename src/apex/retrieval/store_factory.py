"""Selects the configured ``VectorStore`` driver."""
from __future__ import annotations

from functools import lru_cache

from apex.logging_config import logger
from apex.retrieval.vector_store import VectorStore
from apex.settings import get_settings


@lru_cache(maxsize=1)
def get_vector_store() -> VectorStore:
    driver = get_settings().vector_store_driver.lower()
    if driver == "pgvector":
        from vector_db.pgvector.store import PgVectorStore

        logger.info("using pgvector vector store driver")
        return PgVectorStore()
    if driver == "weaviate":
        from vector_db.weaviate.store import WeaviateStore

        logger.info("using weaviate vector store driver")
        return WeaviateStore()
    raise ValueError(f"unsupported VECTOR_STORE_DRIVER={driver!r}; expected pgvector|weaviate")


def reset_store_cache() -> None:
    get_vector_store.cache_clear()
