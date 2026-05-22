#!/usr/bin/env bash
# Apex RAG end-to-end local bootstrap (Linux / macOS / WSL / Git Bash).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

log() { printf "\n\033[1;36m[setup]\033[0m %s\n" "$*"; }
warn() { printf "\n\033[1;33m[warn]\033[0m %s\n" "$*"; }
die()  { printf "\n\033[1;31m[fail]\033[0m %s\n" "$*"; exit 1; }

# 1. Ensure .env
if [[ ! -f .env ]]; then
  log "Creating .env from .env.example"
  cp .env.example .env
fi
set -a
source .env
set +a

# 2. Verify prerequisites
log "Checking prerequisites"
command -v docker >/dev/null || die "docker not found. Install Docker Desktop."
command -v python >/dev/null || die "python not found."
PY_VER=$(python -c 'import sys; print("%d.%d" % sys.version_info[:2])')
log "python ${PY_VER} detected"

# 3. Python virtualenv (uv preferred)
if command -v uv >/dev/null 2>&1; then
  log "Installing python deps with uv"
  uv sync --all-extras
  source .venv/bin/activate 2>/dev/null || true
else
  log "Installing python deps with pip into .venv"
  python -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate || source .venv/Scripts/activate
  python -m pip install --upgrade pip
  pip install -e ".[all]"
fi

# 4. Bring up infrastructure
log "Starting docker-compose services (postgres, redis, ollama, phoenix)"
docker compose up -d postgres redis ollama phoenix

log "Waiting for postgres to be healthy"
for i in {1..30}; do
  if docker exec apex-postgres pg_isready -U "${POSTGRES_USER:-apex}" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

# 5. Migrate
log "Applying Alembic migrations"
python -m alembic upgrade head

# 6. Pull Ollama models
log "Pulling Ollama generation model: ${OLLAMA_GENERATION_MODEL:-llama3.1:8b-instruct-q4_K_M}"
docker exec apex-ollama ollama pull "${OLLAMA_GENERATION_MODEL:-llama3.1:8b-instruct-q4_K_M}" || \
  warn "Could not pull Ollama model. Continuing; pull manually later."

# 7. Download demo corpus
if [[ "${SKIP_DEMO_CORPUS:-0}" != "1" ]]; then
  log "Downloading public-domain demo corpus"
  python -m apex.scripts.download_demo_corpus || warn "Demo corpus download failed; ingest manually."
fi

log "Setup complete. Next steps:"
cat <<'EOF'

  make ingest        # ingest the demo corpus
  make api           # start FastAPI (REST + SSE + GraphQL)
  make ui-next       # in another shell: start Next.js control plane
  make benchmark     # run Naive RAG vs Apex RAG benchmark

EOF
