"""Execute GraphQL queries through the schema with an in-memory store."""

from __future__ import annotations

import pytest

from apex.api.graphql_schema import schema
from apex.schemas import Chunk, Modality, Provenance
from tests.fakes import FakeVectorStore, install_fakes


@pytest.fixture
def fake_store(monkeypatch) -> FakeVectorStore:
    store = install_fakes(monkeypatch)
    store.upsert(
        [
            Chunk(
                id="c1",
                modality=Modality.TEXT,
                content="Marbury v. Madison established judicial review.",
                provenance=Provenance(source_uri="m.pdf", modality=Modality.TEXT, page=1),
            ),
            Chunk(
                id="c2",
                modality=Modality.TEXT,
                content="Brown v. Board overturned Plessy.",
                provenance=Provenance(source_uri="b.pdf", modality=Modality.TEXT, page=2),
            ),
        ]
    )
    return store


@pytest.mark.asyncio
async def test_graphql_search_returns_hits(fake_store):
    result = await schema.execute(
        (
            "query($q: String!) { search(query: $q, topK: 5) { "
            "query latencyMs results { chunk { id content modality provenance { sourceUri page } } score } } }"
        ),
        variable_values={"q": "judicial review"},
    )
    assert result.errors is None, result.errors
    payload = result.data["search"]
    assert payload["query"] == "judicial review"
    assert any("marbury" in r["chunk"]["content"].lower() for r in payload["results"])
    # provenance is wired
    assert payload["results"][0]["chunk"]["provenance"]["sourceUri"]


@pytest.mark.asyncio
async def test_graphql_chunk_fetch_by_id(fake_store):
    result = await schema.execute('{ chunk(id: "c1") { id content modality } }')
    assert result.errors is None, result.errors
    assert result.data["chunk"]["id"] == "c1"
    assert "marbury" in result.data["chunk"]["content"].lower()


@pytest.mark.asyncio
async def test_graphql_chunk_returns_null_for_missing(fake_store):
    result = await schema.execute('{ chunk(id: "does-not-exist") { id } }')
    assert result.errors is None
    assert result.data["chunk"] is None


@pytest.mark.asyncio
async def test_graphql_submit_feedback_mutation(monkeypatch, fake_store):
    captured = {}

    def record(req):
        captured["req"] = req
        return 1

    monkeypatch.setattr("apex.feedback.human_loop.record_feedback", record)

    result = await schema.execute(
        'mutation { submitFeedback(query: "q", response: "r", chunkIds: ["c1"], rating: 1) }'
    )
    assert result.errors is None, result.errors
    assert result.data["submitFeedback"] is True
    assert captured["req"].rating == 1
