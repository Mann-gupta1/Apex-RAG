# ADR 0002 — Hybrid fusion via Reciprocal Rank Fusion (RRF)

**Status**: Accepted
**Date**: 2026-04-24

## Context

We retrieve from multiple ranked lists per query:
- Dense (`embedding <=> q`)
- Sparse (`ts_rank_cd` over `tsvector`)
- Image-CLIP (when modality includes IMAGE/VIDEO)
- Multi-query expansion (HyDE, step-back, multi-query)

Need a way to fuse these without trying to calibrate score scales.

## Options

1. **Score-normalised weighted sum.** Fragile — scores from cosine and
   `ts_rank_cd` are not comparable; we'd have to learn weights per corpus.
2. **Learn-to-rank with a tiny MLP.** Powerful but requires labelled data we
   don't have yet.
3. **Reciprocal Rank Fusion.** Parameter-light (one constant `k`), known to
   beat raw weighted score fusion in many benchmarks (Cormack 2009).

## Decision

**RRF with `k = 60` (Cormack default).** Final order is by Σ over lists of
`1 / (k + rank)`.

## Rationale

- One hyperparameter; safe to leave at default.
- Tolerates incomparable score scales (cosine vs BM25 vs CLIP).
- Cheap to compute in Python; runs after parallel SQL queries.
- We can layer a learned reranker on top (cross-encoder) for orthogonal gains.

## Consequences

- We won't capture absolute confidence from any single ranker. If a downstream
  component (e.g. the agent's "skip context" heuristic) needs raw confidence,
  it should look at `rerank_score`, not the fused score.
- Adding a new ranked list (e.g. multi-vector) is one line: append to
  `ranked_lists` and RRF handles it.
