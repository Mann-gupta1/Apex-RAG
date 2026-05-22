"""open_clip image embedder. Used for both raw images and video keyframes."""
from __future__ import annotations

from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from apex.logging_config import logger
from apex.settings import get_settings

if TYPE_CHECKING:
    from PIL.Image import Image


class ImageEmbedder:
    def __init__(
        self,
        backbone: str | None = None,
        pretrained: str | None = None,
        *,
        device: str = "cpu",
    ) -> None:
        settings = get_settings()
        self.backbone = backbone or settings.image_embed_model
        self.pretrained = pretrained or settings.image_embed_pretrained
        self.device = device
        self._model = None
        self._preprocess = None
        self._tokenizer = None

    def _ensure(self):
        if self._model is None:
            try:
                import open_clip
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError("open-clip-torch not installed (need [ingest] extra)") from exc
            logger.info("loading open_clip {} ({})", self.backbone, self.pretrained)
            model, _, preprocess = open_clip.create_model_and_transforms(
                self.backbone, pretrained=self.pretrained
            )
            model = model.to(self.device).eval()
            self._model = model
            self._preprocess = preprocess
            self._tokenizer = open_clip.get_tokenizer(self.backbone)
        return self._model, self._preprocess, self._tokenizer

    @property
    def dim(self) -> int:
        # ViT-B-32 is 512-dim; trust the model header otherwise
        model, *_ = self._ensure()
        return int(model.visual.output_dim)

    def encode_images(self, images: Iterable[Image]) -> np.ndarray:
        import torch

        model, preprocess, _ = self._ensure()
        tensors = [preprocess(img).unsqueeze(0) for img in images]
        if not tensors:
            return np.zeros((0, self.dim), dtype=np.float32)
        batch = torch.cat(tensors, dim=0).to(self.device)
        with torch.no_grad():
            feats = model.encode_image(batch)
            feats = feats / feats.norm(dim=-1, keepdim=True)
        return feats.cpu().numpy().astype(np.float32, copy=False)

    def encode_paths(self, paths: Iterable[str | Path]) -> np.ndarray:
        from PIL import Image as PImage

        images = []
        for p in paths:
            try:
                images.append(PImage.open(p).convert("RGB"))
            except Exception as exc:
                logger.warning("could not load image {}: {}", p, exc)
        return self.encode_images(images)

    def encode_text(self, texts: Iterable[str]) -> np.ndarray:
        """Encode text queries into the shared CLIP space (for image search)."""
        import torch

        model, _, tokenizer = self._ensure()
        items = list(texts)
        if not items:
            return np.zeros((0, self.dim), dtype=np.float32)
        tokens = tokenizer(items).to(self.device)
        with torch.no_grad():
            feats = model.encode_text(tokens)
            feats = feats / feats.norm(dim=-1, keepdim=True)
        return feats.cpu().numpy().astype(np.float32, copy=False)


@lru_cache(maxsize=2)
def get_image_embedder() -> ImageEmbedder:
    return ImageEmbedder()
