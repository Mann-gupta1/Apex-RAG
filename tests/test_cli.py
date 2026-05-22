"""CLI smoke tests via Typer's runner."""
from __future__ import annotations

from typer.testing import CliRunner

from apex.cli import app


def test_info_command_runs():
    runner = CliRunner()
    result = runner.invoke(app, ["info"])
    assert result.exit_code == 0, result.output
    assert "apex" in result.output.lower()


def test_help_lists_subcommands():
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for sub in ("info", "ingest", "search", "chat", "eval", "benchmark", "serve"):
        assert sub in result.output


def test_search_command_invokes_pipeline(monkeypatch):
    from apex.retrieval import pipeline as pipe
    from apex.schemas import SearchResponse

    captured = {}

    def fake_run_search(req):
        captured["req"] = req
        return SearchResponse(query=req.query, results=[], latency_ms=1, rewritten_queries=[])

    monkeypatch.setattr(pipe, "run_search", fake_run_search)
    runner = CliRunner()
    result = runner.invoke(app, ["search", "hello world"])
    assert result.exit_code == 0, result.output
    assert captured["req"].query == "hello world"


def test_info_shows_settings_values():
    runner = CliRunner()
    result = runner.invoke(app, ["info"])
    assert result.exit_code == 0
    assert "ollama" in result.output.lower()
    assert "vector store" in result.output.lower()
