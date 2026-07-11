# tests/

pytest test suite for the gateway and its guards.

**Status: empty — Phase 0 scaffold only.** First tests are added alongside Phase 3 (Gateway skeleton) and each subsequent guard-implementation phase.

## Conventions (planned)

- One test module per guard: `test_input_guard.py`, `test_rag_guard.py`, `test_output_guard.py`.
- Test fixtures draw from `redteam/` and `datasets/` synthetic content only.
- Every guard capability claimed in `docs/research/llmsvs-checklist.md` should have at least one corresponding test once implemented (`AGENT_RULES.md` rule 9 — evidence requirement).

## Running (once tests exist)

```
pytest
```

No tests exist yet — running `pytest` now will report zero collected tests.
