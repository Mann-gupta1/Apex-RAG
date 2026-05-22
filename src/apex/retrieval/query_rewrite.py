"""Query understanding: HyDE, step-back prompting, multi-query decomposition.

Every rewrite calls Ollama. When Ollama is unreachable the helpers fall back
to returning the original query so the rest of the pipeline keeps working.
"""

from __future__ import annotations

from apex.logging_config import logger
from apex.settings import get_settings

_HYDE_PROMPT = (
    "You are an expert technical writer. Given the user's question, write ONE "
    "concise paragraph (3-5 sentences) that would plausibly appear as an answer in "
    "an authoritative document. Do not hedge. Be specific. Output only the paragraph.\n\n"
    "Question: {query}"
)

_STEPBACK_PROMPT = (
    "Given a specific user question, write ONE broader step-back question whose "
    "answer would provide the conceptual background needed to answer the original.\n"
    "Output only the step-back question.\n\n"
    "Original: {query}\nStep-back:"
)

_MULTI_QUERY_PROMPT = (
    "Decompose the user's question into {n} diverse sub-questions that, taken "
    "together, would help retrieve evidence for a comprehensive answer. "
    "Use one question per line, no numbering, no extra commentary.\n\n"
    "Question: {query}"
)


def _safe_generate(prompt: str, *, max_tokens: int = 200, temperature: float = 0.2) -> str | None:
    try:
        from apex.llm.ollama_client import generate

        return generate(prompt, max_tokens=max_tokens, temperature=temperature)
    except Exception as exc:
        logger.debug("query rewrite LLM call failed: {}", exc)
        return None


def hyde(query: str) -> str:
    """Hypothetical Document Embedding: generate a plausible answer paragraph."""
    if not get_settings().enable_hyde:
        return query
    out = _safe_generate(_HYDE_PROMPT.format(query=query), max_tokens=220)
    return out.strip() if out else query


def step_back(query: str) -> str:
    """Step-back prompting: return a more abstract question."""
    if not get_settings().enable_stepback:
        return query
    out = _safe_generate(_STEPBACK_PROMPT.format(query=query), max_tokens=80, temperature=0.0)
    return out.strip().splitlines()[0] if out else query


def multi_query(query: str, *, n: int = 3) -> list[str]:
    """Generate ``n`` diverse sub-queries for fan-out retrieval."""
    if not get_settings().enable_multi_query:
        return [query]
    raw = _safe_generate(_MULTI_QUERY_PROMPT.format(query=query, n=n), max_tokens=200)
    if not raw:
        return [query]
    queries = [line.strip("-* \t") for line in raw.splitlines() if line.strip()]
    queries = [q for q in queries if 3 <= len(q.split()) <= 40]
    return queries[:n] or [query]


def expand(query: str) -> list[str]:
    """Apply all enabled rewriters and return a deduplicated list of queries.

    The original query is always first; downstream code should treat the order
    as priority order.
    """
    out: list[str] = [query]
    h = hyde(query)
    if h and h != query:
        out.append(h)
    sb = step_back(query)
    if sb and sb not in out:
        out.append(sb)
    for mq in multi_query(query):
        if mq and mq not in out:
            out.append(mq)
    return out
