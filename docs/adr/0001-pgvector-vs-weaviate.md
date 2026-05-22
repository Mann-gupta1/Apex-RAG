# ADR 0001 — Vector database: pgvector primary, Weaviate alternative

**Status**: Accepted
**Date**: 2026-04-22

## Context

Apex RAG needs durable vector storage with hybrid (dense + sparse) retrieval,
multi-tenant isolation, and a path to production at moderate scale (~10 M
chunks). Options surveyed:

- **pgvector** on PostgreSQL — single container, ACID, FTS via `tsvector`.
- **Weaviate OSS** — purpose-built vector DB, BM25 + vector hybrid built-in.
- **Pinecone / Qdrant Cloud** — managed, but violates the "fully local + free" constraint.
- **Elasticsearch + dense_vector** — strong BM25; weaker vector ergonomics; heavy ops.

## Decision

**Default driver: pgvector.** Implement a pluggable `VectorStore` protocol so
**Weaviate** can be substituted with `VECTOR_STORE_DRIVER=weaviate`.

## Rationale

- **Operational simplicity.** Most engagements already run Postgres; one
  fewer service to operate is a real win.
- **Hybrid in one query plan.** `tsvector` + `pgvector` can be queried (and
  later joined) in the same plan, which we'll exploit if/when we move from
  Python RRF fusion to in-database fusion.
- **Transactional ingest.** Multi-row upserts with provenance JSON are
  trivially atomic.
- **HNSW good enough.** Recall@10 of 0.95 at `ef_search=40` is acceptable for
  our golden set; we can crank `ef_search` per-tenant if needed.

We keep Weaviate as an alternative for engagements that need
horizontally-sharded multi-tenant collections out of the box.

## Consequences

- Performance ceiling: `pgvector` HNSW indexes are slower to build than
  Weaviate's; mitigated by `m=16, ef_construction=64` defaults.
- Backups: leveraging existing pg_dump + WAL is a feature, not a bug.
- Sharding: out of scope for the pilot; cross-region read replica gives us
  horizontal read scale (see `infra/terraform/postgres.tf`).
