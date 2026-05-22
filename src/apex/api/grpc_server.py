"""gRPC server.

The generated stubs (``apex_pb2``, ``apex_pb2_grpc``) are produced by
``make proto``. This module supports two modes:

* Stubs available → start a real grpcio server on ``GRPC_PORT``.
* Stubs missing → log a single warning and exit cleanly (the rest of the
  build still passes tests / imports without the generated code).
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import signal
from concurrent import futures

from apex.api.audit import log_event
from apex.logging_config import logger
from apex.settings import get_settings


def _try_import_stubs():
    try:
        from apex.api import apex_pb2, apex_pb2_grpc  # type: ignore

        return apex_pb2, apex_pb2_grpc
    except ImportError as exc:
        logger.warning("gRPC stubs missing — run `make proto`. Server will not start. {}", exc)
        return None, None


def _retrieved_to_pb(pb2, r):
    return pb2.RetrievedChunk(
        chunk=pb2.Chunk(
            id=r.chunk.id or "",
            modality=getattr(pb2, f"MODALITY_{r.chunk.modality.value.upper()}"),
            content=r.chunk.content,
            context_summary=r.chunk.context_summary or "",
            provenance=pb2.Provenance(
                source_uri=r.chunk.provenance.source_uri,
                modality=getattr(pb2, f"MODALITY_{r.chunk.provenance.modality.value.upper()}"),
                page=r.chunk.provenance.page or 0,
                timestamp_start=r.chunk.provenance.timestamp_start or 0.0,
                timestamp_end=r.chunk.provenance.timestamp_end or 0.0,
                speaker=r.chunk.provenance.speaker or "",
            ),
        ),
        score=float(r.score),
        fusion_rank=r.fusion_rank or 0,
    )


def _build_search_servicer(pb2, pb2_grpc):
    from apex.retrieval.pipeline import run_search
    from apex.schemas import Modality, SearchRequest

    class SearchServicer(pb2_grpc.SearchServiceServicer):
        def Search(self, request, context):
            mods = [Modality(m.lower().removeprefix("modality_")) for m in request.modalities or []]
            req = SearchRequest(
                query=request.query,
                tenant_id=request.tenant_id or "default",
                modalities=mods or None,
                top_k=request.top_k or 6,
            )
            resp = run_search(req)
            log_event(tenant_id=req.tenant_id, action="grpc_search", request=req.model_dump())
            for r in resp.results:
                yield _retrieved_to_pb(pb2, r)

    return SearchServicer()


def _build_rag_servicer(pb2, pb2_grpc):
    from apex.agent.graph import stream_agent
    from apex.schemas import ChatRequest

    class RAGServicer(pb2_grpc.RAGServiceServicer):
        def Chat(self, request_iterator, context):
            for turn in request_iterator:
                req = ChatRequest(query=turn.query, tenant_id=turn.tenant_id or "default")
                log_event(tenant_id=req.tenant_id, action="grpc_chat", request=req.model_dump())
                for ev in stream_agent(req):
                    yield pb2.ChatEvent(event=ev.get("event", "message"), payload=json.dumps(ev))

    return RAGServicer()


def _build_agent_servicer(pb2, pb2_grpc):
    from apex.agent.tools import TOOLS

    class AgentServicer(pb2_grpc.AgentServiceServicer):
        def Call(self, request, context):
            tool = TOOLS.get(request.tool)
            if tool is None:
                return pb2.ToolResponse(name=request.tool, ok=False, result_json="{}", error="unknown tool")
            args = json.loads(request.args_json or "{}")
            try:
                result = tool(**args)
                return pb2.ToolResponse(
                    name=result.name,
                    ok=result.ok,
                    result_json=json.dumps(result.result),
                    error=result.error or "",
                )
            except Exception as exc:
                return pb2.ToolResponse(name=request.tool, ok=False, result_json="{}", error=str(exc))

    return AgentServicer()


async def serve() -> None:
    pb2, pb2_grpc = _try_import_stubs()
    if pb2 is None or pb2_grpc is None:
        return

    import grpc

    settings = get_settings()
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=8))
    pb2_grpc.add_SearchServiceServicer_to_server(_build_search_servicer(pb2, pb2_grpc), server)
    pb2_grpc.add_RAGServiceServicer_to_server(_build_rag_servicer(pb2, pb2_grpc), server)
    pb2_grpc.add_AgentServiceServicer_to_server(_build_agent_servicer(pb2, pb2_grpc), server)

    address = f"{settings.api_host}:{settings.grpc_port}"
    server.add_insecure_port(address)
    await server.start()
    logger.info("gRPC server listening on {}", address)

    stop_event = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):  # Windows lacks add_signal_handler
            asyncio.get_running_loop().add_signal_handler(sig, stop_event.set)
    await stop_event.wait()
    await server.stop(grace=5.0)


def main() -> int:
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(serve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
