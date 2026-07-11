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

## Phase 3 — Controlled Synthetic Enterprise Benchmark (data) — **Status: Done**

| Task | Owner | Status |
|---|---|---|
| 5 clean enterprise documents (`datasets/clean/*.md`) | Le Dinh Nghia | Done |
| 5 poisoned documents (`datasets/poisoned/*.md`) | Le Dinh Nghia | Done |
| 40 red-team prompts (`redteam/prompts.jsonl`) | Nguyen Van An | Done |
| Guard decision taxonomy (`redteam/expected-behaviors.yaml`) | Nguyen Van An | Done |
| Attack category reference (`redteam/attack-categories.md`) | Both | Done |

This is the same work recorded against the two Phase 2 rows above ("Synthetic red-team prompt set", "Synthetic poisoned-document set") — listed again here as its own phase for clarity, matching the "Phase 3: Controlled Synthetic Enterprise Benchmark" session label. **Data/test artifacts only — no application code.**

## Phase 3.1 — Dataset Trustworthiness Review and Freeze — **Status: Done (automated review); manual read-through in review**

| Task | Owner | Status |
|---|---|---|
| Automated validation (JSONL parse, duplicate IDs, required fields, canonical taxonomy values, no real PII/secrets/company names) | Both | Done — see `docs/dataset/dataset-validation-report.md`; all checks pass |
| Fix taxonomy-inconsistent fields found during validation | Both | Done — 4 fields across 3 poisoned documents corrected (non-canonical `expected_guard_decision`/`target_guard` values normalized); documented in `docs/dataset/dataset-validation-report.md` §2 |
| Dataset methodology write-up | Both | Done — `docs/dataset/dataset-methodology.md` (why synthetic data, AI-assisted-vs-ground-truth, what the dataset can/cannot prove, limitations) |
| Source mapping (dataset/prompt → risk basis → guard → expected decision) | Both | Done — `docs/dataset/source-mapping.md`, 50/50 items mapped |
| Manual review checklist + sign-off tracking | Both | **In Review** — checklist created (`docs/dataset/manual-review-checklist.md`); **no team member has yet completed a full manual read-through** of all 50 items, tracked honestly as `pending` |

**Corpus is frozen as of this review** (2026-07-11) pending the manual read-through. Any future content change to `datasets/`/`redteam/` should be treated as a new corpus version per `docs/dataset/dataset-methodology.md` §9.

**Next concrete implementation tasks (status as of the Phase 4 session, 2026-07-11):**
1. ~~FastAPI Security Gateway Skeleton~~ — **Done**, see "Phase 3 — Gateway Skeleton" below.
2. ~~Implement Input Guard~~ — **Done**, see "Phase 4 — Input Guard" below.
3. ~~Implement JSONL structured logging~~ — **Done**, see "Phase 3 — Gateway Skeleton" below.
4. Implement the evaluation runner — tracked below (Phase 7, "Automated red-team runner against gateway"), will consume `datasets/` and `redteam/` per `docs/evaluation/evaluation-plan.md` §4. **Still Not Started.**
5. New: implement RAG Guard + dataset ingestion (Phase 5) and an LLM Provider Adapter (Phase 5) — see notes under Phase 5/6/7 below.

## Phase 3 — Gateway Skeleton — **Status: Done**

| Task | Owner | Status |
|---|---|---|
| FastAPI app scaffold | Nguyen Van An | Done — `app/main.py`, `app/api/routes.py` (4 endpoints: `/health`, `/v1/guard/input`, `/v1/guard/output`, `/v1/gateway/chat`) |
| Config management | Nguyen Van An | Done — `app/core/config.py`, plain env-var settings with safe defaults, no `.env` required |
| JSONL structured logging | Le Dinh Nghia | Done — `app/services/audit_logger.py`, writes to `logs/audit.jsonl`, redacts secret-like patterns before writing |
| Base test harness (pytest) | Le Dinh Nghia | Done — `tests/` (4 modules, ~13 test cases), root `conftest.py` |

**Note (phase-numbering disambiguation, resolved 2026-07-11):** This board previously had three different things called "Phase 3" (see prior note, now superseded): the original code section (this one), the 2026-07-11 data session ("Phase 3 — Controlled Synthetic Enterprise Benchmark (data)", done), and session shorthand "Phase 4: FastAPI Security Gateway Skeleton" — all three now point to completed work. Going forward, use this section's name ("Phase 3 — Gateway Skeleton") for the code, and refer to the data work as "Phase 3 (data)" if disambiguation is needed.

