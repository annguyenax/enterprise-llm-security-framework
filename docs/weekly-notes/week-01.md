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

## Phase 1 Kickoff (same week, 2026-07-11)

- Generated an AI-assisted research pass with Gemini, saved as `docs/research/raw/gemini-phase-1-research.md`, covering OWASP LLM Top 10 / OWASP LLMSVS, five guardrail/red-team tools (NeMo Guardrails, Lakera Guard, deepteam, garak, Microsoft PyRIT), and three academic sources (PoisonedRAG, PIDP-Attack, an MDPI *Information* review article).
- Cross-verified every citation in that raw research file via live web search before touching official docs (`AGENT_RULES.md` rule 2 — no fabricated citations). All sources were confirmed to actually exist.
- Found and corrected two citation errors from the raw Gemini draft: PoisonedRAG's first author is Zou, W. (not Zou, Y. as originally drafted), and the MDPI review article is from 2026 (not 2025 as originally drafted).
- Updated `docs/research/related-work.md`, `owasp-llm-top10-mapping.md`, `llmsvs-checklist.md`, `tool-comparison.md`, and `dataset-review.md` with the verified findings, each clearly marked as "existence verified, full team read still pending" — not treated as a completed literature review.
- No public red-team dataset was found and reviewed directly yet; only candidate tool-bundled probe sets (garak, PyRIT, deepteam) were noted for future review.
- No code was written; this was documentation-only work, per the Phase 1 scope and `AGENT_RULES.md` rule 12 (stop at phase boundaries).

## Phase 2 Kickoff (same week, 2026-07-11)

- Wrote functional requirements (FR1–FR9) and non-functional requirements (NFR1–NFR9) for the MVP in `docs/diagrams/architecture.md` §1–2, explicitly including the 16GB-RAM-laptop, no-GPU, no-paid-API-without-approval constraints.
- Expanded the architecture Mermaid diagram to show Config/Settings and Vector Store explicitly, and added a Module Responsibility Table (9 modules, their responsibilities, and target phase).
- Added a second Mermaid diagram to `docs/diagrams/data-flow.md`: a document ingestion flow (synthetic source → ingestion script → provenance tagging → vector store), complementing the existing request/response sequence diagram.
- Expanded the STRIDE threat model in `docs/diagrams/threat-model.md` with qualitative risk ratings (High/Medium/Low — team judgment, not measured) and a new section listing threats deliberately deferred to future thesis scope (Kubernetes container-escape/RBAC risks, SIEM log-tampering, training-data poisoning for a fine-tuning pipeline) — recorded so they aren't silently forgotten, but explicitly not modeled in detail since they're not MVP architecture.
- Added an explicit "MVP Scope vs. Future Thesis Scope" table to `docs/diagrams/architecture.md` §5 and a matching addendum to `docs/decisions/ADR-001-mvp-scope.md`, stating plainly that **Kubernetes, SIEM integration, and local model fine-tuning are not MVP requirements** for this internship.
- Documented architecture-level risks and mitigations (gateway as a single point of failure, guard false positive/negative risk, 16GB RAM constraint on embedding model choice, scope-creep risk, latency risk, framework lock-in risk).
- No code was written, no packages were installed, and no APIs were called this session — documentation-only, per the explicit Phase 2 constraints and `AGENT_RULES.md` rule 12.

## Phase 2.5 Kickoff — Red-Team Test & Evaluation Design (same week, 2026-07-11)

- Created `docs/evaluation/` with three new design documents:
  - `red-team-test-design.md` — designs 5 synthetic clean enterprise documents (HR, IT helpdesk, security guideline, product FAQ, finance reimbursement), 5 synthetic poisoned-document categories (hidden instructions, system-instruction override, secret leakage, policy-bypass request, indirect injection via transcript), and 7 prompt-injection test categories (direct, role override, instruction hierarchy, jailbreak, sensitive-info extraction, RAG context manipulation, tool/action misuse) — each with example synthetic text and an expected-behavior mapping.
  - `metrics-definition.md` — precisely defines 6 metrics (ASR, Block Rate, FPR, FNR, Latency Overhead, Reason Logging Completeness) with formulas, and reconciles them against the candidate metric names logged in Phase 1's `tool-comparison.md`.
  - `evaluation-plan.md` — defines the baseline-vs-guarded evaluation methodology, roles, and constraints for the eventual Phase 7 run.
- All example content uses a fictional company ("Northwind Retail Group") and obviously-fake secret placeholders (e.g., `FAKE-SECRET-0000-EXAMPLE`) — no real PII, credentials, or company data, per `AGENT_RULES.md` rules 5 and 7.
- Updated `docs/research/dataset-review.md` to cross-reference the new design, making clear it is design-only — no files exist yet under `datasets/` or `redteam/`.
- No code was written, no packages were installed, and no APIs were called — documentation and data *design* only, per this session's explicit constraints.

## In Progress / Not Started

- LlamaIndex vs. LangChain, ChromaDB vs. alternative, and API-based LLM provider comparisons — not covered by the Gemini research pass yet, still Not Started.
- Direct team read-through of the three academic papers logged in `related-work.md` — needed before any citation is added to `report-latex/references.bib`.
- Standalone public red-team dataset review — still Not Started.
- Actual synthetic red-team prompt set and poisoned-document set — now fully **designed** in `docs/evaluation/red-team-test-design.md`, but no actual files exist yet under `datasets/` or `redteam/`.

## Blockers / Open Questions

- RAG framework (LlamaIndex vs LangChain) and vector store choice deferred — needs further Phase 1 research before an ADR can be written.
- Choice of API-based LLM provider not yet finalized — pending team decision and budget/approval discussion per `AGENT_RULES.md` rule 4.
- AI-assisted research (Gemini) requires a mandatory verification pass before being trusted — adds time but caught two real citation errors this week, so the process is being kept for future research sessions.
- Latency and false-positive/false-negative NFR targets are intentionally left qualitative until Phase 7 produces real measurements — this is correct per `AGENT_RULES.md` rule 3, but means the report cannot yet state concrete performance numbers.
- The Sanitize vs. Log only boundary for borderline poisoned-document cases (e.g., RT-POISON-004) needs team discussion before guard logic is implemented in Phase 4–6.

## Next Week Plan

- Team members personally read the three logged academic papers and confirm/replace the placeholder "Summary" fields in `related-work.md` with their own understanding.
- Research LlamaIndex vs. LangChain, ChromaDB vs. alternatives, and candidate API-based LLM providers.
- Review garak/PyRIT/deepteam's bundled probe sets for licensing and content type, logging proper entries in `dataset-review.md`.
- Materialize `docs/evaluation/red-team-test-design.md` into actual files under `datasets/` and `redteam/`, using the ID convention in that document's §6 — this is data-file creation, not code, but should be scoped/approved as its own step before Phase 3 code begins.
- Confirm Phase 0/1/2/2.5 documentation deliverables satisfy periodic report 01 requirements.
