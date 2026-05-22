"""End-to-end demo: ingest → search → agent answer, all on one terminal.

Designed to be the script behind the 5-minute screen-recording asset
described in ``docs/demo_script.md``.
"""
from __future__ import annotations

import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from apex.ingest.pipeline import ingest_path
from apex.schemas import ChatRequest, SearchRequest

console = Console()


DEMO_QUERIES = [
    "What is the principle of judicial review established in Marbury v. Madison?",
    "Compare the legal reasoning in Marbury v. Madison and Brown v. Board of Education.",
    "What did witness Smith say about the contract breach in case 24-CV-1234?",
    "Which exhibit conflicts with witness Smith's testimony?",
]


def main() -> int:
    console.rule("[bold]Apex RAG — demo")
    raw = Path("data/raw_docs")
    if not any(raw.rglob("*")):
        console.print("[yellow]No raw docs found; run `make seed` or `python -m apex.scripts.download_demo_corpus` first.[/]")
        return 1

    console.print(Panel(f"Ingesting [b]{raw}[/]", title="Step 1 / 3"))
    results = ingest_path(raw)
    table = Table(title="Ingestion summary")
    table.add_column("source")
    table.add_column("modality")
    table.add_column("chunks")
    for r in results:
        table.add_row(Path(r.source_uri).name, r.modality.value, str(r.chunks_created))
    console.print(table)

    console.print(Panel("Searching", title="Step 2 / 3"))
    from apex.retrieval.pipeline import run_search

    for q in DEMO_QUERIES:
        sr = run_search(SearchRequest(query=q, top_k=3))
        console.rule(f"[cyan]{q}")
        for i, hit in enumerate(sr.results, 1):
            console.print(f"  [b]{i}.[/] score={hit.score:.3f}  {hit.chunk.provenance.source_uri}")
            console.print(f"     {hit.chunk.content[:160].strip()}...")

    console.print(Panel("Agentic answer (LangGraph + NLI)", title="Step 3 / 3"))
    try:
        from apex.agent.graph import run_agent

        resp = run_agent(ChatRequest(query=DEMO_QUERIES[0]))
        console.print(Panel(resp.answer, title="answer"))
        if resp.faithfulness is not None:
            console.print(f"NLI faithfulness: [b]{resp.faithfulness:.2f}[/]")
        console.print("Citations:")
        for c in resp.citations[:6]:
            console.print(f"  - {c.source_uri} ({c.modality.value})")
    except Exception as exc:
        console.print(f"[yellow]agent call failed — likely Ollama unavailable: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
