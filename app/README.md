# app/

Application code for the LLM Security Gateway / Guardrail Proxy.

**Status: Phase 4 — runnable FastAPI skeleton.** Rule-based Input/Output guards, JSONL audit logging, and a mock chat pipeline exist and are covered by `tests/`. **No real LLM call and no real RAG retrieval exist yet** — see "What's NOT implemented" below.

## Layout

```
app/
├── main.py                 # FastAPI app entrypoint (uvicorn app.main:app)
├── api/
│   └── routes.py            # /health, /v1/guard/input, /v1/guard/output, /v1/gateway/chat
├── core/
│   ├── config.py             # env-var settings (APP_ENV, LOG_PATH, ENABLE_AUDIT_LOG), safe defaults
│   └── decisions.py          # Decision enum (allow/block/sanitize/log_only/human_review) + severity ordering
├── guards/
│   ├── input_guard.py        # rule-based prompt-injection/jailbreak/etc. detection
│   └── output_guard.py       # rule-based secret/PII/instruction-leakage detection
├── schemas/
│   ├── requests.py           # Pydantic request models
│   └── responses.py          # Pydantic response models
└── services/
    ├── gateway.py             # orchestrates Input Guard -> mock LLM -> Output Guard -> audit log
    └── audit_logger.py        # appends redacted JSONL events to logs/audit.jsonl
```

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness check. |
| POST | `/v1/guard/input` | Evaluate a raw prompt with the Input Guard only. |
| POST | `/v1/guard/output` | Evaluate a candidate output with the Output Guard only. |
| POST | `/v1/gateway/chat` | Full mock pipeline: Input Guard → mock response → Output Guard → audit log. |

Interactive docs available at `/docs` (Swagger UI) once the server is running — see the repository root `README.md` "Phase 4 local run" section.

## Guard Design

Both guards are **simple, explainable, regex/keyword rule sets** — not machine-learned classifiers, and not a claim of comprehensive attack coverage. Every rule maps to a category from `docs/evaluation/red-team-test-design.md` and `redteam/attack-categories.md`, and the 5-state decision taxonomy (`allow`/`block`/`sanitize`/`log_only`/`human_review`) is the exact same taxonomy defined in `redteam/expected-behaviors.yaml` — this is intentional, not a coincidence, so the Phase 7 evaluation runner can compare this code's actual decisions against the benchmark's expected decisions using one shared vocabulary.

- **Input Guard** (`guards/input_guard.py`): direct prompt injection, role override, instruction-hierarchy attacks, jailbreak wording, sensitive-information extraction, RAG-context manipulation, and tool/action misuse.
- **Output Guard** (`guards/output_guard.py`): the project's fake-secret marker (`FAKE-SECRET-0000-EXAMPLE`), realistic-looking API-key/token patterns, email-like PII, system-prompt/instruction-leakage phrases, and confidentiality/classification markers.

## What's NOT Implemented Yet (by design, this phase)

- **No real LLM call.** `app/services/gateway.py` always returns a fixed mock string; no OpenAI/Anthropic/Gemini/Ollama/any external model call exists anywhere in this codebase.
- **No real RAG retrieval / vector database.** `datasets/clean/` and `datasets/poisoned/` are not ingested by any code yet — that's Phase 5.
- **No RAG Guard.** Only Input Guard and Output Guard exist; the middle "screen retrieved documents" stage from `docs/diagrams/architecture.md` is not built.
- Guard rules are intentionally simple regex/keyword heuristics — false positives/negatives are expected and will be measured, not assumed away, once the Phase 7 evaluation runner exists.

## Audit Logging

Every guard decision (from all three endpoints) is appended as one JSON line to `logs/audit.jsonl` (configurable via `LOG_PATH`). The log directory is created automatically. Secret-like patterns (the project's fake-secret marker, realistic key formats, PEM private-key blocks) are redacted before being written, regardless of what the guard itself decided — see `app/services/audit_logger.py`.

## Not Production-Ready

This is a lab-scale, university-internship proof-of-concept (`AGENT_RULES.md` rule 8, `docs/decisions/ADR-001-mvp-scope.md`). No security guarantee is made or implied.
