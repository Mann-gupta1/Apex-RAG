"""Chunking determinism and modality preservation."""
from __future__ import annotations

from apex.chunking.multimodal import chunk_documents
from apex.schemas import Chunk, Modality, Provenance


def _text_chunk(text: str) -> Chunk:
    return Chunk(
        modality=Modality.TEXT,
        content=text,
        provenance=Provenance(source_uri="t.txt", modality=Modality.TEXT),
    )


def test_short_text_passes_through_unchanged():
    text = "this is a short chunk"
    out = chunk_documents([_text_chunk(text)], chunk_size=512, overlap=64)
    assert len(out) == 1
    assert out[0].content == text


def test_long_text_is_split_with_overlap():
    long_text = " ".join(["word"] * 1200)
    out = chunk_documents([_text_chunk(long_text)], chunk_size=400, overlap=50)
    assert len(out) > 1
    for c in out:
        assert len(c.content.split()) <= 400


def test_non_text_modalities_pass_through():
    image = Chunk(
        modality=Modality.IMAGE,
        content="[image]",
        provenance=Provenance(source_uri="x.jpg", modality=Modality.IMAGE),
    )
    audio = Chunk(
        modality=Modality.AUDIO,
        content="hello world",
        provenance=Provenance(
            source_uri="x.wav", modality=Modality.AUDIO, timestamp_start=0.0, timestamp_end=1.0
        ),
    )
    out = chunk_documents([image, audio])
    assert {c.modality for c in out} == {Modality.IMAGE, Modality.AUDIO}


def test_chunking_is_deterministic():
    text = " ".join(f"w{i}" for i in range(800))
    a = chunk_documents([_text_chunk(text)], chunk_size=200, overlap=40)
    b = chunk_documents([_text_chunk(text)], chunk_size=200, overlap=40)
    assert [c.content for c in a] == [c.content for c in b]
