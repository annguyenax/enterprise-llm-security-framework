$ErrorActionPreference = "Stop"

# Đọc file .env nếu có (ghi đè các biến bên dưới)
if (Test-Path .env) {
    Get-Content .env | Where-Object { $_ -match '^\s*([^#\s]+)\s*=\s*(.*)\s*$' } | ForEach-Object {
        Set-Item -Path Env:$($matches[1]) -Value $matches[2]
    }
}

if (-not $env:LLM_PROVIDER) { $env:LLM_PROVIDER = "ollama" }
if (-not $env:LLM_MODEL_NAME) { $env:LLM_MODEL_NAME = "qwen3:4b-instruct" }
if (-not $env:OLLAMA_BASE_URL) { $env:OLLAMA_BASE_URL = "http://127.0.0.1:11434" }
if (-not $env:LLM_PROVIDER_TIMEOUT_SECONDS) { $env:LLM_PROVIDER_TIMEOUT_SECONDS = "180" }
if (-not $env:WORKSPACE_DB_PATH) { $env:WORKSPACE_DB_PATH = "data/workspace.db" }

& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
