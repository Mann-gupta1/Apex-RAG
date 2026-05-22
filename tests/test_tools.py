"""Agent tool: safe SQL calculator."""

from __future__ import annotations

from apex.agent.tools import sql_calculator, web_fetch


def test_sql_calculator_basic_arithmetic():
    r = sql_calculator("(1 + 2) * 3")
    assert r.ok is True
    assert r.result == 9.0


def test_sql_calculator_rejects_calls():
    r = sql_calculator("__import__('os').system('whoami')")
    assert r.ok is False
    assert r.error


def test_sql_calculator_handles_division():
    r = sql_calculator("10 / 4")
    assert r.ok is True
    assert abs(r.result - 2.5) < 1e-9


def test_web_fetch_disabled_in_local_profile():
    r = web_fetch("https://example.com")
    assert r.ok is False
    assert "disabled" in (r.error or "")
