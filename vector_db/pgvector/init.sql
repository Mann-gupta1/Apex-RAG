-- Apex RAG: minimal extension bootstrap. The full schema is owned by Alembic.
-- This file runs once on container init so the database has pgvector/pg_trgm/pgcrypto
-- ready before `alembic upgrade head` is invoked from the host.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
