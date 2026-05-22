"""Apex RAG Typer CLI — single entry point for all operational tasks.

Examples
--------
    apex ingest --source data/raw_docs
    apex search "What did Smith say about the contract breach?"
    apex eval
    apex serve --reload
"""
from __future__ import annotations

from pathlib import Path

import typer

from apex.logging_config import logger
from apex.settings import get_settings

app = typer.Typer(
    add_completion=False,
    help="Apex RAG — Multi-Modal Enterprise Search command line interface.",
    no_args_is_help=True,
)


@app.command()
def info() -> None:
    """Show the resolved runtime configuration."""
    settings = get_settings()
    typer.echo(f"env:          {settings.apex_env}")
    typer.echo(f"db:           {settings.database_url}")
    typer.echo(f"redis:        {settings.redis_url}")
    typer.echo(f"ollama:       {settings.ollama_host} ({settings.ollama_generation_model})")
    typer.echo(f"text embed:   {settings.text_embed_model}")
    typer.echo(f"image embed:  {settings.image_embed_model} ({settings.image_embed_pretrained})")
    typer.echo(f"reranker:     {settings.reranker_model}")
    typer.echo(f"vector store: {settings.vector_store_driver}")


@app.command()
def ingest(
    source: Path = typer.Option(..., exists=True, help="File or directory to ingest"),
    tenant: str = typer.Option("default", help="Tenant id"),
    modality: str | None = typer.Option(None, help="Force a modality (text/image/video/audio)"),
) -> None:
    """Ingest documents/media into the vector store."""
    from apex.ingest.pipeline import ingest_path

    results = ingest_path(source, tenant_id=tenant, modality=modality)
    for r in results:
        logger.info("Ingested {} chunks from {}", r.chunks_created, r.source_uri)


@app.command()
def search(
    query: str = typer.Argument(..., help="Natural-language query"),
    tenant: str = typer.Option("default"),
    top_k: int = typer.Option(6),
) -> None:
    """Run a hybrid search and print results."""
    from apex.retrieval.pipeline import run_search
    from apex.schemas import SearchRequest

    resp = run_search(SearchRequest(query=query, tenant_id=tenant, top_k=top_k))
    typer.echo(f"\n[query] {resp.query}\nrewrites: {resp.rewritten_queries}\n")
    for i, r in enumerate(resp.results, 1):
        prov = r.chunk.provenance
        typer.echo(
            f"  {i:>2}. [{r.score:.3f}] {prov.modality.value:<5} "
            f"{prov.source_uri}{' p.' + str(prov.page) if prov.page else ''}"
        )
        typer.echo(f"      {r.chunk.content[:160].strip()}...")


@app.command()
def chat(
    query: str = typer.Argument(...),
    tenant: str = typer.Option("default"),
) -> None:
    """Run the LangGraph agent end-to-end and print the grounded answer."""
    from apex.agent.graph import run_agent
    from apex.schemas import ChatRequest

    resp = run_agent(ChatRequest(query=query, tenant_id=tenant))
    typer.echo(f"\n{resp.answer}\n")
    typer.echo("Citations:")
    for c in resp.citations:
        typer.echo(f"  - {c.source_uri} ({c.modality.value})")
    if resp.faithfulness is not None:
        typer.echo(f"\nfaithfulness: {resp.faithfulness:.2f}")


@app.command()
def eval(
    variant: str = typer.Option("apex", help="naive | apex"),
) -> None:
    """Run RAGAS evaluation against the golden set."""
    from apex.eval.ragas_runner import run_eval

    summary = run_eval(variant=variant)
    for m in summary.metrics:
        typer.echo(f"  {m.name:<22} {m.value:.4f}")


@app.command()
def benchmark() -> None:
    """Naive RAG vs Apex RAG comparison on the golden set."""
    from apex.scripts.benchmark import main as bench_main

    bench_main()


@app.command()
def serve(reload: bool = typer.Option(False, "--reload")) -> None:
    """Run the FastAPI app via uvicorn."""
    import uvicorn

    settings = get_settings()
    uvicorn.run("apex.api.main:app", host=settings.api_host, port=settings.api_port, reload=reload)


if __name__ == "__main__":
    app()
