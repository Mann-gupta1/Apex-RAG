"""Smoke tests for the Pydantic data model."""

from __future__ import annotations

from apex.schemas import (
    Chunk,
    Citation,
    FeedbackRequest,
    Modality,
    Provenance,
    RetrievedChunk,
    SearchRequest,
    SearchResponse,
)


def test_chunk_round_trip():
    p = Provenance(source_uri="x.pdf", modality=Modality.TEXT, page=3)
    c = Chunk(modality=Modality.TEXT, content="hello", provenance=p)
    dumped = c.model_dump_json()
    restored = Chunk.model_validate_json(dumped)
    assert restored.provenance.page == 3
    assert restored.modality == Modality.TEXT


def test_retrieved_chunk_ordering_meta():
    p = Provenance(source_uri="x.pdf", modality=Modality.TEXT)
    c = Chunk(modality=Modality.TEXT, content="x", provenance=p)
    rc = RetrievedChunk(chunk=c, score=0.5, fusion_rank=2)
    assert rc.fusion_rank == 2
    assert rc.score == 0.5


def test_search_request_defaults():
    r = SearchRequest(query="hi")
    assert r.tenant_id == "default"
    assert r.top_k == 6


def test_search_response_empty():
    r = SearchResponse(query="q", results=[], latency_ms=0)
    assert r.cache_hit is False


def test_feedback_clamps_rating():
    r = FeedbackRequest(query="q", response="r", chunk_ids=["a"], rating=1)
    assert r.rating == 1
    r = FeedbackRequest(query="q", response="r", chunk_ids=["a"], rating=-1)
    assert r.rating == -1


def test_citation_optional_span():
    cit = Citation(chunk_id="x", source_uri="x.pdf", modality=Modality.TEXT)
    assert cit.span is None
