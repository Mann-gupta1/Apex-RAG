# Point this repo at shared git hooks that remove Cursor commit attribution.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
git config core.hooksPath .githooks
Write-Host "Git hooks path set to .githooks (prepare-commit-msg strips Cursor attribution)."
