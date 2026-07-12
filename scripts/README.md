# scripts/

Offline development, inspection, smoke-test, and evaluation helpers.

## Evaluation

- `run_evaluation.py` validates and evaluates `redteam/prompts.jsonl` directly
  against the guards, then writes JSON and Markdown artifacts under
  `reports/evaluation/`.
- `run_evaluation.ps1` is the PowerShell wrapper for the same offline run.

```powershell
python scripts/run_evaluation.py
.\scripts\run_evaluation.ps1
```

Baseline versus guarded comparison:

```powershell
python scripts/run_evaluation.py --comparison
.\scripts\run_evaluation.ps1 -Comparison
```

## Other Helpers

- `run_dev.ps1` starts the local FastAPI application.
- `smoke_test_gateway.ps1` exercises health, guards, and gateway responses.
- `inspect_dataset.py` / `inspect_dataset.ps1` inspect the synthetic corpus.
- `test_rag_guard.ps1` performs a manual RAG Guard smoke test.
- `smoke_test_retrieval.ps1` (**Phase 12B**) exercises `POST
  /v1/documents/ingest` and `POST /v1/retrieve` against a running server:
  ingests two synthetic documents, retrieves by keyword, updates one
  document, and verifies the stale (pre-update) content is no longer
  retrievable while the new content is. Recommended usage starts the
  server against a scratch database first, so the smoke test never
  touches your normal `data/retrieval.db`:

```powershell
$env:RETRIEVAL_DB_PATH = "$env:TEMP\smoke-retrieval.db"
uvicorn app.main:app --reload
# in a second shell:
powershell -ExecutionPolicy Bypass -File scripts/smoke_test_retrieval.ps1
```

- `smoke_test_rag_pipeline.ps1` (**Phase 12C**) exercises `POST
  /v1/rag/query` end to end against a running server: ingests one benign
  document and two documents containing indirect-prompt-injection text,
  runs a benign query (expects `allow`, provenance returned, the DLP
  stage present in `stage_results`), a mixed query (expects the poisoned
  document excluded from `accepted_context_count`), an all-poisoned
  query (expects `stop_reason=all_context_blocked` and
  `provider_called=false`), and a direct-injection query (expects
  `stop_reason=input_blocked` before retrieval), then reconfirms `POST
  /v1/gateway/chat` is unaffected. Documented, known limitation: it
  cannot demonstrate live secret redaction in a provider response,
  because the default Mock LLM Provider never echoes retrieved chunk
  text into its deterministic output — that exact scenario is covered
  instead by `tests/test_dlp_guard.py` and `tests/test_rag_pipeline.py`
  using a scripted offline provider double. Same scratch-database usage
  pattern as `smoke_test_retrieval.ps1`:

```powershell
$env:RETRIEVAL_DB_PATH = "$env:TEMP\smoke-rag-pipeline.db"
uvicorn app.main:app --reload
# in a second shell:
powershell -ExecutionPolicy Bypass -File scripts/smoke_test_rag_pipeline.ps1
```

The Phase 12C multidisciplinary audit-resolution run repeated this script
against a uniquely named temporary SQLite database and audit log, with the
server started hidden and stopped immediately afterward; it passed. Boundary
DLP and injected-provider scenarios remain deterministic pytest cases because
the live Mock Provider intentionally emits only its fixed short response.

No evaluation script calls an LLM API, vector database, or external service.
`smoke_test_retrieval.ps1` and `smoke_test_rag_pipeline.ps1` use only
Python's standard-library `sqlite3` and the offline Mock LLM Provider (via
the running server), and never touch `datasets/`/`redteam/`. Any future
paid API call still requires explicit approval under `AGENT_RULES.md`
rule 4.
