"""Prompt templates used by the agent graph and the deep-research workflow.

Centralised so they can be A/B-tested + version-controlled. Each prompt
strives to be deterministic, citation-friendly, and short enough for a small
local model (llama3.1:8b) to follow reliably.
"""
from __future__ import annotations

SYSTEM_GROUNDED = (
    "You are Apex, a grounded legal/compliance research assistant. "
    "Answer ONLY using the provided context. "
    "If the context does not contain the answer, reply exactly: "
    "'The provided context does not contain enough information to answer this.' "
    "Cite sources inline using [#] referring to the numbered context items. "
    "Be concise and factual."
)

ANSWER_PROMPT = """\
{system}

# Question
{question}

# Context
{context}

# Instructions
- Use ONLY the context above.
- Cite each non-trivial claim with [#] referring to the context number.
- If the question requires synthesis across modalities (e.g. video + document),
  reference both with their context numbers.
- Keep the answer under 200 words.

# Answer
"""

CRITIQUE_PROMPT = """\
You are an evaluator. Given the question, the retrieved context, and the
candidate answer, judge whether the answer is fully supported by the context.

Question: {question}

Context:
{context}

Candidate answer:
{answer}

Reply with ONE of:
- FAITHFUL: <one short reason>
- UNFAITHFUL: <missing or unsupported claim> | <what to search for next>
"""

DEEP_RESEARCH_PLAN_PROMPT = """\
You are planning a research memo on the following request.

Request: {query}

Decompose this into between 5 and 8 specific sub-questions that, taken
together, would let you produce a thorough memo. Output one sub-question per
line, no numbering, no commentary.
"""

DEEP_RESEARCH_GAP_PROMPT = """\
You are reviewing the current research notes for completeness.

Original request: {query}

Sub-questions answered so far:
{answered}

Current evidence summary:
{evidence}

What ONE additional sub-question would most improve the memo? Output only the
question, or the single word DONE if no further search is required.
"""

DEEP_RESEARCH_SYNTHESIS_PROMPT = """\
You are writing the final memo.

Original request: {query}

Evidence:
{evidence}

Write a memo with these sections, in markdown:

## Executive summary
(3-5 sentences)

## Key findings
(bullet list, each finding cites a source with [#])

## Risks and open questions
(bullet list)

## Recommendations
(numbered list, 2-4 items)

Only use the evidence above. Use [#] citations.
"""
