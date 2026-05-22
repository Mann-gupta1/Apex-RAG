"""Audio ingestion: faster-whisper transcription + optional pyannote diarization.

Produces one Chunk per utterance/segment with ``timestamp_start``,
``timestamp_end``, and ``speaker`` recorded in the provenance.
"""
from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from apex.logging_config import logger
from apex.schemas import Chunk, Modality, Provenance
from apex.settings import get_settings

SUPPORTED = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac"}


@dataclass(frozen=True)
class AudioSegment:
    start: float
    end: float
    text: str
    speaker: str | None = None


def _transcribe(path: Path) -> list[AudioSegment]:
    settings = get_settings()
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("faster-whisper not installed (need [ingest] extra)") from exc

    model = WhisperModel(
        settings.whisper_model,
        device=settings.whisper_device,
        compute_type=settings.whisper_compute_type,
    )
    segments, _info = model.transcribe(str(path), vad_filter=True)
    out: list[AudioSegment] = []
    for seg in segments:
        text = (seg.text or "").strip()
        if text:
            out.append(AudioSegment(start=float(seg.start), end=float(seg.end), text=text))
    return out


def _diarize(path: Path) -> list[tuple[float, float, str]]:
    """Return a list of (start, end, speaker_label). Empty if diarization disabled."""
    settings = get_settings()
    token = settings.huggingface_token
    if not token:
        return []
    try:
        from pyannote.audio import Pipeline
    except ImportError:  # pragma: no cover
        logger.warning("pyannote.audio not installed; skipping diarization")
        return []
    try:
        pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", use_auth_token=token)
        diar = pipeline(str(path))
        return [(float(t.start), float(t.end), str(spk)) for t, _, spk in diar.itertracks(yield_label=True)]
    except Exception as exc:
        logger.warning("diarization failed: {}", exc)
        return []


def _assign_speakers(segments: list[AudioSegment], diar: list[tuple[float, float, str]]) -> list[AudioSegment]:
    if not diar:
        return segments
    out: list[AudioSegment] = []
    for seg in segments:
        speaker = None
        best_overlap = 0.0
        for ds, de, label in diar:
            overlap = max(0.0, min(seg.end, de) - max(seg.start, ds))
            if overlap > best_overlap:
                best_overlap, speaker = overlap, label
        out.append(AudioSegment(seg.start, seg.end, seg.text, speaker))
    return out


def load_audio(path: Path) -> list[Chunk]:
    path = Path(path)
    logger.info("ingest audio: {}", path.name)
    segments = _transcribe(path)
    segments = _assign_speakers(segments, _diarize(path))

    return [
        Chunk(
            modality=Modality.AUDIO,
            content=(f"[{seg.speaker}] " if seg.speaker else "") + seg.text,
            provenance=Provenance(
                source_uri=str(path),
                modality=Modality.AUDIO,
                timestamp_start=seg.start,
                timestamp_end=seg.end,
                speaker=seg.speaker,
            ),
        )
        for seg in segments
    ]


def iter_audio(directory: Path) -> Iterable[Path]:
    for p in directory.rglob("*"):
        if p.is_file() and p.suffix.lower() in SUPPORTED:
            yield p


def transcribe_audio_track(path: Path) -> Iterator[AudioSegment]:
    """Helper for the video pipeline — yields segments without packaging Chunks."""
    yield from _transcribe(path)
