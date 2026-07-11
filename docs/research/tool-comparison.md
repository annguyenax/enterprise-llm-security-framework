# Tool & Framework Comparison

> Status: placeholder — comparison to be filled in during Phase 1. No performance numbers should be added unless sourced from official docs/benchmarks (cited) or produced by this project's own testing (clearly labeled as such).

## Purpose

Compare candidate tools/frameworks for each layer of the planned architecture before locking decisions in via ADRs.

## RAG Orchestration Framework

| Framework | Pros (to verify) | Cons (to verify) | Notes |
|---|---|---|---|
| LlamaIndex | | | Decision deferred — see `docs/decisions/ADR-001-mvp-scope.md` |
| LangChain | | | Decision deferred |

## Vector Store

| Store | Pros (to verify) | Cons (to verify) | Notes |
|---|---|---|---|
| ChromaDB | | | Leading candidate for lab-scale MVP (local, simple) |
| Alternative (TBD) | | | Only evaluate if ChromaDB proves insufficient |

## Guardrail / Prompt-Injection Detection Approaches

| Approach | Description | Notes |
|---|---|---|
| Rule/regex-based heuristics | Pattern matching for known injection phrasing | Likely first layer — fast, explainable |
| Existing OSS guardrail libraries | e.g., libraries providing prompt-injection or PII detection | To be surveyed in Phase 1; list only libraries actually evaluated |
| LLM-as-judge classifier | Secondary LLM call to classify input/output risk | Requires paid API approval per `AGENT_RULES.md` rule 4 if using a hosted model |

## API-based LLM Provider

| Provider | Notes |
|---|---|
| TBD | Selection pending approval for paid API usage; see `AGENT_RULES.md` rule 4 |

## Next Steps

- Populate each table with actually-evaluated options during Phase 1.
- Record the final decision and rationale as ADRs under `docs/decisions/` once choices are made.
