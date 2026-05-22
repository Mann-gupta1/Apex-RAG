"""Pydantic data models shared across ingestion, retrieval, agent, and API layers."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class Modality(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"


class Provenance(BaseModel):
    """Where a chunk came from. Always carried alongside the chunk."""

    source_uri: str
    modality: Modality
    page: int | None = None
    bbox: tuple[float, float, float, float] | None = None
    timestamp_start: float | None = None  # seconds for audio/video
    timestamp_end: float | None = None
    speaker: str | None = None
    scene_index: int | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class Chunk(BaseModel):
    id: str | None = None
    tenant_id: str = "default"
    modality: Modality
    content: str
    context_summary: str | None = None
    provenance: Provenance
    text_embedding: list[float] | None = None
    image_embedding: list[float] | None = None


class RetrievedChunk(BaseModel):
    chunk: Chunk
    score: float
    dense_score: float | None = None
    sparse_score: float | None = None
    rerank_score: float | None = None
    fusion_rank: int | None = None


class SearchRequest(BaseModel):
    query: str
    tenant_id: str = "default"
    modalities: list[Modality] | None = None
    top_k: int = 6
    use_rerank: bool | None = None
    use_hyde: bool | None = None
    use_multi_query: bool | None = None


class SearchResponse(BaseModel):
    query: str
    rewritten_queries: list[str] = Field(default_factory=list)
    results: list[RetrievedChunk]
    latency_ms: int
    cache_hit: bool = False


class Citation(BaseModel):
    chunk_id: str
    source_uri: str
    modality: Modality
    span: tuple[int, int] | None = None  # char offsets into chunk content
    quote: str | None = None
    timestamp_start: float | None = None
    page: int | None = None


class ChatRequest(BaseModel):
    query: str
    tenant_id: str = "default"
    history: list[dict[str, str]] = Field(default_factory=list)
    modalities: list[Modality] | None = None


class AgentStep(BaseModel):
    node: str
    detail: dict[str, Any] = Field(default_factory=dict)
    at: datetime = Field(default_factory=datetime.utcnow)


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    faithfulness: float | None = None
    steps: list[AgentStep] = Field(default_factory=list)
    latency_ms: int
    cache_hit: bool = False


class FeedbackRequest(BaseModel):
    tenant_id: str = "default"
    query: str
    response: str
    chunk_ids: list[str]
    rating: int = Field(ge=-1, le=1)  # -1 down, 0 neutral, +1 up
    comment: str | None = None


class IngestionResult(BaseModel):
    source_uri: str
    modality: Modality
    chunks_created: int
    job_id: str | None = None


class EvalMetric(BaseModel):
    name: str
    value: float


class EvalRunSummary(BaseModel):
    run_id: str
    started_at: datetime
    finished_at: datetime
    metrics: list[EvalMetric]
    variant: str | None = None


def _validate_uuid(value: str) -> str:
    UUID(value)
    return value
