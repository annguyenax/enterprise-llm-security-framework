# tests/

pytest coverage for the gateway, dataset loader, and three rule-based guards.

**Status: Phase 6.** Coverage includes the offline provider contract, bypass variants, targeted RAG
sanitization, benign false positives, gateway ordering, severity aggregation,
and audit redaction.

## Test Modules

| File | Covers |
|---|---|
| `test_health.py` | `GET /health`. |
| `test_input_guard.py` | Input Guard behavior. |
| `test_output_guard.py` | Output decisions and redaction. |
| `test_dataset_loader.py` | Markdown parsing, extraction, and chunking. |
| `test_rag_guard.py` | Corpus behavior, normalization, bypass variants, compound severity, and benign false positives. |
| `test_rag_context_endpoint.py` | RAG endpoint, sanitization, metadata, and audit behavior. |
| `test_gateway_routes.py` | Guard ordering, RAG continuation, short-circuiting, severity, and audit logging. |
| `test_llm_provider.py` | Deterministic mock behavior and factory fail-closed behavior. |
| `test_gateway_provider.py` | Provider placement, skip paths, sanitized inputs, Output Guard handoff, response metadata, and safe audit metadata. |

## Running

```powershell
python -m pytest -q
```

Guard and loader tests run directly. Endpoint tests use FastAPI's `TestClient`
against `app.main:app`; they make no external network calls. Use a clean
project-local environment with the genuine dependencies from `requirements.txt`.
Never install `httpx2`; see the shared-environment warning in `TASK_BOARD.md`.

No test calls a real LLM, uses a vector database, or installs dependencies.
All added attack strings are synthetic and non-operational.
