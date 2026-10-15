# Windows PowerShell: disposable MongoDB (Docker) + the whole test suite.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
if (Test-Path .\.venv\Scripts\Activate.ps1) { .\.venv\Scripts\Activate.ps1 }
docker compose -f scripts/docker-compose.test.yml up -d --wait
try {
  $env:TEST_MONGO_URI = "mongodb://localhost:27018"
  pytest tests -v -rs
} finally {
  docker compose -f scripts/docker-compose.test.yml down -v
}
