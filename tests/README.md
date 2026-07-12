# tests/

pytest coverage for the gateway, dataset loader, three rule-based guards, and
the Phase 12B retrieval foundation.

**Status: Phase 12B (In Review), post Code X audit and re-audit
resolution.** Coverage includes the offline provider contract, bypass
variants, targeted RAG sanitization, benign false positives, gateway
ordering, severity aggregation, audit redaction, and (Phase 12B)
deterministic chunking, SQLite FTS5/BM25 retrieval, safe FTS query
construction, atomic ingestion/upsert, server-controlled source policy,
recursive metadata-spoofing defenses, and the two new retrieval routes.
**177 tests total** (82 pre-Phase-12B + 95 Phase 12B, the latter including
regression tests added across two rounds of independent audit
resolution — see
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
| `test_ingestion.py` | **Phase 12B.** Successful single/batch ingestion, duplicate external_id, unchanged/updated content, oversized/empty documents, unknown source_key, spoofed trust/classification metadata ignored, stable canonical IDs, `is_poisoned` never stored, and (audit fixes) public-endpoint elevated-trust-source rejection, nested/case/whitespace metadata-key spoofing, metadata depth bounds, auditable-without-leaking spoof attempts, same-text-replay field updates, configured resource limits, and ID normalization. |
| `test_retrieval_routes.py` | **Phase 12B.** `POST /v1/documents/ingest` and `POST /v1/retrieve` request/response validation, top_k bounds, safe error responses, regression checks that `/health` and `/v1/gateway/chat` are byte-identical to their pre-Phase-12B behavior, and (audit fixes) HTTP-level elevated-trust-source rejection and safe storage-failure error mapping. An autouse module-scoped fixture cleans up every document this file's tests create. |

## Running

```powershell
python -m pytest -q
```

Guard and loader tests run directly. Endpoint tests use FastAPI's `TestClient`
against `app.main:app`; they make no external network calls. Use a clean
project-local environment with the genuine dependencies from `requirements.txt`.
Never install `httpx2`; see the shared-environment warning in `TASK_BOARD.md`.

No test calls a real LLM, uses a vector database, or installs dependencies.
All added attack strings are synthetic and non-operational.
