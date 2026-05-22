"""FastAPI middleware: tenant resolution, rate limit, audit context, latency header."""
from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from apex.logging_config import logger
from apex.settings import get_settings

try:
    import redis  # type: ignore
except ImportError:  # pragma: no cover
    redis = None  # type: ignore


_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is False:
        return None
    if _redis_client is None:
        if redis is None:
            _redis_client = False
            return None
        try:
            _redis_client = redis.Redis.from_url(get_settings().redis_url, decode_responses=True)
            _redis_client.ping()
        except Exception as exc:
            logger.debug("redis unavailable; rate limit in-memory: {}", exc)
            _redis_client = False
            return None
    return _redis_client


_inmem_counters: dict[str, list[float]] = {}


def resolve_tenant(request: Request) -> str:
    """Tenant resolution order: ``X-Tenant-Id`` header → JWT claim → default."""
    settings = get_settings()
    header = request.headers.get("X-Tenant-Id")
    if header:
        return header
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        try:
            from jose import jwt

            token = auth.split(" ", 1)[1]
            data = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
            tid = data.get("tenant_id")
            if tid:
                return str(tid)
        except Exception as exc:
            logger.debug("JWT decode failed: {}", exc)
    return settings.apex_default_tenant


class TenantAndRateLimitMiddleware(BaseHTTPMiddleware):
    """Sets ``request.state.tenant_id`` and applies a per-tenant token bucket."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        started = time.perf_counter()
        tenant_id = resolve_tenant(request)
        request.state.tenant_id = tenant_id

        whitelisted = ("/health", "/", "/metrics", "/docs", "/openapi.json", "/redoc")
        if request.url.path not in whitelisted and not _check_rate(tenant_id):
            # Raising HTTPException from a Starlette middleware bypasses
            # FastAPI's exception handler, so we return a JSONResponse.
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": "5", "X-Tenant-Id": tenant_id},
                content={
                    "error": "rate_limit_exceeded",
                    "tenant_id": tenant_id,
                    "retry_after_seconds": 5,
                },
            )

        response = await call_next(request)
        response.headers["X-Tenant-Id"] = tenant_id
        response.headers["X-Latency-Ms"] = str(int((time.perf_counter() - started) * 1000))
        return response


def _check_rate(tenant_id: str, *, capacity: int | None = None, window_seconds: int = 60) -> bool:
    settings = get_settings()
    capacity = capacity or settings.rate_limit_per_minute
    now = time.time()
    client = _get_redis()
    if client:
        key = f"rl:{tenant_id}:{int(now // window_seconds)}"
        try:
            count = client.incr(key)
            if count == 1:
                client.expire(key, window_seconds + 1)
            return int(count) <= capacity
        except Exception as exc:
            logger.debug("redis rate-limit failed; fallback to in-memory: {}", exc)
    buf = _inmem_counters.setdefault(tenant_id, [])
    buf[:] = [t for t in buf if now - t < window_seconds]
    if len(buf) >= capacity:
        return False
    buf.append(now)
    return True
