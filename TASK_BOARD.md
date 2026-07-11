# Task Board

Owners: **Nguyen Van An**, **Le Dinh Nghia**, or **Both**. Status values: `Not Started`, `In Progress`, `Blocked`, `Done`.

## Phase 0 — Scaffold & Planning

| Task | Owner | Status |
|---|---|---|
| Repository structure scaffold | Both | Done |
| PROJECT_PLAN.md | Both | Done |
| AGENT_RULES.md | Both | Done |
| TASK_BOARD.md | Both | Done |
| docs/report/ skeleton + periodic report 01 draft | Both | In Progress |
| docs/research/ skeleton | Both | In Progress |
| docs/diagrams/ (architecture, threat model, data flow) | Both | In Progress |
| docs/decisions/ADR-001-mvp-scope.md | Both | Done |
| report-latex/ skeleton (compiles) | Both | In Progress |
| requirements.txt / .env.example / .gitignore | Both | Done |

## Phase 1 — Research Deep Dive

| Task | Owner | Status |
|---|---|---|
| OWASP LLM Top 10 mapping to project threats | Nguyen Van An | In Progress — draft mapping done, source existence verified via web search 2026-07-11, exact revision year still needs team confirmation |
| Related work / literature review | Le Dinh Nghia | In Progress — 3 papers logged (PoisonedRAG, PIDP-Attack, MDPI review), existence + metadata verified, full-text read by team still pending |
| Tool comparison (guardrail libs, RAG frameworks, vector DBs) | Both | In Progress — 5 guardrail/red-team tools documented (NeMo Guardrails, Lakera Guard, deepteam, garak, PyRIT); LlamaIndex/LangChain/ChromaDB/vector-store comparison and LLM provider comparison still Not Started |
| Dataset review (existing public red-team datasets) | Le Dinh Nghia | Not Started — no standalone public dataset reviewed yet; only candidate tool-bundled probe sets noted (garak, PyRIT, deepteam) |
| LLMSVS-style security checklist adaptation | Nguyen Van An | In Progress — real OWASP LLMSVS standard identified and verified (v0.1, Feb 2024) as a loose anchor; project checklist itself still project-defined, not mapped to specific LLMSVS control IDs |

**Note:** Phase 1 research documentation was AI-assisted (Gemini research pass, see `docs/research/raw/gemini-phase-1-research.md`), cross-verified by Claude via live web search on 2026-07-11. This counts as a first documentation pass, not a completed/team-reviewed literature review — see `docs/research/related-work.md` for what still needs a team member's direct read before any citation goes into `report-latex/references.bib`.

## Phase 2 — Threat Modeling & Test Data Design

| Task | Owner | Status |
|---|---|---|
| STRIDE threat model for gateway + RAG | Both | Not Started |
| Synthetic red-team prompt set (prompt injection) | Nguyen Van An | Not Started |
| Synthetic poisoned-document set (RAG poisoning) | Le Dinh Nghia | Not Started |
| Define evaluation metrics | Both | Not Started |

## Phase 3 — Gateway Skeleton

| Task | Owner | Status |
|---|---|---|
| FastAPI app scaffold | Nguyen Van An | Not Started |
| Config management (pydantic settings) | Nguyen Van An | Not Started |
| JSONL structured logging | Le Dinh Nghia | Not Started |
| Base test harness (pytest) | Le Dinh Nghia | Not Started |

## Phase 4 — Input Guard

| Task | Owner | Status |
|---|---|---|
| Prompt injection heuristics/detectors | Nguyen Van An | Not Started |
| Jailbreak pattern detectors | Le Dinh Nghia | Not Started |
| Input Guard unit tests | Both | Not Started |

## Phase 5 — RAG Guard + Demo RAG Pipeline

| Task | Owner | Status |
|---|---|---|
| RAG framework decision (ADR) | Both | Not Started |
| Vector store decision (ADR) | Both | Not Started |
| Demo document ingestion (synthetic corpus) | Le Dinh Nghia | Not Started |
| Retrieved-content sanitization / indirect injection defense | Nguyen Van An | Not Started |

## Phase 6 — Output Guard

| Task | Owner | Status |
|---|---|---|
| Sensitive info leakage detectors | Nguyen Van An | Not Started |
| Output policy enforcement | Le Dinh Nghia | Not Started |
| Output Guard unit tests | Both | Not Started |

## Phase 7 — Evaluation Harness

| Task | Owner | Status |
|---|---|---|
| Automated red-team runner against gateway | Both | Not Started |
| Metrics collection + reporting scripts | Le Dinh Nghia | Not Started |
| Baseline (no-guard) vs guarded comparison run | Nguyen Van An | Not Started |

## Phase 8 — Report Consolidation

| Task | Owner | Status |
|---|---|---|
| Consolidate results into LaTeX report | Both | Not Started |
| Finalize diagrams/figures | Both | Not Started |
| Internal review pass | Both | Not Started |

## Phase 9 — Final Polish & Submission

| Task | Owner | Status |
|---|---|---|
| Demo rehearsal | Both | Not Started |
| Final report proofread | Both | Not Started |
| Submission packaging | Both | Not Started |

## Notes

- This board is updated as phases progress; do not mark a task `Done` without corresponding documentation/evidence per `AGENT_RULES.md` rule 9.
- Phase boundaries are gates — do not start Phase N+1 implementation while Phase N is still `In Progress` without explicit approval.
