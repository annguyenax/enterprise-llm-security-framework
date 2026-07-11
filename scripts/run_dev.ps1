# Phase 4 local dev runner for the LLM Security Gateway skeleton.
#
# Usage (from the repository root):
#   powershell -ExecutionPolicy Bypass -File scripts/run_dev.ps1
#
# Creates a local virtual environment if missing, installs dependencies from
# requirements.txt, then starts the FastAPI app with uvicorn's auto-reload.
# Lab-scale local development only -- not a deployment script.

$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment in .venv ..."
    python -m venv .venv
}

Write-Host "Activating virtual environment ..."
. .\.venv\Scripts\Activate.ps1

Write-Host "Installing dependencies from requirements.txt ..."
pip install -r requirements.txt

Write-Host "Starting FastAPI app (uvicorn --reload) on http://127.0.0.1:8000 ..."
uvicorn app.main:app --reload
