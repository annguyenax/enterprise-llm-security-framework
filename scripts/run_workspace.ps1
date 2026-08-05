$ErrorActionPreference = "Stop"
$env:LLM_PROVIDER = "ollama"
$env:LLM_MODEL_NAME = "qwen3:4b-instruct"
$env:OLLAMA_BASE_URL = "http://127.0.0.1:11434"
$env:WORKSPACE_DB_PATH = "data/workspace.db"
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
