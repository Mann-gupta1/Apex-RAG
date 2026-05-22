"""In-flight request coalescing.

If two identical (tenant, query) chat requests arrive concurrently we share
the result: the second caller awaits the first caller's future instead of
running retrieval twice.

We rely on ``dict.setdefault`` (atomic in CPython) to register the in-flight
future, so no asyncio.Lock is needed — and importantly it doesn't bind to a
specific event loop, which makes the module pytest-friendly.
"""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Awaitable, Callable
from typing import Any

_futures: dict[str, asyncio.Future] = {}


def _key(tenant_id: str, payload: str) -> str:
    return hashlib.sha256(f"{tenant_id}|{payload}".encode()).hexdigest()


async def coalesce(tenant_id: str, payload: str, factory: Callable[[], Awaitable[Any]]) -> Any:
    key = _key(tenant_id, payload)
    loop = asyncio.get_running_loop()
    new_fut: asyncio.Future = loop.create_future()
    fut = _futures.setdefault(key, new_fut)
    if fut is not new_fut:
        return await fut
    try:
        result = await factory()
        if not new_fut.done():
            new_fut.set_result(result)
        return result
    except Exception as exc:
        if not new_fut.done():
            new_fut.set_exception(exc)
        raise
    finally:
        _futures.pop(key, None)
