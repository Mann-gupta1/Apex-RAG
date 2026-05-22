# Pull required Ollama models for Apex RAG (local or Docker).
$ErrorActionPreference = "Stop"
$model = if ($env:OLLAMA_GENERATION_MODEL) { $env:OLLAMA_GENERATION_MODEL } else { "llama3.1:8b-instruct-q4_K_M" }

$container = docker ps --format "{{.Names}}" 2>$null | Select-String "apex-ollama"
if ($container) {
    Write-Host "[pull_models] pulling via Docker container apex-ollama: $model"
    docker exec apex-ollama ollama pull $model
} elseif (Get-Command ollama -ErrorAction SilentlyContinue) {
    Write-Host "[pull_models] pulling via local ollama: $model"
    ollama pull $model
} else {
    Write-Error "Neither apex-ollama container nor local ollama CLI found. Run: docker compose up -d ollama"
}
Write-Host "[pull_models] done."
