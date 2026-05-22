"""Edge cases for the agent router that pair with the e2e graph."""
from __future__ import annotations

from apex.agent.router import classify


def test_deposition_triggers_video_only():
    d = classify("Where in the video deposition does Smith confirm clause 4.2?")
    assert d.kind == "visual"
    assert d.modalities is not None
    assert "video" in [m.value for m in d.modalities]


def test_short_factual_default():
    d = classify("Who decided Marbury v. Madison?")
    assert d.kind == "factual"


def test_compare_marker_analytical():
    d = classify("Compare Marbury v. Madison and Brown v. Board.")
    assert d.kind == "analytical"
