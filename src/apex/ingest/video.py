"""Video ingestion: PySceneDetect scenes → OpenCV keyframes → Whisper transcript.

Each scene becomes one Chunk whose content is the transcript segment text and
whose provenance carries ``timestamp_start/end``, ``scene_index``, and the
path to the saved keyframe (under ``data/processed_chunks/keyframes/``).
"""
from __future__ import annotations

import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from apex.logging_config import logger
from apex.schemas import Chunk, Modality, Provenance
from apex.settings import get_settings

KEYFRAME_DIR = get_settings().root_dir / "data" / "processed_chunks" / "keyframes"
SUPPORTED = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}


@dataclass(frozen=True)
class Scene:
    index: int
    start: float
    end: float
    keyframe_path: Path


def _detect_scenes(path: Path) -> list[tuple[float, float]]:
    try:
        from scenedetect import ContentDetector, SceneManager, open_video
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("scenedetect not installed (need [ingest] extra)") from exc

    video = open_video(str(path))
    manager = SceneManager()
    manager.add_detector(ContentDetector(threshold=27.0))
    manager.detect_scenes(video=video)
    return [(s.get_seconds(), e.get_seconds()) for s, e in manager.get_scene_list()]


def _extract_keyframe(path: Path, t_seconds: float, out_path: Path) -> bool:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-ss", f"{t_seconds:.3f}", "-i", str(path),
                "-frames:v", "1", "-q:v", "3", str(out_path),
            ],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return out_path.exists()
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        logger.warning("ffmpeg keyframe extraction failed for {}: {}", path.name, exc)
        return False


def _extract_audio_track(path: Path) -> Path | None:
    audio_path = path.with_suffix(".extracted.wav")
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(path),
                "-vn", "-ac", "1", "-ar", "16000", str(audio_path),
            ],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return audio_path if audio_path.exists() else None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _transcript_for_scene(audio_path: Path | None, start: float, end: float) -> str:
    if audio_path is None:
        return ""
    try:
        from apex.ingest.audio import transcribe_audio_track

        segments = list(transcribe_audio_track(audio_path))
    except Exception as exc:
        logger.warning("video audio transcription failed: {}", exc)
        return ""
    parts = [s.text for s in segments if not (s.end < start or s.start > end)]
    return " ".join(parts).strip()


def load_video(path: Path) -> list[Chunk]:
    path = Path(path)
    logger.info("ingest video: {}", path.name)
    scenes = _detect_scenes(path) or [(0.0, 0.0)]  # at least one scene
    audio_track = _extract_audio_track(path)

    chunks: list[Chunk] = []
    for i, (start, end) in enumerate(scenes):
        mid = (start + end) / 2.0 if end > start else 0.5
        keyframe_path = KEYFRAME_DIR / f"{path.stem}__scene{i:03d}.jpg"
        _extract_keyframe(path, mid, keyframe_path)

        transcript = _transcript_for_scene(audio_track, start, end)
        content = transcript or f"[video scene {i} from {path.name}]"

        chunks.append(
            Chunk(
                modality=Modality.VIDEO,
                content=content,
                provenance=Provenance(
                    source_uri=str(path),
                    modality=Modality.VIDEO,
                    timestamp_start=start,
                    timestamp_end=end,
                    scene_index=i,
                    extra={"keyframe": str(keyframe_path)} if keyframe_path.exists() else {},
                ),
            )
        )
    return chunks


def iter_videos(directory: Path) -> Iterable[Path]:
    for p in directory.rglob("*"):
        if p.is_file() and p.suffix.lower() in SUPPORTED:
            yield p
