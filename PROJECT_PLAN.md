# Project Plan

## 1. Problem Statement

Enterprise applications increasingly embed LLMs behind RAG pipelines and agentic tools. This introduces new attack surfaces not covered by traditional AppSec:

- **Prompt injection** — attacker-controlled text overrides system/developer instructions.
- **Indirect prompt injection** — malicious instructions hidden inside retrieved documents, web content, or tool outputs.
- **Jailbreaks** — prompts designed to bypass safety/alignment constraints.
- **Sensitive information leakage** — the model exposes system prompts, secrets, or private data present in context.
- **RAG document poisoning** — malicious or misleading documents inserted into a knowledge base to manipulate future outputs.

## 2. Goal (MVP)

Build a **lab-scale LLM Security Gateway / Guardrail Proxy** in front of a demo RAG application that:

- Screens user input before it reaches the LLM (**Input Guard**).
- Screens retrieved documents before they enter the prompt context (**RAG Guard**).
- Screens LLM output before it reaches the user (**Output Guard**).
- Logs security-relevant events for evaluation (**Logging/Evaluation**).
- Is evaluated against a small, synthetic red-team dataset covering the threat categories above.

This is explicitly a **proof-of-concept**, sized for a university internship, not a production security product.

## 3. Non-Goals (Phase 0 / MVP)

- No local LLM fine-tuning or training.
- No production deployment or SLA guarantees.
- No real customer/enterprise data — synthetic data only.
- No coverage claim of "all" prompt injection variants — only what is explicitly tested.
- No autonomous multi-agent tool-use security (out of scope unless explicitly approved later).

## 4. Technical Direction

- **Language/runtime:** Python 3.11 or 3.12
- **API layer:** FastAPI + Pydantic
- **LLM access:** API-based LLM provider first (e.g., hosted commercial API). No local training. Local small model via Ollama is an optional later exploration, not part of Phase 0.
- **RAG framework:** LlamaIndex or LangChain — decision deferred to a later ADR.
- **Vector store:** ChromaDB — decision deferred to a later ADR.
- **Testing:** pytest
- **Logging:** JSONL structured logs; SQLite optional for querying.
- **Packaging/deploy (later phase):** Docker Compose.
- **Optional demo UI (later phase):** Streamlit.
- **Academic report:** LaTeX (see `report-latex/`).

## 5. High-Level Architecture (target, not yet implemented)

```
User -> Demo UI/API -> LLM Security Gateway -> Input Guard -> RAG Guard -> LLM Provider -> Output Guard -> Logging/Evaluation
```

Full diagram: [docs/diagrams/architecture.md](docs/diagrams/architecture.md).

## 6. Phased Roadmap

See [TASK_BOARD.md](TASK_BOARD.md) for the authoritative phase-by-phase breakdown (Phase 0–9), owners, and status.

Summary:

| Phase | Focus |
|---|---|
| 0 | Scaffold, planning, research setup (this phase) |
| 1 | Research deep-dive: OWASP LLM Top 10, related work, tool comparison |
| 2 | Threat modeling & test dataset design (synthetic) |
| 3 | Gateway skeleton: FastAPI app, config, logging |
| 4 | Input Guard implementation |
| 5 | RAG Guard + demo RAG pipeline |
| 6 | Output Guard implementation |
| 7 | Evaluation harness + red-team run against MVP |
| 8 | Report writing, diagrams, results consolidation |
| 9 | Final polish, demo prep, submission |

## 7. Success Criteria for Phase 0

- Repository scaffold exists and matches the structure described in `README.md`.
- Planning, research, and report documents exist (even if placeholders) so Phase 1 can start without setup friction.
- `AGENT_RULES.md` exists so future AI-assisted work stays within scope.
- `report-latex/` compiles (or is ready to compile) to a properly formatted skeleton PDF.
- No application code has been written prematurely.

## 8. Risks & Mitigations (planning-level)

| Risk | Mitigation |
|---|---|
| Scope creep into full production security product | AGENT_RULES.md + TASK_BOARD.md phase gating |
| Fabricated benchmark numbers under deadline pressure | Explicit rule: no numbers without real evaluation runs |
| Accidental use of real PII/secrets in test data | Synthetic-data-only rule; `.env.example` never committed with real keys |
| Paid API cost overruns | Requires explicit approval before any paid API call |
| Framework choice (LlamaIndex vs LangChain, Chroma vs alt) blocking progress | Deferred to ADR-001 and a dedicated ADR once RAG guard work starts |

## 9. Reporting Cadence

- Periodic report 01 due **12–13 July 2026** — see [docs/report/bao-cao-dinh-ky-01.md](docs/report/bao-cao-dinh-ky-01.md).
- Weekly notes tracked under `docs/weekly-notes/`.
