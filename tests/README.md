# tests/

pytest test suite for the gateway skeleton and its guards.

**Status: Phase 4 — 4 test modules, ~13 test cases.** Dependencies (`pytest`, `httpx`, `fastapi`) are **not installed** in this repository — run `pip install -r requirements.txt` first (see repository root `README.md`).

## Test Modules

| File | Covers |
|---|---|
| `test_health.py` | `GET /health` |
| `test_input_guard.py` | `POST /v1/guard/input` — benign allow, direct injection block, sensitive extraction, RAG-context sanitize, tool misuse block |
| `test_output_guard.py` | `POST /v1/guard/output` — benign allow, fake-secret sanitize/block, realistic API key block, email log_only |
| `test_gateway_routes.py` | `POST /v1/gateway/chat` — request_id + guard decisions present, blocked input skips the mock LLM, audit log file is created |

A root-level `conftest.py` (not inside `tests/`) puts the repository root on `sys.path` so `from app.main import app` resolves without installing the project as a package.

## Running

```bash
pytest
```

All tests use FastAPI's `TestClient` against the real `app.main:app` instance — no network calls, no real LLM, no external services. `test_gateway_routes.py`'s audit-log test writes to the real configured `LOG_PATH` (default `logs/audit.jsonl`) and clears any pre-existing file first so the assertion is deterministic.

## Conventions

- One test module per guard/route group, matching `app/api/routes.py`'s endpoints.
- Test prompts are deliberately simple, unambiguous examples chosen to reliably trigger (or not trigger) a specific rule — they are not the full 40-prompt benchmark. For systematic coverage against the full synthetic benchmark, see `redteam/prompts.jsonl` and `docs/evaluation/evaluation-plan.md` (Phase 7 evaluation runner, not yet built).
- No test calls a real LLM API or installs anything.
