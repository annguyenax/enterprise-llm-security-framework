# Weekly Notes — Week 01

**Date range:** 2026-07-06 to 2026-07-11 (report cycle ending with periodic report 01, due 2026-07-12/13)

## Summary

Phase 0 kickoff. Focus was entirely on scaffolding: repository structure, planning documents, research skeletons, diagrams, agent rules, and the LaTeX report skeleton. No application code was written, per Phase 0 scope.

## Completed

- Repository directory structure created (`app/`, `redteam/`, `datasets/`, `tests/`, `scripts/`, `docker/`, `docs/`, `report-latex/`).
- `README.md`, `PROJECT_PLAN.md`, `AGENT_RULES.md`, `TASK_BOARD.md` written.
- `docs/report/` skeleton, including periodic report 01 draft and LaTeX formatting notes.
- `docs/research/` skeleton (related work, OWASP mapping, checklist, tool comparison, dataset review) — placeholders for Phase 1.
- `docs/diagrams/` — architecture (Mermaid), STRIDE threat model, data flow (Mermaid sequence diagram).
- `docs/decisions/ADR-001-mvp-scope.md` recording the MVP scope decision.
- `report-latex/` skeleton with A4/Times New Roman/margin formatting per academic requirements.
- `requirements.txt`, `.env.example`, `.gitignore`.

## In Progress / Not Started

- Phase 1 research deep-dive (OWASP mapping detail, related work entries, tool comparison data) — not started, planned to begin once Phase 0 is confirmed complete.

## Blockers / Open Questions

- RAG framework (LlamaIndex vs LangChain) and vector store choice deferred — needs Phase 1 research before an ADR can be written.
- Choice of API-based LLM provider not yet finalized — pending team decision and budget/approval discussion per `AGENT_RULES.md` rule 4.

## Next Week Plan

- Begin Phase 1: literature review, OWASP LLM Top 10 mapping detail, tool comparison research.
- Confirm Phase 0 deliverables satisfy periodic report 01 requirements.
