"""PII redaction with Microsoft Presidio.

Used at two points:

* **pre-ingest**: scrubs PII before content lands in the vector store.
* **pre-response**: scrubs PII from the generated answer before it leaves the API.

When Presidio is unavailable we fall back to a small set of regex patterns so
the safety story degrades gracefully.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

from apex.logging_config import logger
from apex.settings import get_settings

if TYPE_CHECKING:
    from presidio_analyzer import AnalyzerEngine
    from presidio_anonymizer import AnonymizerEngine


# Order matters — more-specific patterns first so PHONE doesn't swallow SSN etc.
_FALLBACK_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("CREDIT_CARD", re.compile(r"\b(?:\d[ -]*?){13,16}\b")),
    ("US_SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("EMAIL_ADDRESS", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("PHONE_NUMBER", re.compile(r"\+?\d[\d\s\-().]{7,}\d")),
]


@dataclass
class RedactionResult:
    text: str
    entities: list[dict]


@lru_cache(maxsize=1)
def _presidio_engines() -> tuple[AnalyzerEngine, AnonymizerEngine] | None:
    try:
        from presidio_analyzer import AnalyzerEngine
        from presidio_anonymizer import AnonymizerEngine
    except ImportError:  # pragma: no cover
        logger.debug("presidio not installed; using regex fallback")
        return None
    return AnalyzerEngine(), AnonymizerEngine()


def _redact_with_presidio(text: str) -> RedactionResult:
    engines = _presidio_engines()
    if engines is None:
        return _redact_with_regex(text)
    analyzer, anonymizer = engines
    try:
        results = analyzer.analyze(text=text, language="en")
        anonymized = anonymizer.anonymize(text=text, analyzer_results=results)
        return RedactionResult(
            text=anonymized.text,
            entities=[
                {"entity_type": r.entity_type, "start": r.start, "end": r.end, "score": r.score}
                for r in results
            ],
        )
    except Exception as exc:
        logger.warning("presidio analyze failed; falling back to regex: {}", exc)
        return _redact_with_regex(text)


def _redact_with_regex(text: str) -> RedactionResult:
    out = text
    entities: list[dict] = []
    for label, pat in _FALLBACK_PATTERNS:
        for m in pat.finditer(text):
            entities.append(
                {"entity_type": label, "start": m.start(), "end": m.end(), "score": 0.5}
            )
        out = pat.sub(f"<{label}>", out)
    return RedactionResult(text=out, entities=entities)


def redact(text: str) -> RedactionResult:
    if not get_settings().enable_pii_redaction or not text:
        return RedactionResult(text=text, entities=[])
    return _redact_with_presidio(text)
