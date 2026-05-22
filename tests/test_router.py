"""Agent router classification."""

from __future__ import annotations

from apex.agent.router import classify
from apex.schemas import Modality


def test_factual_default():
    d = classify("Who was the chief justice in 1803?")
    assert d.kind in {"factual", "analytical"}


def test_analytical_marker():
    d = classify("Why does Marbury matter to modern constitutional law?")
    assert d.kind in {"analytical", "deep_research"}


def test_visual_routes_to_visual():
    d = classify("Find the exhibit photo of the Supreme Court building.")
    assert d.kind == "visual"
    assert Modality.IMAGE in (d.modalities or []) or Modality.VIDEO in (d.modalities or [])


def test_video_routes_with_video_modality():
    d = classify("At what timestamp does the deposition mention contract clause 4.2?")
    assert d.kind == "visual"
    assert d.modalities == [Modality.VIDEO]


def test_deep_research_for_long_synthesis():
    d = classify(
        "Summarise case law on judicial review from 1800 to 1950, compare "
        "and contrast with later cases, and identify the major trends and tradeoffs."
    )
    assert d.kind == "deep_research"
