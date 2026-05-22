#!/usr/bin/env bash
# Pull required Ollama models for Apex RAG (local or Docker).
set -euo pipefail

MODEL="${OLLAMA_GENERATION_MODEL:-llama3.1:8b-instruct-q4_K_M}"
HOST="${OLLAMA_HOST:-http://localhost:11434}"

if docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^apex-ollama$'; then
  echo "[pull_models] pulling via Docker container apex-ollama: ${MODEL}"
  docker exec apex-ollama ollama pull "${MODEL}"
else
  if command -v ollama >/dev/null 2>&1; then
    echo "[pull_models] pulling via local ollama: ${MODEL}"
    OLLAMA_HOST="${HOST}" ollama pull "${MODEL}"
  else
    echo "[pull_models] ERROR: neither apex-ollama container nor local ollama CLI found."
    echo "  Start services: docker compose up -d ollama"
    echo "  Or install Ollama from https://ollama.com"
    exit 1
  fi
fi

echo "[pull_models] done."
