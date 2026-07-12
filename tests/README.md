# tests/

pytest coverage for the gateway, dataset loader, rule-based guards, the
Phase 12B retrieval foundation, the Phase 12C end-to-end RAG pipeline, and
the Phase 12D v2 benchmark artifacts (`datasets/v2/`).

**Status: Phase 12C In Review — two rounds of Code X final re-audit each
found and fixed one blocking terminal-audit-coverage gap (top_k rejection
and response-construction failure not audited, then nested
`ProvenanceItemResponse` construction not protected); ready for one final
independent re-audit, not yet marked Done.** Phase 12B is post Code X
audit and three rounds of independent re-audit resolution (see
`docs/modernization-ai-reviews/phase-12b-audit-resolution.md`); Phase 12C's
Gemini/Grok/Code X findings, the multidisciplinary resolution, and both
subsequent Code X final re-audit fixes are all recorded in
`docs/modernization-ai-reviews/phase-12c-audit-resolution.md`. Coverage
includes the offline provider contract, bypass variants, targeted RAG
sanitization, benign false positives, gateway ordering, severity
aggregation, audit redaction, (Phase 12B) deterministic chunking, SQLite
FTS5/BM25 retrieval, safe FTS query construction, atomic ingestion/
upsert, server-controlled source policy, recursive metadata-spoofing
defenses, bounded iterative metadata preflight (structure/type/cycle/
depth) with UTF-8 byte-size enforcement, the two Phase 12B retrieval
routes, and (Phase 12C) the deterministic Provenance/Trust Guard,
centralized DLP redaction (plus consolidation-parity regression against
the previously-duplicated `output_guard`/`audit_logger` patterns), the
full end-to-end `POST /v1/rag/query` pipeline (stage order, every
fail-closed stop path, the bounded multi-chunk aggregate check), and
HTTP-level request/response coverage for that endpoint, including both
terminal-audit-coverage fixes: configured `top_k` policy rejection and
outer/nested response-construction failure (`ProvenanceItemResponse`,
`StageResultResponse`) each now commit exactly one safe, accurate audit
event, with the entire response tree built inside one protected block.
**323 tests total** (82 pre-Phase-12B + 106 Phase 12B + 135 Phase 12C —
see `docs/modernization-ai-reviews/phase-12b-audit-resolution.md` for the
Phase 12B breakdown).

## Test Modules

