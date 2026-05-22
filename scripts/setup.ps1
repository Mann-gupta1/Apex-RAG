# Apex RAG end-to-end local bootstrap for Windows PowerShell.
$ErrorActionPreference = "Stop"
Set-Location -Path (Split-Path -Path $PSScriptRoot -Parent)

function Log($m)  { Write-Host "[setup] $m" -ForegroundColor Cyan }
function Warn($m) { Write-Host "[warn]  $m" -ForegroundColor Yellow }
function Die($m)  { Write-Host "[fail]  $m" -ForegroundColor Red; exit 1 }

# 1. .env
if (-not (Test-Path ".env")) {
    Log "Creating .env from .env.example"
    Copy-Item ".env.example" ".env"
}

# 2. Prereqs
Log "Checking prerequisites"
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Die "docker not found. Install Docker Desktop." }
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { Die "python not found." }
$pyVer = & python -c 'import sys; print("%d.%d" % sys.version_info[:2])'
Log "python $pyVer detected"

# 3. Python venv
if (Get-Command uv -ErrorAction SilentlyContinue) {
    Log "Installing python deps with uv"
    & uv sync --all-extras
} else {
    Log "Installing python deps with pip into .venv"
    & python -m venv .venv
    & .\.venv\Scripts\Activate.ps1
    & python -m pip install --upgrade pip
    & pip install -e ".[all]"
}

# 4. Bring up infrastructure
Log "Starting docker-compose services (postgres, redis, ollama, phoenix)"
& docker compose up -d postgres redis ollama phoenix

Log "Waiting for postgres to be healthy"
for ($i = 0; $i -lt 30; $i++) {
    & docker exec apex-postgres pg_isready -U "apex" *> $null
    if ($LASTEXITCODE -eq 0) { break }
    Start-Sleep -Seconds 2
}

# 5. Migrate
Log "Applying Alembic migrations"
& python -m alembic upgrade head

# 6. Ollama models
$model = (Get-Content .env | Select-String "OLLAMA_GENERATION_MODEL=").ToString().Split("=")[1]
if (-not $model) { $model = "llama3.1:8b-instruct-q4_K_M" }
Log "Pulling Ollama generation model: $model"
try { & docker exec apex-ollama ollama pull $model } catch { Warn "Could not pull Ollama model. Pull manually later." }

# 7. Demo corpus
if ($env:SKIP_DEMO_CORPUS -ne "1") {
    Log "Downloading public-domain demo corpus"
    try { & python -m apex.scripts.download_demo_corpus } catch { Warn "Demo corpus download failed; ingest manually." }
}

Log "Setup complete. Next steps:"
Write-Host "  make ingest"
Write-Host "  make api"
Write-Host "  make ui-next"
Write-Host "  make benchmark"
