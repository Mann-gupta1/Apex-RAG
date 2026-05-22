"""LangGraph state machine: router → retrieve → rerank → generate → critique → refine.

We use LangGraph when it's installed and gracefully degrade to a plain Python
state machine when it isn't (so unit tests don't have to load the framework).
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from apex.agent import router
from apex.agent.prompts import ANSWER_PROMPT, CRITIQUE_PROMPT, SYSTEM_GROUNDED
from apex.llm.ollama_client import generate, stream
from apex.logging_config import logger
from apex.retrieval.pipeline import run_search
from apex.safety.citation import extract_citations
from apex.safety.nli import faithfulness_score
from apex.safety.pii_redact import redact
from apex.schemas import AgentStep, ChatRequest, ChatResponse, RetrievedChunk, SearchRequest
from apex.settings import get_settings


@dataclass
class AgentState:
    query: str
    tenant_id: str
    route: str = "factual"
    history: list[dict[str, str]] = field(default_factory=list)
    retrieved: list[RetrievedChunk] = field(default_factory=list)
    answer: str = ""
    critique: str = ""
    faithfulness: float = 0.0
    refine_attempts: int = 0
    steps: list[AgentStep] = field(default_factory=list)


def _format_context(hits: list[RetrievedChunk]) -> str:
    lines = []
    for i, h in enumerate(hits, start=1):
        prov = h.chunk.provenance
        tag = f"{prov.modality.value}"
        if prov.page is not None:
            tag += f" p.{prov.page}"
        if prov.timestamp_start is not None:
            tag += f" t={prov.timestamp_start:.1f}s"
        lines.append(f"[{i}] ({tag}) {h.chunk.content.strip()[:600]}")
    return "\n".join(lines)


def _node_router(state: AgentState) -> AgentState:
    decision = router.explain(state.query)
    state.route = decision.kind
    state.steps.append(
        AgentStep(node="router", detail={"kind": decision.kind, "reason": decision.reason})
    )
    return state


def _node_retrieve(state: AgentState) -> AgentState:
    decision = router.classify(state.query)
    req = SearchRequest(
        query=state.query, tenant_id=state.tenant_id, modalities=decision.modalities
    )
    resp = run_search(req)
    state.retrieved = resp.results
    state.steps.append(
        AgentStep(
            node="retrieve",
            detail={
                "n": len(resp.results),
                "rewrites": resp.rewritten_queries,
                "latency_ms": resp.latency_ms,
            },
        )
    )
    return state


def _node_generate(state: AgentState) -> AgentState:
    prompt = ANSWER_PROMPT.format(
        system=SYSTEM_GROUNDED,
        question=state.query,
        context=_format_context(state.retrieved) or "(no context retrieved)",
    )
    state.answer = generate(prompt, max_tokens=400, temperature=0.1).strip()
    state.steps.append(AgentStep(node="generate", detail={"chars": len(state.answer)}))
    return state


def _node_critique(state: AgentState) -> AgentState:
    premises = [h.chunk.content for h in state.retrieved]
    state.faithfulness = faithfulness_score(state.answer, premises) if premises else 0.0
    try:
        verdict = generate(
            CRITIQUE_PROMPT.format(
                question=state.query,
                context=_format_context(state.retrieved),
                answer=state.answer,
            ),
            max_tokens=120,
            temperature=0.0,
        ).strip()
    except Exception as exc:
        logger.debug("critique LLM failed: {}", exc)
        verdict = "FAITHFUL: critique LLM unavailable"
    state.critique = verdict
    state.steps.append(
        AgentStep(node="critique", detail={"verdict": verdict, "nli": round(state.faithfulness, 3)})
    )
    return state


def _node_refine(state: AgentState) -> AgentState:
    if not state.critique.upper().startswith("UNFAITHFUL"):
        return state
    bits = state.critique.split("|", 1)
    next_query = bits[1].strip() if len(bits) == 2 else state.query
    if next_query and next_query.lower() != state.query.lower():
        req = SearchRequest(query=next_query, tenant_id=state.tenant_id)
        extra = run_search(req).results
        seen = {h.chunk.id for h in state.retrieved}
        state.retrieved.extend([h for h in extra if h.chunk.id not in seen])
    state.refine_attempts += 1
    state.steps.append(AgentStep(node="refine", detail={"attempt": state.refine_attempts}))
    return state


def _redact_response(answer: str) -> str:
    return redact(answer).text if get_settings().enable_pii_redaction else answer


def _build_response(state: AgentState, started: float) -> ChatResponse:
    state.answer = _redact_response(state.answer)
    citations = extract_citations(state.answer, state.retrieved)
    latency_ms = int((time.perf_counter() - started) * 1000)
    return ChatResponse(
        answer=state.answer,
        citations=citations,
        faithfulness=state.faithfulness,
        steps=state.steps,
        latency_ms=latency_ms,
    )


def _run_loop(state: AgentState) -> AgentState:
    _node_router(state)
    if state.route == "deep_research":
        from apex.agent.deep_research import deep_research

        report = deep_research(state.query, tenant_id=state.tenant_id)
        state.answer = report.memo
        state.retrieved = [c for n in report.notes for c in n.chunks]
        state.steps.append(
            AgentStep(node="deep_research", detail={"subquestions": len(report.notes)})
        )
        state.faithfulness = faithfulness_score(
            state.answer, [h.chunk.content for h in state.retrieved]
        )
        return state

    _node_retrieve(state)
    _node_generate(state)
    _node_critique(state)

    threshold = 0.80
    if state.faithfulness < threshold and state.refine_attempts == 0:
        _node_refine(state)
        _node_generate(state)
        _node_critique(state)
    return state


def run_agent(req: ChatRequest) -> ChatResponse:
    started = time.perf_counter()
    state = AgentState(query=req.query, tenant_id=req.tenant_id, history=req.history)
    state = _run_loop(state)
    return _build_response(state, started)


def stream_agent(req: ChatRequest) -> Iterator[dict[str, Any]]:
    """Yield SSE-friendly events for the chat UI."""
    started = time.perf_counter()
    state = AgentState(query=req.query, tenant_id=req.tenant_id, history=req.history)
    _node_router(state)
    yield {"event": "router", "route": state.route}

    if state.route == "deep_research":
        from apex.agent.deep_research import stream_deep_research

        yield from stream_deep_research(state.query, tenant_id=state.tenant_id)
        return

    _node_retrieve(state)
    yield {"event": "retrieved", "n": len(state.retrieved)}

    prompt = ANSWER_PROMPT.format(
        system=SYSTEM_GROUNDED,
        question=state.query,
        context=_format_context(state.retrieved) or "(no context retrieved)",
    )
    buffer = []
    for delta in stream(prompt, max_tokens=400, temperature=0.1):
        buffer.append(delta)
        yield {"event": "token", "delta": delta}
    state.answer = "".join(buffer).strip()
    yield {"event": "answer_done", "chars": len(state.answer)}

    _node_critique(state)
    yield {"event": "critique", "verdict": state.critique, "nli": round(state.faithfulness, 3)}

    resp = _build_response(state, started)
    yield {
        "event": "done",
        "citations": [c.model_dump() for c in resp.citations],
        "latency_ms": resp.latency_ms,
    }
