# Apex RAG vs Naive RAG Benchmark

_Generated at 2026-05-22T05:35:53.802892+00:00_

> **Snapshot mode** (`--mock`): structured JSON from committed numbers. Run `make benchmark` with the live stack for updated metrics.

Compares a naive single-vector top-k baseline against the full Apex RAG pipeline (HyDE rewriting + hybrid + cross-encoder rerank + agent).

| Metric | naive | apex | Δ (apex - naive) |
|---|---|---|---|
| context_recall | 0.620 | 0.890 | +0.270 |
| context_precision | 0.580 | 0.870 | +0.290 |
| faithfulness | 0.710 | 0.940 | +0.230 |
| answer_relevance | 0.680 | 0.910 | +0.230 |
| answer_correctness | 0.640 | 0.880 | +0.240 |

### Latency profile
| Variant | n | p50 (ms) | p95 (ms) | p99 (ms) | mean (ms) |
|---|---|---|---|---|---|
| naive | 50 | 180.0 | 410.0 | 450.0 | 215.0 |
| apex | 50 | 320.0 | 760.0 | 890.0 | 388.0 |

See `notebooks/benchmark_report.ipynb` for charts and the raw JSON at `data/eval_runs/benchmark_1779428153.json`.
