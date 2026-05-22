"""Reciprocal Rank Fusion math + monotonicity properties."""
from __future__ import annotations

from apex.retrieval.hybrid import reciprocal_rank_fusion
from apex.retrieval.vector_store import RetrievalHit
from apex.schemas import Modality, Provenance


def _hit(cid: str, score: float = 1.0) -> RetrievalHit:
    return RetrievalHit(
        chunk_id=cid,
        content=cid,
        score=score,
        provenance=Provenance(source_uri=f"{cid}.txt", modality=Modality.TEXT),
        modality=Modality.TEXT,
    )


def test_rrf_merges_distinct_lists():
    a = [_hit("x"), _hit("y"), _hit("z")]
    b = [_hit("p"), _hit("q"), _hit("z")]
    out = reciprocal_rank_fusion([a, b])
    ids = [h.chunk_id for h in out]
    assert "z" in ids
    assert ids[0] == "z"
    assert set(ids) == {"x", "y", "z", "p", "q"}


def test_rrf_top_k_truncation():
    a = [_hit(f"a{i}") for i in range(10)]
    b = [_hit(f"b{i}") for i in range(10)]
    out = reciprocal_rank_fusion([a, b], top_k=5)
    assert len(out) == 5


def test_rrf_higher_rank_gets_higher_score():
    a = [_hit("x"), _hit("y")]
    out = reciprocal_rank_fusion([a])
    assert out[0].chunk_id == "x"
    assert out[0].score > out[1].score


def test_rrf_handles_empty_lists():
    out = reciprocal_rank_fusion([[], [], []], top_k=10)
    assert out == []
