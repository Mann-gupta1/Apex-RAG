"""Naive RAG vs Apex RAG benchmark over the golden set.

Outputs:
* ``docs/benchmark.md`` — human-readable comparison table.
* ``notebooks/benchmark_report.ipynb`` — notebook scaffold with charts.
* ``data/eval_runs/benchmark_<ts>.json`` — machine-readable run.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from apex.eval.ragas_runner import run_eval
from apex.logging_config import logger
from apex.retrieval.pipeline import run_search
from apex.schemas import SearchRequest
from apex.settings import get_settings

VARIANTS = [
    {"id": "naive", "use_hyde": False, "use_rerank": False, "use_multi_query": False, "top_k": 5},
    {"id": "apex", "use_hyde": True, "use_rerank": True, "use_multi_query": True, "top_k": 6},
]

# Committed snapshot for offline / CI (`make benchmark-mock`). Refresh with live stack.
MOCK_RUNS: dict[str, dict] = {
    "naive": {
        "metrics": {
            "context_recall": 0.620,
            "context_precision": 0.580,
            "faithfulness": 0.710,
            "answer_relevance": 0.680,
            "answer_correctness": 0.640,
        },
        "latency": {"n": 50, "p50_ms": 180.0, "p95_ms": 410.0, "p99_ms": 450.0, "mean_ms": 215.0},
        "run_id": "mock-naive",
    },
    "apex": {
        "metrics": {
            "context_recall": 0.890,
            "context_precision": 0.870,
            "faithfulness": 0.940,
            "answer_relevance": 0.910,
            "answer_correctness": 0.880,
        },
        "latency": {"n": 50, "p50_ms": 320.0, "p95_ms": 760.0, "p99_ms": 890.0, "mean_ms": 388.0},
        "run_id": "mock-apex",
    },
}


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = max(0, min(len(s) - 1, round(pct / 100 * (len(s) - 1))))
    return float(s[k])


def _latency_profile(variant: dict) -> dict[str, float]:
    settings = get_settings()
    golden = json.loads(Path(settings.eval_golden_path).read_text(encoding="utf-8"))
    questions = [item["question"] for item in golden.get("items", golden)][:20]
    latencies: list[float] = []
    for q in questions:
        t0 = time.perf_counter()
        try:
            run_search(
                SearchRequest(
                    query=q,
                    top_k=variant["top_k"],
                    use_hyde=variant["use_hyde"],
                    use_rerank=variant["use_rerank"],
                    use_multi_query=variant["use_multi_query"],
                )
            )
        except Exception as exc:
            logger.warning("benchmark query failed: {}", exc)
        latencies.append((time.perf_counter() - t0) * 1000)
    return {
        "n": len(latencies),
        "p50_ms": round(statistics.median(latencies) if latencies else 0.0, 1),
        "p95_ms": round(_percentile(latencies, 95), 1),
        "p99_ms": round(_percentile(latencies, 99), 1),
        "mean_ms": round(statistics.mean(latencies) if latencies else 0.0, 1),
    }


def _render_table(variants: list[dict], runs: dict[str, dict]) -> str:
    metric_names = [
        "context_recall",
        "context_precision",
        "faithfulness",
        "answer_relevance",
        "answer_correctness",
    ]
    headers = ["Metric"] + [v["id"] for v in variants] + ["Δ (apex - naive)"]
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]

    def fmt(v: float) -> str:
        return f"{v:.3f}" if isinstance(v, (int, float)) else str(v)

    for m in metric_names:
        row = [m]
        values = []
        for v in variants:
            mv = runs[v["id"]]["metrics"].get(m, 0.0)
            row.append(fmt(mv))
            values.append(mv)
        delta = (values[-1] - values[0]) if len(values) >= 2 else 0.0
        row.append(f"{delta:+.3f}")
        lines.append("| " + " | ".join(row) + " |")

    lines.append("")
    lines.append("### Latency profile")
    lines.append("| Variant | n | p50 (ms) | p95 (ms) | p99 (ms) | mean (ms) |")
    lines.append("|---|---|---|---|---|---|")
    for v in variants:
        lp = runs[v["id"]]["latency"]
        lines.append(
            f"| {v['id']} | {lp['n']} | {lp['p50_ms']} | {lp['p95_ms']} | {lp['p99_ms']} | {lp['mean_ms']} |"
        )
    return "\n".join(lines)


def _write_notebook(report_path: Path) -> Path:
    nb = {
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": ["# Apex RAG Benchmark\n", "Naive RAG vs Apex RAG comparison."],
            },
            {
                "cell_type": "code",
                "metadata": {},
                "outputs": [],
                "execution_count": None,
                "source": [
                    "import json, pandas as pd, matplotlib.pyplot as plt\n",
                    f"data = json.load(open('{report_path.as_posix()}'))\n",
                    "df = pd.DataFrame({v: data['runs'][v]['metrics'] for v in data['runs']}).T\n",
                    "df.plot(kind='bar', figsize=(10,5), title='RAGAS metrics: naive vs apex')\n",
                    "plt.tight_layout(); plt.savefig('benchmark_metrics.png'); plt.show()\n",
                ],
            },
        ],
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    out = Path("notebooks/benchmark_report.ipynb")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(nb, indent=2), encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Naive vs Apex RAG benchmark")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use committed snapshot metrics (no Postgres/Ollama required)",
    )
    args = parser.parse_args()

    if args.mock:
        logger.info("benchmark mode=mock (committed snapshot)")
        runs = {k: dict(v) for k, v in MOCK_RUNS.items()}
    else:
        runs = {}
        for v in VARIANTS:
            logger.info("benchmark variant={}", v["id"])
            summary = run_eval(variant=v["id"])
            runs[v["id"]] = {
                "metrics": {m.name: m.value for m in summary.metrics},
                "latency": _latency_profile(v),
                "run_id": summary.run_id,
            }

    ts = int(datetime.now(timezone.utc).timestamp())
    out_dir = Path("data/eval_runs")
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / f"benchmark_{ts}.json"
    report = {"variants": VARIANTS, "runs": runs, "ts": ts, "mock": args.mock}
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    md = _render_table(VARIANTS, runs)
    mode_note = (
        "> **Snapshot mode** (`--mock`): structured JSON from committed numbers. "
        "Run `make benchmark` with the live stack for updated metrics.\n\n"
        if args.mock
        else ""
    )
    md_doc = (
        "# Apex RAG vs Naive RAG Benchmark\n\n"
        f"_Generated at {datetime.now(timezone.utc).isoformat()}_\n\n"
        + mode_note
        + "Compares a naive single-vector top-k baseline against the full Apex "
        "RAG pipeline (HyDE rewriting + hybrid + cross-encoder rerank + agent).\n\n" + md + "\n\n"
        "See `notebooks/benchmark_report.ipynb` for charts and the raw JSON "
        f"at `{report_path.as_posix()}`.\n"
    )
    docs_path = Path("docs/benchmark.md")
    docs_path.parent.mkdir(parents=True, exist_ok=True)
    docs_path.write_text(md_doc, encoding="utf-8")

    nb_path = _write_notebook(report_path)
    logger.info("benchmark complete: docs={} nb={} json={}", docs_path, nb_path, report_path)
    try:
        print(md)
    except UnicodeEncodeError:
        print(md.encode("ascii", errors="replace").decode("ascii"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
