"""Audit-log helper: every search/chat/upload/feedback action is recorded.

The table schema lives in alembic/versions/0001_initial_schema.py.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from apex.db import session_scope
from apex.logging_config import logger


def log_event(
    *,
    tenant_id: str,
    action: str,
    request: dict[str, Any] | None = None,
    response_summary: dict[str, Any] | None = None,
    source_chunk_ids: list[str] | None = None,
    latency_ms: int | None = None,
    user_id: str | None = None,
) -> None:
    try:
        with session_scope() as s:
            s.execute(
                text(
                    """
                    INSERT INTO audit_log
                        (tenant_id, user_id, action, request, response_summary, source_chunk_ids, latency_ms)
                    VALUES (:tenant_id, :user_id, :action,
                            CAST(:request AS jsonb), CAST(:response_summary AS jsonb),
                            CAST(:source_chunk_ids AS jsonb), :latency_ms)
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "action": action,
                    "request": json.dumps(request or {}),
                    "response_summary": json.dumps(response_summary or {}),
                    "source_chunk_ids": json.dumps(source_chunk_ids or []),
                    "latency_ms": latency_ms,
                },
            )
    except Exception as exc:
        logger.debug("audit log insert failed: {}", exc)
