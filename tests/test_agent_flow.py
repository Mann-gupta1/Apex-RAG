"""LangGraph agent end-to-end with mocked Ollama + NLI + FakeVectorStore."""

from __future__ import annotations

import pytest

from apex.agent import graph as agent_graph
from apex.schemas import ChatRequest, Chunk, Modality, Provenance
from tests.fakes import FakeVectorStore, install_fakes


@pytest.fixture
def seeded(monkeypatch) -> FakeVectorStore:
    store = install_fakes(monkeypatch)
    store.upsert(
        [
            Chunk(
                id="c1",
                modality=Modality.TEXT,
                content="Marbury v. Madison established judicial review in 1803.",
                provenance=Provenance(source_uri="m.pdf", modality=Modality.TEXT, page=1),
            )
        ]
    )
    # Stub LLM + safety modules.
    monkeypatch.setattr(
        agent_graph, "generate", lambda *a, **k: "Marbury established judicial review in 1803 [1]."
    )
    monkeypatch.setattr(agent_graph, "faithfulness_score", lambda *a, **k: 0.95)
    monkeypatch.setattr(
        agent_graph,
        "stream",
        lambda *a, **k: iter(["Marbury ", "established ", "judicial ", "review."]),
    )
    return store


def test_run_agent_produces_answer_and_citations(seeded):
    resp = agent_graph.run_agent(ChatRequest(query="What did Marbury establish?"))
    assert "marbury" in resp.answer.lower()
    assert resp.faithfulness == 0.95
    assert len(resp.steps) >= 3  # router, retrieve, generate, critique
    # at least one citation refers to the seeded chunk
    assert any(c.source_uri == "m.pdf" for c in resp.citations)


def test_agent_refines_when_unfaithful(monkeypatch, seeded):
    monkeypatch.setattr(agent_graph, "faithfulness_score", lambda *a, **k: 0.5)

    def fake_generate(prompt, *_args, **_kwargs):
        # Critique prompt mentions evaluator + Candidate answer; answer prompt does not.
        if "Candidate answer" in prompt or "evaluator" in prompt.lower():
            return "UNFAITHFUL: needs more context | when was Marbury decided?"
        return "attempt answer with citation [1]."

    monkeypatch.setattr(agent_graph, "generate", fake_generate)
    resp = agent_graph.run_agent(ChatRequest(query="What did Marbury establish?"))
    nodes = [s.node for s in resp.steps]
    assert "refine" in nodes


def test_stream_agent_yields_router_retrieved_done(seeded):
    events = list(agent_graph.stream_agent(ChatRequest(query="What did Marbury establish?")))
    kinds = [ev["event"] for ev in events]
    assert "router" in kinds
    assert "retrieved" in kinds
    assert "token" in kinds
    assert kinds[-1] == "done"
    final = events[-1]
    assert final["latency_ms"] >= 0
    assert isinstance(final["citations"], list)


def test_agent_routes_deep_research(monkeypatch, seeded):
    called = {"deep": False}

    def fake_deep(*_a, **_kw):
        called["deep"] = True
        from apex.agent.deep_research import ResearchReport

        return ResearchReport(query="q", notes=[], memo="memo body with citation", citations=[])

    monkeypatch.setattr("apex.agent.deep_research.deep_research", fake_deep)
    resp = agent_graph.run_agent(
        ChatRequest(
            query="Summarise and compare across all the cases and identify trends and tradeoffs in detail"
        )
    )
    assert called["deep"] is True
    assert "memo" in resp.answer.lower()
