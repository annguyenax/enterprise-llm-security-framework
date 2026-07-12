# tests/

pytest coverage for the gateway, dataset loader, rule-based guards, the
Phase 12B retrieval foundation, and the Phase 12C end-to-end RAG pipeline.

**Status: Phase 12C (In Review).** Phase 12B is post Code X audit and
three rounds of independent re-audit resolution (see
`docs/modernization-ai-reviews/phase-12b-audit-resolution.md`); Phase 12C
is newly implemented and has not yet had an independent audit pass.
**Neither phase is marked Done yet** — see `TASK_BOARD.md`. Coverage
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
HTTP-level request/response coverage for that endpoint. **267 tests
total** (82 pre-Phase-12B + 106 Phase 12B + 79 Phase 12C — see
`docs/modernization-ai-reviews/phase-12b-audit-resolution.md` for the
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
| `test_dlp_guard.py` | **Phase 12C.** Centralized DLP: no-secret passthrough, single/multiple/repeated secret redaction, full private-key-block redaction, benign-identifier non-over-redaction, Vietnamese surrounding text preserved, bounded-input-size truncation, findings never carry the raw value, and consolidation-parity regression proving `app.guards.output_guard` and `app.services.audit_logger`'s redaction behavior is byte-identical after both were changed to import their patterns from this module instead of duplicating them. |
| `test_rag_pipeline.py` | **Phase 12C.** Service-level `run_rag_query()` coverage (via a stub retriever test double plus two real-`SqliteBM25Retriever` end-to-end cases): full stage order, every fail-closed stop path (input blocked, no hits, all rejected by provenance, all/aggregate-blocked by the RAG Context Guard, provider failure, output blocked), guard-exception fail-closed behavior at every stage, rejected chunks never reaching the provider, DLP redaction before the Output Guard sees the text, no raw secret or raw query in the audit log, and the bounded aggregate check catching an instruction split across two otherwise-clean chunks. |
| `test_rag_query_routes.py` | **Phase 12C.** HTTP-level `POST /v1/rag/query` coverage: strict-schema rejection of `context_chunks`/`trust_level`/`classification`/`source_type`/`is_poisoned`/`expected_decision`/`security_decision`/`document_id`/`chunk_id`, safe response shape (no full chunk text in provenance), safe error mapping (storage failure, empty-query 400, configured `top_k` maximum 400), unique request IDs, and regression checks that `/health`, `POST /v1/gateway/chat` (including with a matching ingested document present, to prove it never silently switches to retrieval), and `POST /v1/retrieve` are all unaffected. An autouse module-scoped fixture gives this module its own fresh, isolated database file. |

## Running

```powershell
python -m pytest -q
```

If the shared machine's default Windows temp directory has a pre-existing
permissions issue (unrelated to this project), pass an explicit writable
`--basetemp`, e.g. `python -m pytest -q --basetemp=C:\some\writable\dir`.

Guard and loader tests run directly. Endpoint tests use FastAPI's `TestClient`
against `app.main:app`; they make no external network calls. Use a clean
project-local environment with the genuine dependencies from `requirements.txt`.
Never install `httpx2`; see the shared-environment warning in `TASK_BOARD.md`.

No test calls a real LLM, uses a vector database, or installs dependencies.
All added attack strings are synthetic and non-operational.
