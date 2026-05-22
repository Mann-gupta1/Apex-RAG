"""In-memory fakes used across deep tests.

A ``FakeVectorStore`` implements the ``VectorStore`` protocol with deterministic
tokenwise scoring so we can run the full retrieval + agent pipeline without
Postgres/pgvector. ``patch_factory`` swaps it into ``apex.retrieval.store_factory``.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from apex.retrieval.vector_store import RetrievalHit
from apex.schemas import Chunk, Modality, Provenance


@dataclass
class _Row:
    chunk_id: str
    tenant_id: str
    modality: Modality
    source_uri: str
    content: str
    context_summary: str | None
    provenance: Provenance
    text_embedding: list[float] | None
    image_embedding: list[float] | None


def _cos(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    num = sum(a[i] * b[i] for i in range(n))
    da = sum(a[i] * a[i] for i in range(n)) ** 0.5
    db = sum(b[i] * b[i] for i in range(n)) ** 0.5
    return float(num / (da * db)) if da and db else 0.0


@dataclass
class FakeVectorStore:
    """In-memory store. Score = cosine if embeddings present, else token overlap."""

    rows: list[_Row] = field(default_factory=list)
    _next_id: int = 0

    def upsert(self, chunks: list[Chunk]) -> int:
        for c in chunks:
            self._next_id += 1
            cid = c.id or f"chunk-{self._next_id}"
            self.rows.append(
                _Row(
                    chunk_id=cid,
                    tenant_id=c.tenant_id,
                    modality=c.modality,
                    source_uri=c.provenance.source_uri,
                    content=c.content,
                    context_summary=c.context_summary,
                    provenance=c.provenance,
                    text_embedding=c.text_embedding,
                    image_embedding=c.image_embedding,
                )
            )
        return len(chunks)

    def _hit(self, row: _Row, score: float) -> RetrievalHit:
        return RetrievalHit(
            chunk_id=row.chunk_id,
            content=row.content,
            score=float(score),
            provenance=row.provenance,
            modality=row.modality,
            context_summary=row.context_summary,
        )

    def _filter(self, tenant_id: str, modalities: list[Modality] | None) -> Iterable[_Row]:
        for r in self.rows:
            if r.tenant_id != tenant_id:
                continue
            if modalities and r.modality not in modalities:
                continue
            yield r

    def dense_search(self, embedding, *, tenant_id, modalities=None, top_k=50):
        scored: list[tuple[float, _Row]] = []
        for r in self._filter(tenant_id, modalities):
            score = _cos(embedding, r.text_embedding or [])
            scored.append((score, r))
        scored.sort(key=lambda t: t[0], reverse=True)
        return [self._hit(r, s) for s, r in scored[:top_k]]

    def dense_image_search(self, embedding, *, tenant_id, top_k=50):
        scored: list[tuple[float, _Row]] = []
        for r in self._filter(tenant_id, None):
            if not r.image_embedding:
                continue
            scored.append((_cos(embedding, r.image_embedding), r))
        scored.sort(key=lambda t: t[0], reverse=True)
        return [self._hit(r, s) for s, r in scored[:top_k]]

    def sparse_search(self, query, *, tenant_id, modalities=None, top_k=50):
        q_tokens = set(query.lower().split())
        scored: list[tuple[float, _Row]] = []
        for r in self._filter(tenant_id, modalities):
            c_tokens = set(r.content.lower().split())
            if not c_tokens:
                continue
            inter = len(q_tokens & c_tokens)
            if inter == 0:
                continue
            scored.append((inter / max(1, len(c_tokens)), r))
        scored.sort(key=lambda t: t[0], reverse=True)
        return [self._hit(r, s) for s, r in scored[:top_k]]

    def get_chunk(self, chunk_id, *, tenant_id):
        for r in self.rows:
            if r.chunk_id == chunk_id and r.tenant_id == tenant_id:
                return self._hit(r, 1.0)
        return None

    def delete_by_tenant(self, tenant_id):
        before = len(self.rows)
        self.rows = [r for r in self.rows if r.tenant_id != tenant_id]
        return before - len(self.rows)

    def count(self, tenant_id=None):
        if tenant_id is None:
            return len(self.rows)
        return sum(1 for r in self.rows if r.tenant_id == tenant_id)


class FakeTextEmbedder:
    """Deterministic, dependency-free embedder. Uses tokenised hash buckets."""

    dim = 32

    def encode(self, texts):
        import numpy as np

        out = []
        for t in texts:
            vec = [0.0] * self.dim
            for tok in (t or "").lower().split():
                idx = hash(tok) % self.dim
                vec[idx] += 1.0
            arr = np.array(vec, dtype="float32")
            n = float((arr * arr).sum() ** 0.5)
            if n > 0:
                arr = arr / n
            out.append(arr)
        return np.stack(out) if out else np.zeros((0, self.dim), dtype="float32")

    def encode_one(self, text):
        return self.encode([text])[0]

    def encode_query(self, query):
        return self.encode_one(query)


def install_fakes(monkeypatch, store: FakeVectorStore | None = None) -> FakeVectorStore:
    """Wire FakeVectorStore + FakeTextEmbedder into the retrieval modules.

    Also short-circuits Ollama and the heavy NLI scorer so tests don't drag
    in network calls or the sentence-transformers download cycle.
    """
    # Clear cached settings — prior tests may have mutated env vars (e.g.
    # ``RATE_LIMIT_PER_MINUTE``) and left the cached singleton stale.
    from apex.settings import reset_caches

    reset_caches()

    store = store or FakeVectorStore()
    fake_embedder = FakeTextEmbedder()

    from apex.embedding import text as text_mod
    from apex.ingest import pipeline as ingest_pipeline
    from apex.llm import ollama_client
    from apex.retrieval import hybrid as hyb
    from apex.retrieval import query_rewrite as qr
    from apex.retrieval import store_factory as sf
    from apex.safety import nli as nli_mod

    monkeypatch.setattr(sf, "get_vector_store", lambda: store)
    monkeypatch.setattr(hyb, "get_vector_store", lambda: store)
    monkeypatch.setattr(hyb, "get_text_embedder", lambda: fake_embedder)
    monkeypatch.setattr(text_mod, "get_text_embedder", lambda model_name=None: fake_embedder)

    # Disable all LLM-backed query rewrites by default; tests can re-enable.
    monkeypatch.setattr(qr, "_safe_generate", lambda *a, **k: None)
    # Make Ollama "healthy" everywhere it's bound.
    monkeypatch.setattr(ollama_client, "health", lambda: True)
    try:
        from apex.api import degraded as _deg

        monkeypatch.setattr(_deg, "_ollama_health", lambda: True)
        monkeypatch.setattr(_deg, "llm_healthy", lambda: True)
    except Exception:
        pass
    try:
        from apex.api import rest as _rest

        monkeypatch.setattr(_rest, "llm_healthy", lambda: True)
    except Exception:
        pass
    monkeypatch.setattr(nli_mod, "faithfulness_score", lambda *a, **k: 0.91)
    try:
        from apex.agent import graph as _g

        monkeypatch.setattr(_g, "faithfulness_score", lambda *a, **k: 0.91)
        monkeypatch.setattr(_g, "generate", lambda *a, **k: "Stub answer with citation [1].")
        monkeypatch.setattr(_g, "stream", lambda *a, **k: iter(["Stub ", "answer ", "[1]."]))
    except Exception:
        pass

    # Reset the in-memory rate-limit counter so tests start with a clean budget.
    try:
        from apex.api import middleware as _mw

        _mw._inmem_counters.clear()  # type: ignore[attr-defined]
        monkeypatch.setattr(_mw, "_get_redis", lambda: None)
    except Exception:
        pass

    def _fake_embed(chunks):
        vectors = fake_embedder.encode([c.content for c in chunks])
        out = []
        for c, v in zip(chunks, vectors, strict=False):
            out.append(c.model_copy(update={"text_embedding": v.tolist()}))
        return out

    monkeypatch.setattr(ingest_pipeline, "_embed", _fake_embed)
    monkeypatch.setattr(ingest_pipeline, "_store", lambda chunks: store.upsert(list(chunks)))

    return store