**Important limits of this implementation (see `app/README.md` for full detail):** no real LLM API is called anywhere (mock response only); no real RAG retrieval/vector database exists; only Input Guard and Output Guard are implemented — RAG Guard (the middle stage) does not exist yet. Dependencies (FastAPI, Pydantic, Uvicorn, pytest, httpx) are **not installed** in this repository — a human must run `pip install -r requirements.txt` before the app or tests can actually execute; this session validated the code by (1) `py_compile` syntax-checking every file and (2) extracting and testing the guard regex rules directly against every test-suite prompt/output using only Python's standard library, confirming all expected decisions match — but did not run `uvicorn` or `pytest` themselves.

## Phase 4 — Input Guard — **Status: Done**

| Task | Owner | Status |
|---|---|---|
| Prompt injection heuristics/detectors | Nguyen Van An | Done — `app/guards/input_guard.py`, rule-based (direct injection, role override, instruction hierarchy, sensitive extraction, RAG context manipulation, tool/action misuse) |
| Jailbreak pattern detectors | Le Dinh Nghia | Done — same file, jailbreak-keyword and fictional-framing rules |
| Input Guard unit tests | Both | Done — `tests/test_input_guard.py` |

## Phase 4.1 — Gateway QA and Skeleton Hardening — **Status: Done**

