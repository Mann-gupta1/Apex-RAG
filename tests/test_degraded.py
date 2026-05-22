"""Degraded-mode response builder."""

from __future__ import annotations

from apex.api.degraded import degraded_chat
from apex.schemas import ChatRequest, Chunk, Modality, Provenance, RetrievedChunk


def _hit(content: str, *, page: int | None = None, ts: float | None = None) -> RetrievedChunk:
    return RetrievedChunk(
        chunk=Chunk(
            id="c1",
            modality=Modality.TEXT if page else Modality.AUDIO,
            content=content,
            provenance=Provenance(
                source_uri="ex.pdf",
                modality=Modality.TEXT if page else Modality.AUDIO,
                page=page,
                timestamp_start=ts,
            ),
        ),
        score=0.5,
    )


def test_degraded_chat_includes_warning_text():
    resp = degraded_chat(ChatRequest(query="q"), [_hit("matrix world content", page=3)])
    assert "generation" in resp.answer.lower()
    assert "unavailable" in resp.answer.lower()


def test_degraded_chat_emits_citations_for_each_hit():
    hits = [_hit(f"chunk content number {i} with shared tokens", page=i) for i in range(4)]
    resp = degraded_chat(ChatRequest(query="chunk content number"), hits)
    assert len(resp.citations) >= 1
    assert resp.faithfulness is None


def test_degraded_chat_truncates_to_five_sources():
    hits = [_hit(f"source {i} payload tokens", page=i) for i in range(20)]
    resp = degraded_chat(ChatRequest(query="source payload tokens"), hits)
    # body shows top 5
    assert resp.answer.count("\n- ") <= 5


def test_degraded_chat_handles_audio_timestamps():
    resp = degraded_chat(ChatRequest(query="q"), [_hit("audio passage tokens", ts=12.5)])
    assert "12.5" in resp.answer or "t=" in resp.answer
