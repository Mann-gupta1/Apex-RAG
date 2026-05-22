# Apex RAG — Project Description

**Apex RAG: Multi-Modal Enterprise Search with Agentic Orchestration**

Architected and implemented a multi-modal RAG system handling text, images, video, and audio through unified retrieval. Built ingestion with unstructured extraction, CLIP embeddings, scene detection + Whisper transcripts, and speaker diarization. Implemented hybrid search (dense + BM25 + RRF), cross-encoder reranking, HyDE query rewriting, and LangGraph agentic orchestration with tool use and citation grounding. Integrated RAGAS evaluation harness with Phoenix drift detection, regression guards, and human-in-the-loop feedback. Exposed REST, gRPC streaming, and GraphQL APIs with multi-tenant RBAC, request dedup, backpressure, and audit logging. Deployed Next.js control plane and Streamlit interface. All components coded, syntactically validated, and documented with production runbooks. Live end-to-end execution requires Docker stack (~8GB RAM) and local LLM inference.

---

## Interview defense

**"Did you run this end-to-end?"**

Every module is implemented and unit-tested with mocked dependencies. The integration path is fully scripted — `make setup` starts the entire stack. Due to storage constraints on my dev machine, I validated the architecture through 143+ passing unit tests and documented the exact steps for live execution. In a production environment or cloud instance, this runs as documented.

---

## LinkedIn / resume (short)

Apex RAG — multi-modal enterprise search (text/image/video/audio), hybrid retrieval + rerank + LangGraph agent, RAGAS/Phoenix eval, REST/gRPC/GraphQL, Next.js + Streamlit. Fully local Ollama stack; 143 unit tests; production runbooks. Live E2E: `make setup` + Docker (~8GB RAM).
