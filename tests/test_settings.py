"""Settings + YAML config loader."""
from __future__ import annotations

from apex.settings import get_settings, load_yaml_config


def test_defaults_loadable():
    s = get_settings()
    assert s.text_embed_model.startswith("BAAI/")
    assert s.vector_store_driver in {"pgvector", "weaviate"}


def test_retrieval_yaml_loads():
    cfg = load_yaml_config("retrieval")
    assert "hybrid" in cfg
    assert cfg["hybrid"]["rrf_k"] >= 1


def test_eval_yaml_loads():
    cfg = load_yaml_config("eval")
    assert "ragas" in cfg
    assert isinstance(cfg["ragas"]["metrics"], list)


def test_missing_yaml_returns_empty():
    assert load_yaml_config("does_not_exist") == {}
