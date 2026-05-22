"""NLI faithfulness scoring.

Splits the generated answer into individual claim-like sentences and, for each
claim, asks an NLI cross-encoder whether any retrieved passage entails it.
The final faithfulness is the mean entailment probability across claims.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

from apex.logging_config import logger
from apex.settings import get_settings

if TYPE_CHECKING:
    from sentence_transformers import CrossEncoder


_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _split_sentences(text: str) -> list[str]:
    sents = [s.strip() for s in _SENT_SPLIT.split(text.strip()) if s.strip()]
    return [s for s in sents if len(s.split()) >= 3]


@dataclass
class FaithfulnessResult:
    score: float
    per_claim: list[tuple[str, float, int | None]]  # (claim, prob, best_premise_idx)


class FaithfulnessScorer:
    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or get_settings().nli_model
        self._model: CrossEncoder | None = None

    def _ensure(self) -> CrossEncoder:
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError("sentence-transformers required for NLI scoring") from exc
            logger.info("loading NLI model {}", self.model_name)
            self._model = CrossEncoder(self.model_name)
        return self._model

    def score(self, answer: str, premises: Sequence[str]) -> FaithfulnessResult:
        claims = _split_sentences(answer)
        if not claims or not premises:
            return FaithfulnessResult(score=0.0, per_claim=[])
        model = self._ensure()
        results: list[tuple[str, float, int | None]] = []
        running = 0.0
        for claim in claims:
            pairs = [[p, claim] for p in premises]
            preds = model.predict(pairs, show_progress_bar=False)
            entail = []
            for row in preds:
                if hasattr(row, "__len__") and len(row) == 3:
                    entail.append(float(row[0]))  # convention: index 0 = entailment
                else:
                    entail.append(float(row))
            best = max(range(len(entail)), key=lambda i: entail[i])
            results.append((claim, float(entail[best]), best))
            running += entail[best]
        avg = running / len(claims)
        return FaithfulnessResult(score=avg, per_claim=results)


@lru_cache(maxsize=1)
def get_faithfulness_scorer() -> FaithfulnessScorer:
    return FaithfulnessScorer()


def faithfulness_score(answer: str, premises: Sequence[str]) -> float:
    try:
        return get_faithfulness_scorer().score(answer, premises).score
    except Exception as exc:
        logger.warning("faithfulness scoring failed: {}", exc)
        return 0.0
