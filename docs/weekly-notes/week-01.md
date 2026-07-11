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

## Next Week Plan

- Team members personally read the three logged academic papers and confirm/replace the placeholder "Summary" fields in `related-work.md` with their own understanding.
- Research LlamaIndex vs. LangChain, ChromaDB vs. alternatives, and candidate API-based LLM providers.
- Review garak/PyRIT/deepteam's bundled probe sets for licensing and content type, logging proper entries in `dataset-review.md`.
- Materialize `docs/evaluation/red-team-test-design.md` into actual files under `datasets/` and `redteam/`, using the ID convention in that document's §6 — this is data-file creation, not code, but should be scoped/approved as its own step before Phase 3 code begins.
- Confirm Phase 0/1/2/2.5 documentation deliverables satisfy periodic report 01 requirements.
