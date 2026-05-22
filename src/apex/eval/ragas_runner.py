"""RAGAS evaluation runner.

Builds a Dataset of (question, ground_truth, contexts, answer) tuples by running
the configured retrieval + agent variant over the golden set, then computes
the metrics enumerated in ``config/eval.yaml``.

Falls back to a deterministic, lightweight scoring path when RAGAS itself is
not installed so the CI regression guard still has something to compare.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from apex.logging_config import logger
from apex.schemas import ChatRequest, EvalMetric, EvalRunSummary, SearchRequest
from apex.settings import get_settings, load_yaml_config


def _load_golden() -> list[dict[str, Any]]:
    path = Path(get_settings().eval_golden_path)
    if not path.exists():
        raise FileNotFoundError(f"golden set not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("items", data)


def _build_records(variant: str) -> list[dict[str, Any]]:
    from apex.retrieval.pipeline import run_search

    use_apex = variant.lower() == "apex"
    records: list[dict[str, Any]] = []
    golden = _load_golden()
    for item in golden:
        question = item["question"]
        gt = item.get("ground_truth", "")
        try:
            top_k = 6 if use_apex else 5
            sr = run_search(
                SearchRequest(
                    query=question,
                    top_k=top_k,
                    use_rerank=use_apex,
                    use_hyde=use_apex,
                    use_multi_query=use_apex,
                )
            )
            contexts = [r.chunk.content for r in sr.results]
            answer = ""
            if use_apex:
                try:
                    from apex.agent.graph import run_agent

                    answer = run_agent(ChatRequest(query=question)).answer
                except Exception as exc:
                    logger.debug("agent unavailable; using top context as answer: {}", exc)
                    answer = contexts[0] if contexts else ""
            else:
                answer = contexts[0] if contexts else ""
        except Exception as exc:
            logger.warning("record build failed for {!r}: {}", question, exc)
            contexts, answer = [], ""

        records.append(
            {
                "question": question,
                "ground_truth": gt,
                "contexts": contexts,
                "answer": answer,
                "expected_sources": item.get("expected_sources", []),
            }
        )
    return records


def _fallback_metrics(records: list[dict[str, Any]]) -> list[EvalMetric]:
    """Cheap deterministic substitutes for the RAGAS metrics."""
    n = max(1, len(records))
    faith = (
        sum(
            1
            for r in records
            if r["ground_truth"]
            and r["answer"]
            and any(tok in r["answer"].lower() for tok in r["ground_truth"].lower().split()[:5])
        )
        / n
    )
    recall = sum(1 for r in records if r["contexts"]) / n
    precision = (
        sum(
            1
            for r in records
            if r["contexts"] and r["ground_truth"][:30].lower() in " ".join(r["contexts"]).lower()
        )
        / n
    )
    relevance = sum(1 for r in records if r["answer"]) / n
    correctness = (faith + relevance) / 2
    return [
        EvalMetric(name="faithfulness", value=round(faith, 4)),
        EvalMetric(name="context_recall", value=round(recall, 4)),
        EvalMetric(name="context_precision", value=round(precision, 4)),
        EvalMetric(name="answer_relevance", value=round(relevance, 4)),
        EvalMetric(name="answer_correctness", value=round(correctness, 4)),
    ]


def _ragas_metrics(records: list[dict[str, Any]]) -> list[EvalMetric] | None:
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import (
            answer_correctness,
            answer_relevancy,
            context_precision,
            context_recall,
            faithfulness,
        )
    except Exception as exc:
        logger.warning("ragas/datasets not installed; using fallback metrics: {}", exc)
        return None

    if not records:
        return None

    ds = Dataset.from_list(
        [
            {
                "question": r["question"],
                "answer": r["answer"],
                "contexts": r["contexts"] or [""],
                "ground_truth": r["ground_truth"],
            }
            for r in records
        ]
    )
    try:
        result = evaluate(
            ds,
            metrics=[
                faithfulness,
                context_recall,
                context_precision,
                answer_relevancy,
                answer_correctness,
            ],
            raise_exceptions=False,
        )
        scores = result.to_pandas().mean(numeric_only=True).to_dict()
        return [EvalMetric(name=k, value=float(v)) for k, v in scores.items()]
    except Exception as exc:
        logger.warning("ragas evaluation failed: {}", exc)
        return None


def run_eval(variant: str = "apex") -> EvalRunSummary:
    started = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    records = _build_records(variant)
    metrics = _ragas_metrics(records) or _fallback_metrics(records)
    finished = datetime.now(timezone.utc)

    out_dir = Path(load_yaml_config("eval").get("dataset", {}).get("results_dir", "data/eval_runs"))
    out_dir.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex[:12]
    artefact = {
        "run_id": run_id,
        "variant": variant,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "metrics": {m.name: m.value for m in metrics},
        "n_records": len(records),
        "seconds": round(time.perf_counter() - t0, 2),
    }
    (out_dir / f"{run_id}.json").write_text(json.dumps(artefact, indent=2), encoding="utf-8")
    logger.info("eval done variant={} metrics={}", variant, artefact["metrics"])
    return EvalRunSummary(
        run_id=run_id, started_at=started, finished_at=finished, metrics=metrics, variant=variant
    )


if __name__ == "__main__":
    summary = run_eval()
    for m in summary.metrics:
        print(f"{m.name:<22} {m.value:.4f}")
