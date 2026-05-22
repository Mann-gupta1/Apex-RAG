"""Strawberry GraphQL schema for Apex RAG.

Exposes:
- ``query.search(query, modalities)`` → hybrid search.
- ``query.chunk(id)`` → single chunk fetch with provenance.
- ``mutation.submitFeedback(...)``
- ``subscription.chatStream(query)`` for streaming agent events.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from enum import Enum as PyEnum

import strawberry
from strawberry.fastapi import GraphQLRouter

from apex.api.audit import log_event
from apex.api.degraded import degraded_chat, llm_healthy
from apex.schemas import (
    ChatRequest,
    FeedbackRequest,
    SearchRequest,
)
from apex.schemas import (
    Modality as ApexModality,
)


@strawberry.enum
class Modality(PyEnum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"


@strawberry.type
class Provenance:
    source_uri: str
    modality: Modality
    page: int | None = None
    timestamp_start: float | None = None
    speaker: str | None = None


@strawberry.type
class Chunk:
    id: str
    modality: Modality
    content: str
    context_summary: str | None
    provenance: Provenance


@strawberry.type
class SearchResult:
    chunk: Chunk
    score: float
    fusion_rank: int | None


@strawberry.type
class SearchPayload:
    query: str
    rewritten_queries: list[str]
    results: list[SearchResult]
    latency_ms: int


@strawberry.type
class Citation:
    chunk_id: str
    source_uri: str
    modality: Modality
    quote: str | None
    page: int | None
    timestamp_start: float | None


@strawberry.type
class ChatPayload:
    answer: str
    citations: list[Citation]
    faithfulness: float | None
    latency_ms: int


def _retrieved_to_gql(r) -> SearchResult:
    return SearchResult(
        chunk=Chunk(
            id=r.chunk.id or "",
            modality=Modality(r.chunk.modality.value),
            content=r.chunk.content,
            context_summary=r.chunk.context_summary,
            provenance=Provenance(
                source_uri=r.chunk.provenance.source_uri,
                modality=Modality(r.chunk.provenance.modality.value),
                page=r.chunk.provenance.page,
                timestamp_start=r.chunk.provenance.timestamp_start,
                speaker=r.chunk.provenance.speaker,
            ),
        ),
        score=r.score,
        fusion_rank=r.fusion_rank,
    )


@strawberry.type
class Query:
    @strawberry.field
    async def search(
        self,
        query: str,
        tenant_id: str = "default",
        modalities: list[Modality] | None = None,
        top_k: int = 6,
    ) -> SearchPayload:
        from apex.retrieval.pipeline import run_search

        mods = [ApexModality(m.value) for m in modalities] if modalities else None
        req = SearchRequest(query=query, tenant_id=tenant_id, modalities=mods, top_k=top_k)
        resp = await asyncio.to_thread(run_search, req)
        log_event(
            tenant_id=tenant_id,
            action="gql_search",
            request=req.model_dump(),
            response_summary={"n_results": len(resp.results)},
            source_chunk_ids=[r.chunk.id for r in resp.results if r.chunk.id],
            latency_ms=resp.latency_ms,
        )
        return SearchPayload(
            query=resp.query,
            rewritten_queries=resp.rewritten_queries,
            results=[_retrieved_to_gql(r) for r in resp.results],
            latency_ms=resp.latency_ms,
        )

    @strawberry.field
    async def chunk(self, id: str, tenant_id: str = "default") -> Chunk | None:
        from apex.retrieval.store_factory import get_vector_store

        hit = await asyncio.to_thread(get_vector_store().get_chunk, id, tenant_id=tenant_id)
        if not hit:
            return None
        return Chunk(
            id=hit.chunk_id,
            modality=Modality(hit.modality.value),
            content=hit.content,
            context_summary=hit.context_summary,
            provenance=Provenance(
                source_uri=hit.provenance.source_uri,
                modality=Modality(hit.provenance.modality.value),
                page=hit.provenance.page,
                timestamp_start=hit.provenance.timestamp_start,
                speaker=hit.provenance.speaker,
            ),
        )


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def submit_feedback(
        self,
        query: str,
        response: str,
        chunk_ids: list[str],
        rating: int,
        comment: str | None = None,
        tenant_id: str = "default",
    ) -> bool:
        from apex.feedback.human_loop import record_feedback

        await asyncio.to_thread(
            record_feedback,
            FeedbackRequest(
                tenant_id=tenant_id,
                query=query,
                response=response,
                chunk_ids=chunk_ids,
                rating=max(-1, min(1, rating)),
                comment=comment,
            ),
        )
        return True


@strawberry.type
class Subscription:
    @strawberry.subscription
    async def chat_stream(self, query: str, tenant_id: str = "default") -> AsyncIterator[str]:
        from apex.agent.graph import stream_agent
        from apex.retrieval.pipeline import run_search

        req = ChatRequest(query=query, tenant_id=tenant_id)

        if not llm_healthy():
            search_resp = await asyncio.to_thread(
                run_search, SearchRequest(query=query, tenant_id=tenant_id)
            )
            yield json.dumps(
                {
                    "event": "degraded",
                    "payload": degraded_chat(req, search_resp.results).model_dump(),
                }
            )
            return

        loop = asyncio.get_running_loop()
        it = iter(stream_agent(req))

        def _next():
            try:
                return next(it)
            except StopIteration:
                return None

        while True:
            ev = await loop.run_in_executor(None, _next)
            if ev is None:
                return
            yield json.dumps(ev)


schema = strawberry.Schema(query=Query, mutation=Mutation, subscription=Subscription)
graphql_app = GraphQLRouter(schema)
