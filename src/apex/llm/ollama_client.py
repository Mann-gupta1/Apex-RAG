"""Thin Ollama HTTP client used for HyDE / step-back / agent generation.

We avoid hard-depending on the ``ollama`` python SDK so this module remains
importable when only ``httpx`` is installed. The SDK is used opportunistically
if it happens to be available; otherwise we hit the REST API directly.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from apex.logging_config import logger
from apex.settings import get_settings


def _endpoint(path: str) -> str:
    base = get_settings().ollama_host.rstrip("/")
    return f"{base}{path}"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=0.5, max=3), reraise=True)
def generate(
    prompt: str,
    *,
    model: str | None = None,
    system: str | None = None,
    max_tokens: int = 512,
    temperature: float = 0.2,
    stop: list[str] | None = None,
) -> str:
    settings = get_settings()
    model = model or settings.ollama_generation_model
    payload: dict = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": max_tokens, "temperature": temperature},
    }
    if system:
        payload["system"] = system
    if stop:
        payload["options"]["stop"] = stop

    timeout = httpx.Timeout(settings.ollama_timeout_seconds)
    with httpx.Client(timeout=timeout) as client:
        r = client.post(_endpoint("/api/generate"), json=payload)
        r.raise_for_status()
        data = r.json()
        return (data.get("response") or "").strip()


def stream(
    prompt: str,
    *,
    model: str | None = None,
    system: str | None = None,
    max_tokens: int = 512,
    temperature: float = 0.2,
) -> Iterator[str]:
    """Stream tokens from Ollama. Yields incremental text deltas."""
    settings = get_settings()
    model = model or settings.ollama_generation_model
    payload: dict = {
        "model": model,
        "prompt": prompt,
        "stream": True,
        "options": {"num_predict": max_tokens, "temperature": temperature},
    }
    if system:
        payload["system"] = system

    timeout = httpx.Timeout(settings.ollama_timeout_seconds)
    with (
        httpx.Client(timeout=timeout) as client,
        client.stream("POST", _endpoint("/api/generate"), json=payload) as r,
    ):
        r.raise_for_status()
        for line in r.iter_lines():
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            delta = obj.get("response", "")
            if delta:
                yield delta
            if obj.get("done"):
                break


def health() -> bool:
    try:
        with httpx.Client(timeout=2.0) as client:
            r = client.get(_endpoint("/api/tags"))
            return r.status_code == 200
    except Exception as exc:
        logger.debug("ollama health check failed: {}", exc)
        return False
