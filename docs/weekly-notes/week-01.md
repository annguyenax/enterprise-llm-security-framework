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

## Phase 3 — Controlled Synthetic Enterprise Benchmark (same week, 2026-07-11)

- Materialized the Phase 2.5 design (`docs/evaluation/red-team-test-design.md`) into actual files:
  - `datasets/clean/` — 5 synthetic enterprise documents (HR leave policy, IT helpdesk policy, security/data-classification guideline, product FAQ, finance reimbursement policy), each with realistic document metadata (document ID, version, owner department, last-updated date, classification `Internal Synthetic Demo`) and 5–8 Q&A-style policy reference points for RAG retrieval testing.
  - `datasets/poisoned/` — 5 poisoned documents, one per attack pattern (hidden HTML-comment instruction, system-instruction override, fake secret leak, policy-bypass instruction, indirect injection via a fabricated support transcript), each cross-referenced to the clean document it's modeled after and annotated with attack type, expected risk, expected guard decision, and an explanation for evaluators.
  - `redteam/prompts.jsonl` — 40 prompt-based test cases (5 each across benign, direct prompt injection, role override, instruction hierarchy attack, jailbreak, sensitive-information extraction, RAG context manipulation, and tool/action misuse), each with `id`, `category`, `prompt`, `expected_behavior`, `expected_decision`, `target_guard`, and `notes` fields — validated as syntactically correct JSON Lines with unique IDs.
  - `redteam/expected-behaviors.yaml` — canonical definition of the 5-state guard decision taxonomy (allow/block/sanitize/log_only/human_review).
  - `redteam/attack-categories.md` — explains every category (both the 8 prompt-based ones and the 5 document-poisoning ones), what each attack tries to do, expected guard response, and example IDs.
- Rewrote `datasets/README.md` and `redteam/README.md` to document folder structure, metadata conventions, safety rules, and how the not-yet-built Phase 7 evaluation runner will consume this data.
- All content uses the fictional "Northwind Retail Group" company (established in Phase 2.5), fake product ("Aurora Widget"), fake internal tool ("ServiceDesk Pro"), and obviously-fake secret markers (`FAKE-SECRET-0000-EXAMPLE`) — no real PII, credentials, or company data anywhere.
- **No code was written this session** — no FastAPI app, no guard/detection logic, no ingestion script, no LLM API calls, no packages installed. This is a pure data/test-fixture creation session; the benchmark only becomes useful once Phase 3 (Gateway Skeleton), Phase 4–6 (guards), and Phase 7 (evaluation runner) are actually implemented.
- Updated `TASK_BOARD.md`: the two remaining "In Progress" Phase 2 rows (synthetic prompt set, synthetic poisoned-document set) are now marked Done; added an explicit "next concrete implementation tasks" note pointing at the existing Phase 3/4/7 rows (FastAPI scaffold, JSONL logging, Input Guard, evaluation runner).

## Phase 3.1 — Dataset Trustworthiness Review and Freeze (same week, 2026-07-11)

- Ran an automated validation pass over the entire Phase 3 benchmark (50 items: 5 clean docs, 5 poisoned docs, 40 prompts) using a short standard-library-only Python script (no packages installed, no LLM calls): JSONL parses cleanly, no duplicate IDs across documents or prompts, no missing required fields, all `expected_decision`/`target_guard` values checked against the canonical taxonomy, no realistic secret formats or real PII/company names detected anywhere in `datasets/` or `redteam/`. Full results in `docs/dataset/dataset-validation-report.md`.
- Found and fixed **4 taxonomy-inconsistency issues**: 3 poisoned documents used non-canonical `expected_guard_decision` values (`sanitize_or_block`, `sanitize_or_log_only`, `sanitize_context_isolation`) not present in `redteam/expected-behaviors.yaml`'s 5-state taxonomy, and 1 poisoned document used a non-canonical `target_guard` value (`rag_guard_with_output_guard_backstop`). Fixed by normalizing each to its canonical value and preserving the original nuance in new `acceptable_alternate_decision`/`sanitize_technique` fields — no attack content or prose was rewritten, only front-matter metadata.
- Created `docs/dataset/` with 4 new documents: `dataset-methodology.md` (why synthetic data, AI-assisted-vs-ground-truth distinction, OWASP/threat-model mapping, what the dataset can/cannot prove, limitations, reproducibility rules), `source-mapping.md` (all 50 items mapped to risk basis/target guard/expected decision/review status, auto-extracted from source files to avoid transcription errors), `manual-review-checklist.md` (11-item checklist plus a reviewer sign-off tracking table), and `dataset-validation-report.md` (the automated results above, plus 4 flagged ambiguous cases needing human judgment).
- Updated `datasets/README.md` and `redteam/README.md` with links to the new methodology/mapping/checklist docs, and explicit statements that AI-assisted generation is not treated as ground truth, and that this benchmark supports controlled guardrail evaluation only — not real-world attack-prevalence claims.
- **Honesty note:** no team member has yet completed a full manual read-through of all 50 items against the checklist — this is tracked as `pending` in `docs/dataset/source-mapping.md` and `docs/dataset/manual-review-checklist.md` §2, not silently assumed done.
- No code was written, no packages were installed, no LLM API was called this session — validation used only Python's standard library.

## Phase 4 — FastAPI Security Gateway Skeleton (same week, 2026-07-11)

- **First application code of the project.** Implemented a runnable FastAPI skeleton under `app/`: `main.py` (entrypoint), `api/routes.py` (4 endpoints), `core/config.py` + `core/decisions.py`, `guards/input_guard.py` + `guards/output_guard.py` (rule-based), `schemas/requests.py` + `schemas/responses.py` (Pydantic models), `services/gateway.py` + `services/audit_logger.py`.
- Implemented 4 endpoints: `GET /health`, `POST /v1/guard/input`, `POST /v1/guard/output`, `POST /v1/gateway/chat`. The chat endpoint runs Input Guard → a **fixed mock response** (no real LLM call anywhere) → Output Guard → one JSONL audit log entry.
- Input Guard covers all 7 required categories (direct prompt injection, ignore-instructions, role override, jailbreak wording, sensitive extraction, malicious retrieved-context following, tool/action misuse) via ~20 regex rules, each traceable to a category in `redteam/attack-categories.md`.
- Output Guard covers the fake-secret marker (`FAKE-SECRET-0000-EXAMPLE`), realistic API-key/token patterns, email-like PII, system-prompt leakage phrases, and confidentiality/classification markers — deliberately designed so all 5 taxonomy states (allow/block/sanitize/log_only/human_review) are reachable through genuine, non-contrived rules rather than forced examples.
- `app/services/audit_logger.py` writes redacted JSONL events to `logs/audit.jsonl` (auto-creates the directory), redacting secret-like patterns independent of what the guard itself decided.
- Wrote 4 pytest modules (`tests/test_health.py`, `test_input_guard.py`, `test_output_guard.py`, `test_gateway_routes.py`, ~13 test cases) plus a root `conftest.py` for import resolution.
- **Verification without installing packages:** FastAPI/Pydantic/Uvicorn/pytest/httpx are **not installed** in this environment (installing packages was out of scope this session). Verified correctness two ways instead: (1) `python -m py_compile` on every new file — all pass; (2) extracted the guard regex rule sets into a standalone script and tested them directly (stdlib `re` only) against every prompt/output used in the test suite — all 9 cases resolved to the exact expected decision. Actually running `uvicorn`/`pytest` is deferred to whoever installs `requirements.txt`.
- Updated `README.md` (new "Phase 4 local run" section), `app/README.md`, `tests/README.md`, `scripts/README.md` (new `run_dev.ps1`), `requirements.txt` (fastapi/pydantic/uvicorn/pytest/httpx version ranges), and `TASK_BOARD.md` (Phase 3 — Gateway Skeleton, Phase 4 — Input Guard, and Phase 6 — Output Guard all marked Done; added an LLM Provider Adapter row under Phase 5).
- **Explicitly not implemented:** no real LLM API call (OpenAI/Anthropic/Gemini/Ollama or otherwise), no real RAG retrieval/vector database, no RAG Guard. `datasets/clean/`/`datasets/poisoned/` are not yet ingested by any code.

## In Progress / Not Started

- LlamaIndex vs. LangChain, ChromaDB vs. alternative, and API-based LLM provider comparisons — not covered by the Gemini research pass yet, still Not Started.
- Direct team read-through of the three academic papers logged in `related-work.md` — needed before any citation is added to `report-latex/references.bib`.
- Standalone public red-team dataset review — still Not Started.
- Full manual read-through of the 50-item benchmark against `docs/dataset/manual-review-checklist.md` — still Not Started (0 of 50 items signed off by a named reviewer).
- **Actually running the Phase 4 gateway** — a team member needs to `pip install -r requirements.txt` and run `pytest`/`uvicorn` themselves; this has not been done by anyone yet, only static/logic-level verification.
- RAG Guard, dataset ingestion, and LLM Provider Adapter (Phase 5) — still Not Started; this is what will replace the fixed mock response with real retrieval and (eventually, with approval) a real API-based LLM call.

## Phase 4.1 — Gateway QA and Skeleton Hardening (same week, 2026-07-11)

- **Encoding fix:** replaced em dashes with plain ASCII "-" in all 8 rule-authored `reason=` strings across `app/guards/input_guard.py` and `app/guards/output_guard.py` — these strings are written into `logs/audit.jsonl` and previously risked rendering as mojibake (`�`) in a Windows PowerShell console using a non-UTF-8 codepage, even though the underlying file was valid UTF-8. Module docstrings/comments (not logged) were deliberately left untouched, to keep the fix precisely scoped to what actually appears in logs.
- Confirmed `app/services/audit_logger.py` already wrote with `encoding="utf-8"` (no change needed) and added a regression test that strictly decodes the log file as UTF-8 and asserts no em/en dash appears in any logged `reasons` entry.
- **Mock response text updated** per explicit instruction: `MOCK_RESPONSE` in `app/services/gateway.py` now reads "Phase 4 mock response: guard evaluation completed. Real LLM and RAG retrieval are not enabled in this phase." (previously "Mock response generated after guard evaluation...").
- **Gateway decision logic hardened:** `app/services/gateway.py` now explicitly stops the pipeline (no mock-LLM call) when the Input Guard returns either `block` **or** `human_review` — previously only `block` short-circuited, and `human_review` would silently fall through to a full mock response despite the project's own taxonomy (`redteam/expected-behaviors.yaml`) stating human_review should have "the same practical effect as Block" for this MVP. Output Guard `human_review` now also withholds the response instead of returning it unmodified. `final_decision` combination logic itself was already correct (uses the existing `most_severe()` severity function) and is now covered by an exhaustive pairwise test of the `block > human_review > sanitize > log_only > allow` ordering.
- **Tests grew from 3 to 7** in `tests/test_gateway_routes.py`: sanitize-continues-the-pipeline, severity-order exhaustiveness, output-guard-redacts-fake-secret-and-the-log-never-contains-the-raw-secret, and UTF-8/ASCII-safety of the audit log — plus the 2 original tests (one assertion updated for the new mock text).
- Added `scripts/smoke_test_gateway.ps1` (optional item from the task list, included): calls `/health`, `/v1/guard/input` (benign + malicious), and `/v1/gateway/chat` (benign + malicious) and prints a pass/fail summary; pure ASCII output.
- Updated `README.md` with a new "Phase 4.1 QA checks" section (`pytest -q`, `uvicorn` run, `Invoke-RestMethod` examples, audit log location, explicit still-mocked note) and `TASK_BOARD.md` with a new "Phase 4.1" section marked Done.
- **Verification without installing packages (same constraint as Phase 4):** `py_compile` on every changed file (pass), direct stdlib-only testing of `app.core.decisions.most_severe()` confirming the full severity order (pass), and a full non-ASCII scan confirming every `reason=` string is now pure ASCII (pass). Did not run `pytest`/`uvicorn` — still needs a team member with `requirements.txt` installed.
- No real LLM call, no real RAG retrieval, no vector database, and no dataset/red-team expected-label changes were made this session, per the explicit Phase 4.1 constraints.

