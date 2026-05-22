# Apex RAG — On-Call Runbook

This is the incident response playbook for the Apex RAG production stack. All
commands assume the operator has the `apex` CLI installed and Postgres access.

---

## 1. Quick health check

```bash
curl -s http://localhost:8000/api/health | jq
docker compose ps
psql "$DATABASE_URL" -c "SELECT count(*) FROM chunks;"
redis-cli ping
curl -s http://localhost:11434/api/tags | jq '.models[].name'
```

Expected:
- `/api/health` → `{"status":"ok","llm_healthy":true}`
- pgvector chunk count > 0
- Redis returns `PONG`
- Ollama lists the configured model

---

## 2. "Vector DB latency spike"

**Symptom**: P95 retrieval latency > 500 ms; `X-Latency-Ms` headers regress.

**Triage**:
1. `docker exec apex-postgres pg_stat_statements` → identify slow queries.
2. Check HNSW `ef_search`:
   ```sql
   SHOW hnsw.ef_search;
   ```
   Default is 40. Higher values increase recall but quadratic latency.
**Mitigation**:
- If sustained: temporarily lower `ef_search` to 20 in `config/retrieval.yaml`.
- Re-build HNSW index with new params via `scripts/hnsw_tune.py`.

---

## 3. "LLM unavailable"

**Symptom**: `/api/health.llm_healthy == false`; chat returns the degraded
"sources found, generation unavailable" payload.

**Triage**:
- `docker logs apex-ollama --tail 200`
- `docker exec apex-ollama ollama list`

**Mitigation**:
- Restart Ollama: `docker compose restart ollama`.
- Re-pull the configured model: `docker exec apex-ollama ollama pull llama3.1:8b-instruct-q4_K_M`.
- If the model file is corrupted: `docker volume rm apex-rag_ollama_data` and
  re-bootstrap (`make setup`).

Degraded mode is intentional and safe: searches still return ranked sources
with span highlights; only the generation step is suppressed.

---

## 4. "Duplicate query stampede"

**Symptom**: Many parallel identical search/chat requests overload Postgres.

**Mitigation**:
- The dedup layer (`src/apex/api/dedup.py`) coalesces in-flight identical
  (tenant, query) requests so the second caller awaits the first.

---

## 5. "Ingestion queue backed up"

**Symptom**: `/api/metrics.queue_size` ~= `queue_max`; uploads return 429.

**Mitigation**:
- Increase `BoundedTaskQueue(max_size=…)` in `src/apex/api/backpressure.py`,
  or scale out API replicas.
- Inspect failures in `ingestion_jobs` table:
  ```sql
  SELECT status, count(*) FROM ingestion_jobs
  WHERE created_at > now() - INTERVAL '1 hour' GROUP BY status;
  ```

---

## 6. "RAGAS regression alert"

**Symptom**: CI failed with `regression guard FAILED`.

**Triage**:
1. Read the diff in the CI logs (baseline vs latest per metric).
2. Cross-check Phoenix at <http://localhost:6006> — what changed in the
   retrieval traces?
3. Inspect `data/eval_runs/<run_id>.json` for per-question records.

**Mitigation**:
- If the regression is real: revert the offending PR.
- If the regression is a baseline drift (corpus rotated, models swapped):
  rebaseline via `python -m apex.eval.ragas_runner && cp data/eval_runs/<latest>.json data/eval_baseline.json`.

---

## 7. "PII suspected in cache / vector store"

1. Pause ingestion: `docker compose stop ollama-bootstrap`.
2. Run a one-off scrub:
   ```bash
   python -m apex.safety.pii_redact --rescan-tenant <tenant_id>
   ```
3. Delete the offending source's chunks:
   ```sql
   DELETE FROM chunks WHERE source_uri = '<URI>' RETURNING id;
   ```
4. Re-ingest after fixing redaction rules.

---

## 8. Common SQL snippets

```sql
-- queries per tenant in last hour
SELECT tenant_id, count(*) FROM audit_log
WHERE created_at > now() - INTERVAL '1 hour' GROUP BY tenant_id;

-- top failing chunks by negative feedback
SELECT chunk_id, count(*) FROM feedback, jsonb_array_elements_text(chunk_ids) AS chunk_id
WHERE rating < 0 GROUP BY chunk_id ORDER BY count DESC LIMIT 20;

-- index size + bloat
SELECT pg_size_pretty(pg_relation_size('chunks'));
SELECT pg_size_pretty(pg_relation_size('ix_chunks_embed_hnsw'));
```