| Task | Owner | Status |
|---|---|---|
| Fix encoding-sensitive strings (em dash -> ASCII "-" in logged reason strings) | Le Dinh Nghia | Done — 8 `reason=` strings across `app/guards/input_guard.py` and `app/guards/output_guard.py` fixed; module docstrings/comments intentionally left as-is (not logged, out of scope) |
| Confirm audit logs write as UTF-8 with readable redaction | Le Dinh Nghia | Done — `app/services/audit_logger.py` already used `encoding="utf-8"`; added regression test confirming strict-UTF-8 decode and no em/en dash in logged reasons |
| Improve mock gateway response text | Nguyen Van An | Done — `app/services/gateway.py` `MOCK_RESPONSE` now reads "Phase 4 mock response: guard evaluation completed. Real LLM and RAG retrieval are not enabled in this phase." |
| Improve final_decision logic (deterministic severity order) | Nguyen Van An | Done — `app/services/gateway.py` refactored: BLOCK and HUMAN_REVIEW on the Input Guard now both stop the pipeline before any mock-LLM call (matching `redteam/expected-behaviors.yaml`'s "human_review has the same practical effect as Block" definition); Output Guard HUMAN_REVIEW now withholds the response instead of silently returning it; `final_decision` combination continues to use the existing `most_severe()` severity function (`block > human_review > sanitize > log_only > allow`), now verified by a dedicated test |
| Add/strengthen tests | Both | Done — `tests/test_gateway_routes.py` grew from 3 to 7 tests: sanitize-continues-pipeline, severity-order (exhaustive pairwise check), output-guard-sanitizes-fake-secret-and-log-never-leaks-it, UTF-8-readable-log-with-ASCII-safe-reasons, plus the 2 original tests (one assertion updated for the new mock text) |
| Smoke test script | Both | Done (optional item, included) — `scripts/smoke_test_gateway.ps1`, calls `/health` + `/v1/guard/input` (benign & malicious) + `/v1/gateway/chat` (benign & malicious), ASCII-only output |
| README "Phase 4.1 QA checks" section | Both | Done — `pytest -q`, `uvicorn` run, `Invoke-RestMethod` examples, audit log location, explicit "still mocked" note |

**Verification method (same constraint as Phase 4):** dependencies are still **not installed** in this repository, so this session again validated changes via (1) `py_compile` on every changed file, (2) direct logic testing of `app.core.decisions.most_severe()` (zero external dependencies, runs with stdlib only) confirming the full severity order pairwise, and (3) a full non-ASCII character scan confirming every `reason=` string is now pure ASCII while docstrings/comments (not logged) were left untouched. Actually running `pytest`/`uvicorn` still requires a team member to `pip install -r requirements.txt` first.

## Phase 5 — RAG Guard + Demo RAG Pipeline — **Status: In Review (RAG Guard + dataset ingestion done; vector store/LLM adapter still pending)**

| Task | Owner | Status |
|---|---|---|
| RAG framework decision (ADR) | Both | Not Started — deferred; no real RAG/vector retrieval in this phase by design |
| Vector store decision (ADR) | Both | Not Started — deferred; no real vector database in this phase by design |
| Demo document ingestion (synthetic corpus) | Le Dinh Nghia | Done — `app/services/dataset_loader.py`: reads `datasets/clean/` and `datasets/poisoned/` (frozen benchmark from Phase 3.1), parses simple front matter, extracts real content vs. this project's own evaluator commentary, deterministic fixed-size chunking (no external deps) |
| Retrieved-content sanitization / indirect injection defense (RAG Guard) | Nguyen Van An | Done — `app/guards/rag_guard.py`, 8 rule-based detectors (hidden HTML comment, system-instruction override, fake-secret marker, policy bypass, quoted-transcript injection, generic ignore-instructions, ambiguous-authority-claim, weak override keyword); validated against all 5 `datasets/poisoned/*.md` files and all 5 `datasets/clean/*.md` files with zero false positives |
| RAG Guard API endpoint | Nguyen Van An | Done — `POST /v1/guard/rag-context` in `app/api/routes.py`, redacts the fake-secret marker and strips hidden-instruction content, writes an audit log event via `app/services/audit_logger.py` (extended with a `rag_decision` field), never logs the marker unredacted |
| Gateway integration | Nguyen Van An | Done — `app/services/gateway.py` `run_chat()` now accepts optional `context_chunks`; runs the RAG Guard after the Input Guard; BLOCK/HUMAN_REVIEW stop the pipeline before the mock LLM call (same contract as the Input Guard); SANITIZE continues with the sanitized chunks; `final_decision` uses `most_severe()` across all three guards |
| Dataset loader + RAG Guard + endpoint + gateway unit tests | Both | Done — `tests/test_dataset_loader.py` (7 tests), `tests/test_rag_guard.py` (9 tests), `tests/test_rag_context_endpoint.py` (4 tests), 4 new cases added to `tests/test_gateway_routes.py` |
| Inspection / smoke-test scripts | Both | Done — `scripts/inspect_dataset.py` + `scripts/inspect_dataset.ps1` (doc/chunk counts, sample IDs), `scripts/test_rag_guard.ps1` (clean + poisoned smoke test against a running server) |
| LLM Provider Adapter (mock-first; real provider call requires `AGENT_RULES.md` rule 4 approval) | Nguyen Van An | Not Started — see `docs/diagrams/architecture.md` §4, module target phase "Phase 3/5"; replaces `app/services/gateway.py`'s fixed `MOCK_RESPONSE` once implemented; this is the concrete next task (see note below) |

**Verification method (Phase 5 session, 2026-07-11):** unlike Phase 3/4/4.1, this session found FastAPI, Pydantic, pytest, and uvicorn **already installed** in the shared Python environment used to run commands (not a project-local `.venv`). All logic was verified for real: `app/services/dataset_loader.py` and `app/guards/rag_guard.py` were run directly against every file in `datasets/clean/` and `datasets/poisoned/`, confirming the RAG Guard reproduces every poisoned document's own `expected_guard_decision` (or a documented, justified alternate — see `app/guards/rag_guard.py` module docstring for the one deliberate deviation, the fake-secret-leak case); `pytest -q tests/test_dataset_loader.py tests/test_rag_guard.py` (16 tests, no HTTP layer involved) passed for real; a real `uvicorn` server was started locally and `/v1/guard/rag-context` and `/v1/gateway/chat` were exercised end-to-end with `curl`, confirming the block/sanitize/allow behavior and audit-log redaction match the test assertions exactly. The remaining `TestClient`-based tests (`tests/test_rag_context_endpoint.py`, the 4 new `tests/test_gateway_routes.py` cases) could not be executed via `pytest` in this environment because the installed `starlette` package fails to import its `TestClient` (see Notes section below for a security concern about this, unrelated to Phase 5 code correctness) — their behavior was instead confirmed manually via the live-server `curl` checks above, which exercise the identical code path.

**Test-expectation fix (same-day follow-up, 2026-07-11):** `tests/test_gateway_routes.py::test_audit_log_records_rag_guard_decision_without_leaking_fake_secret` originally asserted the literal string `"[REDACTED]"` must appear in the raw audit log file. That's stricter than the actual logging contract: `app/services/audit_logger.py` only ever persists a `rag_decision` summary (`decision`/`matched_rules`/`risk_score`) plus `reasons`, never the full (sanitized) context chunk text — so `"[REDACTED]"` legitimately never appears in the log for this case, even though the real secret never leaks either. Fixed the test to assert what actually matters: the raw secret string is absent, `rag_decision.decision == "sanitize"`, and the `reasons` text contains a redaction/sanitization-related word. Re-verified against a live `uvicorn` server + `curl` (same `TestClient`/`httpx2` limitation as above applies to running this via `pytest` directly in this shared environment).

## Phase 6 — Output Guard — **Status: Done (basic rule-based skeleton)**

| Task | Owner | Status |
|---|---|---|
| Sensitive info leakage detectors | Nguyen Van An | Done — `app/guards/output_guard.py` (fake-secret marker, realistic API-key/token patterns, system-prompt leakage phrases) |
| Output policy enforcement | Le Dinh Nghia | Done (basic) — decision/redaction logic exists; no dynamic/configurable policy engine, still a fixed rule list |
| Output Guard unit tests | Both | Done — `tests/test_output_guard.py` |

## Phase 7 — Evaluation Harness

| Task | Owner | Status |
|---|---|---|
| Automated red-team runner against gateway | Both | Not Started — methodology pre-specified in `docs/evaluation/evaluation-plan.md` §4; can now target the real `/v1/guard/input`, `/v1/guard/output`, `/v1/gateway/chat` endpoints once dependencies are installed |
| Metrics collection + reporting scripts | Le Dinh Nghia | Not Started — metric formulas pre-specified in `docs/evaluation/metrics-definition.md` |
| Baseline (no-guard) vs guarded comparison run | Nguyen Van An | Not Started — comparison structure pre-specified in `docs/evaluation/evaluation-plan.md` §3 |

**Note (Phase 4 session, 2026-07-11 — "next tasks" mapping):** the instruction to add "Phase 5: RAG context guard and dataset ingestion", "Phase 6: LLM provider adapter", "Phase 7: evaluation runner" as next tasks is recorded as follows, since this board's existing Phase 6 already means Output Guard (now done): RAG context guard + dataset ingestion → **Phase 5** rows above; LLM provider adapter → new row added under **Phase 5** above (not Phase 6, to avoid colliding with the existing Output Guard section); evaluation runner → **Phase 7** rows above (unchanged).

**Note (Phase 5 session, 2026-07-11 — "next tasks" mapping):** the same collision applies to the Phase 5 request's own "next phase: Phase 6: LLM Provider Adapter... Phase 7: Evaluation Runner" instruction. Per the same resolution as above: the LLM Provider Adapter work item stays as a row under **Phase 5** (added this session, not started), and the evaluation runner stays under the existing **Phase 7 — Evaluation Harness** section (unchanged, not started). Concretely, the next implementation session should pick up the LLM Provider Adapter row under Phase 5.

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

### Phase 5.1 - RAG Guard Red-team Hardening - **Status: Done**

| Task | Owner | Status |
|---|---|---|
| Detection normalization and bypass hardening | Nguyen Van An | Done - detection-only case/whitespace/zero-width/light-leetspeak normalization; hidden block, directive replacement, transcript, policy bypass, and compound-signal rules added without changing gateway architecture |
| False-positive and cross-guard tests | Both | Done - benign enterprise suite plus poisoned-context continuation, malicious-input short-circuit, metadata preservation, sanitization, and severity-order coverage |
| Phase 5.1 verification | Both | Done - 23 direct RAG Guard/dataset tests passed; 2 gateway service integration checks passed. HTTP `TestClient` collection remains blocked by the documented shared-environment issue; no packages were installed |

**Next implementation phase:** Phase 6 LLM Provider Adapter (mock-first). Any real provider call still requires explicit approval under `AGENT_RULES.md`; vector retrieval remains out of scope.

- This board is updated as phases progress; do not mark a task `Done` without corresponding documentation/evidence per `AGENT_RULES.md` rule 9.
- Phase boundaries are gates — do not start Phase N+1 implementation while Phase N is still `In Progress` without explicit approval.
- **Environment security observation (Phase 5 session, 2026-07-11, unrelated to this project's own code):** the `starlette` package installed in the shared Python environment used for this session (version reported as `1.2.1`, not a genuine upstream Starlette release) contains a modified `starlette/testclient.py` that tries to `import httpx2` before falling back to the real `httpx` package, and refuses to run at all if neither is present. `httpx2` is not this project's dependency (see `requirements.txt`, which correctly lists `httpx`) and is not a package anyone on this team asked to install. This matches a dependency-confusion / typosquat pattern. No agent session should ever run `pip install httpx2`; if `TestClient`-based tests need to run, install the genuine `httpx` package (already listed in `requirements.txt`) in a clean project-local virtual environment instead, and separately verify the integrity of the shared Python environment (`C:\Users\ADMIN\AppData\Roaming\Python\Python313\site-packages`) this was found in.
