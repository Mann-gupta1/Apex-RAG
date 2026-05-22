"""Query-distribution drift detector.

Pulls the last ``window_days`` of search queries from ``audit_log``, embeds
them, and runs a 1-D KS test on the per-dimension means against a reference
distribution computed at the time of the last baseline.

The output is a JSON report in ``data/eval_runs/drift/`` that the Eval tab
in the Next.js UI surfaces.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from sqlalchemy import text

from apex.db import session_scope
from apex.embedding.text import get_text_embedder
from apex.logging_config import logger
from apex.settings import get_settings, load_yaml_config


def _recent_queries(window_days: int, limit: int = 1000) -> list[str]:
    settings = get_settings()  # noqa: F841 (kept for symmetry / future tenant scoping)
    with session_scope() as s:
        rows = s.execute(
            text(
                """
                SELECT request->>'query' AS q
                FROM audit_log
                WHERE action IN ('search', 'chat', 'gql_search')
                  AND created_at > now() - (:days * INTERVAL '1 day')
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"days": window_days, "limit": limit},
        ).all()
    return [r.q for r in rows if r.q]


def _reference_corpus() -> list[str]:
    """Use the golden set as the reference distribution. Cheap and stable."""
    path = Path(get_settings().eval_golden_path)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [item["question"] for item in data.get("items", data)]


def _ks_test_per_dim(a: np.ndarray, b: np.ndarray) -> dict[str, float]:
    try:
        from scipy.stats import ks_2samp

        d_stats = []
        p_values = []
        for i in range(a.shape[1]):
            stat, p = ks_2samp(a[:, i], b[:, i])
            d_stats.append(float(stat))
            p_values.append(float(p))
        return {
            "ks_d_mean": float(np.mean(d_stats)),
            "ks_p_min": float(np.min(p_values)),
            "ks_p_median": float(np.median(p_values)),
        }
    except Exception as exc:
        logger.warning("scipy unavailable; using cosine-distance proxy: {}", exc)
        ca = a.mean(axis=0)
        cb = b.mean(axis=0)
        cos = float(ca @ cb / (np.linalg.norm(ca) * np.linalg.norm(cb) + 1e-9))
        return {"cosine_drift": 1.0 - cos}


def run_drift() -> dict[str, Any]:
    cfg = load_yaml_config("eval").get("drift", {})
    if not cfg.get("enabled", True):
        return {"enabled": False}
    window_days = int(cfg.get("window_days", 7))
    recent = _recent_queries(window_days)
    reference = _reference_corpus()
    if not recent or not reference:
        logger.warning(
            "drift: insufficient data (recent={}, reference={})", len(recent), len(reference)
        )
        return {"status": "insufficient_data", "recent": len(recent), "reference": len(reference)}

    embedder = get_text_embedder()
    a = embedder.encode(recent)
    b = embedder.encode(reference)
    stats = _ks_test_per_dim(a, b)

    out = Path("data/eval_runs/drift")
    out.mkdir(parents=True, exist_ok=True)
    report = {
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "window_days": window_days,
        "n_recent": len(recent),
        "n_reference": len(reference),
        "stats": stats,
        "threshold_p_value": cfg.get("ks_p_value_threshold", 0.05),
        "alert": (stats.get("ks_p_min", 1.0) < cfg.get("ks_p_value_threshold", 0.05))
        if "ks_p_min" in stats
        else (stats.get("cosine_drift", 0.0) > 0.2),
    }
    (out / f"drift_{int(datetime.now(timezone.utc).timestamp())}.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    logger.info("drift report: {}", report)
    return report


if __name__ == "__main__":
    run_drift()
