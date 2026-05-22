"""Thumbs up/down feedback recording + export pipelines.

Two downstream datasets are produced from the ``feedback`` table:

* ``data/reranker_finetune.jsonl`` — positive/negative chunk pairs per query
  for fine-tuning the cross-encoder reranker. Each line:
  ``{"query": ..., "positive": [...], "negative": [...]}``
* ``data/dpo_dataset.jsonl`` — chosen/rejected response pairs in DPO format:
  ``{"prompt": ..., "chosen": ..., "rejected": ...}``

These exports are deliberately idempotent and stream-friendly so they can be
run on a cron / nightly.
"""
from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

from apex.db import session_scope
from apex.logging_config import logger
from apex.schemas import FeedbackRequest


def record_feedback(req: FeedbackRequest) -> int:
    """Insert a feedback row. Returns the new id."""
    with session_scope() as s:
        row = s.execute(
            text(
                """
                INSERT INTO feedback (tenant_id, query, response, chunk_ids, rating, comment)
                VALUES (:tenant_id, :query, :response, CAST(:chunk_ids AS jsonb), :rating, :comment)
                RETURNING id
                """
            ),
            {
                "tenant_id": req.tenant_id,
                "query": req.query,
                "response": req.response,
                "chunk_ids": json.dumps(req.chunk_ids),
                "rating": req.rating,
                "comment": req.comment,
            },
        ).first()
    fid = int(row.id) if row else -1
    logger.info("feedback recorded id={} rating={} tenant={}", fid, req.rating, req.tenant_id)
    return fid


def _iter_feedback() -> Iterator[dict]:
    sql = text(
        """
        SELECT id, tenant_id, query, response, chunk_ids, rating, comment, created_at
        FROM feedback ORDER BY id ASC
        """
    )
    with session_scope() as s:
        for r in s.execute(sql).all():
            yield {
                "id": int(r.id),
                "tenant_id": r.tenant_id,
                "query": r.query,
                "response": r.response,
                "chunk_ids": r.chunk_ids if isinstance(r.chunk_ids, list) else json.loads(r.chunk_ids or "[]"),
                "rating": int(r.rating),
                "comment": r.comment,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }


def export_reranker_pairs(out_path: Path) -> int:
    """Group feedback by query; positives are chunks from up-voted responses,
    negatives are chunks from down-voted responses for the same query."""
    grouped: dict[str, dict[str, set[str]]] = defaultdict(lambda: {"positive": set(), "negative": set()})
    for row in _iter_feedback():
        bucket = "positive" if row["rating"] > 0 else ("negative" if row["rating"] < 0 else None)
        if bucket is None:
            continue
        for cid in row["chunk_ids"]:
            grouped[row["query"]][bucket].add(cid)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with out_path.open("w", encoding="utf-8") as fh:
        for query, buckets in grouped.items():
            if not buckets["positive"] and not buckets["negative"]:
                continue
            fh.write(
                json.dumps(
                    {
                        "query": query,
                        "positive": sorted(buckets["positive"]),
                        "negative": sorted(buckets["negative"]),
                    }
                )
                + "\n"
            )
            n += 1
    logger.info("reranker fine-tune dataset: {} queries -> {}", n, out_path)
    return n


def export_dpo_dataset(out_path: Path) -> int:
    """Build DPO chosen/rejected pairs by pairing up- and down-voted responses for the same query."""
    by_query: dict[str, dict[str, list[str]]] = defaultdict(lambda: {"chosen": [], "rejected": []})
    for row in _iter_feedback():
        if row["rating"] > 0:
            by_query[row["query"]]["chosen"].append(row["response"])
        elif row["rating"] < 0:
            by_query[row["query"]]["rejected"].append(row["response"])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with out_path.open("w", encoding="utf-8") as fh:
        for query, rs in by_query.items():
            for chosen in rs["chosen"]:
                for rejected in rs["rejected"]:
                    fh.write(json.dumps({"prompt": query, "chosen": chosen, "rejected": rejected}) + "\n")
                    n += 1
    logger.info("DPO dataset: {} pairs -> {}", n, out_path)
    return n


def export_datasets(reranker_out: Path | None = None, dpo_out: Path | None = None) -> dict[str, int]:
    rr = reranker_out or Path("data/reranker_finetune.jsonl")
    dpo = dpo_out or Path("data/dpo_dataset.jsonl")
    return {
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "reranker_pairs": export_reranker_pairs(rr),
        "dpo_pairs": export_dpo_dataset(dpo),
    }


if __name__ == "__main__":
    print(json.dumps(export_datasets(), indent=2))
