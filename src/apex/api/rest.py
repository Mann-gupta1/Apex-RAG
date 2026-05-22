"""FastAPI REST + SSE endpoints."""
from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, UploadFile
from sse_starlette.sse import EventSourceResponse

from apex.api import dedup
from apex.api.audit import log_event
from apex.api.backpressure import QueueFull, queue
from apex.api.degraded import degraded_chat, llm_healthy
from apex.logging_config import logger
from apex.schemas import (
    ChatRequest,
    ChatResponse,
    FeedbackRequest,
    SearchRequest,
    SearchResponse,
)
from apex.settings import get_settings

router = APIRouter()


def _request_tenant(req: Request, payload_tenant: str | None) -> str:
    state_tenant = getattr(req.state, "tenant_id", None)
    return payload_tenant or state_tenant or get_settings().apex_default_tenant


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "llm_healthy": llm_healthy()}


@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest, http: Request) -> SearchResponse:
    from apex.retrieval.pipeline import run_search

    request.tenant_id = _request_tenant(http, request.tenant_id)
    started = time.perf_counter()
    resp = await asyncio.to_thread(run_search, request)
    log_event(
        tenant_id=request.tenant_id,
        action="search",
        request=request.model_dump(),
        response_summary={"n_results": len(resp.results), "rewrites": resp.rewritten_queries},
        source_chunk_ids=[r.chunk.id for r in resp.results if r.chunk.id],
        latency_ms=int((time.perf_counter() - started) * 1000),
    )
    return resp


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, http: Request) -> ChatResponse:
    from apex.agent.graph import run_agent
    from apex.retrieval.pipeline import run_search

    request.tenant_id = _request_tenant(http, request.tenant_id)
    started = time.perf_counter()

    payload = json.dumps({"q": request.query, "mods": [m.value for m in (request.modalities or [])]}, sort_keys=True)

    async def _factory():
        if not llm_healthy():
            search_resp = await asyncio.to_thread(
                run_search,
                SearchRequest(query=request.query, tenant_id=request.tenant_id, modalities=request.modalities),
            )
            return degraded_chat(request, search_resp.results)
        return await asyncio.to_thread(run_agent, request)

    resp = await dedup.coalesce(request.tenant_id, payload, _factory)
    log_event(
        tenant_id=request.tenant_id,
        action="chat",
        request=request.model_dump(),
        response_summary={"answer_len": len(resp.answer), "faithfulness": resp.faithfulness},
        source_chunk_ids=[c.chunk_id for c in resp.citations],
        latency_ms=int((time.perf_counter() - started) * 1000),
    )
    return resp


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest, http: Request) -> EventSourceResponse:
    from apex.agent.graph import stream_agent

    request.tenant_id = _request_tenant(http, request.tenant_id)
    started = time.perf_counter()

    async def event_gen() -> AsyncIterator[dict]:
        loop = asyncio.get_running_loop()
        it = iter(stream_agent(request))

        def _next():
            try:
                return next(it)
            except StopIteration:
                return None

        while True:
            ev = await loop.run_in_executor(None, _next)
            if ev is None:
                break
            yield {"event": ev.get("event", "message"), "data": json.dumps(ev)}

        log_event(
            tenant_id=request.tenant_id,
            action="chat_stream",
            request=request.model_dump(),
            latency_ms=int((time.perf_counter() - started) * 1000),
        )

    return EventSourceResponse(event_gen())


@router.post("/upload")
async def upload(
    http: Request,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    tenant_id: str | None = Form(None),
) -> dict:
    tenant_id = _request_tenant(http, tenant_id)
    settings = get_settings()
    upload_dir = settings.data_dir / "uploads" / tenant_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    target = upload_dir / Path(file.filename or "uploaded.bin").name
    content = await file.read()
    target.write_bytes(content)

    async def _ingest_job() -> None:
        from apex.ingest.pipeline import ingest_file

        await asyncio.to_thread(ingest_file, target, tenant_id=tenant_id)

    try:
        await queue.submit(_ingest_job)
    except QueueFull as exc:
        raise HTTPException(status_code=429, headers={"Retry-After": str(exc.retry_after_seconds)}) from exc

    log_event(tenant_id=tenant_id, action="upload", request={"filename": str(target.name), "bytes": len(content)})
    return {"status": "queued", "filename": target.name, "bytes": len(content), "tenant_id": tenant_id}


@router.post("/feedback")
async def feedback(req: FeedbackRequest, http: Request) -> dict:
    from apex.feedback.human_loop import record_feedback

    req.tenant_id = _request_tenant(http, req.tenant_id)
    record_feedback(req)
    log_event(tenant_id=req.tenant_id, action="feedback", request=req.model_dump())
    return {"status": "ok"}


@router.post("/eval")
async def trigger_eval(http: Request, variant: str = "apex") -> dict:
    from apex.eval.ragas_runner import run_eval

    tenant_id = _request_tenant(http, None)

    async def _job() -> None:
        await asyncio.to_thread(run_eval, variant=variant)

    try:
        await queue.submit(_job)
    except QueueFull as exc:
        raise HTTPException(status_code=429, headers={"Retry-After": str(exc.retry_after_seconds)}) from exc
    log_event(tenant_id=tenant_id, action="trigger_eval", request={"variant": variant})
    return {"status": "queued", "variant": variant}


@router.get("/metrics")
async def metrics() -> dict:
    return {"queue_size": queue.size, "queue_max": queue.max_size}


@router.get("/ready")
async def ready() -> dict:
    logger.debug("readiness probe")
    return {"ready": True}