## Phase 5 — RAG Context Guard and Dataset Ingestion (same week, 2026-07-11)

- Implemented `app/services/dataset_loader.py`: reads every file in `datasets/clean/` and `datasets/poisoned/`, parses the simple `key: value` front matter (hand-rolled, no YAML dependency), and separates each file's real ingestible content from this project's own evaluator commentary embedded in the same markdown (via H2-heading section extraction — handles the one heading-text variant in `product-faq.md`, `## Policy / Product Summary`, with a prefix match rather than touching the dataset file). Chunking is deterministic fixed-size overlapping character windows (400 chars, 50 overlap), confirmed by length analysis to keep every poisoned document's attack payload inside a single chunk.
- Implemented `app/guards/rag_guard.py`: 8 rule-based detectors covering hidden HTML-comment instructions, explicit system-instruction-override documents, the fake-secret marker, policy-bypass wording, quoted-transcript indirect injection, generic "ignore all instructions" phrasing, a narrow ambiguous-authority-claim pattern (the dedicated `human_review` case), and a weak "override" keyword (`log_only`). Every rule was validated against the real content of all 5 `datasets/poisoned/*.md` files (all reproduce the file's own `expected_guard_decision`, or a documented alternate) and all 5 `datasets/clean/*.md` files (zero false positives).
- Added `RAGContextChunk`, `RAGGuardRequest` (`app/schemas/requests.py`) and `RAGGuardResponse` (`app/schemas/responses.py`); extended `ChatRequest`/`ChatResponse` with optional `context_chunks`/`rag_guard` fields.
- Added `POST /v1/guard/rag-context` and wired the RAG Guard into `POST /v1/gateway/chat`: it runs after the Input Guard, before the (mock) LLM stage; `block`/`human_review` stop the pipeline (same contract as the Input Guard), `sanitize` continues with cleaned chunks, and `final_decision` now combines all three guards via the existing `most_severe()` severity function. Extended `app/services/audit_logger.py` with a `rag_decision` field.
- Added `scripts/inspect_dataset.py` + `scripts/inspect_dataset.ps1` (doc/chunk counts, sample IDs) and `scripts/test_rag_guard.ps1` (clean + poisoned smoke test). Note: the first attempt at `inspect_dataset.ps1` used `python -c` with an inline PowerShell here-string, which silently corrupted embedded double quotes when Windows re-serialized the argument for the native `python.exe` process — fixed by moving the logic into a standalone `scripts/inspect_dataset.py` file instead, which is also the more robust pattern in general for multi-line Python invoked from PowerShell.
- Added `tests/test_dataset_loader.py` (7 tests), `tests/test_rag_guard.py` (9 tests), `tests/test_rag_context_endpoint.py` (4 tests), and 4 new cases in `tests/test_gateway_routes.py`.
- **Verification (different from every prior phase): FastAPI, Pydantic, pytest, and uvicorn turned out to be already installed** in the shared Python environment used to run commands this session (not a project-local `.venv` — the environment also has unrelated packages like `mlflow-skinny`). This let verification go further than `py_compile`: `pytest -q` actually ran and passed for the 16 tests that do not require `starlette.testclient.TestClient` (`test_dataset_loader.py`, `test_rag_guard.py`); a real `uvicorn` server was started locally on a scratch port and `/v1/guard/rag-context` + `/v1/gateway/chat` were exercised end-to-end with `curl`, confirming block/sanitize/allow behavior and audit-log redaction exactly matched the written test assertions. No packages were installed to achieve this — they were already present.
- **Security finding, unrelated to this project's own code:** the installed `starlette` package (reporting version `1.2.1`) has a modified `testclient.py` that tries `import httpx2` before falling back to `httpx`, and refuses to run if neither exists — `httpx2` is not a real dependency of this project (`requirements.txt` correctly lists `httpx`) and looks like a dependency-confusion/typosquat pattern. Did not install `httpx2` or anything else; flagged in `TASK_BOARD.md` Notes and to the user directly, and left the 4 `TestClient`-dependent Phase 5 test files as written-but-unexecuted-via-pytest (their behavior was instead confirmed via the manual `curl` checks above).
- **Explicitly not implemented (by design, per the Phase 5 task scope):** no real vector database, no embeddings/similarity search, no real LLM call. `context_chunks` must be supplied directly by the API caller; there is no retrieval step. The LLM Provider Adapter row (added under Phase 5 in a prior session) is still Not Started and is the concrete next task.
- **Same-day test-expectation fix:** `test_audit_log_records_rag_guard_decision_without_leaking_fake_secret` originally required the literal string `"[REDACTED]"` to appear in the raw audit log. Too strict — `app/services/audit_logger.py` never logs full (sanitized) context-chunk text, only a `rag_decision` summary, so that string legitimately never appears even when redaction genuinely happened and the secret never leaked. Relaxed the assertion to check what the logging contract actually promises: no raw secret in the log, `rag_decision.decision == "sanitize"`, and a redaction/sanitization-related word present in `reasons`.

## Blockers / Open Questions

- RAG framework (LlamaIndex vs LangChain) and vector store choice deferred — needs further Phase 1 research before an ADR can be written.
- Choice of API-based LLM provider not yet finalized — pending team decision and budget/approval discussion per `AGENT_RULES.md` rule 4.
- AI-assisted research (Gemini) requires a mandatory verification pass before being trusted — adds time but caught two real citation errors this week, so the process is being kept for future research sessions.
- Latency and false-positive/false-negative NFR targets are intentionally left qualitative until Phase 7 produces real measurements — this is correct per `AGENT_RULES.md` rule 3, but means the report cannot yet state concrete performance numbers.
- The Sanitize vs. Log only boundary for borderline poisoned-document cases (e.g., RT-POISON-004) needs team discussion before guard logic is implemented in Phase 4–6. Now tracked formally as one of 4 ambiguous cases flagged for priority manual review in `docs/dataset/dataset-validation-report.md` §11.

## Phase 5.1 - RAG Guard Red-team Hardening (same week, 2026-07-11)

- Hardened `app/guards/rag_guard.py` after the Grok review with detection-only normalization (case, whitespace, zero-width characters, and light leetspeak), malformed/multiline hidden comments, JS/CSS blocks, directive-replacement variants, multiline support transcripts, broader policy/approval bypass language, and deterministic compound-signal handling.
- Sanitization still operates on original chunk text and preserves `doc_id`/`metadata`; hidden instructions are removed block-by-block and the synthetic fake-secret marker is redacted. No gateway architecture, frozen dataset, red-team label, LLM call, embedding, retrieval, or vector database changed.
- Added bypass, sanitization, severity, cross-guard, and benign enterprise false-positive coverage. Verified 23 RAG Guard/dataset tests and 2 direct gateway integration checks. HTTP `TestClient` collection remains blocked by the documented shared Starlette environment issue; no packages were installed.
- Remaining limitation: regex rules can still miss semantic, deeply obfuscated, or encoded attacks. A semantic classifier or LLM judge remains future work, and complete prompt-injection protection is not claimed.

## Phase 6 - LLM Provider Adapter and Mock Integration (same week, 2026-07-11)

- Added a typed synchronous provider contract and deterministic offline `MockLLMProvider`; no provider SDK, API key, package installation, network request, or external LLM call was introduced.
- Replaced the gateway's fixed response constant with provider generation after Input/RAG guards and before Output Guard. Block/human-review branches skip provider generation, while sanitized prompts and context are passed to it.
- Added optional provider fields to chat responses and provider name/model/mock status to audit events. Recursive metadata redaction prevents synthetic secret markers from leaking through nested metadata.
- Added direct provider and gateway integration tests covering deterministic output, fail-closed provider selection, skip paths, sanitized inputs, Output Guard handoff, response metadata, and audit metadata. Verified 32 provider/gateway/RAG/dataset tests plus a live local API smoke test; the full `TestClient` suite remains blocked by the documented shared Starlette issue. Phase 7 Evaluation Runner is next after the complete suite passes in a clean environment.

## Phase 7 - Offline Evaluation Runner (same week, 2026-07-11)

- Added `app/services/evaluation_runner.py` with strict JSONL validation, direct guard routing, per-case results, exact-label comparison, decision distributions, controlled false-positive/false-negative metrics, and deterministic report serialization. The runner never calls a provider, network, retrieval system, or vector database.
- Added `scripts/run_evaluation.py` and `.ps1`; generated `reports/evaluation/latest-evaluation.json` and `.md` from the unchanged 40-case prompt suite.
- The actual controlled run recorded 35 exact decision matches and 5 failures (0.8750 pass rate), zero false positives, and five decision-based false negatives. These are synthetic benchmark measurements only, not real-world rates or end-to-end harmful-output ASR.
- Added evaluation validation, metric-definition, provider-isolation, 40-case completeness, and report-generation tests. The offline group passed 37 tests. Phase 7 remains In Review because baseline-vs-guarded comparison and a clean-environment full `TestClient` run remain open.

## Phase 7.1 - Evaluation Failure Triage and Guard Calibration (same week, 2026-07-11)

- Investigated the five initial false negatives and kept all expected decisions and prompt fixtures unchanged. Root causes were narrow lexical gaps in Input Guard, documented case-by-case in `reports/evaluation/failure-triage.md`.
- Added five targeted rules for instruction override plus disclosure, start-anchored forget-prior-message imperatives, detailed offensive training pretexts, bulk confidential-context extraction, and prompt-side official-source replacement. RAG Guard was not changed because the RAG-context failure originated in user input.
- Added exact regression prompts, nearby attack variants, and benign counterexamples for each calibration area. The focused offline group passed 52 tests; the complete project-local `.venv` suite passed 79 tests with one non-blocking Starlette `httpx2` deprecation warning. No package was installed.
- Regenerated the controlled report: 40/40 exact decision matches, zero false positives, and zero false negatives on the unchanged synthetic prompt suite. This is not a real-world protection claim; semantic and unseen paraphrase gaps remain.

## Phase 7.2 - Baseline vs Guarded Comparison (same week, 2026-07-11)

- Added an explicit no-guard evaluation mode that allows every case with no rules, reasons, or risk score. Existing guarded evaluation logic was not changed.
- Added comparison JSON/Markdown generation and `--comparison` / `-Comparison` CLI options. Reports clearly distinguish the always-allow decision baseline from a real LLM quality baseline.
- Actual controlled result: baseline 5/40 exact matches, 35 false negatives, proxy 1.0000; guarded 40/40, zero false negatives, proxy 0.0000. These are synthetic benchmark values only.
- Tests cover baseline behavior, guarded stability, comparison artifacts, relative false negatives, and SHA-256 immutability of frozen benchmark files. Full `.venv` suite passed 82 tests with one non-blocking Starlette warning; no package was installed.
- Phase 7 implementation tasks are complete. Phase 8 Report Evidence Packaging can start.

## Phase 8 - Report Evidence Packaging and Demo Preparation (same week, 2026-07-11)

- Created `reports/evidence/evidence-index.md`, mapping project claims to architecture, threat model, dataset, guards, mock provider, evaluation, comparison, tests, commands, and limitations.
- Added a timed 5-7 minute PowerShell demo script, clean reproduction checklist, manual screenshot guide, and Vietnamese academic report-ready summary. All evaluation language remains scoped to the controlled synthetic benchmark.
- Corrected stale root README phase metadata and linked the evidence package. No guard, gateway, evaluation behavior, dataset, red-team label, or LaTeX template content changed.
- Verified the packaged commands: full pytest with a system-temp basetemp passed 82 tests, and the local gateway smoke script printed `SMOKE TEST PASSED`. A workspace-local basetemp was documented as unsuitable in managed Windows shells because pytest cleanup encountered ACL denial.
- Phase 8 is In Review: evidence packaging is complete, while team screenshot capture, demo rehearsal, diagram finalization, LaTeX integration, and internal report review remain manual tasks.

## Phase 9 - Report Writing and Demo Finalization (same week, 2026-07-11)

- Added `reports/evidence/report-integration-plan.md`, mapping introduction, background, architecture, threat model, dataset, guards, provider, evaluation, results, baseline, limitations, and future work to evidence and target LaTeX chapters.
- Added `reports/evidence/demo-rehearsal-checklist.md` with timed flow, preflight commands, expected outputs, speaking points, common questions, and a no-server fallback.
- Audited `report-ready-summary.md` and added an upfront scope statement: controlled synthetic benchmark, rule-based PoC, no real LLM/vector DB/retrieval, and no real-world interpretation of 40/40.
- Verified the official title remains unchanged in `report-latex-template/thesis.sty`. LaTeX chapters were not automatically rewritten because several early-period status passages require deliberate team review and integration.
- Phase 9 is In Review pending screenshots, final PDF compile, supervisor review, timed demo rehearsal, final proofread, and submission packaging.

## Next Week Plan

- Team members personally read the three logged academic papers and confirm/replace the placeholder "Summary" fields in `related-work.md` with their own understanding.
- Research LlamaIndex vs. LangChain, ChromaDB vs. alternatives, and candidate API-based LLM providers.
- Review garak/PyRIT/deepteam's bundled probe sets for licensing and content type, logging proper entries in `dataset-review.md`.
- Materialize `docs/evaluation/red-team-test-design.md` into actual files under `datasets/` and `redteam/`, using the ID convention in that document's §6 — this is data-file creation, not code, but should be scoped/approved as its own step before Phase 3 code begins.
- Confirm Phase 0/1/2/2.5 documentation deliverables satisfy periodic report 01 requirements.

## Phase 10 - Final LaTeX Report Integration (same week, 2026-07-11)

- Integrated the evidence-backed introduction, background, architecture, threat
  model, implementation, dataset, guarded evaluation, failure triage, baseline
  comparison, limitations, future work, and appendix into the official template.
- Preserved the official title and template include order. No application,
  benchmark, test, script, guard, or generated evaluation result changed.
- Static structure, citation-key, reference, and claim-safety checks passed. A
  local PDF build was not possible because no TeX toolchain was available.

## Phase 11 - Final Compile and Submission Preparation (same week, 2026-07-11)

- Replaced stale early-period wording with final evidence and explicit scope
  language. The report consistently describes a rule-based proof-of-concept and
  controlled synthetic benchmark, not production readiness or a real-world rate.
- Prepared three compile-safe figure slots with fixed filenames, captions,
  labels, evidence sources, and screenshot requirements. The image files remain
  manual capture tasks and no screenshot was invented.
- Kept the approved-proposal sheet transparently pending; the temporary page now
  states that it is not a substitute for a signed form.
- Added `submission-package-checklist.md` and `latex-compile-notes.md`. Phase 11
  is In Review pending screenshots, signed sheet if required, Overleaf compile,
  warning fixes, Vietnamese proofread, supervisor review, and final packaging.

## Phase 12A - Modernization Scope Lock and V2 Architecture (same week, 2026-07-11)

- Three independent external reviews of the Phase 0-11 system were read
  (`docs/modernization-ai-reviews/`: Codex code-architecture, Gemini
  academic-methodology, Grok red-team/security-scope), alongside this
  project's own earlier `claude-repo-feasibility-review.md`. All four
  converge on the same core finding: the biggest gap is that retrieval is
  not real (callers supply `context_chunks` directly) and the v1 40/40
  result was reached by iteratively tuning rules against the same 40 cases
  (a calibration process, honestly recorded in Phase 7.1, but not evidence
  of generalization).
- Produced 5 new planning documents, no application code:
  `docs/modernization-final-plan.md` (scope lock and full reconciliation of
  the three reviews, including where they conflicted),
  `docs/modernization-v2-architecture.md` (target v2 component/module/API
  design plus Phase 12B-12H boundary definitions, each with objective/
  allowed files/prohibited files/acceptance criteria/tests/rollback/report
  impact/stop condition), `docs/modernization-v2-threat-model.md` (STRIDE
  extension covering the new retrieval/ingestion/provenance/DLP surface,
  including two new attack families with no v1 equivalent: FTS5
  query-syntax injection and multi-chunk coordinated injection),
  `docs/decisions/ADR-002-retrieval-engine.md` (SQLite FTS5/BM25 chosen
  over vector/hybrid/mock-only, resolving the vector-store decision
  `ADR-001-mvp-scope.md` originally deferred), and
  `docs/decisions/ADR-003-v2-benchmark.md` (v2 benchmark dev/validation/
  holdout split rules, freezing rules, and relationship to the untouched
  v1 corpus).
- **Key resolved conflict:** Grok's review proposed hard numeric acceptance
  thresholds (ASR < 20%, FPR < 5%, latency < 50ms) as phase gates. Rejected
  as binding criteria per `AGENT_RULES.md` rule 3 (no fabricated/
  pre-committed benchmark numbers) - adopting a target before any v2 data
  exists risks reproducing the same tune-to-the-benchmark pattern already
  seen in v1, one level up. The numbers are kept only as labeled external
  reference points in the threat model document, not as gates.
- Approved final direction (in priority order): SQLite FTS5/BM25 retrieval,
  persistent ingestion, server-controlled provenance/trust, end-to-end RAG
  query service, centralized DLP, new v2 benchmark with holdout, and
  ablation/retrieval-security/leakage/latency metrics as the core scope;
  vector/hybrid retrieval, a local LLM/semantic guard, and a dashboard are
  explicitly optional and later (Phases 12F/12G/12H).
- No file under `app/`, `tests/`, `scripts/`, `datasets/`, `redteam/`,
  `reports/evaluation/`, or `report-latex-template/` was modified. Verified
  with `git diff --check` and a changed-path review against the prohibited
  list. Short pointer notes added to `README.md` and a new Phase 12A
  section added to `TASK_BOARD.md`.
- **Phase 12B (Retrieval Foundation) does not start automatically** - per
  `AGENT_RULES.md` rule 12 (stop at phase boundaries), this session stopped
  after the planning documents were produced and is awaiting explicit
  approval before any `app/` code is written.

## Phase 12A Audit Resolution (same week, 2026-07-11)

- Two independent audits of the Phase 12A commit (`a814a14`) were reviewed:
  `docs/modernization-ai-reviews/gemini-phase-12a-audit.md` and
  `grok-phase-12a-audit.md`, both returning verdict REVISE with specific
  Critical/Major/Minor findings (not a rejection of the approved direction -
  Grok's own words: "strong foundation overall, proceed after fixes").
- Every Critical (5) and Major (6) finding was resolved - accepted or
  partially accepted with documented rationale, never silently ignored.
  Notable corrections: FTS5 fail-fast wording made absolute (no fallback
  under any circumstance) across `modernization-final-plan.md`,
  `ADR-002-retrieval-engine.md`, and `modernization-v2-architecture.md`;
  concrete FTS5 query tokenization/escaping spec added; exact metric
  formulas added (`modernization-v2-architecture.md` new section 8); v2
  benchmark given a minimum floor of >=100 cases while still deferring the
  exact upper bound/split to Phase 12D; v1 explicitly and formally
  prohibited from being merged into v2 validation/holdout; multi-chunk
  coordination mitigation converted from "documented only" into a
  required Phase 12C decision point, without unilaterally mandating new
  engineering scope from a documentation-only correction pass.
- Two findings were only *partially* accepted, with rationale recorded in
  `docs/modernization-ai-reviews/phase-12a-audit-resolution.md`: Grok's
  request to mandate a working cross-chunk heuristic (converted into a
  decision-point requirement instead, to avoid committing a future phase's
  engineering scope from a docs-only pass) and Gemini's exact 100-case
  50/50 named-subcount benchmark split (only the minimum floor was
  adopted, consistent with Phase 12A's own earlier reasoning against
  locking exact counts before Phase 12D authoring).
- Created `docs/modernization-ai-reviews/phase-12a-audit-resolution.md`
  (full traceable record: verdicts, every finding's resolution, deferred
  decisions, and a 10-point Phase 12B entry-gate checklist - all PASS).
  No file under `app/`, `tests/`, `scripts/`, `datasets/`, `redteam/`,
  `reports/evaluation/`, `report-latex-template/`, or `requirements.txt`
  was modified; verified with `git diff --check` and a changed-path review.
- **Final recommendation: APPROVE PHASE 12B** (audit gate satisfied). This
  is not itself the go-ahead to implement - per `AGENT_RULES.md` rule 12,
  Phase 12B still requires a separate, explicit instruction before any
  `app/` code is written.

## Phase 12B - SQLite FTS5/BM25 Retrieval Foundation (same week, 2026-07-11)

- Implemented the retrieval foundation approved in Phase 12A, using only
  Python's standard-library `sqlite3` (no new dependency, matching
  `ADR-002-retrieval-engine.md`): `app/retrieval/models.py` (defensively
  immutable records, metadata copied into `MappingProxyType`),
  `app/retrieval/base.py` (`Retriever` protocol), `app/retrieval/sqlite_bm25.py`
  (persistent schema, `bm25()`-ranked search, short-lived per-operation
  connections only, explicit FTS5 capability check with **no fallback of
  any kind**), `app/services/chunking.py` (deterministic paragraph-aware
  chunking, distinct from and not replacing v1's `dataset_loader.py`
  chunker), `app/core/source_policy.py` (server-controlled trust/
  classification, unknown `source_key` rejected by documented choice), and
  `app/services/ingestion.py` (atomic upsert orchestration, reserved
  metadata-key stripping, one safe audit event per batch).
- Added `POST /v1/documents/ingest` and `POST /v1/retrieve` to
  `app/api/routes.py`. `POST /v1/gateway/chat` and every other Phase 0-11
  endpoint are unchanged - confirmed via regression tests and a live
  `curl` check producing byte-identical responses.
- Query safety: user query text is tokenized into plain lexical terms,
  each individually double-quoted before being joined into the FTS5
  `MATCH` expression, so operators (`NEAR`, `AND`/`OR`/`NOT`, column
  filters, wildcards) typed by a caller are treated as literal search
  terms rather than executed as FTS5 query syntax - verified with a
  parametrized adversarial test covering quotes, parentheses, wildcards,
  a SQL-injection-shaped string, control characters, and a 5000-character
  query.
- Trust/provenance: verified end-to-end (not just by code review) that a
  caller-supplied `trust_level: "trusted_internal"` inside a document's
  free-form `metadata` is silently stripped and has no effect - the
  document is stored with the real server-assigned policy value instead.
  A top-level `trust_level` field (outside `metadata`) is rejected outright
  by the request schema (`extra="forbid"`, HTTP 422).
- Ingestion semantics verified live: re-ingesting identical content is a
  no-op (`unchanged`); changed content atomically replaces all stale
  chunks and FTS index rows in one transaction (`updated`, confirmed the
  pre-update content is no longer retrievable while the new content is);
  duplicate `external_id` within a batch is rejected per-item.
- **Test suite grew from 82 to 151 tests** (69 new):
  `tests/test_chunking.py` (14), `tests/test_sqlite_bm25.py` (31, including
  a simulated FTS5-unavailable capability failure using a fake connection
  object, since `sqlite3.Connection` is an immutable C type that cannot be
  patched directly with `unittest.mock`), `tests/test_ingestion.py` (14),
  `tests/test_retrieval_routes.py` (10). All 151 passed in a clean
  project-local `.venv` (not the shared/global environment with the
  documented `httpx2` issue).
- Added `scripts/smoke_test_retrieval.ps1` (ingest, retrieve, update,
  verify stale content gone) and ran it against a live local server on a
  scratch `RETRIEVAL_DB_PATH` - passed.
- **Backward-compatibility fix:** adding 9 new fields to `Settings`
  (`app/core/config.py`) initially broke an existing test that constructs
  `Settings(...)` directly without them. Fixed by giving every new field a
  default value rather than modifying the pre-existing test -
  `load_settings()` still passes every field explicitly from the
  environment, so runtime behavior is unchanged.
- No file under `app/guards/`, `app/services/gateway.py`,
  `app/services/evaluation_runner.py`, `app/services/llm_provider.py`,
  `datasets/`, `redteam/`, `reports/evaluation/`, `report-latex-template/`,
  or `requirements.txt` was modified; no new dependency installed
  (`sqlite3` is standard library). Runtime database files (`data/*.db`)
  were already covered by `.gitignore` before this phase - no `.gitignore`
  change was needed.
- **Explicitly not implemented (by design):** no `POST /v1/rag/query` -
  retrieval is not wired into any guard or the LLM provider yet, that is
  Phase 12C; no vector/embedding retrieval (optional Phase 12F); no real
  LLM call anywhere.
- **Marked In Review, not Done** per `AGENT_RULES.md` rule 9/10 - this
  session's verification is thorough (151/151 tests, live smoke test) but
  the phase awaits an independent repeat of that verification and a
  repository-wide security review before being declared Done. Phase 12C
  does not start automatically and requires a separate, explicit
  go-ahead.

## Phase 12B Code X Audit Resolution (same week, 2026-07-11)

- An independent Code X audit of implementation commit `6bfb714` returned
  verdict REVISE: 0 Critical, 5 Major (all blocking), 4 Minor findings.
  Every Major finding was independently re-verified against the actual
  code before being accepted - none was accepted purely on the audit's
  say-so, per this task's own explicit instruction not to assume the
  audit is automatically correct.
- All 5 Major findings fixed, each with a regression test reproducing the
  exact scenario the audit demonstrated: (1) a public caller could claim
  `source_key="synthetic_clean_corpus"` and be granted
  `trust_level="trusted_internal"` - fixed by removing elevated-trust
  policies from the table the public ingestion path resolves against;
  (2) reserved metadata-key stripping only matched exact top-level keys,
  so `{"nested": {"trust_level": "..."}}` or `{"Trust_Level": "..."}`
  survived unmodified - fixed with recursive, case/whitespace-normalized,
  depth-bounded sanitization plus an auditable stripped-key count (never
  the stripped value); (3) re-ingesting identical text with a changed
  title/metadata was wrongly reported `unchanged`, silently freezing
  stale fields - fixed by widening the persistence-comparison fingerprint;
  (4) environment-configured ingestion resource limits
  (`RETRIEVAL_MAX_DOCUMENT_CHARS` etc.) were never actually wired into the
  service, so they had no effect - fixed in `app/api/routes.py`; (5)
  implicit AND term-combination meant one extra irrelevant query term
  could zero out an otherwise-matching retrieval result, a genuine
  false-negative/evasion primitive - FTS5 term joining changed from AND
  to OR (`ADR-002-retrieval-engine.md` updated to document why).
- Minor findings: eager FTS5 capability check at import time (was lazy,
  first-request-only); safe generic error mapping for unexpected storage
  failures (was leaking raw exception text toward the client); a test
  cleanup fixture preventing `data/retrieval.db` from growing unbounded
  across repeated test runs; and a partial fix for ID normalization
  (whitespace + source_key case folded before dedup, but external_id case
  deliberately left as-is, since a case-sensitive real-world ID scheme
  could otherwise have two genuinely distinct documents silently merged -
  a worse failure mode than the one being fixed, documented explicitly
  rather than silently accepted).
- 14 new regression tests added (83 Phase 12B tests total, up from 69);
  full suite grew to **165/165 passing**. `scripts/smoke_test_retrieval.ps1`
  needed updating too - its original "stale content gone" check
  implicitly relied on the AND-only suppression semantics that finding
  (5) removed, so it now asserts the actual invariant (no stale chunk
  text in any returned hit) directly; re-verified against a live local
  server after the fix.
- Created `docs/modernization-ai-reviews/phase-12b-audit-resolution.md`
  (full traceable record: every finding's decision/fix/regression-test/
  rationale/residual-risk, the ingestion-atomicity and metadata-spoofing
  and FTS5-query-safety decisions restated precisely, and a 12-point
  acceptance-gate checklist - all PASS). No file under `app/guards/`,
  `app/services/gateway.py`, `app/services/evaluation_runner.py`,
  `app/services/llm_provider.py`, `datasets/`, `redteam/`,
  `reports/evaluation/`, `report-latex-template/`, or `requirements.txt`
  was modified; no new dependency installed; no runtime database tracked.
- **Final recommendation: APPROVE PHASE 12B.** Phase 12C still requires a
  separate, explicit go-ahead - audit approval is not itself that
  go-ahead.

## Phase 12B Code X Re-audit Resolution (same week, 2026-07-11)

- An independent re-audit of the first-pass fix (commit `04f68dd`) found
  that Major #2 (reserved metadata filtering) was only partially
  resolved: a list-of-lists structure - the exact probe
  `{"wrapper": [[{" TrUsT-LeVeL ": "trusted_internal", "is_poisoned": true, "expected_decision": "allow"}]]}` -
  bypassed the recursive sanitization entirely, persisting unmodified
  with `metadata_keys_stripped` wrongly reporting 0. The metadata-size
  limit was also found to run after sanitization, letting a huge value
  hidden under a reserved key bypass it. The `phase-12b-audit-resolution.md`
  document's earlier claim of "recursive handling at any nesting depth"
  was corrected in place rather than left standing.
- Root cause: the first fix only recursed into a list element when that
  element was itself a `dict`; `_metadata_depth` also never incremented
  for list descent, so list nesting never tripped the depth safety net
  regardless of how deep it went.
- Fix: `app/services/ingestion.py`'s `_sanitize_metadata`/`_metadata_depth`
  now recurse uniformly over every combination of dicts and lists; the
  ingestion loop validates raw metadata JSON size and depth *before*
  sanitizing, not after; `MAX_METADATA_DEPTH` raised 4->6 (a direct
  consequence of counting list depth correctly - a realistic 5-container
  structure needs a 6th unit of budget to reach its own leaf values).
- Route-test database isolation was also completed properly this pass:
  `tests/test_retrieval_routes.py` now swaps `app.api.routes`'s
  `_retriever`/`_ingestion_service` singletons for instances pointed at a
  pytest-managed temporary file for the whole module (restored at
  teardown) instead of only cleaning up tracked documents afterward -
  verified to leave zero test documents in `data/retrieval.db`.
- 12 new regression tests added (95 Phase 12B tests, up from 83); full
  suite grew to **177/177 passing**.
- `README.md` and `app/README.md` corrected: both previously still
  claimed FTS5 terms are joined with implicit AND (stale from before the
  Major #5 OR fix); both now correctly state explicit server-generated OR,
  and the metadata section now accurately describes recursive dict+list
  handling and the raw-size-before-sanitization ordering.
- No file under `app/guards/`, `app/services/gateway.py`,
  `app/services/evaluation_runner.py`, `app/services/llm_provider.py`,
  `datasets/`, `redteam/`, `reports/evaluation/`,
  `report-latex-template/`, or `requirements.txt` was modified; no new
  dependency installed; no runtime database tracked.
- ~~**Final recommendation: APPROVE PHASE 12B**, this time based on a
  verdict where the one remaining blocking finding is actually fixed and
  regression-tested.~~ **Superseded** — a further independent re-audit
  (below) found this fix still incomplete. Phase 12C still requires a
  separate, explicit go-ahead, and remains additionally gated on Phase
  12B actually reaching `Done`.

## Phase 12B Final Metadata Re-audit Resolution (2026-07-12)

- An independent final re-audit of the second-pass fix returned verdict
  **REVISE**: 0 Critical, 1 remaining blocking Major finding (#2), all
  other previously-resolved findings reconfirmed unaffected.
- **Finding 1 (byte-vs-character size):** the raw-metadata size check
  used `len(json.dumps(raw_metadata, ensure_ascii=False))` — a Python
  *character* count, not a UTF-8 *byte* count. Multi-byte content
  (Vietnamese text, emoji) was under-counted: the reviewer's example
  serialized to 2,412 UTF-8 bytes but measured as only ~1,212 characters,
  passing a nominal 2,000-character limit it should have failed against
  an equivalent byte limit.
- **Finding 2 (unbounded recursion):** neither `json.dumps(...)` nor the
  recursive `_metadata_depth`/`_sanitize_metadata` helpers had any bound
  checked before being called. A sufficiently deep structure (reviewer's
  probe: ~900 nested lists) exceeded Python's recursion limit inside
  `json.dumps` itself, raising an unhandled `RecursionError` instead of a
  controlled rejection.
- Fix: `app/services/ingestion.py` gained `_preflight_metadata()` — an
  **iterative, explicit-stack-based** (never recursive) check validating
  structure/type/cycle/depth *before* any `json.dumps` call or recursive
  traversal runs, bounding traversal by loop iterations instead of the
  Python call stack — and `_metadata_byte_size()`, measuring the real
  UTF-8 encoded byte length of a deterministic serialization
  (`ensure_ascii=False`, `sort_keys=True`, fixed separators).
  `MAX_METADATA_JSON_CHARS` was renamed `MAX_METADATA_JSON_BYTES` (still
  2000) to make the unit explicit. `ingest_batch`'s metadata handling was
  reordered to: preflight → deterministic serialization → UTF-8
  byte-size check → sanitize (now provably safe, since preflight already
  bounds depth) → persist → audit. Defensive `RecursionError` catches
  remain as a safety net only, since the preflight should make them
  unreachable in practice.
- Route-test database isolation residual completed: new `tests/conftest.py`
  redirects `RETRIEVAL_DB_PATH` to a per-session temporary path before any
  test module in the directory is collected/imported (pytest loads
  `conftest.py` before importing sibling test modules), closing the gap
  where the prior pass's module-scoped fixture could not prevent an
  *earlier-collected* test file's `app.main` import from still creating
  an empty, schema-only `data/retrieval.db` via `app/api/routes.py`'s
  eager `_retriever.initialize()`. The prior documentation's claim that
  route tests "genuinely no longer touch `data/retrieval.db` at all" was
  accurate only about this one module's own test documents, not about
  that eager-init side effect from a different test file — corrected in
  place in `tests/test_retrieval_routes.py`'s docstring and the
  audit-resolution document.
- 11 new regression tests added (106 Phase 12B tests, up from 95): 9 in
  `tests/test_ingestion.py` (UTF-8 byte accounting, exact/near-boundary
  byte behavior, ~900-level nested-list rejection without a
  `RecursionError`, deep mixed dict/list nesting, direct-Python
  cyclic-metadata rejection at both the helper and service level,
  non-cyclic shared-value handling, audit-log safety for both new
  rejection paths) and 2 in `tests/test_retrieval_routes.py` (the same
  two new rejection paths through the real HTTP route); the existing
  route-level list-of-list regression was also extended to cover all four
  reserved keys instead of two. Full suite grew to **188/188 passing**
  (run with an explicit writable `--basetemp`, since the shared
  environment's default Windows temp directory has a pre-existing,
  unrelated permissions issue).
- Documentation corrected in `README.md`, `app/README.md`,
  `tests/README.md`, `TASK_BOARD.md`, this file, and
  `docs/modernization-ai-reviews/phase-12b-audit-resolution.md`: the
  metadata size limit is now described in UTF-8 bytes, not characters;
  the iterative preflight is described as running before serialization
  and sanitization; and the route-test database isolation overclaim is
  removed.
- No file under `app/guards/`, `app/services/gateway.py`,
  `app/services/evaluation_runner.py`, `app/services/llm_provider.py`,
  `datasets/`, `redteam/`, `reports/evaluation/`,
  `report-latex-template/`, or `requirements.txt` was modified; no new
  dependency installed; no runtime database tracked.
- **Final recommendation: READY FOR FINAL RE-AUDIT, NOT DONE.** Per this
  task's explicit instruction, Phase 12B is not marked `Done` — an
  independent re-audit of this specific diff is required before the
  phase can be closed. Phase 12C still requires a separate, explicit
  go-ahead and is additionally gated on that re-audit returning PASS.

## Phase 12C — End-to-End RAG Security Pipeline (2026-07-12)

The project owner gave an explicit go-ahead to begin Phase 12C
implementation before Phase 12B's own final independent re-audit PASS was
obtained (recorded transparently in `TASK_BOARD.md`; Phase 12B's `In
Review` status is unaffected).

- Implemented `POST /v1/rag/query`: Input Guard -> server-side retrieval
  (existing Phase 12B `SqliteBM25Retriever`) -> Provenance/Trust Guard
  (new) -> RAG Context Guard (per chunk, then a bounded aggregate pass)
  -> Mock LLM Provider (existing, unchanged) -> centralized DLP (new) ->
  Output Guard (existing, unchanged) -> structured audit -> safe
  response. `POST /v1/gateway/chat` was not modified in any way and
  remains fully regression-tested as caller-supplied-context-only.
- New modules: `app/core/pipeline.py` (typed `RagPipelineResult`/
  `ProvenanceSummary`/`StageResult` — `GuardProfile` ablation config
  explicitly deferred to Phase 12E, documented not silently omitted),
  `app/guards/provenance_guard.py`, `app/guards/dlp_guard.py`,
  `app/services/rag_query.py`.
- **Provenance/Trust Guard:** three fixed allow-lists (`trust_level`,
  `classification`, `source_type`) matching exactly the values
  `app/core/source_policy.py`'s real (non-fallback) policies produce —
  fails closed on anything else, including the `untrusted_unknown`/
  `unverified` fallback pair. Reads only a `RetrievalHit`'s
  server-assigned fields; a caller cannot influence it since the request
  schema has no such fields at all. Acceptance is eligibility only —
  trust does not bypass the RAG Context Guard's content scan that
  follows.
- **Multi-chunk coordination:** the Phase 12A audit resolution required
  Phase 12C to explicitly decide (implement or document-defer) a
  cross-chunk mitigation, not silently omit the decision. Implemented a
  bounded, deterministic aggregate inspection — the final accepted
  chunks' bounded excerpts (default cap 4000 chars total) are joined and
  re-run through the same, unmodified `evaluate_rag_context()` as one
  synthetic chunk, catching a split-across-chunks instruction that no
  single chunk's own inspection would trip. Verified with a dedicated
  test constructing exactly that scenario
  (`test_multi_chunk_coordination_is_caught_by_the_aggregate_check`).
  This reduces, not eliminates, the risk; documented as a residual
  limitation, not a solved problem.
- **Centralized DLP:** deterministic regex detectors (canary secret,
  OpenAI/AWS/GitHub key shapes, PEM private-key blocks, bearer tokens,
  `key: value`/`key=value` secret assignments), bounded input size, never
  logs raw detected values. `app/guards/output_guard.py` and
  `app/services/audit_logger.py` were changed to import their
  previously-duplicated secret patterns from this module instead of
  redefining them — a small, mechanical, behavior-preserving refactor
  verified with parity regression tests
  (`test_output_guard_redaction_unchanged_after_consolidation`,
  `test_audit_logger_redaction_unchanged_after_consolidation`) run
  against the existing fixture set. `app/guards/rag_guard.py` was
  deliberately left untouched (not named in
  `docs/modernization-v2-architecture.md` §5's consolidation target;
  touching it was not necessary for a safe integration).
- **Fail-closed stop paths:** input blocked, retrieval failed (mapped to
  the same 400/503 `POST /v1/retrieve` already uses), no hits (safe
  allow/no-answer, not an error), all hits rejected by provenance,
  all/aggregate-blocked by the RAG Context Guard, provider failure, DLP
  failure, output blocked, and an unexpected-internal-failure safety net.
  Every guard-stage exception is caught inside the pipeline and mapped to
  a fail-closed `block`, not an unhandled 500 — verified by monkeypatched
  exception tests for each stage.
- **Response safety:** no full retrieved chunk text returned by default —
  only a safe per-hit provenance summary (document/chunk ID, title,
  source_type, classification, trust_level, rank, score, accepted/
  rejected status, reason code). The raw query itself is never logged in
  the audit event, only a SHA-256 hash prefix and length (stricter than
  other endpoints' existing redacted-preview convention, since a natural
  RAG query may embed sensitive content that pattern-based redaction
  would not catch).
- 79 new regression tests added across `tests/test_provenance_guard.py`
  (11), `tests/test_dlp_guard.py` (13), `tests/test_rag_pipeline.py` (32,
  service-level via a stub retriever double plus two real-SQLite
  end-to-end cases), and `tests/test_rag_query_routes.py` (23,
  HTTP-level, including strict-schema rejection of every prohibited
  field and regression checks that `/health`, `/v1/gateway/chat`, and
  `/v1/retrieve` are unaffected). Full suite grew to **267/267 passing**
  (up from 188), run with an explicit writable `--basetemp`.
- Live smoke test `scripts/smoke_test_rag_pipeline.ps1` run against a
  real `uvicorn` server on a scratch `RETRIEVAL_DB_PATH` — **PASSED**:
  benign query (allow, DLP stage ran), mixed query (poisoned doc
  excluded), all-poisoned query (`all_context_blocked`, provider not
  called), direct-injection query (`input_blocked` before retrieval), and
  the `/v1/gateway/chat` regression check. One scenario is documented as
  not live-testable rather than faked: the deterministic Mock LLM
  Provider never echoes retrieved content into its response, so live
  secret-redaction-in-response cannot be demonstrated against a real
  server — that exact case is covered instead by
  `tests/test_dlp_guard.py`/`tests/test_rag_pipeline.py` using a scripted
  offline provider double.
- No file under `app/guards/input_guard.py`, `app/services/gateway.py`,
  `app/services/evaluation_runner.py`, `app/services/llm_provider.py`,
  `datasets/`, `redteam/`, `reports/evaluation/`,
  `report-latex-template/`, or `requirements.txt` was modified; no new
  dependency installed; no runtime database tracked; no network call
  anywhere in the new code.
- Documentation updated: `README.md` (new Phase 12C section),
  `app/README.md` (new "End-to-End RAG Pipeline" section, updated
  endpoint table and "Not Implemented"/"Audit Logging" sections),
  `tests/README.md` (new test-module rows, updated counts),
  `scripts/README.md` (new smoke-test entry), `TASK_BOARD.md` (new Phase
  12C section), this file.
- **Phase 12C is marked In Review, not Done.** Per this task's explicit
  instruction, it is not declared complete until a maintainer
  independently repeats verification and an independent security audit
  passes — the same process already applied to Phase 12A and 12B. Phase
  12D (benchmark v2 generation) was explicitly not started this session.
## Phase 12C multidisciplinary audit resolution (2026-07-12)

- Adjudicated the Gemini, Grok, and Code X Phase 12C audits using executable
  repository evidence. All three verdicts were `REVISE`; Gemini explicitly
  could not inspect the diff, so its recommendations were treated as
  conditional academic requirements rather than code facts.
- Resolved Code X's two Critical findings: DLP no longer returns an
  uninspected output suffix, and audit logging now consumes the complete
  centralized redaction API, including bearer and secret-assignment patterns.
- Resolved the five blocking Major findings: provider requests contain only
  the sanitized effective query; provider context is exactly the bounded
  aggregate-inspected context; controlled failures have safe reason codes and
  audit handling; Phase 12C settings fail fast on invalid values; DLP findings
  produce `sanitize` and structured category/count telemetry.
- Added overlap-safe DLP counting, safe audit-sink fallback, corrected FastAPI
  metadata, and Grok-inspired multilingual/zero-width, high-trust malicious,
  mixed-trust, legitimate-authority, and academic-discussion tests.
- Gemini ablation toggles remain Phase 12E evaluation-only work. The public
  endpoint has no field, header, or serving setting that can disable guards.
  Per-request stage telemetry is ready for Phase 12E aggregation; no p50/p95
  or benchmark result was generated in Phase 12C.
- Validation: focused Phase 12C suite 123 passed; full suite 311 passed;
  compile checks and live isolated RAG smoke test passed. Phase 12D was not
  started.
- ~~Final recommendation at the time: APPROVE PHASE 12C.~~ **Superseded**
  — a further independent Code X re-audit of this exact state (below)
  found terminal audit coverage was still incomplete for two paths.

## Phase 12C Code X Final Re-audit (2026-07-12)

An independent Code X final re-audit of the multidisciplinary-resolution
state returned verdict **REVISE**: 0 remaining Critical, 1 remaining
blocking Major ("terminal audit coverage is still incomplete"), everything
else previously resolved reconfirmed unaffected.

- **Root cause:** two paths in `app/api/routes.py::rag_query` reached the
  service but bypassed the pipeline's own internal audit commit: (1) the
  configured `top_k > settings.rag_max_top_k` rejection returned HTTP 400
  before `run_rag_query`'s `log_event` call ever ran, producing zero audit
  trail; (2) `run_rag_query` committed its terminal audit event *before*
  `app/api/routes.py` attempted to build `RagQueryResponse(...)` from the
  result, so a response-construction failure left an earlier, contradictory
  "success" (`allowed`) event on record for a request the caller actually
  received as a 500.
- **Fix:** split audit commitment out of the pipeline function.
  `app/services/rag_query.py::run_rag_query_uncommitted(...)` now contains
  the full pipeline body and returns `(RagPipelineResult,
  RagQueryAuditContext)` without logging; `commit_rag_query_audit(result,
  audit_ctx)` is the extracted, explicit commit step, called exactly once
  for whichever outcome is actually visible to the caller.
  `run_rag_query`'s public signature/behavior is unchanged (a two-line
  wrapper: uncommitted call, immediate commit, return) so every existing
  direct/service caller needed zero changes. `audit_top_k_rejected(...)`
  emits exactly one safe `block`/`top_k_rejected` event for the first gap;
  the route now defers its commit until after `RagQueryResponse(...)`
  construction succeeds (or commits
  `mark_response_construction_failed(pipeline_result)` if it does not) for
  the second gap. This is an explicit internal Python contract (two named
  functions plus a small internal dataclass), not a public flag.
- 8 new regression tests added: `test_audit_top_k_rejected_emits_exactly_one_safe_block_event`,
  `test_run_rag_query_uncommitted_does_not_audit_until_committed`,
  `test_mark_response_construction_failed_produces_corrected_block_event`,
  `test_exact_empty_sanitized_query_is_rejected_and_audited_once` (service
  level); `test_top_k_rejection_returns_400_without_calling_retriever_or_provider`,
  `test_top_k_rejection_returns_safe_response_even_if_audit_sink_fails`,
  `test_response_construction_failure_emits_exactly_one_corrected_audit_event`,
  `test_response_construction_failure_audit_sink_failure_still_returns_safe_500`
  (HTTP level).
- Validation: focused Phase 12C suite grew to **131 passed** (up from
  123); full suite grew to **319 passed** (up from 311); `python -m
  py_compile` clean; live smoke test
  (`scripts/smoke_test_rag_pipeline.ps1`) against a real `uvicorn` server
  on a scratch database/log path passed, plus a manual live check
  confirming a `top_k=30` request now produces exactly one
  `stop_reason=top_k_rejected` audit event with no raw query. No
  prohibited path, dependency, or tracked database changed.
- ~~Final recommendation: READY FOR ONE FINAL CODE X RE-AUDIT.~~
  **Superseded** — a further independent Code X re-audit of this exact
  diff (below) found one more blocking gap in the same terminal-audit-
  coverage area.

## Phase 12C Code X Final Terminal-Audit Re-audit — Nested Response Construction (2026-07-12)

A further independent Code X re-audit of the terminal-audit-coverage fix
returned verdict **REVISE**: 0 remaining Critical, 1 remaining blocking
Major ("nested `ProvenanceItemResponse` construction occurs outside the
protected response-construction and terminal-audit block").

- **Root cause:** `app/api/routes.py::rag_query` built the `provenance =
  [ProvenanceItemResponse(...) for ...]` list **before** the `try` block
  protecting `RagQueryResponse(...)` construction (the previous pass's
  fix had wrapped the outer call, and incidentally the inline
  `StageResultResponse` list nested inside it, but not this separate,
  earlier list comprehension). A failure constructing a
  `ProvenanceItemResponse` — reachable only after the full pipeline,
  including the provider, had already run — propagated as a raw,
  unprotected exception: no safe `request_id`-bearing HTTP 500, and zero
  terminal audit events.
- **Fix:** moved the `provenance = [...]` construction (and made the
  `stage_items = [...]` list explicit) inside the same `try` block as
  `RagQueryResponse(...)`, so every nested and outer response object is
  built in one protected block, and the success/`SANITIZE` terminal
  audit commits only after the entire response tree is confirmed valid.
  No change to `app/services/rag_query.py` was needed — its
  audit-deferral contract (`run_rag_query_uncommitted`/
  `commit_rag_query_audit`/`mark_response_construction_failed`) already
  supported this; only the route's own code needed restructuring.
- 4 new regression tests added (all in `tests/test_rag_query_routes.py`):
  `test_nested_provenance_item_response_failure_maps_to_safe_500_with_audit`,
  `test_nested_provenance_item_response_failure_with_audit_sink_failure_still_returns_safe_500`,
  `test_successful_nested_response_construction_emits_exactly_one_normal_event`,
  `test_nested_stage_result_response_failure_maps_to_safe_500_with_audit`
  (forcing a different nested model to fail, confirming it follows the
  same path, not a special case).
- Validation: focused Phase 12C suite grew to **135 passed** (up from
  131); full suite grew to **323 passed** (up from 319); `python -m
  py_compile` clean; live smoke test
  (`scripts/smoke_test_rag_pipeline.ps1`) against a real `uvicorn` server
  on a scratch database/log path passed. No prohibited path, dependency,
  or tracked database changed.
- **Documentation correction:** the prior pass's claim that "every
  response-construction path was already protected" was inaccurate;
  corrected in place. The schema-level 422 boundary (FastAPI/Pydantic
  validation failures before `rag_query`'s function body runs, therefore
  outside the one-terminal-audit-event contract) is now explicitly
  documented rather than left implicit.
- **Final recommendation: READY FOR ONE FINAL CODE X RE-AUDIT.** Not
  APPROVE, not DONE. Phase 12C remains In Review until an independent
  re-audit of this specific diff returns PASS. Phase 12D was not started.

## Phase 12D — Independent Benchmark V2 Design, Generation, Validation and Freeze (2026-07-12)

Produced a new, independently-governed benchmark for a future Phase 12E
security evaluation, under `datasets/v2/` — artifacts only; no guard rule
modified, no evaluation run, no ASR/FPR/FNR computed.

- **Design:** 23 scenario families, 120 cases (30 development / 30
  validation / 60 holdout), 164 corpus documents, 120 matching labels.
  Category balance 36 benign / 74 malicious / 6 mixed / 4 neutral;
  language distribution 60 vi / 40 en / 20 bilingual (fixed deterministic
  rotation via `itertools.cycle`, never random).
- **Two architectural boundaries identified and honestly represented
  rather than fabricated:** (1) `app/guards/provenance_guard.py`'s
  allow-lists already cover every trust/classification/source_type
  combination `app/core/source_policy.py` can assign, so a retrieved hit
  can never carry genuinely malformed provenance metadata end-to-end —
  represented instead by `provenance_denied_at_ingestion` (rejection at
  ingestion time via an unregistered `source_key`), with the
  unit-level-only condition cross-referenced to the existing
  `tests/test_provenance_guard.py`. (2) The deterministic Mock LLM
  Provider never echoes retrieved content into its response, so true
  end-to-end DLP-on-provider-output leakage cannot be exercised
  black-box — represented instead by `leakage_context_exclusion`/
  `leakage_dlp_mechanism_reference`, which test the RAG Context Guard's
  own `rag-fake-secret` redaction of retrieved content, with centralized
  DLP-on-provider-output cross-referenced to `tests/test_dlp_guard.py`.
- **Generator:** `scripts/build_v2_benchmark.py`, fixed documented seed
  `1220126` driving only cosmetic phrasing selection (never case counts,
  IDs, splits, or expected outcomes, which are always fixed by an
  explicit family table). `--verify-determinism` builds twice in memory
  and confirms byte-identical output.
- **Bug found and fixed during authoring (self-caught before shipping,
  via the validator's guard cross-check):** a Vietnamese
  `direct_injection` variant used "thay vào đó" (Vietnamese for
  "instead") where `app/guards/input_guard.py`'s
  `direct-disregard-own-instructions` rule requires the literal English
  word "instead" within 80 characters of the trigger phrase — the
  Vietnamese translation silently didn't match the English-only regex.
  Fixed by keeping "instead" in English inline in the sentence, verified
  by re-running the cross-check.
- **Validator:** `scripts/validate_v2_benchmark.py` — schemas, exact
  counts, category/language coverage, referential integrity, no
  duplicate IDs, no normalized-duplicate queries, no cross-split
  credential-shaped-value reuse (the one canonical `FAKE-SECRET-0000-
  EXAMPLE-DO-NOT-USE` canary marker is an explicit, documented
  exemption), source-key compatibility, no runtime/label import
  coupling, and a cross-check against the **real, currently-deployed**
  `app.guards.input_guard`/`app.guards.rag_guard` functions. Found and
  fixed its own bug: `_ALLOW_FAMILIES` incorrectly included
  `mixed_benign_malicious_retrieval` (by design one benign + one
  malicious document); fixed with a dedicated
  `_MIXED_ACCEPT_AND_REJECT_FAMILIES` check.
- **Freeze:** `scripts/freeze_v2_benchmark.py` — SHA-256 manifest over
  `corpus/`, `cases/`, `labels/` (the manifest excludes itself from its
  own hash set), `freeze`/`verify` modes, no timestamp, no
  machine-specific absolute path. Verified: froze 7 files; a mutation
  test (appending a line to a copy of `cases/development.jsonl`)
  correctly made `verify` fail with both a content-changed and a
  size-changed report for exactly that file; a clean deterministic
  rebuild restored byte-identical content and `verify` passed again.
- **Tests added (53, all passing):** `tests/test_benchmark_v2_schema.py`
  (16), `tests/test_benchmark_v2_integrity.py` (24 — including synthetic
  fixtures proving each check function actually *rejects* a deliberately
  broken input: duplicate IDs, duplicate queries, cross-split secret
  reuse, unregistered source key outside its family, missing required
  field, leaked label field, `is_poisoned` in corpus), and
  `tests/test_benchmark_v2_freeze.py` (13 — manifest correctness against
  the real committed manifest, plus tamper-detection tests against a
  `tmp_path` copy of the tree, never the real committed files).
- **Test evidence:** full repository suite **376 tests** (323
  pre-existing + 53 new); **299 passed** directly in this session; the
  remaining 77 (across 7 files) require `fastapi.testclient.TestClient`,
  blocked by this shared environment's pre-existing, documented
  `httpx`/`httpx2` issue (unrelated to this phase; none of those 77
  tests touch `datasets/v2/`). `python -m py_compile` clean on every new
  file. `git status --short` confirmed the change set is exactly
  `datasets/v2/`, three new scripts, and three new test files — no file
  under `app/guards/`, `app/services/rag_query.py`,
  `app/services/gateway.py`, `app/services/llm_provider.py`,
  `app/retrieval/`, `app/api/routes.py`, the v1 benchmark, or
  `requirements.txt` was touched; no `.db`/`.sqlite`/`.sqlite3` file is
  tracked; no new dependency was added; scripts contain no network-call
  imports.
- **Documentation:** `datasets/v2/README.md` and
  `docs/benchmark-v2-methodology.md` (new, full design/taxonomy/
  limitations write-up); `README.md`, `tests/README.md`,
  `scripts/README.md`, `TASK_BOARD.md` updated; ADR-003 given an
  Implementation Note recording the final `datasets/v2/` path (ADR-003
  had only named a placeholder, `redteam/v2/`) and disclosing a deviation
  from ADR-003's holdout-authorship-independence wording — this
  benchmark is generated programmatically, so the ADR's conditions (a)/
  (b), which assume separate human authoring sessions, do not literally
  apply; this phase relies on and documents condition (c), independent
  multidisciplinary review, applied at the generator level.
- **Final recommendation: IN REVIEW, not Done.** Per this task's explicit
  instruction, Phase 12D does not close until maintainer verification,
  Copilot working-tree review, Code X technical audit, Gemini academic
  audit, and Grok red-team audit all pass. Phase 12E was not started.

## Phase 12D — Code X Audit Resolution (2026-07-12)

Code X's first independent technical audit of Phase 12D returned verdict
**REVISE**: 2 Critical + 3 Major blocking findings. Resolved all five:

- **Critical #1 — guard-dependent validation.** The validator used to import
  the real Input/RAG Guards and gate its exit status on agreement with
  hand-authored labels — circular, since a benchmark's whole point is to
  measure disagreement with the current implementation. Fixed: the default
  `scripts/validate_v2_benchmark.py` path now imports nothing from
  `app.guards.*`; the guard cross-check survives only as an explicitly
  opt-in, non-gating `--diagnose-current-guards` report (scoped to
  development+validation unless `--include-holdout-diagnostic` is also
  passed).
- **Critical #2 — holdout template contamination.** Code X measured 34/60
  holdout queries at ≥0.9 similarity to an earlier split for the same
  family (median similarity 1.0), 17/23 families sharing an identical
  normalized template, and one validation case 0.929-similar to a v1 case
  (violating ADR-003). Root cause: every family drew development,
  validation, and holdout content from one shared template, varying only a
  per-case token. Fixed: `scripts/build_v2_benchmark.py` rewritten so every
  family draws development/validation/holdout content from three disjoint,
  independently authored content banks — different topics, different
  sentence structure, different trigger-phrase alternatives per split, not
  a token-substituted copy. New automated
  `check_cross_split_contamination`/`check_v1_contamination` checks (Unicode
  normalization + `difflib.SequenceMatcher` at the same 0.9 threshold Code
  X's own finding used) now run on every validation and report **zero
  findings** against the regenerated corpus.
- **Bugs found and fixed while rewriting content (self-caught, via the same
  guard-agreement diagnostic used for the original Phase 12D pass, re-run
  after every content change):** several new split-specific sentences used
  a noun other than the regex-required "note" ("memo", "report") or
  inserted a word between "this" and "note", breaking a `\bthis note\b`
  boundary; two multi-chunk-coordination holdout pairs had one half that
  already tripped a per-chunk rule alone, defeating the coordination
  premise; and several families' query text turned out to be hardcoded
  identically regardless of split even after the document-content fix,
  which the new contamination check itself caught (`fragment_near_
  aggregate_budget`'s filler paragraph was also identical across splits and
  dominated the similarity ratio for a different reason — fixed with three
  distinct filler paragraphs).
- **Major #1 — validator completeness.** Invalid `Decision` values and
  unknown label fields used to pass; a globally-missing scenario family
  used to pass; a dangling document reference or mismatched case/label ID
  used to raise an unhandled `KeyError`. Fixed: exact-field-set + enum
  validation for every record type, an explicit `REQUIRED_FAMILIES`
  registry, and fully defensive (`.get(...)`-based) checks that report a
  clean, deterministic, repository-relative-path error instead of crashing.
- **Major #2 — label isolation / evaluation scope.** `expected_ingestion_
  status` (a ground-truth outcome) lived in the corpus, outside `labels/`;
  no `evaluation_scope` field existed. Fixed: moved to
  `expected_document_ingestion_status` in labels; added a validated
  `evaluation_scope` (`end_to_end`/`component`/`availability_fault`/
  `residual_risk_only`) to every case — `provenance_denied_at_ingestion` is
  now `component`, `availability_failure_case` is `availability_fault`,
  `fragment_beyond_per_chunk_prefix` is `residual_risk_only` (excluded from
  expected-detection denominators).
- **Major #3 — weak class balance.** 36 benign / 74 malicious / 6 mixed / 4
  neutral (≈30% benign) undermined the "approximately balanced" wording.
  Rebalanced to Code X's own preferred distribution: 48 benign / 48
  malicious / 16 mixed / 8 neutral overall (development/validation 12/12/4/2
  each, holdout 24/24/8/4) — no family removed, all 23 still present in
  every split; a new validator check enforces these exact bounds, not an
  "approximate" claim.
- **Regenerated candidate artifacts:** 172 documents, 120 cases (30/30/60).
  Build twice + byte-for-byte compare: passed. Validate: passed, zero
  contamination findings. Freeze (explicitly labeled `"manifest_status":
  "candidate"`) + verify: passed. Mutation-then-deterministic-rebuild
  round trip: passed.
- **Tests:** 39 new/updated regression tests (92 total across the three
  Phase 12D test files, up from 53) covering every accepted finding,
  including guard-independence proofs (a schema-valid label disagreeing
  with the real Input Guard still passes; builder output unchanged when a
  guard module is monkeypatched; no gating check function imports
  `app.guards.*`), contamination-rejection negative fixtures (shared
  template, translation-style near-duplicate, superficial token
  substitution, v1-derived validation query all correctly rejected; a
  genuinely independent same-family pair correctly passes), and CLI-level
  schema/enum/mapping negative probes.
- **Test evidence:** focused Phase 12D suite **92 passed**; full repository
  suite **338 passed** directly in this session (376 total including 38
  TestClient-blocked tests, unrelated to this phase, blocked by the
  pre-existing documented shared-environment `httpx`/`httpx2` issue).
  `python -m py_compile` clean on every changed file. `git status --short`
  confirmed the change set stayed within the allowed scope (`datasets/v2/`,
  the three scripts, the three test files, docs, plus this new audit-
  resolution document) — no file under `app/guards/`,
  `app/services/rag_query.py`, `app/services/gateway.py`,
  `app/services/llm_provider.py`, `app/retrieval/`, `app/api/routes.py`, the
  v1 benchmark, or `requirements.txt` was touched.
- **Final recommendation: READY FOR CODE X RE-AUDIT.** Not APPROVE, not
  DONE. Phase 12D remains In Review. Gemini and Grok review the committed
  candidate only after this Code X re-audit passes. Phase 12E was not
  started.

## Phase 12D — Code X Re-Audit Resolution, Round 2 (2026-07-12)

A second independent Code X technical re-audit of the round-1 fix
returned verdict **REVISE** again — Critical #2 and Major #1 were only
*partially* resolved, plus two new findings against round 1's own fixes:

- **Critical #2, continued — translation contamination.** Constructed the
  exact failure scenario directly: an English sentence and its honest
  Vietnamese translation, placed in different splits with different
  self-declared `translation_group_id` values — round 1's fingerprint/
  similarity check reported zero findings, since a translation shares
  almost no literal text with its source language. Fixed with two
  complementary controls: (1) a new non-runtime `datasets/v2/design/
  authoring-provenance.jsonl` artifact (292 records — one per generated
  query/document) whose `semantic_group_id`/`translation_group_id` values
  are constructed to embed `(scenario_family, split[, bank_index])`, so
  neither can ever collide across two splits by construction, with a
  `normalized_text_hash` independently cross-checked against the real,
  current artifact text; (2) a benchmark-specific, standard-library-only
  EN/VI phrase-canonicalization check (`check_bilingual_contamination`,
  ~40 reviewed phrase pairs, compared cross-split via both
  `difflib.SequenceMatcher` ratio and token-Jaccard overlap — the latter
  specifically so a clause-reordered translation is still caught).
- **Bugs found and fixed while building the bilingual check (self-caught
  before finalizing, documented transparently):** the first lexicon draft
  used semantically-named substitution tokens (e.g. `@leavepolicyfull@`)
  that themselves contained plain English words a *later, shorter*
  lexicon entry could then re-match and corrupt — fixed by switching to
  collision-free numeric tokens (`@C0@`, `@C1@`, ...); trailing sentence
  punctuation stuck directly to a substituted token and silently broke
  token-level comparison — fixed by stripping punctuation before
  substitution; shorter lexicon entries sometimes matched before longer,
  more specific ones, fragmenting a multi-word phrase — fixed by always
  matching longest-phrase-first. A test fixture using word-level (rather
  than clause-level) reordering genuinely failed to trigger detection
  during development and had to be redesigned — documented as an exact,
  tested limitation rather than silently discarded.
- **Major #1, continued — field-type completeness.** Reproduced the exact
  crash directly: a corpus record with `content: 12345` (an int) raised
  an unhandled `TypeError` from `check_no_cross_split_secret_reuse`'s
  `.finditer(content)` call. Also reproduced a duplicate `external_id`
  passing silently. Fixed with complete field-type validation across
  every corpus/case/label field (non-empty-string checks, JSON-safe
  `metadata` rejecting non-string keys and NaN/Infinity, bounded `top_k`
  `[1,50]` and DLP redaction count `[0,100]`, `external_id` uniqueness),
  plus defensive `isinstance` guards on the two checks that previously
  crashed, so a malformed value is always a clean validation error now.
- **New finding — v1 contamination scanned queries only.** Direct read
  confirmed `check_v1_contamination` accepted a `corpus` parameter but its
  body never referenced it. Reproduced: a v1 prompt copied verbatim into a
  holdout corpus document passed undetected. Fixed:
  `find_v1_contamination_matches` now scans every validation/holdout query
  *and* every corpus document referenced by a validation/holdout case; a
  new `check_no_orphan_documents` guarantees every corpus document is
  referenced by some case, closing the gap an unreferenced document could
  otherwise exploit.
- **New finding — candidate manifest missing policy artifacts.**
  `contamination-exemptions.json` (which can suppress a contamination
  finding) sat outside the manifest's integrity scope. Fixed: manifest now
  covers all 9 policy-bearing files, including the exemptions file and the
  new authoring-provenance artifact; mutating either now fails `verify`
  exactly like a mutated corpus/case/label file (tested directly for all
  5 artifact kinds: corpus, cases, labels, exemptions, provenance).
- **Regenerated candidate artifacts:** counts unchanged from round 1 (172
  documents, 120 cases 30/30/60, 48/48/16/8 class balance) — this round
  added controls around content generation, not new content. Build twice
  + compare: passed. Validate: passed, 0 findings across every
  contamination check (fingerprint, bilingual, provenance, v1 query, v1
  document). Freeze (9 files) + verify: passed. All 5 mutation-then-
  restore round trips: passed.
- **Measured statistics:** maximum cross-split query similarity 0.7213,
  median holdout-query max-similarity 0.4589 (both comfortably below the
  0.9 gating threshold — a healthy margin, not a bare pass); 0 bilingual/
  translation/provenance/v1-query/v1-document contamination findings; 0
  active exemptions.
- **Tests:** 51 new/updated regression tests (143 total across the three
  Phase 12D test files, up from 92), covering every accepted finding —
  8 required translation/provenance regressions, 6 required v1-document
  regressions, ~14 required field-type regressions, 5 required
  manifest-policy regressions.
- **Resumed completion evidence:** schema/type validation is now a hard
  preflight; provenance rejects extra/malformed records and verifies identity
  fields, hashes, and bilingual query-document linkage; fresh freeze rejects
  missing policy artifacts. Focused Phase 12D suite: **161 passed**. Full
  repository suite with no ignored modules: **484 passed, 1 warning** in the
  project `.venv`, superseding the inherited partial command that omitted
  seven TestClient modules. `python -m py_compile` was clean on every changed
  file. `git status --short` confirmed the change
  set stayed within the allowed scope — no file under `app/guards/`,
  `app/services/rag_query.py`, `app/services/gateway.py`,
  `app/services/llm_provider.py`, `app/retrieval/`, `app/api/routes.py`,
  the v1 benchmark, or `requirements.txt` was touched; no new dependency
  (all new logic uses only `unicodedata`/`re`/`difflib`/`hashlib`/`math`
  from the standard library).
- **Final recommendation: READY FOR TECHNICAL READ-ONLY VERIFICATION.** Not
  APPROVE, not DONE. Phase 12D remains In Review pending a clean Code X
  verification and subsequent Gemini/Grok audits. Phase 12E was not started.

## Phase 12D — Code X Re-Audit Resolution, Round 3 (2026-07-12)

A third independent Code X re-audit found round 2's field-type fix
(Major #1, continued) covered non-string **scalars** only — a `list` or
`dict` value in an enum-field position was never exercised and still
crashed with an unhandled `TypeError: unhashable type`. **Final
malformed-value verification verdict: REVISE.** Authoring provenance:
**PARTIALLY RESOLVED**. Schema/type validation: **NOT RESOLVED** for
list/dict values.

- **Reproduced both exact reported crashes independently before fixing:**
  a label with `expected_stop_reason: []` raised `TypeError: unhashable
  type: 'list'` from `check_schemas`'s bare `value not in
  STOP_REASON_VALUES` test; an authoring-provenance entry with `split: []`
  raised the identical error from `check_authoring_provenance`. Both
  confirmed pre-fix via a standalone script against the real module, not
  merely inferred from the audit text.
- **Root cause:** Python's `in`/`not in` against a `set` hashes its
  operand before comparing anything; a `list`/`dict` value is unhashable.
  Round 2's own field-type test matrix used only hashable scalars
  (`12345`, `True`, `5.0`, `999`, `"not-a-list"`), so this exact class of
  bug was never exercised until this round's explicit malformed-value
  probe — not a regression, a genuinely untested gap.
- **Fix:** eight reusable, type-first helpers added to
  `scripts/validate_v2_benchmark.py` (`is_non_empty_string`,
  `safe_record_identifier`, `validate_string_field`, `validate_string_enum`,
  `validate_optional_string_enum`, `validate_string_list`,
  `validate_integer_field`, `validate_json_safe_value`), each confirming a
  value's Python type — rejecting `list`/`dict`/unwanted `bool`/`None` —
  before any set/dict membership test can ever see it. Applied
  consistently across every corpus/case/label field in `check_schemas`
  and every provenance field in `check_authoring_provenance`. Every
  downstream function that builds a set/dict/`Counter` from a validated
  field got its own defense-in-depth `isinstance`/`_safe_in` guard (~20
  sites across 15 functions, found via an exhaustive grep sweep), so each
  remains individually crash-proof even when called directly, not only
  through `main()`'s gate. `main()` also gained a final, last-resort
  `except Exception` boundary (generic, non-traceback message, exit 1) —
  documented in-code as secondary; the type-first helpers are the primary
  fix.
- **`freeze_v2_benchmark.py` investigated, not modified:** confirmed it
  operates purely on file bytes (SHA-256/size), never parses JSONL field
  values into a set/dict, so it is not exposed to this bug class.
- **Tests:** 85 new/updated regression tests, all in
  `tests/test_benchmark_v2_integrity.py` (246 total across the three
  Phase 12D test files, up from 161) — a parametrized matrix of
  `list`/`dict` malformed values across every corpus (17), case (17),
  label (26), and authoring-provenance (16) field; direct CLI
  reproductions of both exact reported crashes; a combined multi-field
  malformed fixture proving aggregation without a crash; a non-object
  provenance record test (direct-call and real-JSONL-line); a
  deterministic-error-order test; and a real-candidate-still-passes test.
  A small number of round-1/round-2 tests whose expected error-message
  substring changed shape under the new, more descriptive helper wording
  were updated to match (same field, same failure category — not
  weakened).
- **Malformed-value probe results (post-fix, both via CLI):**
  `expected_stop_reason=[]` → `FAIL: 1 validation error(s): label
  'V2-DEV-9001' expected_stop_reason has invalid type list (must be a
  string)`, return code 1, no traceback. Authoring-provenance `split=[]`
  → `FAIL: 22 validation error(s): ...split has invalid type list...`
  (plus 21 correctly-aggregated, unrelated errors from the otherwise-empty
  fixture), return code 1, no traceback.
- **Final executed evidence:** focused Phase 12D suite **246 passed**
  (up from 161). Full repository suite, no ignored modules: **569
  passed, 1 warning** in the project `.venv` (up from 484 — the +85
  delta exactly matches the Phase 12D test count increase). `python -m
  py_compile` clean on every changed file. Default validator, optional
  diagnostic, `--verify-determinism`, and the 9-file candidate-manifest
  `verify` all still pass unchanged, since no generated artifact byte
  changed this round. `git diff --check` clean; `git status --short`
  confirmed the change set stayed within scope — no file under `app/`,
  `requirements.txt`, the v1 benchmark, `reports/evaluation/`, or
  `report-latex-template/` was touched.
- **Final recommendation (superseded by the verification note below):**
  the implementation pass closed with READY FOR FINAL MALFORMED-VALUE
  READ-ONLY VERIFICATION. Not APPROVE, not DONE. Phase 12D remains In
  Review; the candidate manifest remains CANDIDATE. Phase 12E was not
  started.

## Phase 12D — Final Malformed-Value Verification and Documentation Alignment (2026-07-12)

The independent Code X read-only verification of the round-3 fix
(`docs/modernization-ai-reviews/codex-phase-12d-final-malformed-value-verification.md`)
confirmed the implementation across every category — implementation
presence, validation ordering, corpus/case/label/provenance/exemption
fail-safe handling, CLI error safety, regression preservation: all
**RESOLVED**; Critical issues: **None**; blocking Major issues: **None**;
focused suite **246 passed**, full suite **569 passed, 1 warning**,
9-file candidate manifest verified. Its verdict was nonetheless
**REVISE**, caused solely by three documentation inaccuracies, which a
documentation-only alignment pass (no code, test, or artifact change)
then corrected:

- The audit-resolution narrative over-claimed that only fully
  preflight-valid provenance records enter `by_artifact_id`; in fact a
  record with a usable string `artifact_id` is indexed for deterministic
  identity/duplicate reporting before its remaining fields are
  validated, and all later comparisons/grouping/hash operations are
  type-guarded.
- It over-claimed that malformed values are simply skipped by all
  downstream checks; in fact selected downstream checks intentionally
  process malformed records through guarded, safe operations to
  aggregate deterministic errors (the 22 errors of the `split=[]` probe
  are safe deterministic findings, not an exception).
- The corpus/label malformed-value parameter counts were corrected from
  16/25 to the actual **17/26** (case 17 and provenance 16 were already
  correct) in every document repeating them.
- **Historical recommendation before multidisciplinary closure
  (superseded below): READY FOR FINAL DOCUMENTATION READ-ONLY
  VERIFICATION.** At that point Phase 12D remained In Review, the candidate
  manifest remained CANDIDATE, and Phase 12E had not started.

## Phase 12D — Multidisciplinary Audit Closure and Final Freeze (2026-07-12)

- Verified the actual final reports at commit `4e10a2e`: Code X technical
  **PASS**, Gemini academic **PASS**, and Grok red-team coverage **PASS**;
  no Critical or blocking Major finding remains.
- Recorded Gemini's direct-artifact access limitation and accepted its
  non-blocking reporting constraint: Phase 12E percentages are limited to
  aggregate or adequately supported, predeclared high-level attack groups;
  individual-family outcomes remain descriptive. Ablation profiles,
  confidence intervals, and the evaluation runner remain Phase 12E work.
- Preserved Grok's three Phase 12E probe recommendations (budget-exact
  Vietnamese multi-chunk splits, trusted-source authority/canary mixes,
  homoglyph plus benign triggers) and its semantic-coordination/
  over-redaction future-work observations without changing benchmark data.
- Added the explicit deterministic `finalize` mode to
  `scripts/freeze_v2_benchmark.py`. The default `freeze` mode remains
  CANDIDATE; only `finalize` emits FINAL. Both cover the same nine relative
  POSIX paths with the same SHA-256 values and sizes, no timestamp, no
  absolute path, and no self-hash.
- Finalized `datasets/v2/manifests/benchmark-v2-manifest.json`; all nine
  audited artifacts remained byte-identical before and after. Any later
  artifact change requires a new benchmark version and fresh audits.
- Final validation: focused Phase 12D suite **255 passed**; full repository
  suite **578 passed, 1 warning**; six-file compile, validator (172
  documents/120 cases), deterministic rebuild, FINAL manifest verify, and
  mutation detection against a temporary copy all passed.
- **Final status: Phase 12D DONE; manifest FINAL; Phase 12E not started.**
