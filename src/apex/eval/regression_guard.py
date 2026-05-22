"""RAGAS regression guard.

Compares the latest eval run against ``data/eval_baseline.json`` and exits
non-zero if any tracked metric dropped by more than ``threshold`` (default 5%).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from apex.logging_config import logger
from apex.settings import get_settings, load_yaml_config


def _load_baseline(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_run(results_dir: Path) -> dict | None:
    files = sorted(results_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None
    return json.loads(files[0].read_text(encoding="utf-8"))


def compare(latest: dict, baseline: dict, *, threshold: float, tracked: list[str]) -> dict:
    base_metrics = (
        baseline.get("metrics") if isinstance(baseline.get("metrics"), dict) else baseline
    )
    latest_metrics = latest.get("metrics", {})
    diffs = {}
    failures = []
    for name in tracked:
        b = float(base_metrics.get(name, 0.0))
        v = float(latest_metrics.get(name, 0.0))
        delta = v - b
        diffs[name] = {"baseline": b, "latest": v, "delta": delta}
        if b > 0 and delta < -threshold:
            failures.append(name)
    return {"diffs": diffs, "failures": failures}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", default=None)
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument("--results-dir", default=None)
    args = parser.parse_args()

    settings = get_settings()
    eval_cfg = load_yaml_config("eval")
    baseline_path = Path(
        args.baseline
        or eval_cfg.get("dataset", {}).get("baseline_path", settings.eval_baseline_path)
    )
    threshold = float(
        args.threshold
        or eval_cfg.get("regression", {}).get("threshold", settings.eval_regression_threshold)
    )
    tracked = eval_cfg.get("regression", {}).get(
        "tracked_metrics", ["faithfulness", "context_recall", "answer_relevance"]
    )
    results_dir = Path(
        args.results_dir or eval_cfg.get("dataset", {}).get("results_dir", "data/eval_runs")
    )

    baseline = _load_baseline(baseline_path)
    latest = _latest_run(results_dir)
    if latest is None:
        logger.warning("no latest eval run found in {}; stub success", results_dir)
        return 0
    if not baseline:
        logger.warning("no baseline at {}; recording latest as baseline", baseline_path)
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(
            json.dumps({"metrics": latest.get("metrics", {})}, indent=2), encoding="utf-8"
        )
        return 0

    report = compare(latest, baseline, threshold=threshold, tracked=tracked)
    for name, d in report["diffs"].items():
        logger.info(
            "{:<22} baseline={:.4f} latest={:.4f} delta={:+.4f}",
            name,
            d["baseline"],
            d["latest"],
            d["delta"],
        )
    if report["failures"]:
        logger.error("regression guard FAILED on: {}", ", ".join(report["failures"]))
        return 1
    logger.info("regression guard passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
