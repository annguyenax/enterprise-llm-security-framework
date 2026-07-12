# tests/

pytest coverage for the gateway, dataset loader, three rule-based guards, and
the Phase 12B retrieval foundation.

**Status: Phase 12B (In Review), post Code X audit and two rounds of
independent re-audit resolution. Not yet marked Done — a further
independent re-audit of the latest pass is still required (see
`docs/modernization-ai-reviews/phase-12b-audit-resolution.md`).**
Coverage includes the offline provider contract, bypass variants,
targeted RAG sanitization, benign false positives, gateway ordering,
severity aggregation, audit redaction, and (Phase 12B) deterministic
chunking, SQLite FTS5/BM25 retrieval, safe FTS query construction, atomic
ingestion/upsert, server-controlled source policy, recursive
metadata-spoofing defenses, bounded iterative metadata preflight
(structure/type/cycle/depth) with UTF-8 byte-size enforcement, and the
two new retrieval routes. **188 tests total** (82 pre-Phase-12B + 106
Phase 12B, the latter including regression tests added across three
rounds of independent audit resolution — see
`docs/modernization-ai-reviews/phase-12b-audit-resolution.md`).

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
| `conftest.py` | **Final re-audit fix.** Session-wide, non-behavioral pytest configuration: redirects `RETRIEVAL_DB_PATH` to a per-session temporary path before any test module in this directory is collected/imported, so the very first `app.main` import in the session (which eagerly creates the SQLite retrieval schema, per Minor #1) never touches the repository's `data/retrieval.db`. |

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
