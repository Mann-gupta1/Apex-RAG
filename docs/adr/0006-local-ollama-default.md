# ADR 0006 — Local Ollama as the default LLM provider

**Status**: Accepted
**Date**: 2026-05-12

## Context

Two competing constraints:
- The client's data-residency rules forbid cloud LLM calls for sensitive
  matters.
- The portfolio narrative requires a "fully local + free" build for reviewers
  who don't have OpenAI / Anthropic credentials.

## Decision

**Default to Ollama (`llama3.1:8b-instruct-q4_K_M`) for generation, HyDE,
critique, and the deep-research planner. All access goes through one tiny
client (`apex.llm.ollama_client`).**

## Rationale

- Ollama is Docker-shippable; pulls the model on first boot via a one-shot
  init container.
- The 8B q4 quant runs at acceptable latency on CPU-only laptops (the smoke
  test takes ~6 s end-to-end per chat).
- Swapping models is one env var; the client uses no SDK-specific features.
- For non-sensitive tenants in production, switching to OpenAI is a one-file
  change (add `apex.llm.openai_client`, route by tenant).

## Consequences

- Quality ceiling is lower than GPT-4o. Mitigated by aggressive grounding
  (every claim cited; NLI critique; refine loop).
- HyDE quality is the most-affected step. We make HyDE optional per request.
- The eval harness uses Ollama as the RAGAS judge — we accept some judge
  noise; the regression guard runs against itself, so absolute scores matter
  less than deltas.
