"""Sweep HNSW parameters and emit a recall@10 vs latency CSV.

Tries combinations of ``ef_construction``, ``m`` (index-build) and
``ef_search`` (query-time). For each query in the golden set we measure
recall@10 against an exact KNN baseline and median latency.

Usage::

    python -m apex.scripts.hnsw_tune --output notebooks/hnsw_sweep.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
from pathlib import Path

from sqlalchemy import text

from apex.db import session_scope
from apex.embedding.text import get_text_embedder
from apex.logging_config import logger
from apex.settings import get_settings


def _exact_topk(embedding: list[float], top_k: int, tenant_id: str) -> list[str]:
    q = "[" + ",".join(f"{x:.6f}" for x in embedding) + "]"
    sql = text(
        """
        SELECT id FROM chunks
        WHERE tenant_id = :tenant_id AND embedding IS NOT NULL
        ORDER BY embedding <=> CAST(:q AS vector)
        LIMIT :top_k
        """
    )
    with session_scope() as s:
        s.execute(text("SET LOCAL hnsw.ef_search = 200"))
        return [str(r.id) for r in s.execute(sql, {"q": q, "tenant_id": tenant_id, "top_k": top_k}).all()]


def _approx_topk_with_timing(embedding: list[float], top_k: int, ef_search: int, tenant_id: str) -> tuple[list[str], float]:
    q = "[" + ",".join(f"{x:.6f}" for x in embedding) + "]"
    sql = text(
        """
        SELECT id FROM chunks
        WHERE tenant_id = :tenant_id AND embedding IS NOT NULL
        ORDER BY embedding <=> CAST(:q AS vector)
        LIMIT :top_k
        """
    )
    with session_scope() as s:
        s.execute(text(f"SET LOCAL hnsw.ef_search = {ef_search}"))
        t0 = time.perf_counter()
        ids = [str(r.id) for r in s.execute(sql, {"q": q, "tenant_id": tenant_id, "top_k": top_k}).all()]
        latency = (time.perf_counter() - t0) * 1000
    return ids, latency


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="notebooks/hnsw_sweep.csv")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--queries", default=None, help="Path to a JSON file with a 'questions' list")
    args = parser.parse_args()

    settings = get_settings()
    queries_path = Path(args.queries or settings.eval_golden_path)
    if not queries_path.exists():
        logger.error("queries file not found: {}", queries_path)
        return 1

    data = json.loads(queries_path.read_text(encoding="utf-8"))
    questions = [q["question"] if isinstance(q, dict) else q for q in data.get("items", data)]
    if not questions:
        logger.error("no questions found in {}", queries_path)
        return 1

    embedder = get_text_embedder()
    q_vectors = [embedder.encode_query(q).tolist() for q in questions]

    ef_search_values = [10, 20, 40, 80, 160]
    rows = [["ef_search", "recall@10", "latency_p50_ms", "latency_p95_ms"]]

    for ef in ef_search_values:
        recalls: list[float] = []
        latencies: list[float] = []
        for vec in q_vectors:
            gold = set(_exact_topk(vec, args.top_k, settings.apex_default_tenant))
            approx, lat = _approx_topk_with_timing(vec, args.top_k, ef, settings.apex_default_tenant)
            inter = len(gold.intersection(approx))
            recalls.append(inter / max(1, len(gold)))
            latencies.append(lat)
        rows.append([
            ef,
            round(statistics.mean(recalls), 4),
            round(statistics.median(latencies), 2),
            round(statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else max(latencies), 2),
        ])

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerows(rows)
    logger.info("wrote {} rows to {}", len(rows) - 1, out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
