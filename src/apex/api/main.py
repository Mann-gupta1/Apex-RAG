"""FastAPI app: REST + SSE + GraphQL mounted side-by-side.

Lifespan starts the bounded ingestion queue + Phoenix OTEL exporter.
CORS is wide open in dev; tighten via env var for production.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apex.api.backpressure import queue
from apex.api.graphql_schema import graphql_app
from apex.api.middleware import TenantAndRateLimitMiddleware
from apex.api.rest import router as rest_router
from apex.logging_config import logger
from apex.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    await queue.start()
    try:
        from apex.eval.phoenix_setup import maybe_init_phoenix

        maybe_init_phoenix()
    except Exception as exc:
        logger.debug("phoenix init skipped: {}", exc)
    logger.info("apex API ready on :{}", get_settings().api_port)
    yield
    await queue.stop()


def build_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Apex RAG",
        version="0.1.0",
        description="Multi-Modal Enterprise Search — REST + SSE + GraphQL",
        lifespan=lifespan,
    )

    cors_origins = os.environ.get("CORS_ORIGINS", "*").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(TenantAndRateLimitMiddleware)

    app.include_router(rest_router, prefix="/api")
    app.include_router(graphql_app, prefix=settings.graphql_path)

    @app.get("/")
    def root() -> dict:
        return {
            "name": "apex-rag",
            "version": "0.1.0",
            "docs": "/docs",
            "graphql": settings.graphql_path,
        }

    return app


app = build_app()
