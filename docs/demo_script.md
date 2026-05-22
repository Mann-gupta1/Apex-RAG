# Apex RAG — Demo-Day Screen Recording (5 minutes)

This is the shot list for the LinkedIn "Demo Day" asset.
Each scene includes the URL/command, what to show on screen, and what to say.

Tools: Loom or OBS. Resolution: 1920 × 1080. Captions burned-in.

---

## Scene 0 (0:00–0:10) — title card
- Visual: black background, single line: **Apex RAG · multi-modal enterprise search · fully local**
- Voice-over: "Apex RAG is a multi-modal enterprise search system. Text,
  image, video, audio. Hybrid retrieval, cross-encoder rerank, grounded LLM
  answers. Five minutes."

## Scene 1 (0:10–0:40) — the problem
- Visual: split screen showing four file icons (PDF / image / video / audio)
  on the left, "30 hours per case" tag on the right.
- Voice-over: "A legal discovery team spends 30 hours per case manually
  reviewing evidence across PDFs, deposition videos, audio recordings, and
  exhibit images. Keyword search misses 22 % of relevant material."

## Scene 2 (0:40–1:20) — the system in one diagram
- Visual: the mermaid diagram from `docs/architecture.md` (top-level).
- Voice-over: "Apex RAG ingests all four modalities into pgvector, runs
  hybrid retrieval with HyDE rewriting, cross-encoder reranking, then a
  LangGraph agent that grounds every claim with an inline citation and an
  NLI faithfulness check."

## Scene 3 (1:20–2:10) — ingestion
- Action:
  ```bash
  make ingest
  ```
- Visual: the rich-table summary in the terminal showing PDFs, image,
  audio, video being ingested with their chunk counts.
- Voice-over: "One command ingests the corpus. PDFs get page-anchored
  chunks. Videos get scene-detected keyframes plus per-scene transcripts.
  Audio gets diarised utterances with timestamps."

## Scene 4 (2:10–3:00) — search with provenance
- Action: open <http://localhost:3000/search>, type the legal query.
- Demo query: *"What did witness Smith say about the contract breach in case 24-CV-1234, and show me the relevant document sections and video timestamps?"*
- Visual: results panel with score breakdown, text chunk, video chunk at
  12:34–14:56, image exhibit thumbnail, click "useful" on the top result.
- Voice-over: "Hybrid + rerank surfaces a text chunk and the matching video
  segment, with the deposition timestamp baked in. The thumbs-up feeds the
  HITL dataset."

## Scene 5 (3:00–3:50) — chat with citations + NLI
- Action: navigate to <http://localhost:3000/chat>, ask the same question.
- Visual: streaming answer with inline `[1]` `[2]` citations; right panel
  shows the agent's router → retrieved → critique steps live.
- Voice-over: "Now the agent. It routes, retrieves, generates with inline
  citations, then runs an NLI faithfulness check. Watch the bottom-right —
  NLI = 0.94, the agent is confident in its grounding."

## Scene 6 (3:50–4:30) — eval & benchmark
- Action: navigate to <http://localhost:3000/eval>, then in a terminal:
  ```bash
  make benchmark
  ```
- Visual: the RAGAS scores tab, then the Naive RAG vs Apex RAG markdown
  table popping into terminal: recall@10 0.62 → 0.89, faithfulness 0.71 → 0.94.
- Voice-over: "The eval harness is continuous. Naive RAG gets 0.62 recall;
  Apex gets 0.89. Faithfulness goes from 0.71 to 0.94. Latency goes from
  180 ms to 320 ms — a trade-off we accept for research workflows."

## Scene 7 (4:30–4:55) — admin + safety
- Action: navigate to <http://localhost:3000/admin>, upload a sample PDF.
- Visual: "queued" pill, ingestion job progressing in the background.
- Voice-over: "Multi-tenant, audited, PII-redacted on the way in. Phoenix
  traces every step at localhost:6006."

## Scene 8 (4:55–5:00) — closing card
- Visual: GitHub repo URL + "Apache 2.0".
- Voice-over: "Fully local. Apache 2.0. Repo link below."

---

## Pre-recording checklist
- [ ] `make setup` completed; demo corpus indexed.
- [ ] Browser zoomed to 110 %.
- [ ] OS notifications silenced.
- [ ] Light mode (better for embedding in LinkedIn).
- [ ] `localStorage.apex.tenant` set to `default`.
- [ ] Two terminals visible — one for `make ingest` / `make benchmark`, one
      for `make api`.