| File | Covers |
|---|---|
| `test_health.py` | `GET /health`. |
| `test_input_guard.py` | Input Guard behavior. |
| `test_input_guard_calibration.py` | Phase 7.1 failed cases, nearby attack variants, and benign counterexamples. |
| `test_output_guard.py` | Output decisions and redaction. |
| `test_dataset_loader.py` | Markdown parsing, extraction, and chunking (v1 loader, unchanged). |
| `test_rag_guard.py` | Corpus behavior, normalization, bypass variants, compound severity, and benign false positives. |
| `test_rag_context_endpoint.py` | RAG endpoint, sanitization, metadata, and audit behavior. |
| `test_gateway_routes.py` | Guard ordering, RAG continuation, short-circuiting, severity, and audit logging. |
| `test_llm_provider.py` | Deterministic mock behavior and factory fail-closed behavior. |
| `test_gateway_provider.py` | Provider placement, skip paths, sanitized inputs, Output Guard handoff, response metadata, and safe audit metadata. |
| `test_evaluation_runner.py` | JSONL validation, all 40 prompts, controlled FP/FN definitions, baseline/guarded modes, corpus immutability, provider isolation, and report generation. |
| `test_chunking.py` | **Phase 12B.** Deterministic paragraph-aware chunking: normal/empty/whitespace-only/oversized-paragraph/exact-boundary/overlap/Unicode-Vietnamese/determinism/stable IDs/no-empty-chunks. |
| `test_sqlite_bm25.py` | **Phase 12B.** FTS5 capability (success, simulated failure, no-fallback), schema/persistence/foreign-keys, atomic upsert/rollback, no-stale-FTS-rows after replace, deterministic ranking, adversarial FTS query strings, and (audit fixes) extra-term retrieval suppression, BM25 term-coverage ranking under OR, and unchanged-detection covering title/metadata/policy fields. |
| `test_ingestion.py` | **Phase 12B.** Successful single/batch ingestion, duplicate external_id, unchanged/updated content, oversized/empty documents, unknown source_key, spoofed trust/classification metadata ignored, stable canonical IDs, `is_poisoned` never stored, and (audit fixes) public-endpoint elevated-trust-source rejection, nested/case/whitespace metadata-key spoofing, metadata depth bounds, auditable-without-leaking spoof attempts, same-text-replay field updates, configured resource limits, ID normalization, and (final re-audit fixes) UTF-8 byte-size measurement (Vietnamese text, exact/one-over boundary), bounded iterative preflight rejecting ~900-level nested lists and deep mixed dict/list nesting without an unhandled RecursionError, direct-Python cyclic-metadata rejection, shared/repeated (non-cyclic) values not being false-positively rejected, and audit-log safety for both new rejection paths. |
| `test_retrieval_routes.py` | **Phase 12B.** `POST /v1/documents/ingest` and `POST /v1/retrieve` request/response validation, top_k bounds, safe error responses, regression checks that `/health` and `/v1/gateway/chat` are byte-identical to their pre-Phase-12B behavior, and (audit fixes) HTTP-level elevated-trust-source rejection, safe storage-failure error mapping, and (final re-audit fixes) HTTP-level UTF-8 oversize and deep-nesting rejection, and a route-level list-of-list metadata-spoofing regression extended to cover all four reserved keys. An autouse module-scoped fixture gives this module its own fresh, isolated database file. |
| `conftest.py` | **Phase 12B final re-audit fix.** Session-wide, non-behavioral pytest configuration: redirects `RETRIEVAL_DB_PATH` to a per-session temporary path before any test module in this directory is collected/imported, so the very first `app.main` import in the session (which eagerly creates the SQLite retrieval schema, per Minor #1) never touches the repository's `data/retrieval.db`. |
| `test_provenance_guard.py` | **Phase 12C.** Deterministic Provenance/Trust Guard: allowed public/internal sources, unknown/malformed trust level, classification restriction, unknown source_type, mixed accepted/rejected batches, all-rejected batches, caller-metadata spoofing has no effect (decision reads only server-assigned hit fields), the allow-lists match `app/core/source_policy.py`'s real values, and acceptance does not imply content safety (trust does not bypass the RAG Context Guard). |
| `test_dlp_guard.py` | **Phase 12C.** Centralized DLP: complete-prefix enforcement with no uninspected suffix, after/across-boundary credential and private-key cases, long-benign truncation, non-overlapping source-span counts, full shared audit redaction API, repeated secrets, benign counterexamples, and historical Output Guard parity. |
| `test_rag_pipeline.py` | **Phase 12C.** Service-level `run_rag_query()` coverage: full stage order and stop paths; sanitized-only provider input; provider context byte-for-byte bounded by aggregate enforcement; aggregate SANITIZE fail-closed; per-chunk/global-budget and separator accounting; multilingual/zero-width split attacks; high-trust malicious content; benign authority/academic counterexamples; DLP SANITIZE telemetry; retrieval/provenance/context/aggregate/provider/DLP/output/audit-sink exception behavior; two real-SQLite end-to-end cases; and (Code X final re-audit) `top_k`-rejection audit, `run_rag_query_uncommitted`/`commit_rag_query_audit` deferred-commit behavior, `mark_response_construction_failed`'s corrected audit event, and an exact empty-sanitized-query (`sanitized_text=""`) regression. |
| `test_rag_query_routes.py` | **Phase 12C.** HTTP-level strict schema, safe response/error mapping, no uninspected DLP tail, real-endpoint nested audit redaction for all detector families, response-construction safety, request IDs, backward compatibility for `/health`, `/v1/gateway/chat`, ingestion and retrieval, and (Code X final re-audit) exactly-one-safe-terminal-event coverage for both the configured `top_k` policy rejection and a forced `RagQueryResponse` construction failure, including audit-sink-failure behavior for each; and (Code X final terminal-audit re-audit) the same guarantee extended to nested response-model construction (`ProvenanceItemResponse`, `StageResultResponse`) — forced failure, combined with a broken audit sink, and the unaffected success path. |
| `test_phase12c_config.py` | **Phase 12C audit resolution.** Direct and environment-driven validation for positive limits, top-k relationships, hard ceilings, malformed integers/booleans, contradictory values, valid boundaries, and backward-compatible direct `Settings(...)` construction. |
| `test_benchmark_v2_schema.py` | **Phase 12D, updated across two Code X audit-resolution rounds.** Corpus/case/label schema for `datasets/v2/`: required fields (case files include `evaluation_scope`; corpus carries no `expected_ingestion_status`; labels carry `expected_document_ingestion_status`/`template_id`/`semantic_group_id`/`translation_group_id`/`authoring_set`), no ground-truth field in the corpus, case files contain only execution inputs, label files carry the full ground-truth schema using real `Decision` values, every case has exactly one matching label, and (round 2) the non-runtime `datasets/v2/design/authoring-provenance.jsonl` artifact's own schema: required fields, valid `artifact_type`, `split`/`authoring_set` agreement, 64-char hex `normalized_text_hash`, coverage of every query and document, no duplicate `artifact_id`, no cross-split `semantic_group_id`/`translation_group_id` reuse, and confirmation none of its fields leak into the runtime case/corpus schema. |
| `test_benchmark_v2_integrity.py` | **Phase 12D, updated across three Code X audit-resolution rounds and the resumed completion pass.** Real-data checks cover counts, distributions, taxonomy, mappings, IDs, contamination, provenance, v1 isolation, deterministic ordering, and runtime separation. Negative fixtures cover real EN/VI translations, reordered translations, provenance hash/group/identity/schema failures, v1 query/document copies, malformed corpus/case/label values, and guard independence. The completion pass adds an exact CLI rejection matrix for malformed types, rejects extra provenance records, cross-checks provenance identity fields against real artifacts, and verifies bilingual query-document source-group linkage. **Round 3 (malformed-value re-audit)** adds a parametrized matrix of `list`/`dict`/`bool`/`float` values across every corpus (17), case (17), label (26), and authoring-provenance (16) field (parameter-combination counts, verified from the `*_MALFORMED_FIELDS` arrays; 4 parametrized test functions producing 76 collected pytest cases, plus 9 single-case test functions) — each proven to produce a clean, type-first validation error rather than an unhandled `TypeError: unhashable type`; direct CLI-level reproductions of the two exact reported crashes (`expected_stop_reason=[]`, provenance `split=[]`); a combined multi-field malformed fixture proving aggregation without a crash; a non-object provenance record test (both direct-call and real JSONL-line CLI); a deterministic-error-order test; and a confirmation the real, unmutated candidate benchmark still passes end to end. |
| `test_benchmark_v2_freeze.py` | **Phase 12D final freeze.** Candidate and FINAL manifest correctness covers all 9 policy-bearing files, SHA-256/size/path/order safety, mutation detection for all five artifact kinds, missing/new files, and deterministic restoration. Finalization tests prove candidate remains the default, FINAL requires the explicit `finalize` mode, repeated finalization is byte-identical, all covered artifacts remain unchanged, final verification succeeds, and mutation/incomplete-tree detection remains active. |

## Running

```powershell
python -m pytest -q
```

Final Phase 12D evidence: `255 passed` across the three benchmark modules;
complete repository suite `578 passed, 1 warning`, with no ignored test
module. The increase from 246/569 is exactly the nine explicit-finalization
regressions in `test_benchmark_v2_freeze.py`.

If the shared machine's default Windows temp directory has a pre-existing
permissions issue (unrelated to this project), pass an explicit writable
`--basetemp`, e.g. `python -m pytest -q --basetemp=C:\some\writable\dir`.

Guard and loader tests run directly. Endpoint tests use FastAPI's `TestClient`
against `app.main:app`; they make no external network calls. Use a clean
project-local environment with the genuine dependencies from `requirements.txt`.
Never install `httpx2`; see the shared-environment warning in `TASK_BOARD.md`.

No test calls a real LLM, uses a vector database, or installs dependencies.
All added attack strings are synthetic and non-operational.
