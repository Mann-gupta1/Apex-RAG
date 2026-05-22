"""Centralised runtime settings and config loader.

Reads `.env` (via pydantic-settings) and `config/*.yaml` (via PyYAML). Use
`get_settings()` from anywhere in the codebase; the result is cached.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT_DIR / "config"
DATA_DIR = ROOT_DIR / "data"


class Settings(BaseSettings):
    """Environment-backed settings. Values in `.env` override defaults here."""

    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- application ----
    apex_env: str = "local"
    apex_log_level: str = "INFO"
    apex_default_tenant: str = "default"

    # ---- postgres ----
    database_url: str = "postgresql+psycopg://apex:apex_dev_password@localhost:5432/apex_rag"

    # ---- redis ----
    redis_url: str = "redis://localhost:6379/0"

    # ---- ollama ----
    ollama_host: str = "http://localhost:11434"
    ollama_generation_model: str = "llama3.1:8b-instruct-q4_K_M"
    ollama_rewrite_model: str = "llama3.1:8b-instruct-q4_K_M"
    ollama_timeout_seconds: int = 120

    # ---- models ----
    text_embed_model: str = "BAAI/bge-base-en-v1.5"
    image_embed_model: str = "ViT-B-32"
    image_embed_pretrained: str = "laion2b_s34b_b79k"
    reranker_model: str = "BAAI/bge-reranker-base"
    nli_model: str = "cross-encoder/nli-deberta-v3-base"

    # ---- ASR ----
    whisper_model: str = "base"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    huggingface_token: str = ""

    # ---- vector store ----
    vector_store_driver: str = "pgvector"
    weaviate_url: str = "http://localhost:8080"

    # ---- phoenix ----
    phoenix_host: str = "localhost"
    phoenix_port: int = 6006
    phoenix_collector_endpoint: str = "http://localhost:6006/v1/traces"
    apex_otel_enabled: bool = True

    # ---- api ----
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    grpc_port: int = 50051
    graphql_path: str = "/graphql"
    rate_limit_per_minute: int = 60
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"

    # ---- eval ----
    eval_golden_path: str = "data/eval_golden.json"
    eval_baseline_path: str = "data/eval_baseline.json"
    eval_regression_threshold: float = 0.05

    # ---- feature flags ----
    enable_hyde: bool = True
    enable_stepback: bool = True
    enable_multi_query: bool = True
    enable_reranker: bool = True
    enable_contextual_retrieval: bool = True
    enable_pii_redaction: bool = True

    root_dir: Path = Field(default_factory=lambda: ROOT_DIR)
    data_dir: Path = Field(default_factory=lambda: DATA_DIR)
    config_dir: Path = Field(default_factory=lambda: CONFIG_DIR)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton settings object."""
    return Settings()


@lru_cache(maxsize=8)
def load_yaml_config(name: str) -> dict[str, Any]:
    """Load one of the YAML files in `config/` by stem (e.g. ``retrieval``)."""
    path = CONFIG_DIR / f"{name}.yaml"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def reset_caches() -> None:
    """Useful for tests."""
    get_settings.cache_clear()
    load_yaml_config.cache_clear()
