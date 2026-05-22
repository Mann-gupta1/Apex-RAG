"""Image ingestion: EXIF + OCR (Tesseract) + thumbnail generation.

Produces a Chunk per image with the OCR'd text (if any) as ``content`` and the
image source path retained for downstream CLIP embedding.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from apex.logging_config import logger
from apex.schemas import Chunk, Modality, Provenance
from apex.settings import get_settings

THUMB_DIR = get_settings().root_dir / "data" / "processed_chunks" / "thumbs"
SUPPORTED = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff"}


def _ocr(image) -> str:
    try:
        import pytesseract
    except ImportError:  # pragma: no cover
        return ""
    try:
        return pytesseract.image_to_string(image).strip()
    except Exception as exc:
        logger.debug("OCR failed: {}", exc)
        return ""


def _exif(image) -> dict:
    try:
        raw = image.getexif()
        return {str(k): str(v) for k, v in raw.items() if v} if raw else {}
    except Exception:
        return {}


def _save_thumbnail(image, path: Path) -> Path:
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    thumb_path = THUMB_DIR / (path.stem + ".jpg")
    try:
        img = image.copy()
        img.thumbnail((512, 512))
        img.convert("RGB").save(thumb_path, "JPEG", quality=80)
    except Exception as exc:
        logger.warning("thumbnail failed for {}: {}", path.name, exc)
    return thumb_path


def load_image(path: Path) -> Chunk:
    from PIL import Image as PImage

    path = Path(path)
    logger.info("ingest image: {}", path.name)
    image = PImage.open(path).convert("RGB")
    ocr_text = _ocr(image)
    exif = _exif(image)
    thumb = _save_thumbnail(image, path)

    content = ocr_text if ocr_text else f"[image: {path.name}]"
    return Chunk(
        modality=Modality.IMAGE,
        content=content,
        provenance=Provenance(
            source_uri=str(path),
            modality=Modality.IMAGE,
            extra={
                "thumbnail": str(thumb),
                "width": image.width,
                "height": image.height,
                "exif": exif,
                "has_ocr": bool(ocr_text),
            },
        ),
    )


def iter_images(directory: Path) -> Iterable[Path]:
    for p in directory.rglob("*"):
        if p.is_file() and p.suffix.lower() in SUPPORTED:
            yield p
