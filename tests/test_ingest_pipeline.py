"""End-to-end ingestion pipeline for plain-text files (no heavy ML deps)."""
from __future__ import annotations

import pytest

from apex.ingest.pipeline import _detect_modality, ingest_file, ingest_path
from apex.schemas import Modality
from tests.fakes import install_fakes


def test_detect_modality_by_extension(tmp_path):
    assert _detect_modality(tmp_path / "f.pdf") == Modality.TEXT
    assert _detect_modality(tmp_path / "f.md") == Modality.TEXT
    assert _detect_modality(tmp_path / "f.png") == Modality.IMAGE
    assert _detect_modality(tmp_path / "f.mp3") == Modality.AUDIO
    assert _detect_modality(tmp_path / "f.mp4") == Modality.VIDEO
    assert _detect_modality(tmp_path / "f.unknown") is None


def test_ingest_text_file_creates_chunks(tmp_path, monkeypatch):
    store = install_fakes(monkeypatch)
    src = tmp_path / "memo.txt"
    src.write_text(
        "Paragraph one with several tokens.\n\n"
        "Paragraph two with more interesting content tokens.\n\n"
        "Paragraph three completing the document.",
        encoding="utf-8",
    )
    result = ingest_file(src)
    assert result.chunks_created >= 1
    assert result.modality == Modality.TEXT
    # rows landed in the in-memory store
    assert store.count() >= 1
    assert any("Paragraph" in r.content for r in store.rows)


def test_ingest_path_handles_directory(tmp_path, monkeypatch):
    store = install_fakes(monkeypatch)
    a = tmp_path / "a.txt"
    a.write_text("alpha document body with tokens.", encoding="utf-8")
    b = tmp_path / "sub" / "b.md"
    b.parent.mkdir()
    b.write_text("# beta\n\nbeta document body with tokens.", encoding="utf-8")
    results = ingest_path(tmp_path)
    assert {r.source_uri for r in results} == {str(a), str(b)}
    assert store.count() >= 2


def test_ingest_path_skips_unknown_extensions(tmp_path, monkeypatch):
    install_fakes(monkeypatch)
    (tmp_path / "ignored.xyz").write_text("noop", encoding="utf-8")
    results = ingest_path(tmp_path)
    assert results == []


def test_ingest_file_raises_on_unknown_extension(tmp_path, monkeypatch):
    install_fakes(monkeypatch)
    target = tmp_path / "f.unknown"
    target.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        ingest_file(target)
