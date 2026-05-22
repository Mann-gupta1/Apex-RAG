"""Agent tools: a small, deterministic toolbelt callable from the LangGraph nodes.

Each tool returns a JSON-serializable dict so the agent can reason about it.
"""
from __future__ import annotations

import ast
import operator as op
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text

from apex.db import session_scope
from apex.logging_config import logger
from apex.retrieval.store_factory import get_vector_store


@dataclass
class ToolResult:
    name: str
    ok: bool
    result: Any
    error: str | None = None


# ---------- sql_calculator: safe expression eval ----------
_ALLOWED_BINOPS = {
    ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv,
    ast.Mod: op.mod, ast.Pow: op.pow, ast.FloorDiv: op.floordiv,
}
_ALLOWED_UNARY = {ast.UAdd: op.pos, ast.USub: op.neg}


def _safe_eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        return _ALLOWED_BINOPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARY:
        return _ALLOWED_UNARY[type(node.op)](_safe_eval(node.operand))
    raise ValueError(f"unsupported expression node: {ast.dump(node)}")


def sql_calculator(expression: str) -> ToolResult:
    """Evaluate a basic arithmetic expression (no variables, no calls)."""
    try:
        tree = ast.parse(expression, mode="eval")
        value = _safe_eval(tree)
        return ToolResult(name="sql_calculator", ok=True, result=value)
    except Exception as exc:
        return ToolResult(name="sql_calculator", ok=False, result=None, error=str(exc))


# ---------- citation_lookup: fetch a chunk by id ----------
def citation_lookup(chunk_id: str, tenant_id: str = "default") -> ToolResult:
    try:
        hit = get_vector_store().get_chunk(chunk_id, tenant_id=tenant_id)
        if not hit:
            return ToolResult(name="citation_lookup", ok=False, result=None, error="not found")
        return ToolResult(
            name="citation_lookup",
            ok=True,
            result={
                "chunk_id": hit.chunk_id,
                "content": hit.content,
                "source_uri": hit.provenance.source_uri,
                "modality": hit.modality.value,
                "page": hit.provenance.page,
                "timestamp_start": hit.provenance.timestamp_start,
            },
        )
    except Exception as exc:
        return ToolResult(name="citation_lookup", ok=False, result=None, error=str(exc))


# ---------- web_fetch (stub) ----------
def web_fetch(url: str) -> ToolResult:
    """Web fetch is intentionally stubbed in the local build; documented for
    completeness. Production deployments would wire this up behind an
    allow-list + audit log."""
    return ToolResult(
        name="web_fetch",
        ok=False,
        result=None,
        error="web_fetch is disabled in the local profile",
    )


# ---------- audit: lightweight count over a tenant's recent activity ----------
def recent_query_count(tenant_id: str = "default", hours: int = 24) -> ToolResult:
    try:
        with session_scope() as s:
            n = s.execute(
                text(
                    """
                    SELECT COUNT(*) FROM audit_log
                    WHERE tenant_id = :tid AND created_at > now() - (:hours * INTERVAL '1 hour')
                    """
                ),
                {"tid": tenant_id, "hours": hours},
            ).scalar()
        return ToolResult(name="recent_query_count", ok=True, result={"count": int(n or 0)})
    except Exception as exc:
        logger.debug("recent_query_count failed: {}", exc)
        return ToolResult(name="recent_query_count", ok=False, result=None, error=str(exc))


TOOLS = {
    "sql_calculator": sql_calculator,
    "citation_lookup": citation_lookup,
    "web_fetch": web_fetch,
    "recent_query_count": recent_query_count,
}
