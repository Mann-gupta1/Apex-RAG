"""Embedding quantization demo: float32 → int8 / binary with recall delta.

We embed the golden questions plus the contents of all currently-indexed
chunks (a sample), compute exact float32 top-k as the gold standard, then
score int8 and binary-quantised variants for memory + recall trade-offs.

Output:
* ``notebooks/quantization_report.csv`` — variant, memory_per_vec_bytes,
  recall_at_10
* prints a summary table at the end.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from apex.embedding.text import get_text_embedder
from apex.logging_config import logger
from apex.settings import get_settings


def quantize_int8(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    scale = np.max(np.abs(matrix), axis=1, keepdims=True) + 1e-9
    q = np.round(matrix / scale * 127).astype(np.int8)
    return q, scale


def dequantize_int8(q: np.ndarray, scale: np.ndarray) -> np.ndarray:
    return (q.astype(np.float32) / 127.0) * scale


def quantize_binary(matrix: np.ndarray) -> np.ndarray:
    return (matrix > 0).astype(np.uint8)


def _hamming(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.sum(a[:, None, :] != b[None, :, :], axis=-1)


def recall_at_k(gold: np.ndarray, candidate: np.ndarray, k: int = 10) -> float:
    overlaps = [len(set(gold[i, :k].tolist()) & set(candidate[i, :k].tolist())) for i in range(gold.shape[0])]
    return float(np.mean(overlaps) / k)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", default=None)
    parser.add_argument("--passages", default=None, help="JSON list of passages; defaults to golden answers")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--output", default="notebooks/quantization_report.csv")
    args = parser.parse_args()

    settings = get_settings()
    golden_path = Path(args.queries or settings.eval_golden_path)
    data = json.loads(golden_path.read_text(encoding="utf-8"))
    items = data.get("items", data)
    questions = [it["question"] for it in items]
    passages = (
        json.loads(Path(args.passages).read_text(encoding="utf-8"))
        if args.passages
        else [it["ground_truth"] for it in items if it.get("ground_truth")]
    )
    if not passages:
        logger.error("no passages to score")
        return 1

    embedder = get_text_embedder()
    q_vecs = embedder.encode(questions)
    p_vecs = embedder.encode(passages)

    sims = q_vecs @ p_vecs.T
    gold_ranks = np.argsort(-sims, axis=1)

    int8_q, scale_q = quantize_int8(q_vecs)
    int8_p, scale_p = quantize_int8(p_vecs)
    int8_sims = dequantize_int8(int8_q, scale_q) @ dequantize_int8(int8_p, scale_p).T
    int8_ranks = np.argsort(-int8_sims, axis=1)

    bin_q = quantize_binary(q_vecs)
    bin_p = quantize_binary(p_vecs)
    bin_sims = -_hamming(bin_q, bin_p).astype(np.float32)
    bin_ranks = np.argsort(-bin_sims, axis=1)

    rows = [
        ["variant", "memory_bytes_per_vec", "recall@10"],
        ["float32", int(q_vecs.shape[1] * 4), 1.0],
        ["int8", int(q_vecs.shape[1] * 1), recall_at_k(gold_ranks, int8_ranks, args.top_k)],
        ["binary", int(q_vecs.shape[1] / 8), recall_at_k(gold_ranks, bin_ranks, args.top_k)],
    ]
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)
    for r in rows:
        print(f"  {r[0]:<8}  mem={r[1]:>4} bytes/vec  recall@{args.top_k}={r[2]}")
    logger.info("quantization report written to {}", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
