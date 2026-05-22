#!/usr/bin/env bash
# Point this repo at shared git hooks that remove Cursor commit attribution.
set -euo pipefail
cd "$(dirname "$0")/.."
git config core.hooksPath .githooks
chmod +x .githooks/prepare-commit-msg
echo "Git hooks path set to .githooks (prepare-commit-msg strips Cursor attribution)."
