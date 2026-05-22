"""Bounded task queue."""
from __future__ import annotations

import asyncio

import pytest

from apex.api.backpressure import BoundedTaskQueue, QueueFull


@pytest.mark.asyncio
async def test_queue_accepts_and_drains():
    q = BoundedTaskQueue(max_size=4, worker_count=2)
    await q.start()
    counter = {"n": 0}

    async def task():
        counter["n"] += 1
        await asyncio.sleep(0.01)

    for _ in range(4):
        await q.submit(task)
    await asyncio.sleep(0.2)
    assert counter["n"] == 4
    await q.stop()


@pytest.mark.asyncio
async def test_queue_full_raises():
    q = BoundedTaskQueue(max_size=1, worker_count=0)

    async def slow():
        await asyncio.sleep(10.0)

    await q.submit(slow)
    with pytest.raises(QueueFull):
        await q.submit(slow)
