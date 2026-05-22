"""Embedding quantization math (no model deps required)."""
from __future__ import annotations

import numpy as np

from apex.scripts.quantize_embeddings import (
    _hamming,
    dequantize_int8,
    quantize_binary,
    quantize_int8,
    recall_at_k,
)


def test_int8_quantize_dequantize_round_trip():
    rng = np.random.default_rng(7)
    x = rng.standard_normal((8, 16)).astype(np.float32)
    q, scale = quantize_int8(x)
    assert q.dtype == np.int8
    deq = dequantize_int8(q, scale)
    # Tolerance because of 7-bit quant
    assert np.allclose(deq, x, atol=0.05)


def test_binary_quantize_shape_and_values():
    rng = np.random.default_rng(0)
    x = rng.standard_normal((4, 16)).astype(np.float32)
    b = quantize_binary(x)
    assert b.shape == x.shape
    assert set(np.unique(b).tolist()) <= {0, 1}


def test_hamming_self_distance_is_zero():
    a = np.array([[1, 0, 1, 1], [0, 0, 1, 0]], dtype=np.uint8)
    d = _hamming(a, a)
    assert np.allclose(np.diag(d), 0)


def test_hamming_off_diagonal_positive():
    a = np.array([[1, 0, 1, 1]], dtype=np.uint8)
    b = np.array([[0, 0, 1, 1]], dtype=np.uint8)
    d = _hamming(a, b)
    assert d[0, 0] == 1


def test_recall_at_k_perfect():
    gold = np.array([[1, 2, 3, 4, 5]])
    cand = np.array([[1, 2, 3, 4, 5]])
    assert recall_at_k(gold, cand, k=5) == 1.0


def test_recall_at_k_partial():
    gold = np.array([[1, 2, 3, 4, 5]])
    cand = np.array([[1, 2, 9, 8, 7]])
    assert recall_at_k(gold, cand, k=5) == 0.4
