"""In-flight request coalescing."""
from __future__ import annotations

import asyncio

import pytest

from apex.api import dedup


@pytest.mark.asyncio
async def test_two_callers_get_same_result():
    calls = {"n": 0}

    async def factory():
        calls["n"] += 1
        await asyncio.sleep(0.05)
        return calls["n"]

    a, b = await asyncio.gather(
        dedup.coalesce("default", "same-payload", factory),
        dedup.coalesce("default", "same-payload", factory),
    )
    assert a == b


@pytest.mark.asyncio
async def test_different_payloads_run_independently():
    counter = {"n": 0}

    def make_factory(tag: str):
        async def factory():
            counter["n"] += 1
            n = counter["n"]
            await asyncio.sleep(0.01)
            return (tag, n)

        return factory

    (a_tag, a_n), (b_tag, b_n) = await asyncio.gather(
        dedup.coalesce("default", "payload-a", make_factory("a")),
        dedup.coalesce("default", "payload-b", make_factory("b")),
    )
    assert a_tag == "a" and b_tag == "b"
    assert {a_n, b_n} == {1, 2}
