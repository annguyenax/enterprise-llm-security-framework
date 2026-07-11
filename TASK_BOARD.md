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
| docs/diagrams/ (architecture, threat model, data flow) | Both | Done — expanded in Phase 2 (2026-07-11) with FR/NFR, module table, MVP-vs-future-scope, risk ratings; see Phase 2 section below |
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
| STRIDE threat model for gateway + RAG | Both | In Progress — STRIDE table expanded with qualitative risk ratings and module cross-references (`docs/diagrams/threat-model.md`); still needs Phase 2 continuation to derive concrete synthetic test cases per row |
| Functional & non-functional requirements | Both | Done — documented in `docs/diagrams/architecture.md` §1–2 (2026-07-11) |
| Module responsibility table | Both | Done — documented in `docs/diagrams/architecture.md` §4 (2026-07-11) |
| MVP scope vs. future thesis scope (Kubernetes/SIEM/fine-tuning explicitly deferred) | Both | Done — documented in `docs/diagrams/architecture.md` §5 and `docs/decisions/ADR-001-mvp-scope.md` addendum (2026-07-11) |
| Architecture-level risks and mitigations | Both | Done — documented in `docs/diagrams/architecture.md` §6 (2026-07-11) |
| Document ingestion data flow diagram | Both | Done — documented in `docs/diagrams/data-flow.md` §2 (2026-07-11) |
| Synthetic red-team prompt set (prompt injection) | Nguyen Van An | Done — materialized as `redteam/prompts.jsonl` (40 test cases across 8 categories: benign, direct injection, role override, instruction hierarchy, jailbreak, sensitive extraction, RAG context manipulation, tool/action misuse), `redteam/expected-behaviors.yaml`, `redteam/attack-categories.md` |
| Synthetic poisoned-document set (RAG poisoning) | Le Dinh Nghia | Done — materialized as 5 clean documents (`datasets/clean/*.md`) and 5 poisoned documents (`datasets/poisoned/*.md`), each with enterprise-style metadata (ID, version, owner, classification) and explicit expected guard decisions |
| Define evaluation metrics | Both | Done (definitions) — 6 metrics (ASR, Block Rate, FPR, FNR, Latency Overhead, Reason Logging Completeness) precisely defined with formulas in `docs/evaluation/metrics-definition.md`, reconciled against Phase 1's candidate metric names; **no measurements exist**, only definitions |
| Evaluation plan / methodology | Both | Done (planning) — `docs/evaluation/evaluation-plan.md` documents the baseline-vs-guarded methodology, roles, and constraints for the eventual Phase 7 run |

**Note:** This Phase 2 pass (2026-07-11) was documentation-only — no code, no package installs, no API calls, per the explicit constraints for this session. Kubernetes, SIEM integration, and local fine-tuning were deliberately kept out of MVP requirements and recorded only as future thesis scope.

**Note (Phase 2.5, 2026-07-11):** A follow-on documentation-only session designed the red-team test corpus and evaluation criteria in detail — see `docs/evaluation/`. This is still design work, not actual test-data files or code; the "Not Started" → "In Progress" transitions above reflect that the *design* exists, not that `datasets/`/`redteam/` contain files yet.

**Note (Controlled Synthetic Enterprise Benchmark, 2026-07-11):** A follow-on data-only session turned the Phase 2.5 design into actual files: `datasets/clean/` (5 docs), `datasets/poisoned/` (5 docs), `redteam/prompts.jsonl` (40 prompts), `redteam/expected-behaviors.yaml`, `redteam/attack-categories.md`. This closes out the last two "In Progress" rows above. **No code was written** — no FastAPI app, no guard logic, no ingestion script, no LLM API calls; this data only becomes useful once Phase 3–7 below are implemented. Full inventory: `datasets/README.md`, `redteam/README.md`.

**Next concrete implementation tasks** (unblocked by this session, not yet started):
1. Implement FastAPI gateway skeleton — tracked below (Phase 3, "FastAPI app scaffold").
2. Implement Input Guard — tracked below (Phase 4), will be tested against `redteam/prompts.jsonl`.
3. Implement JSONL structured logging — tracked below (Phase 3, "JSONL structured logging"), format anticipated by FR7/NFR3 in `docs/diagrams/architecture.md`.
4. Implement the evaluation runner — tracked below (Phase 7, "Automated red-team runner against gateway"), will consume `datasets/` and `redteam/` per `docs/evaluation/evaluation-plan.md` §4.

## Phase 3 — Gateway Skeleton

| Task | Owner | Status |
|---|---|---|
| FastAPI app scaffold | Nguyen Van An | Not Started |
| Config management (pydantic settings) | Nguyen Van An | Not Started |
| JSONL structured logging | Le Dinh Nghia | Not Started |
| Base test harness (pytest) | Le Dinh Nghia | Not Started |

**Note:** "Phase 3" in the sense of *this* task board (Gateway Skeleton — code) is distinct from the "Phase 3: Controlled Synthetic Enterprise Benchmark" label used in the 2026-07-11 data-creation session referenced above (which materialized `datasets/`/`redteam/`, not application code). That data-creation work is recorded against the Phase 2 rows above since it materializes what Phase 2/2.5 designed. This Phase 3 (Gateway Skeleton) remains **Not Started**.

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
| Automated red-team runner against gateway | Both | Not Started — methodology pre-specified in `docs/evaluation/evaluation-plan.md` §4 |
| Metrics collection + reporting scripts | Le Dinh Nghia | Not Started — metric formulas pre-specified in `docs/evaluation/metrics-definition.md` |
| Baseline (no-guard) vs guarded comparison run | Nguyen Van An | Not Started — comparison structure pre-specified in `docs/evaluation/evaluation-plan.md` §3 |

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
