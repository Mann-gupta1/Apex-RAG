# ADR 0004 — LangGraph for agent orchestration (over LlamaIndex)

**Status**: Accepted
**Date**: 2026-05-03

## Context

The agent needs a small, explicit state machine: router → retrieve → rerank
→ generate → critique → (refine loop) → respond. We want streaming, easy
unit-testability, and human-in-the-loop pause points.

## Options considered

1. **LangGraph** (LangChain). Explicit graph with nodes and edges, built-in
   streaming, integrates with LangSmith / Phoenix tracing.
2. **LlamaIndex Workflows**. Newer; ergonomic decorator-based syntax; less
   community coverage at the time of decision.
3. **Plain Python state machine.** Maximum control, zero deps. We use it as
   the fallback when LangGraph is unavailable.

## Decision

**LangGraph as the canonical orchestration layer, with a plain-Python
fallback (`apex.agent.graph._run_loop`) for environments without it.**

## Rationale

- Graph is small enough (5-7 nodes) that LangGraph adds clarity without
  ceremony.
- We get streaming, checkpointing, and human-in-the-loop hooks essentially
  for free.
- LangSmith / Phoenix tracing integration is one line, which we exploit in
  `phoenix_setup.py`.
- LlamaIndex is excellent for retrieval, but we already own retrieval. The
  agent only needs orchestration.

## Consequences

- We hard-pin `langgraph` and `langchain-core` versions; we treat LangGraph
  as infrastructure not application code.
- A plain-Python parallel implementation lives in `_run_loop` so unit tests
  can run without the LangGraph import path.
