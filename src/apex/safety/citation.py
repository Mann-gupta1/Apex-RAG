"""Citation grounding: map answer spans back to chunks with char offsets.

Strategy: for each retrieved chunk, find the longest common contiguous
sub-sequence between the answer and the chunk (tokenwise, with min length).
We use difflib's ``SequenceMatcher`` over lowercased word tokens which is
robust to mild paraphrasing and avoids dragging in heavy NLP deps.
"""
from __future__ import annotations

from collections.abc import Sequence
from difflib import SequenceMatcher

from apex.schemas import Citation, RetrievedChunk

_MIN_OVERLAP_TOKENS = 6
_PUNCT = ".,;:?!\"'()[]{}"


def _norm(token: str) -> str:
    return token.lower().strip(_PUNCT)


def _normalised_tokens(text: str) -> list[str]:
    return [t for t in (_norm(tok) for tok in text.split()) if t]


def _best_span(answer: str, chunk: str) -> tuple[int, int, str] | None:
    a_norm = _normalised_tokens(answer)
    c_raw = chunk.split()
    c_norm = [_norm(t) for t in c_raw]
    if len(a_norm) < _MIN_OVERLAP_TOKENS or len(c_norm) < _MIN_OVERLAP_TOKENS:
        return None
    matcher = SequenceMatcher(a=a_norm, b=c_norm, autojunk=False)
    match = matcher.find_longest_match(0, len(a_norm), 0, len(c_norm))
    if match.size < _MIN_OVERLAP_TOKENS:
        return None
    # Find the character offsets of the matched span in the ORIGINAL chunk text.
    quote_tokens = c_raw[match.b : match.b + match.size]
    needle = " ".join(quote_tokens)
    char_start = chunk.find(needle)
    if char_start < 0:
        # Fall back to a normalised lookup if exact whitespace doesn't match.
        normalised_chunk = " ".join(c_raw)
        idx = normalised_chunk.find(needle)
        if idx < 0:
            return None
        char_start = idx
    return char_start, char_start + len(needle), needle


def extract_citations(answer: str, hits: Sequence[RetrievedChunk]) -> list[Citation]:
    """For each hit, attempt to find a quote-able span in the answer."""
    citations: list[Citation] = []
    for h in hits:
        cid = h.chunk.id or h.chunk.provenance.source_uri
        span = _best_span(answer, h.chunk.content)
        if span is None:
            citations.append(
                Citation(
                    chunk_id=cid,
                    source_uri=h.chunk.provenance.source_uri,
                    modality=h.chunk.modality,
                    page=h.chunk.provenance.page,
                    timestamp_start=h.chunk.provenance.timestamp_start,
                )
            )
            continue
        start, end, quote = span
        citations.append(
            Citation(
                chunk_id=cid,
                source_uri=h.chunk.provenance.source_uri,
                modality=h.chunk.modality,
                span=(start, end),
                quote=quote,
                page=h.chunk.provenance.page,
                timestamp_start=h.chunk.provenance.timestamp_start,
            )
        )
    return citations
