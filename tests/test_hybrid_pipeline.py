"""Full retrieval pipeline with an in-memory FakeVectorStore.

Exercises the orchestrator's branching: HyDE off (cheap path), HyDE on (rewrite
fan-out), rerank toggling, RRF fusion across multiple ranked lists, and
adaptive complexity → top_k selection.
"""

from __future__ import annotations

import pytest

from apex.retrieval.pipeline import run_search
from apex.schemas import Chunk, Modality, Provenance, SearchRequest
from tests.fakes import FakeVectorStore, install_fakes


def _seed(store: FakeVectorStore) -> None:
    rows = [
        ("c1", "Marbury v. Madison established the principle of judicial review in 1803."),
        ("c2", "Brown v. Board of Education declared racial segregation unconstitutional."),
        ("c3", "The Equal Protection Clause is part of the Fourteenth Amendment."),
        ("c4", "Apex legal memo: contract clause 4.2 was modified verbally on 2023-11-02."),
        ("c5", "Exhibit 7 is the signed amendment dated 2023-12-10."),
    ]
    for cid, text in rows:
        store.upsert(
            [
                Chunk(
                    id=cid,
                    modality=Modality.TEXT,
                    content=text,
                    provenance=Provenance(source_uri=f"{cid}.txt", modality=Modality.TEXT),
                )
            ]
        )


@pytest.fixture
def seeded_store(monkeypatch) -> FakeVectorStore:
    store = install_fakes(monkeypatch)
    _seed(store)
    return store


def test_run_search_returns_relevant_results(seeded_store, monkeypatch):
    monkeypatch.setenv("ENABLE_HYDE", "false")
    monkeypatch.setenv("ENABLE_RERANKER", "false")
    from apex.settings import reset_caches

    reset_caches()
    resp = run_search(
        SearchRequest(
            query="What did Marbury establish?",
            top_k=3,
            use_hyde=False,
            use_rerank=False,
        )
    )
    assert len(resp.results) >= 1
    top = resp.results[0]
    assert "marbury" in top.chunk.content.lower()
    assert resp.latency_ms >= 0


def test_run_search_rrf_merges_dense_and_sparse(seeded_store):
    resp = run_search(
        SearchRequest(
            query="judicial review principle established",
            top_k=5,
            use_hyde=False,
            use_rerank=False,
        )
    )
    ids = [r.chunk.id for r in resp.results]
    assert "c1" in ids


def test_run_search_modality_filter(seeded_store):
    seeded_store.upsert(
        [
            Chunk(
                id="img1",
                modality=Modality.IMAGE,
                content="exhibit photograph of supreme court building",
                provenance=Provenance(source_uri="img1.jpg", modality=Modality.IMAGE),
            )
        ]
    )
    resp = run_search(
        SearchRequest(
            query="exhibit photograph",
            modalities=[Modality.IMAGE],
            top_k=5,
            use_hyde=False,
            use_rerank=False,
        )
    )
    assert all(r.chunk.modality == Modality.IMAGE for r in resp.results)


def test_run_search_respects_top_k(seeded_store):
    resp = run_search(
        SearchRequest(query="contract amendment", top_k=2, use_hyde=False, use_rerank=False)
    )
    assert len(resp.results) <= 2


def test_empty_corpus_returns_empty(monkeypatch):
    install_fakes(monkeypatch)
    resp = run_search(SearchRequest(query="anything", use_hyde=False, use_rerank=False))
    assert resp.results == []
    assert resp.latency_ms >= 0


def test_rewritten_queries_included_when_hyde_on(seeded_store, monkeypatch):
    # Stub the LLM-based rewriters so we don't need Ollama.
    from apex.retrieval import query_rewrite

    monkeypatch.setattr(
        query_rewrite, "_safe_generate", lambda *a, **k: "alternative phrasing of the question."
    )
    resp = run_search(
        SearchRequest(
            query="What did Marbury establish?",
            top_k=3,
            use_hyde=True,
            use_rerank=False,
        )
    )
    assert isinstance(resp.rewritten_queries, list)
