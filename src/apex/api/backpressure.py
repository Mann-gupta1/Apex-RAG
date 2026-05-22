"""Bounded async queue for ingestion/long-running tasks.

When the queue is full callers receive a 429 with a Retry-After hint instead
of blocking. The queue worker runs in the same event loop as the app.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from apex.logging_config import logger


@dataclass
class QueueFull(Exception):
    retry_after_seconds: int = 5

    def __str__(self) -> str:  # pragma: no cover
        return f"queue is full; retry after {self.retry_after_seconds}s"


class BoundedTaskQueue:
    def __init__(self, max_size: int = 100, worker_count: int = 2) -> None:
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_size)
        self._worker_count = worker_count
        self._workers: list[asyncio.Task] = []
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        for i in range(self._worker_count):
            self._workers.append(asyncio.create_task(self._worker(i)))
        self._started = True
        logger.info("backpressure queue started workers={}", self._worker_count)

    async def stop(self) -> None:
        for w in self._workers:
            w.cancel()
        self._workers.clear()
        self._started = False

    async def _worker(self, idx: int) -> None:
        while True:
            task = await self._queue.get()
            try:
                await task()
            except Exception as exc:
                logger.error("worker {} task failed: {}", idx, exc)
            finally:
                self._queue.task_done()

    async def submit(self, task: Callable[[], Awaitable[None]]) -> None:
        try:
            self._queue.put_nowait(task)
        except asyncio.QueueFull as exc:
            raise QueueFull() from exc

    @property
    def size(self) -> int:
        return self._queue.qsize()

    @property
    def max_size(self) -> int:
        return self._queue.maxsize


queue = BoundedTaskQueue()
