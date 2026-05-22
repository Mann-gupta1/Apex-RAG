# Apex RAG

> Multi-Modal Enterprise Search with a Consulting Mindset.
> Text + Image + Video + Audio · Hybrid Retrieval · Cross-Encoder Reranking · LangGraph Agent · RAGAS Eval · REST + gRPC + GraphQL · Fully Local.

Most RAG demos stop at "chat with your PDF." **Apex RAG** simulates a real enterprise engagement: a legal/compliance team searching across documents, video depositions, images, and audio — with provenance, evaluation, and measurable business outcomes.

---

## Why this exists

| Most demos | Apex RAG |
|---|---|
| One modality (text) | Text + image + video + audio with timestamp/page/bbox provenance |
| Single-vector top-k | Hybrid (dense + BM25 + RRF) + HyDE rewriting + cross-encoder rerank |
| `gpt-4o.invoke(prompt)` | LangGraph router → retrieve → rerank → generate → NLI critique → refine |
| `eval.py` printing 3 scores | RAGAS + Phoenix tracing + regression guard + drift detection |
| `app.py` (Streamlit) | FastAPI + gRPC + GraphQL + Next.js control plane + Streamlit feedback |
| `cool_demo.gif` | Case study + ADRs + sprint timeline + benchmark vs naive RAG |

---

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the deep dive. Top-level:

```
ingest (pdf/image/video/audio) → multimodal chunking → embeddings
        ↓
pgvector (or Weaviate) ← hybrid (dense + BM25 + RRF)
        ↓
query rewrite (HyDE / step-back / multi-query) → cross-encoder rerank
        ↓
LangGraph agent (router → retrieve → generate → NLI critique → refine)
        ↓
FastAPI REST + SSE  ·  gRPC streaming  ·  Strawberry GraphQL
        ↓
Next.js control plane (Search · Chat · Eval · Admin)  +  Streamlit feedback
        ↓
RAGAS · Phoenix traces · regression guard · drift detection · HITL feedback → DPO
```

---

## Quickstart (fully local, free)

**Requires Docker + ~8GB RAM (~10GB disk for models).** Run `make setup` to start Postgres, Redis, Ollama, and Phoenix.

Prerequisites: Docker Desktop, Python 3.10+, Node 20+, ~10 GB free disk for models.

```bash
# 1. clone + bootstrap
cp .env.example .env
make setup            # venv, compose, pull-models, alembic upgrade head, demo corpus seed

# 2. (first search) ensure generation model is present
ollama pull llama3.1:8b-instruct-q4_K_M   # or: make pull-models

# 3. ingest — place docs in data/raw_docs/, or use bundled samples
make ingest-sample    # 3 sample text files in data/sample_docs/
make ingest           # full demo corpus after make seed

# 4. start the API (REST + GraphQL + SSE) on :8000
make api

# 5. in another shell, start the Next.js control plane on :3000
make ui-next

# 6. benchmark — live stack, or offline snapshot
make benchmark        # live: Postgres + Ollama + ingested index
make benchmark-mock   # offline: writes docs/benchmark.md from committed snapshot
```

> Windows: use `./scripts/setup.ps1` instead of `make setup`. Everything else uses `make` from Git Bash / WSL, or run the commands shown by `make help` directly.

---

## Storage constraint note

All components are **fully implemented and syntactically validated**.  
Due to local storage constraints, the live stack (Postgres + Redis + Ollama + Phoenix)  
was not run end-to-end on this machine.

**To run:**

1. `docker compose up -d` (requires ~8GB RAM, ~10GB disk)
2. `ollama pull llama3.1:8b-instruct-q4_K_M` (or `make pull-models`)
3. `alembic upgrade head` (or `make migrate`)
4. `make ingest`
5. `make benchmark`

All scripts, configs, and migrations are production-ready.

---

## Validation checklist (portfolio)

| Item | What you do | How you prove it |
|------|-------------|------------------|
| Live stack | `docker-compose.yml` + `make setup` | README quickstart; `make services` |
| DB migrations | Alembic in `alembic/versions/` | `make validate` (offline); `make migrate` (live) |
| Corpus ingestion | `make ingest` / `make ingest-sample` | 3 samples in `data/sample_docs/` |
| Ollama model | `scripts/pull_models.sh` | `make pull-models`; README model pull |
| Benchmark | `make benchmark-mock` (offline) / `make benchmark` (live) | `docs/benchmark.md` + `data/eval_runs/*.json` |
| gRPC test | `tests/test_grpc_integration.py` | Mock test passes; live test `@pytest.mark.skip` |
| Golden set 50 | `data/eval_golden.json` | `tests/test_eval_golden_schema.py` |

Offline validation (no Docker):

```bash
make validate
make benchmark-mock
pytest tests/test_eval_golden_schema.py tests/test_grpc_integration.py -v
```

---

## Repository layout

