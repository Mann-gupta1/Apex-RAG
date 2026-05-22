-- Canonical pgvector schema for Apex RAG.
-- This mirrors alembic/versions/0001_initial_schema.py and is provided as a
-- standalone reference so reviewers can read the data model without parsing
-- migrations.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS tenants (
    id                      VARCHAR(64)  PRIMARY KEY,
    name                    VARCHAR(255) NOT NULL,
    rate_limit_per_minute   INTEGER      NOT NULL DEFAULT 60,
    created_at              TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ingestion_jobs (
    id           VARCHAR(64)  PRIMARY KEY,
    tenant_id    VARCHAR(64)  NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    source_uri   TEXT         NOT NULL,
    modality     VARCHAR(16)  NOT NULL,
    status       VARCHAR(24)  NOT NULL DEFAULT 'pending',
    error        TEXT,
    started_at   TIMESTAMPTZ,
    finished_at  TIMESTAMPTZ,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_ingestion_jobs_tenant ON ingestion_jobs(tenant_id);
CREATE INDEX IF NOT EXISTS ix_ingestion_jobs_status ON ingestion_jobs(status);

CREATE TABLE IF NOT EXISTS chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       VARCHAR(64) NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    modality        VARCHAR(16) NOT NULL,
    source_uri      TEXT NOT NULL,
    content         TEXT NOT NULL,
    context_summary TEXT,
    provenance      JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding       vector(768),
    image_embedding vector(512),
    content_tsv     tsvector GENERATED ALWAYS AS (to_tsvector('english', coalesce(content, ''))) STORED,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_chunks_tenant   ON chunks(tenant_id);
CREATE INDEX IF NOT EXISTS ix_chunks_modality ON chunks(modality);
CREATE INDEX IF NOT EXISTS ix_chunks_source   ON chunks(source_uri);
CREATE INDEX IF NOT EXISTS ix_chunks_tsv      ON chunks USING GIN (content_tsv);
CREATE INDEX IF NOT EXISTS ix_chunks_embed_hnsw
    ON chunks USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
CREATE INDEX IF NOT EXISTS ix_chunks_image_embed_hnsw
    ON chunks USING hnsw (image_embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

CREATE TABLE IF NOT EXISTS audit_log (
    id                BIGSERIAL PRIMARY KEY,
    tenant_id         VARCHAR(64) NOT NULL,
    user_id           VARCHAR(128),
    action            VARCHAR(64) NOT NULL,
    request           JSONB,
    response_summary  JSONB,
    source_chunk_ids  JSONB,
    latency_ms        INTEGER,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_audit_tenant_created ON audit_log(tenant_id, created_at);

CREATE TABLE IF NOT EXISTS feedback (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   VARCHAR(64) NOT NULL,
    query       TEXT NOT NULL,
    response    TEXT NOT NULL,
    chunk_ids   JSONB NOT NULL,
    rating      SMALLINT NOT NULL,
    comment     TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_feedback_tenant ON feedback(tenant_id);
CREATE INDEX IF NOT EXISTS ix_feedback_rating ON feedback(rating);
