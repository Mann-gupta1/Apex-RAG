"""Citation span extraction."""
from __future__ import annotations

from apex.safety.citation import extract_citations
from apex.schemas import Chunk, Modality, Provenance, RetrievedChunk


def _retrieved(content: str, cid: str = "c1") -> RetrievedChunk:
    chunk = Chunk(
        id=cid,
        modality=Modality.TEXT,
        content=content,
        provenance=Provenance(source_uri="t.pdf", modality=Modality.TEXT, page=1),
    )
    return RetrievedChunk(chunk=chunk, score=1.0)


def test_extract_finds_overlap_span():
    answer = "Marbury v. Madison established the principle of judicial review."
    chunk_text = (
        "Decided in 1803, Marbury v. Madison established the principle of "
        "judicial review across the federal judiciary."
    )
    citations = extract_citations(answer, [_retrieved(chunk_text)])
    assert len(citations) == 1
    cit = citations[0]
    assert cit.quote is not None
    assert "judicial review" in cit.quote


def test_extract_returns_citation_even_when_no_quote_found():
    answer = "Completely unrelated content."
    citations = extract_citations(answer, [_retrieved("Cats sleep a lot.")])
    assert len(citations) == 1
    assert citations[0].quote is None


def test_extract_carries_provenance():
    answer = "The Court ruled the act unconstitutional in 1803."
    chunk_text = "In 1803 the Court ruled the act unconstitutional."
    cit = extract_citations(answer, [_retrieved(chunk_text)])[0]
    assert cit.source_uri == "t.pdf"
    assert cit.page == 1
    assert cit.modality == Modality.TEXT
