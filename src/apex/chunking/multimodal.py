"""Modality-aware chunking.

- Text: sliding-window with token-approximate split. We approximate tokens as
  whitespace tokens (good enough for chunking; embedders will re-tokenise).
- Image: one chunk per image (loader-level).
- Video: one chunk per scene (loader-level).
- Audio: one chunk per utterance/segment (loader-level).

Optionally applies **Contextual Retrieval** (Anthropic 2024): a one-sentence
LLM-generated context summary is prepended to each text chunk before
embedding. The LLM call is gated by ``enable_contextual_retrieval`` so the
pipeline still runs without Ollama available.
"""
from __future__ import annotations

from collections.abc import Iterable

from apex.logging_config import logger
from apex.schemas import Chunk, Modality
from apex.settings import get_settings, load_yaml_config


def _sliding_window(text: str, chunk_size: int, overlap: int) -> list[str]:
    tokens = text.split()
    if not tokens:
        return []
    if len(tokens) <= chunk_size:
        return [text]
    out: list[str] = []
    step = max(1, chunk_size - overlap)
    for start in range(0, len(tokens), step):
        window = tokens[start : start + chunk_size]
        if not window:
            break
        out.append(" ".join(window))
        if start + chunk_size >= len(tokens):
            break
    return out


def _chunk_text(parent: Chunk, chunk_size: int, overlap: int) -> list[Chunk]:
    pieces = _sliding_window(parent.content, chunk_size, overlap)
    if len(pieces) <= 1:
        return [parent]
    return [
        Chunk(
            modality=parent.modality,
            content=piece,
            provenance=parent.provenance.model_copy(update={"extra": {**parent.provenance.extra, "chunk_index": i}}),
        )
        for i, piece in enumerate(pieces)
    ]


def chunk_documents(
    parent_chunks: Iterable[Chunk],
    *,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[Chunk]:
    """Apply modality-appropriate chunking. Non-text chunks pass through."""
    cfg = load_yaml_config("retrieval").get("chunking", {}).get("text", {})
    chunk_size = chunk_size or int(cfg.get("chunk_size", 512))
    overlap = overlap or int(cfg.get("chunk_overlap", 64))

    out: list[Chunk] = []
    for c in parent_chunks:
        if c.modality == Modality.TEXT:
            out.extend(_chunk_text(c, chunk_size, overlap))
        else:
            out.append(c)
    return out


def _contextual_prompt(doc_summary: str, chunk_text: str) -> str:
    return (
        "You are helping make a single text chunk searchable in a corpus.\n"
        "Document summary:\n"
        f"{doc_summary}\n\n"
        "Chunk content:\n"
        f"{chunk_text}\n\n"
        "Write ONE short sentence that situates this chunk in the document "
        "(who/what/when/why). Keep it under 25 words. Output only the sentence."
    )


def contextualize(chunks: list[Chunk], *, doc_summary: str | None = None) -> list[Chunk]:
    """Anthropic Contextual Retrieval: prepend a one-sentence context to each text chunk.

    Falls through (no-op) when the feature flag is off or Ollama is unreachable.
    """
    settings = get_settings()
    if not settings.enable_contextual_retrieval or not chunks:
        return chunks

    try:
        from apex.llm.ollama_client import generate
    except Exception as exc:
        logger.debug("contextualize: ollama client unavailable: {}", exc)
        return chunks

    summary = doc_summary or ((chunks[0].content[:240]).strip() + "...")
    out: list[Chunk] = []
    for c in chunks:
        if c.modality != Modality.TEXT:
            out.append(c)
            continue
        try:
            ctx = generate(_contextual_prompt(summary, c.content), max_tokens=80, temperature=0.0).strip()
            ctx = ctx.replace("\n", " ").strip()
        except Exception as exc:
            logger.debug("contextualize fallback for one chunk: {}", exc)
            ctx = ""
        out.append(c.model_copy(update={"context_summary": ctx}))
    return out
