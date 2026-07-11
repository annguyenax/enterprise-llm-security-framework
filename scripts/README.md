# scripts/

Utility and automation scripts.

**Status: Phase 4 — 1 script exists.**

## Contents

- `run_dev.ps1` — Windows PowerShell helper that creates/activates a local `.venv`, installs `requirements.txt`, and starts `uvicorn app.main:app --reload`. Local development convenience only, not a deployment script. Usage: `powershell -ExecutionPolicy Bypass -File scripts/run_dev.ps1`.

## Planned Contents (not yet created)

- `generate_synthetic_data.py` — helper to (re)generate/extend the synthetic RAG corpus / red-team prompts, if the team decides to grow `datasets/`/`redteam/` beyond the Phase 3/3.1 frozen benchmark.
- `run_evaluation.py` — batch runner for the red-team evaluation harness (Phase 7), consuming `redteam/prompts.jsonl` and `datasets/` against a running gateway instance.

Any script that calls a paid LLM API must not run automatically without explicit user approval per `AGENT_RULES.md` rule 4.
