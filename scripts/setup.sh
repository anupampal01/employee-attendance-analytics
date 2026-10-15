#!/usr/bin/env bash
# One-shot local setup for Linux/macOS: virtualenv, backend deps, frontend deps, .env files.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -r requirements-dev.txt
[ -f .env ] || cp .env.example .env
if command -v npm >/dev/null 2>&1; then
  (cd frontend && npm install && { [ -f .env ] || cp .env.example .env; })
else
  echo "npm not found: skipping the frontend install (install Node.js 18+)"
fi
echo "Done. Start MongoDB, then:  source .venv/bin/activate && uvicorn app.main:app --port 8000"
