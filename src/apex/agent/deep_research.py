"""Iterative deep-research agent.

Workflow:
    1. plan: LLM decomposes the query into N sub-questions.
    2. iterate: for each open sub-question, retrieve + summarise.
    3. gap-finder: LLM proposes the next sub-question, or DONE.
    4. synthesise: LLM writes the structured memo with [#] citations.
"""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from apex.agent.prompts import (
    DEEP_RESEARCH_GAP_PROMPT,
    DEEP_RESEARCH_PLAN_PROMPT,
    DEEP_RESEARCH_SYNTHESIS_PROMPT,
)
from apex.llm.ollama_client import generate
from apex.logging_config import logger
from apex.retrieval.pipeline import run_search
from apex.schemas import RetrievedChunk, SearchRequest


@dataclass
class ResearchNote:
    sub_question: str
    chunks: list[RetrievedChunk] = field(default_factory=list)
    summary: str = ""


@dataclass
class ResearchReport:
    query: str
    notes: list[ResearchNote]
    memo: str
    citations: list[str]


def _plan(query: str) -> list[str]:
    raw = generate(DEEP_RESEARCH_PLAN_PROMPT.format(query=query), max_tokens=320, temperature=0.2)
    return [line.strip("-* \t") for line in raw.splitlines() if line.strip()][:8]


def _summarise(question: str, chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return ""
    context = "\n".join(f"[{i+1}] {c.chunk.content[:600]}" for i, c in enumerate(chunks[:5]))
    prompt = (
        f"Summarise what the following context tells us about: {question}\n\n"
        f"Context:\n{context}\n\nSummary (3 sentences, cite with [#]):"
    )
    return generate(prompt, max_tokens=220, temperature=0.1).strip()


def _gap(query: str, notes: list[ResearchNote]) -> str:
    answered = "\n".join(f"- {n.sub_question}" for n in notes if n.summary)
    evidence = "\n".join(f"- {n.summary}" for n in notes if n.summary)
    raw = generate(
        DEEP_RESEARCH_GAP_PROMPT.format(query=query, answered=answered, evidence=evidence),
        max_tokens=80,
        temperature=0.2,
    )
    return raw.strip().splitlines()[0] if raw else "DONE"


def _synthesise(query: str, notes: list[ResearchNote]) -> str:
    evidence_blocks: list[str] = []
    counter = 1
    for n in notes:
        for c in n.chunks[:3]:
            evidence_blocks.append(f"[{counter}] ({c.chunk.provenance.source_uri}) {c.chunk.content[:400]}")
            counter += 1
    evidence = "\n".join(evidence_blocks) or "(no evidence collected)"
    return generate(
        DEEP_RESEARCH_SYNTHESIS_PROMPT.format(query=query, evidence=evidence),
        max_tokens=800,
        temperature=0.2,
    ).strip()


def deep_research(
    query: str,
    *,
    tenant_id: str = "default",
    max_iterations: int = 6,
    per_query_top_k: int = 6,
) -> ResearchReport:
    logger.info("deep_research start: {!r}", query)
    sub_questions = _plan(query)
    notes: list[ResearchNote] = []

    for sub in sub_questions:
        results = run_search(SearchRequest(query=sub, tenant_id=tenant_id, top_k=per_query_top_k))
        summary = _summarise(sub, results.results)
        notes.append(ResearchNote(sub_question=sub, chunks=results.results, summary=summary))

    for _ in range(max_iterations):
        nxt = _gap(query, notes)
        if not nxt or nxt.upper().startswith("DONE"):
            break
        results = run_search(SearchRequest(query=nxt, tenant_id=tenant_id, top_k=per_query_top_k))
        summary = _summarise(nxt, results.results)
        notes.append(ResearchNote(sub_question=nxt, chunks=results.results, summary=summary))

    memo = _synthesise(query, notes)
    citations = []
    for n in notes:
        for c in n.chunks[:3]:
            citations.append(c.chunk.provenance.source_uri)
    return ResearchReport(query=query, notes=notes, memo=memo, citations=list(dict.fromkeys(citations)))


def stream_deep_research(query: str, *, tenant_id: str = "default") -> Iterator[dict]:
    """Yield progress events for SSE streaming."""
    yield {"event": "plan_start", "query": query}
    plan = _plan(query)
    yield {"event": "plan", "subquestions": plan}
    notes: list[ResearchNote] = []
    for sub in plan:
        yield {"event": "retrieve_start", "subquestion": sub}
        results = run_search(SearchRequest(query=sub, tenant_id=tenant_id, top_k=6))
        notes.append(
            ResearchNote(sub_question=sub, chunks=results.results, summary=_summarise(sub, results.results))
        )
        yield {"event": "subquestion_done", "subquestion": sub, "n_chunks": len(results.results)}
    yield {"event": "synthesise_start"}
    memo = _synthesise(query, notes)
    yield {"event": "memo", "memo": memo}
