"""PDF / text-document ingestion via ``unstructured`` with page-anchored provenance."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from apex.logging_config import logger
from apex.schemas import Chunk, Modality, Provenance


def _load_with_unstructured(path: Path) -> list[tuple[str, dict]]:
    """Returns a list of (text, metadata) per page-like element."""
    try:
        from unstructured.partition.auto import partition
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("unstructured not installed (need [ingest] extra)") from exc

    elements = partition(filename=str(path), strategy="fast")
    out: list[tuple[str, dict]] = []
    for el in elements:
        text = getattr(el, "text", None)
        if not text or not text.strip():
            continue
        meta = el.metadata.to_dict() if hasattr(el, "metadata") else {}
        out.append((text.strip(), meta))
    return out


def _load_plain_text(path: Path) -> list[tuple[str, dict]]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return [
        (t.strip(), {"page_number": i + 1}) for i, t in enumerate(text.split("\n\n")) if t.strip()
    ]


def load_document(path: Path) -> list[Chunk]:
    """Read a PDF / text / markdown / docx file into page-level (pre-chunking) Chunks.

    The chunker downstream is what splits these into final-sized chunks; here we
    only preserve page-anchored provenance.
    """
    path = Path(path)
    logger.info("ingest pdf/text: {}", path.name)
    if path.suffix.lower() in {".txt", ".md"}:
        elements = _load_plain_text(path)
    else:
        elements = _load_with_unstructured(path)

    chunks: list[Chunk] = []
    for text, meta in elements:
        page = meta.get("page_number")
        bbox = meta.get("coordinates", {}).get("points") if meta.get("coordinates") else None
        bbox_tuple: tuple[float, float, float, float] | None = None
        if bbox and len(bbox) >= 2:
            xs = [pt[0] for pt in bbox]
            ys = [pt[1] for pt in bbox]
            bbox_tuple = (float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys)))

        chunks.append(
            Chunk(
                modality=Modality.TEXT,
                content=text,
                provenance=Provenance(
                    source_uri=str(path),
                    modality=Modality.TEXT,
                    page=int(page) if page else None,
                    bbox=bbox_tuple,
                    extra={"category": meta.get("category")} if meta.get("category") else {},
                ),
            )
        )
    return chunks


def iter_documents(directory: Path) -> Iterable[Path]:
    exts = {".pdf", ".txt", ".md", ".docx", ".html", ".htm"}
    for p in directory.rglob("*"):
        if p.is_file() and p.suffix.lower() in exts:
            yield p
