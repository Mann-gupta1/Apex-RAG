"""initial schema: tenants, chunks, audit_log, feedback, ingestion_jobs

Revision ID: 0001
Revises:
Create Date: 2026-05-19

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "tenants",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("rate_limit_per_minute", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.execute("INSERT INTO tenants (id, name) VALUES ('default', 'Default Tenant')")

    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("source_uri", sa.Text(), nullable=False),
        sa.Column("modality", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="pending"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_ingestion_jobs_tenant", "ingestion_jobs", ["tenant_id"])
    op.create_index("ix_ingestion_jobs_status", "ingestion_jobs", ["status"])

    op.execute(
        """
        CREATE TABLE chunks (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id       VARCHAR(64) NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            modality        VARCHAR(16) NOT NULL,
            source_uri      TEXT NOT NULL,
            content         TEXT NOT NULL,
            context_summary TEXT,
            provenance      JSONB NOT NULL DEFAULT '{}'::jsonb,
            embedding       vector(768),
            image_embedding vector(512),
            content_tsv     tsvector
                GENERATED ALWAYS AS (to_tsvector('english', coalesce(content, ''))) STORED,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )
    op.create_index("ix_chunks_tenant", "chunks", ["tenant_id"])
    op.create_index("ix_chunks_modality", "chunks", ["modality"])
    op.create_index("ix_chunks_source", "chunks", ["source_uri"])
    op.execute("CREATE INDEX ix_chunks_tsv ON chunks USING GIN (content_tsv)")
    op.execute(
        "CREATE INDEX ix_chunks_embed_hnsw ON chunks USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )
    op.execute(
        "CREATE INDEX ix_chunks_image_embed_hnsw ON chunks USING hnsw (image_embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("request", sa.JSON(), nullable=True),
        sa.Column("response_summary", sa.JSON(), nullable=True),
        sa.Column("source_chunk_ids", sa.JSON(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_audit_tenant_created", "audit_log", ["tenant_id", "created_at"])

    op.create_table(
        "feedback",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("response", sa.Text(), nullable=False),
        sa.Column("chunk_ids", sa.JSON(), nullable=False),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_feedback_tenant", "feedback", ["tenant_id"])
    op.create_index("ix_feedback_rating", "feedback", ["rating"])


def downgrade() -> None:
    op.drop_table("feedback")
    op.drop_table("audit_log")
    op.execute("DROP TABLE IF EXISTS chunks CASCADE")
    op.drop_table("ingestion_jobs")
    op.drop_table("tenants")
