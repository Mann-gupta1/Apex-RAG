# Sample documents for local ingestion smoke tests

Place additional files here, or use the parent `data/raw_docs/` tree after `make seed`.

**Bundled samples (no download required):**

| File | Modality | Purpose |
|------|----------|---------|
| `sample_marbury_excerpt.txt` | text | Judicial review (Marbury v. Madison) |
| `sample_brown_excerpt.txt` | text | Brown v. Board holding |
| `sample_apex_legal_memo.txt` | text | Synthetic discovery memo (Smith / Exhibit 7) |

**Ingest:**

```bash
make ingest-sample    # ingests only this folder
# or
make ingest           # ingests data/raw_docs/ (full demo corpus after make seed)
```

Tested with these three sample text files via unit tests; full multimodal corpus requires `make seed`.
