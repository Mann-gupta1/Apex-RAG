"""Degraded-mode helpers.

When the generator LLM (Ollama) is unreachable we still want to return
something useful — namely the retrieved chunks with a "sources found,
generation unavailable" banner.
"""

from __future__ import annotations

from apex.llm.ollama_client import health as _ollama_health
from apex.safety.citation import extract_citations
from apex.schemas import ChatRequest, ChatResponse, RetrievedChunk


def llm_healthy() -> bool:
    return _ollama_health()


def degraded_chat(req: ChatRequest, retrieved: list[RetrievedChunk]) -> ChatResponse:
    bullets = []
    for h in retrieved[:5]:
        prov = h.chunk.provenance
        loc = ""
        if prov.page is not None:
            loc = f" (p. {prov.page})"
        elif prov.timestamp_start is not None:
            loc = f" (t={prov.timestamp_start:.1f}s)"
        bullets.append(f"- {prov.source_uri}{loc}: {h.chunk.content[:200].strip()}...")

    body = "Sources found, generation currently unavailable. Top matches:\n\n" + "\n".join(bullets)
    citations = extract_citations(body, retrieved)
    return ChatResponse(
        answer=body,
        citations=citations,
        faithfulness=None,
        latency_ms=0,
    )
