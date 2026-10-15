# One-shot local setup for Windows PowerShell: virtualenv, backend deps, frontend deps, .env files.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
if (Get-Command npm -ErrorAction SilentlyContinue) {
  Push-Location frontend
  npm install
  if (-not (Test-Path .env)) { Copy-Item .env.example .env }
  Pop-Location
} else { Write-Host "npm not found: skipping the frontend install (install Node.js 18+)" }
Write-Host "Done. Start MongoDB, then: .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --port 8000"
