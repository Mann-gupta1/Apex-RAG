.PHONY: help setup install services services-down services-logs migrate seed \
	ingest ingest-sample eval benchmark benchmark-mock validate pull-models \
	api api-rest api-grpc ui-next ui-streamlit demo \
	lint format test test-fast proto clean clean-all

PYTHON ?= python
UV ?= uv

help:  ## Show this help
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# ---------- bootstrap ----------
setup:  ## End-to-end local bootstrap (venv, deps, services, migrate, models, seed)
	bash scripts/setup.sh
	@echo "Requires Docker + ~8GB RAM. Starts Postgres/Redis/Ollama/Phoenix."

install:  ## Install python deps via uv
	$(UV) sync --all-extras

# ---------- infrastructure ----------
services:  ## Start docker-compose services in background
	docker compose up -d postgres redis ollama phoenix
	docker compose up ollama-bootstrap

services-weaviate:  ## Start with Weaviate driver enabled
	docker compose --profile weaviate up -d

services-down:  ## Stop all services
	docker compose down

services-logs:  ## Tail logs for all services
	docker compose logs -f

migrate:  ## Apply Alembic migrations
	$(PYTHON) -m alembic upgrade head

validate:  ## Offline Alembic revision chain check (no Postgres)
	$(PYTHON) scripts/validate_alembic.py

pull-models:  ## Pull Ollama generation model (llama3.1:8b-instruct-q4_K_M)
	bash scripts/pull_models.sh

# ---------- data ----------
seed:  ## Download the public demo corpus
	$(PYTHON) -m apex.scripts.download_demo_corpus

ingest:  ## Run multimodal ingestion over data/raw_docs
	$(PYTHON) -m apex.cli ingest --source data/raw_docs

ingest-sample:  ## Ingest bundled sample docs in data/sample_docs/
	$(PYTHON) -m apex.cli ingest --source data/sample_docs

# ---------- eval ----------
eval:  ## Run RAGAS evaluation against the golden set
	$(PYTHON) -m apex.eval.ragas_runner

benchmark:  ## Compare naive RAG vs Apex RAG (live stack required)
	$(PYTHON) -m apex.scripts.benchmark

benchmark-mock:  ## Write benchmark JSON + docs from committed snapshot (offline)
	$(PYTHON) -m apex.scripts.benchmark --mock

drift:  ## Run drift detection over recent queries
	$(PYTHON) -m apex.eval.drift

# ---------- serving ----------
api: api-rest  ## Default: start FastAPI (REST + GraphQL)

api-rest:  ## Start FastAPI uvicorn (REST + SSE + GraphQL)
	uvicorn apex.api.main:app --host 0.0.0.0 --port 8000 --reload

api-grpc:  ## Start gRPC server
	$(PYTHON) -m apex.api.grpc_server

ui-next:  ## Start Next.js control plane (dev mode)
	cd ui/app && pnpm install && pnpm dev

ui-streamlit:  ## Start Streamlit human-feedback app
	streamlit run ui/streamlit_app.py

demo:  ## Run the canned end-to-end demo
	$(PYTHON) -m apex.scripts.demo

# ---------- code quality ----------
lint:  ## Lint with ruff + mypy
	ruff check src tests
	mypy src

format:  ## Auto-format with ruff
	ruff check --fix src tests
	ruff format src tests

test:  ## Run the full test suite
	pytest -v

test-fast:  ## Run only fast unit tests (skip model-heavy / integration)
	pytest -v -m "not slow and not integration"

# ---------- codegen ----------
proto:  ## Regenerate gRPC python stubs from proto/apex.proto
	$(PYTHON) -m grpc_tools.protoc \
		-I proto \
		--python_out=src/apex/api \
		--grpc_python_out=src/apex/api \
		--pyi_out=src/apex/api \
		proto/apex.proto

# ---------- cleanup ----------
clean:  ## Remove caches and build artifacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +

clean-all: clean services-down  ## Clean + stop services + remove volumes
	docker compose down -v
