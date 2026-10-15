#!/usr/bin/env bash
# Starts a disposable MongoDB (Docker), runs the whole test suite against it, then removes it.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -d .venv ] && source .venv/bin/activate
docker compose -f scripts/docker-compose.test.yml up -d --wait
trap 'docker compose -f scripts/docker-compose.test.yml down -v' EXIT
export TEST_MONGO_URI="mongodb://localhost:27018"
pytest tests -v -rs
