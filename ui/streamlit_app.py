"""Streamlit feedback / HITL app.

Lightweight companion to the Next.js control plane focused on the
human-in-the-loop deliverable. Reviewers paste a query, the app retrieves +
generates an answer, and the reviewer rates each chunk + the final answer.

Run with: ``make ui-streamlit``
"""
from __future__ import annotations

import streamlit as st

from apex.feedback.human_loop import record_feedback
from apex.schemas import ChatRequest, FeedbackRequest, SearchRequest

st.set_page_config(page_title="Apex RAG · Feedback", layout="wide")
st.title("Apex RAG — Human Feedback")
st.caption("Rate retrieved chunks and the final answer. Ratings feed reranker fine-tuning and DPO.")

tenant = st.sidebar.text_input("Tenant", value="default")
use_agent = st.sidebar.checkbox("Generate agent answer", value=True)
top_k = st.sidebar.slider("top_k", min_value=1, max_value=20, value=6)

with st.form("query"):
    query = st.text_input("Query", placeholder="Ask anything across your corpus")
    submitted = st.form_submit_button("Search")

if submitted and query.strip():
    from apex.retrieval.pipeline import run_search

    with st.spinner("Retrieving…"):
        sr = run_search(SearchRequest(query=query, tenant_id=tenant, top_k=top_k))
    st.subheader(f"Top {len(sr.results)} chunks · {sr.latency_ms} ms")

    for i, hit in enumerate(sr.results, 1):
        with st.expander(
            f"#{i}  [{hit.chunk.modality.value}]  {hit.chunk.provenance.source_uri}  · score {hit.score:.3f}"
        ):
            if hit.chunk.context_summary:
                st.markdown(f"_{hit.chunk.context_summary}_")
            st.write(hit.chunk.content[:1500])
            col_up, col_down = st.columns(2)
            with col_up:
                if st.button("Useful", key=f"up-{i}"):
                    record_feedback(
                        FeedbackRequest(
                            tenant_id=tenant,
                            query=query,
                            response=hit.chunk.content,
                            chunk_ids=[hit.chunk.id or ""],
                            rating=1,
                        )
                    )
                    st.success("Recorded as positive")
            with col_down:
                if st.button("Not useful", key=f"down-{i}"):
                    record_feedback(
                        FeedbackRequest(
                            tenant_id=tenant,
                            query=query,
                            response=hit.chunk.content,
                            chunk_ids=[hit.chunk.id or ""],
                            rating=-1,
                        )
                    )
                    st.warning("Recorded as negative")

    if use_agent:
        st.divider()
        st.subheader("Agent answer")
        try:
            from apex.agent.graph import run_agent

            with st.spinner("Running LangGraph agent…"):
                resp = run_agent(ChatRequest(query=query, tenant_id=tenant))
            st.markdown(resp.answer)
            if resp.faithfulness is not None:
                st.metric("NLI faithfulness", f"{resp.faithfulness:.2f}")
            st.write("Citations:")
            for c in resp.citations:
                st.write(f"- {c.source_uri} ({c.modality.value})")

            col_up, col_down = st.columns(2)
            with col_up:
                if st.button("Answer: Useful", key="answer-up"):
                    record_feedback(
                        FeedbackRequest(
                            tenant_id=tenant,
                            query=query,
                            response=resp.answer,
                            chunk_ids=[c.chunk_id for c in resp.citations],
                            rating=1,
                        )
                    )
                    st.success("Answer recorded as positive")
            with col_down:
                if st.button("Answer: Not useful", key="answer-down"):
                    record_feedback(
                        FeedbackRequest(
                            tenant_id=tenant,
                            query=query,
                            response=resp.answer,
                            chunk_ids=[c.chunk_id for c in resp.citations],
                            rating=-1,
                        )
                    )
                    st.warning("Answer recorded as negative")
        except Exception as exc:  # noqa: BLE001
            st.error(f"Agent unavailable (Ollama not running?): {exc}")
