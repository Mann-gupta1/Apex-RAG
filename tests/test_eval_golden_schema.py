"""Golden eval set schema validation (50 items)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

GOLDEN_PATH = Path(__file__).resolve().parents[1] / "data" / "eval_golden.json"
REQUIRED_ITEM_KEYS = {"id", "question", "ground_truth", "expected_modalities", "expected_sources"}


@pytest.fixture(scope="module")
def golden() -> dict:
    assert GOLDEN_PATH.exists(), f"missing {GOLDEN_PATH}"
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def test_golden_has_fifty_items(golden: dict):
    items = golden["items"]
    assert len(items) == 50, f"expected 50 items, got {len(items)}"


def test_golden_item_schema(golden: dict):
    ids: list[str] = []
    for item in golden["items"]:
        missing = REQUIRED_ITEM_KEYS - set(item)
        assert not missing, f"{item.get('id')}: missing keys {missing}"
        assert item["id"].startswith("Q")
        ids.append(item["id"])
        assert isinstance(item["question"], str) and item["question"].strip()
        assert isinstance(item["ground_truth"], str) and item["ground_truth"].strip()
        assert isinstance(item["expected_modalities"], list) and item["expected_modalities"]
        assert isinstance(item["expected_sources"], list)
    assert len(ids) == len(set(ids)), "duplicate ids in golden set"
