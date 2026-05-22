"""Unified ingestion pipeline.

`ingest_path(path)` dispatches by extension to the per-modality loader, applies
modality-aware chunking + contextual retrieval, computes embeddings, and
persists the result to the configured `VectorStore`.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from apex.chunking.multimodal import chunk_documents, contextualize
from apex.logging_config import logger
from apex.schemas import Chunk, IngestionResult, Modality
from apex.settings import get_settings

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff"}
TEXT_EXTS = {".pdf", ".txt", ".md", ".docx", ".html", ".htm"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac"}


def _detect_modality(path: Path) -> Modality | None:
    suf = path.suffix.lower()
    if suf in TEXT_EXTS:
        return Modality.TEXT
    if suf in IMAGE_EXTS:
        return Modality.IMAGE
    if suf in VIDEO_EXTS:
        return Modality.VIDEO
    if suf in AUDIO_EXTS:
        return Modality.AUDIO
    return None


def _load(path: Path, modality: Modality) -> list[Chunk]:
    if modality == Modality.TEXT:
        from apex.ingest.pdf import load_document

        return load_document(path)
    if modality == Modality.IMAGE:
        from apex.ingest.image import load_image

        return [load_image(path)]
    if modality == Modality.VIDEO:
        from apex.ingest.video import load_video

        return load_video(path)
    if modality == Modality.AUDIO:
        from apex.ingest.audio import load_audio

        return load_audio(path)
    raise ValueError(f"unsupported modality: {modality}")


def _embed(chunks: list[Chunk]) -> list[Chunk]:
    if not chunks:
        return chunks
    out: list[Chunk] = []

    text_items = [(i, c) for i, c in enumerate(chunks)]
    if text_items:
        try:
            from apex.embedding.text import get_text_embedder

            embedder = get_text_embedder()
            text_inputs = [
                (c.context_summary + " | " + c.content if c.context_summary else c.content)
                for _, c in text_items
            ]
            text_vecs = embedder.encode(text_inputs)
        except Exception as exc:
            logger.warning("text embedding skipped: {}", exc)
            text_vecs = np.zeros((len(text_items), 0), dtype=np.float32)
    else:
        text_vecs = np.zeros((0, 0), dtype=np.float32)

    image_indices: list[int] = []
    image_paths: list[str] = []
    for i, c in enumerate(chunks):
        if c.modality == Modality.IMAGE:
            image_indices.append(i)
            image_paths.append(c.provenance.source_uri)
        elif c.modality == Modality.VIDEO and c.provenance.extra.get("keyframe"):
            image_indices.append(i)
            image_paths.append(c.provenance.extra["keyframe"])

    if image_paths:
        try:
            from apex.embedding.image import get_image_embedder

            img_embedder = get_image_embedder()
            image_vecs = img_embedder.encode_paths(image_paths)
        except Exception as exc:
            logger.warning("image embedding skipped: {}", exc)
            image_vecs = np.zeros((0, 0), dtype=np.float32)
    else:
        image_vecs = np.zeros((0, 0), dtype=np.float32)

    for j, c in enumerate(chunks):
        text_vec = text_vecs[j].tolist() if text_vecs.size else None
        image_vec = None
        if j in image_indices and image_vecs.size:
            row = image_indices.index(j)
            image_vec = image_vecs[row].tolist() if row < image_vecs.shape[0] else None
        out.append(c.model_copy(update={"text_embedding": text_vec, "image_embedding": image_vec}))
    return out


def _store(chunks: Iterable[Chunk]) -> int:
    if not chunks:
        return 0
    try:
        from apex.retrieval.store_factory import get_vector_store

        store = get_vector_store()
        return store.upsert(list(chunks))
    except Exception as exc:
        logger.warning("vector store upsert skipped: {}", exc)
        return 0


def ingest_file(path: Path, *, tenant_id: str = "default") -> IngestionResult:
    settings = get_settings()
    path = Path(path)
    modality = _detect_modality(path)
    if modality is None:
        raise ValueError(f"unsupported file extension: {path.suffix}")

    job_id = str(uuid.uuid4())
    started = datetime.now(timezone.utc)
    logger.info("ingest start job={} path={} modality={}", job_id, path.name, modality.value)

    raw_chunks = _load(path, modality)
    for c in raw_chunks:
        c.tenant_id = tenant_id

    sized = chunk_documents(raw_chunks)
    contextual = contextualize(sized) if settings.enable_contextual_retrieval else sized
    embedded = _embed(contextual)
    n = _store(embedded) if embedded else 0

    logger.info(
        "ingest done job={} chunks={} elapsed={:.2f}s",
        job_id,
        n,
        (datetime.now(timezone.utc) - started).total_seconds(),
    )
    return IngestionResult(source_uri=str(path), modality=modality, chunks_created=n, job_id=job_id)


def ingest_path(
    source: Path,
    *,
    tenant_id: str = "default",
    modality: str | None = None,
) -> list[IngestionResult]:
    """Top-level entry: file or directory."""
    source = Path(source)
    targets: list[Path]
    if source.is_file():
        targets = [source]
    else:
        targets = [p for p in source.rglob("*") if p.is_file() and _detect_modality(p) is not None]
    results: list[IngestionResult] = []
    for p in targets:
        try:
            results.append(ingest_file(p, tenant_id=tenant_id))
        except Exception as exc:
            logger.error("ingest failed for {}: {}", p, exc)
    return results
