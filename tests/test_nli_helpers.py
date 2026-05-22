"""Faithfulness scorer helpers — sentence splitter + scorer behaviour with stubs."""

from __future__ import annotations

from apex.safety import nli


def test_split_sentences_filters_short_fragments():
    out = nli._split_sentences("Hi. This is a longer sentence. Ok.")
    assert all(len(s.split()) >= 3 for s in out)
    assert "This is a longer sentence." in out


def test_split_sentences_handles_punctuation():
    text = "Marbury established review. Brown overruled Plessy! Was this in 1954?"
    out = nli._split_sentences(text)
    assert len(out) == 3


def test_faithfulness_score_returns_zero_when_no_premises(monkeypatch):
    assert nli.faithfulness_score("any answer", []) == 0.0


def test_faithfulness_score_handles_model_errors(monkeypatch):
    class _Bad:
        def score(self, *_a, **_kw):
            raise RuntimeError("model down")

    monkeypatch.setattr(nli, "get_faithfulness_scorer", lambda: _Bad())
    # logged + degraded to 0.0, must not raise
    assert nli.faithfulness_score("answer", ["premise"]) == 0.0


def test_faithfulness_score_with_stubbed_cross_encoder(monkeypatch):
    class _FakeCE:
        def predict(self, pairs, *_a, **_kw):
            # entailment, neutral, contradiction triple — index 0 is entailment
            return [[0.9, 0.05, 0.05] for _ in pairs]

    class _FakeScorer(nli.FaithfulnessScorer):
        def _ensure(self):  # type: ignore[override]
            return _FakeCE()

    monkeypatch.setattr(nli, "get_faithfulness_scorer", lambda: _FakeScorer())
    score = nli.faithfulness_score(
        "This is one strong claim. And here is another claim.", ["supporting passage"]
    )
    assert 0.8 <= score <= 1.0
