# scripts/

Utility and automation scripts (e.g., running evaluation batches, data generation helpers).

**Status: empty — Phase 0 scaffold only.** Populated as needed starting Phase 2/7.

## Planned Contents (not yet created)

- `generate_synthetic_data.py` — helper to generate synthetic RAG corpus / red-team prompts (Phase 2).
- `run_evaluation.py` — batch runner for the red-team evaluation harness (Phase 7).

Any script that calls a paid LLM API must not run automatically without explicit user approval per `AGENT_RULES.md` rule 4.
