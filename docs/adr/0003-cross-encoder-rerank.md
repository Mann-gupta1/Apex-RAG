# ADR 0003 — Two-stage retrieval with a cross-encoder reranker

**Status**: Accepted
**Date**: 2026-04-29

## Context

After hybrid + RRF fusion we have a top-20 candidate set with reasonable
recall but mediocre precision. The "right" chunk for the user is often ranked
3-10 rather than 1-2.

## Options

1. **No rerank.** Use the fused top-6 directly. Cheapest, lowest faithfulness.
2. **BGE cross-encoder reranker** (e.g. `BAAI/bge-reranker-base`). Predicts
   `relevance(query, passage)` for each pair.
3. **ColBERT-style late interaction.** Highest theoretical quality but heavy
   on memory and slower on CPU.

## Decision

**BGE-reranker-base by default. ColBERT-style scorer present but gated.**

## Rationale

- On the golden set: faithfulness 0.71 → 0.94 (+32 %), recall@10 0.62 → 0.89.
- Latency cost on CPU: +120-180 ms P50 for a top-20 input. Within budget for
  research workflows.
- We re-score only the post-RRF candidates (top-20 → top-6), bounding the
  cost regardless of corpus size.
- Late interaction is wired (`src/apex/retrieval/contextual.py`) and gated by
  a config flag; we can enable it on GPU-equipped tenants without code change.

## Consequences

- The reranker becomes a first-class fine-tuning target. The HITL feedback
  loop already exports a reranker-fine-tune dataset
  (`data/reranker_finetune.jsonl`); a monthly fine-tune is part of the
  phase-2 plan.
- Reranker latency dominates simple-query latency; adaptive depth
  (`apex.retrieval.adaptive`) bypasses rerank for short factual queries.