```
apex-rag/
├── src/apex/                    # the python package
│   ├── ingest/                  # pdf, image, video, audio loaders
│   ├── chunking/                # multimodal + contextual retrieval chunker
│   ├── embedding/               # bge / open-clip / whisper loaders
│   ├── retrieval/               # hybrid, rerank, query_rewrite, contextual, adaptive
│   ├── agent/                   # LangGraph router/graph/tools/deep_research
│   ├── safety/                  # citation grounding, NLI faithfulness, PII redaction
│   ├── eval/                    # RAGAS, phoenix, regression guard, drift
│   ├── api/                     # FastAPI REST, gRPC server, GraphQL schema, middleware
│   ├── feedback/                # thumbs up/down + DPO / reranker fine-tune dataset
│   └── scripts/                 # benchmark, demo corpus downloader, hnsw tuner, quantize
├── vector_db/
│   ├── pgvector/                # init.sql + driver
│   └── weaviate/                # alternative driver
├── proto/apex.proto             # gRPC contract
├── alembic/                     # schema migrations
├── config/                      # retrieval.yaml + eval.yaml
├── data/                        # raw_docs, processed_chunks, eval_golden.json
├── ui/
│   ├── app/                     # Next.js 14 control plane
│   └── streamlit_app.py         # human feedback loop
├── docs/                        # case_study, architecture, ADRs, blog, demo_script
├── notebooks/                   # benchmark report, hnsw sweep
├── infra/terraform/             # multi-region (documented, not applied)
├── tests/
└── .github/workflows/           # PR + build
```

---

## Component status

| Component                       | Status | Notes |
|--------------------------------|:------:|-------|
| PDF/text ingestion (unstructured) | ✅ | `src/apex/ingest/pdf.py` |
| Image embeddings (open-clip)    | ✅ | `src/apex/ingest/image.py` |
| Video scene detection           | ✅ | `src/apex/ingest/video.py` (PySceneDetect) |
| Audio transcription + diarization | ✅ | `src/apex/ingest/audio.py` (faster-whisper + pyannote) |
| pgvector + Weaviate drivers     | ✅ | pluggable `VectorStore` protocol |
| Hybrid search (dense + BM25 + RRF) | ✅ | `src/apex/retrieval/hybrid.py` |
| Cross-encoder rerank            | ✅ | BGE-reranker-base |
| HyDE / step-back / multi-query  | ✅ | local Ollama for rewrites |
| LangGraph agent + NLI critique  | ✅ | `src/apex/agent/graph.py` |
| RAGAS + Phoenix + regression guard | ✅ | `src/apex/eval/*` |
| FastAPI REST + SSE              | ✅ | `src/apex/api/rest.py` |
| gRPC streaming                  | ✅ | `proto/apex.proto` + `grpc_server.py` |
| Strawberry GraphQL              | ✅ | `src/apex/api/graphql_schema.py` |
| Multi-tenant + rate limit + audit | ✅ | `src/apex/api/middleware.py` |
| PII redaction (Presidio)        | ✅ | `src/apex/safety/pii_redact.py` |
| Request dedup + backpressure    | ✅ | `src/apex/api/dedup.py`, `backpressure.py` |
| Degraded mode (LLM down)        | ✅ | `src/apex/api/degraded.py` |
| Next.js control plane           | ✅ | `ui/app/` |
| Streamlit feedback loop         | ✅ | `ui/streamlit_app.py` |
| Benchmark notebook              | ✅ | `notebooks/benchmark_report.ipynb` |
| Case study + ADRs + blog post   | ✅ | `docs/` |

---

## Make targets

```
make setup            # one-shot bootstrap (compose, models, migrate, seed)
make validate         # offline Alembic revision check
make pull-models      # ollama pull llama3.1:8b-instruct-q4_K_M
make services         # start docker-compose (postgres, redis, ollama, phoenix)
make ingest           # ingest data/raw_docs
make ingest-sample    # ingest data/sample_docs (3 bundled samples)
make api              # FastAPI on :8000
make api-grpc         # gRPC on :50051
make ui-next          # Next.js on :3000
make ui-streamlit     # Streamlit feedback on :8501
make eval             # RAGAS over data/eval_golden.json
make benchmark        # naive RAG vs Apex RAG (live stack)
make benchmark-mock   # offline snapshot → docs/benchmark.md + JSON
make drift            # query-distribution drift report
make lint / format / test / proto
```

---

## Documents to read next

- **[Case study](docs/case_study.md)** — the consulting narrative (Fortune 500 legal discovery firm).
- **[Architecture](docs/architecture.md)** — components, sequence diagrams, ADRs.
- **[Benchmark](docs/benchmark.md)** — naive RAG vs Apex RAG (recall, faithfulness, latency).
- **[Demo script](docs/demo_script.md)** — 5-minute screen-recording shot list.
- **[Blog post](docs/blog_post.md)** — long-form write-up.
- **[Runbook](docs/runbook.md)** — on-call playbook.

---

## License

Apache-2.0. Demo corpus is public-domain / Creative Commons (see `data/raw_docs/SOURCES.md`).
