# Sprint updates

Public summaries shared with the client at the end of each two-week sprint.
Detailed engineering notes live in private channels; this file holds the
stakeholder-facing narrative.

---

## Sprint 1 (weeks 1-2): foundations

**Status**: green
**Headline**: PDF + image + audio + video ingestion live; hybrid search returning sensible results.

**What we shipped**
- Postgres + pgvector + Redis on the client VPC (single AZ for the pilot).
- Ingestion pipeline for all four modalities. Initial corpus: 800 PDFs,
  120 deposition transcripts, 60 exhibit images, 24 audio recordings.
- BM25-via-`tsvector` + dense fusion (RRF).
- First demo: live search inside the active matter.

**What we learned**
- The deposition transcripts have inconsistent speaker labels. Diarization is
  unblocked; transcript labels are a separate ingestion fix.
- Two of the older PDFs are image-only. Plan: OCR via Tesseract (already wired).

**Next sprint**: reranker, golden set, first benchmark.

---

## Sprint 2 (weeks 3-4): retrieval quality

**Status**: green
**Headline**: faithfulness up 32 % against the new 30-question golden set.

**What we shipped**
- BGE-reranker-base cross-encoder.
- HyDE / step-back / multi-query rewriting.
- Video scene detection + per-scene transcript binding (so "what did Smith
  say at 12:34" works).
- RAGAS runner + first regression baseline checked into `data/eval_baseline.json`.

**Numbers (vs naive baseline)**
- Recall@10: 0.62 → 0.89 (+43 %).
- Faithfulness: 0.71 → 0.94 (+32 %).
- P50 latency: 180 ms → 320 ms (trade-off, accepted).

**Risk**: Ollama 8B quality on the critique step is a soft ceiling. We've
documented an upgrade path to GPT-4o-mini for non-sensitive tenants.

**Next sprint**: agent + citation grounding + APIs.

---

## Sprint 3 (weeks 5-6): agent + integration

**Status**: green
**Headline**: LangGraph agent with NLI critique; REST + gRPC + GraphQL all live.

**What we shipped**
- Agent state machine with refine-on-failure loop.
- Citation grounding (every claim → page or timestamp).
- Three API surfaces with shared Pydantic models.
- `X-Tenant-Id` middleware, per-tenant rate limit, audit log.

**Field test**: paralegals piloted on three active matters. Reported 30-40 %
time savings on the initial research phase.

**Next sprint**: UI, HITL, hardening.

---

## Sprint 4 (weeks 7-8): UX + hardening + handoff

**Status**: green
**Headline**: Pilot complete. 95 % citation accuracy human-graded; runbook signed.

**What we shipped**
- Next.js control plane (Search / Chat / Eval / Admin).
- Streamlit feedback app; 612 rated responses captured.
- Production hardening: circuit breaker, degraded mode, dedup, backpressure.
- Phoenix tracing for every chat span.
- Runbook + ADR pack.

**Final partner readout deck**: `docs/blog_post.md` covers the public version.

**What's next** (phase 2 proposal):
- User-level RBAC and matter-level access control.
- Reranker fine-tune on the 612 collected feedbacks.
- Weaviate driver evaluation at 10× scale.
- Drift detector wired into the eval dashboard.
