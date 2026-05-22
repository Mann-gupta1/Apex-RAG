# Apex RAG — 8-Week Consulting Timeline

> Bi-weekly partner demos. Daily standups internal. Weekly stakeholder
> update in `docs/sprint_updates.md`.

## Week 1 — Discovery & ingestion foundation
- Stakeholder interviews (litigators, partner, paralegals, IT).
- Stand up Postgres + pgvector + Redis in client VPC.
- Land PDF + plain-text ingestion path; first 200 docs indexed.
- Confirm data residency boundary and PII scrubbing requirements.
- **Exit criterion**: 50 docs queryable via the CLI.

## Week 2 — Image + audio ingestion, hybrid search
- Wire OpenCV / open_clip / pytesseract path.
- Wire faster-whisper for audio depositions.
- Implement BM25-via-tsvector + RRF.
- **Demo 1**: search inside a single matter from CLI.
- **Exit criterion**: 4 modalities ingested; hybrid retrieval working.

## Week 3 — Cross-encoder reranker + eval harness
- BGE-reranker-base online; benchmarks vs no-rerank.
- Build the first 30-question golden set with the paralegals.
- RAGAS runner + first regression baseline.
- **Exit criterion**: faithfulness +20 % vs naive RAG (measured).

## Week 4 — Video ingestion + HyDE + query rewriting
- PySceneDetect + ffmpeg keyframes + per-scene transcript binding.
- HyDE / step-back / multi-query rewrites via Ollama.
- **Demo 2**: rerank vs naive RAG side-by-side on golden set.
- **Exit criterion**: video deposition search with timestamps.

## Week 5 — LangGraph agent + citation grounding + NLI
- Router → retrieve → generate → critique → refine.
- Citation span extraction; UI mockups for highlighted quotes.
- **Exit criterion**: end-to-end agent answer with inline citations.

## Week 6 — Three API surfaces + multi-tenancy
- FastAPI REST + SSE chat stream.
- Strawberry GraphQL with the same surface.
- gRPC proto + server.
- `X-Tenant-Id` middleware + Redis token bucket + audit log.
- **Demo 3**: integration test from a partner's internal service via gRPC.
- **Exit criterion**: tenant isolation enforced; audit log populated.

## Week 7 — UI polish, HITL, deep research
- Next.js control plane (Search / Chat / Eval / Admin) wired to the API.
- Streamlit feedback app for paralegals.
- Deep-research agent for partners ("draft me a memo on case law X").
- **Demo 4**: control plane walkthrough; live feedback → DPO dataset.
- **Exit criterion**: paralegals using the tool daily; 100+ feedbacks captured.

## Week 8 — Hardening, runbook, handoff
- Circuit breaker, degraded mode, dedup, backpressure.
- Phoenix tracing wired in; drift detector cron.
- **Demo 5**: final partner readout with metrics + roadmap.
- **Exit criterion**: runbook signed off; CI gates production deploys.
