# Phase 12B Resolution Re-audit

## Reviewed commits
- Original implementation: `6bfb7147a080346b1879bd8e05fd04efec5f36c5`
- Fix commit: `04f68dd9fda9f8e58553fad844a27384de96aa21`
- Tests executed by reviewer: yes — `165 passed, 1 warning` using the project `.venv`, with database, audit log, pytest cache, bytecode, and basetemp redirected outside the repository

## Original Major Findings

### 1. Public source-policy trust escalation
- Status: RESOLVED
- Exact file and function: `app/core/source_policy.py::resolve_source_policy`, `app/services/ingestion.py::IngestionService.ingest_batch`
- Code evidence: Only `api_upload` exists in `PUBLIC_SOURCE_POLICIES`. Internal policies require explicit `allow_internal=True`; public ingestion calls the default public-only resolver. Trust, classification, and source type are taken from the frozen `SourcePolicyDecision`.
- Regression-test evidence: `test_public_ingestion_cannot_claim_trusted_synthetic_source_key` and `test_public_ingestion_cannot_claim_trusted_synthetic_source`
- Remaining risk: Future internal callers must not expose `allow_internal=True` to unauthenticated request input.
- Blocking: no

### 2. Nested metadata spoofing
- Status: PARTIALLY RESOLVED
- Exact file and function: `app/services/ingestion.py::_metadata_depth`, `_sanitize_metadata`, `IngestionService._log_ingestion_event`
- Code evidence: Dictionary nesting, key case, surrounding whitespace, hyphens, and underscores are handled. Size and nominal depth limits exist, and the audit event stores only `metadata_keys_stripped`.
  
  However, list nesting is not traversed correctly. `_metadata_depth` does not increment depth for lists, and `_sanitize_metadata` only sanitizes dictionaries that are direct list elements. A reviewer probe using:
  `{"wrapper": [[{" TrUsT-LeVeL ": "trusted_internal", "is_poisoned": true, "expected_decision": "allow"}]]}`
  produced `metadata_keys_stripped=0` and persisted every prohibited value.
  
  The size check also runs after sanitization, so arbitrarily large values under stripped keys evade the configured metadata-size rejection after request parsing has already consumed them.
- Regression-test evidence: Existing tests cover nested dictionaries and deeply nested dictionaries, but not lists-of-lists or raw pre-sanitization metadata size.
- Remaining risk: Security and benchmark labels can still be persisted through list-of-list metadata; the audit signal incorrectly reports no stripping.
- Blocking: yes

### 3. Incorrect unchanged detection
- Status: RESOLVED
- Exact file and function: `app/retrieval/sqlite_bm25.py::_is_unchanged`, `SqliteBM25Retriever.upsert_documents`
- Code evidence: Comparison now includes content hash, title, canonical safe metadata, source type, classification, and trust level. Any difference enters the existing transactional replacement path.
- Regression-test evidence: `test_unchanged_detection_covers_title_metadata_and_policy_fields` and `test_same_text_replay_with_changed_title_and_metadata_is_updated`
- Remaining risk: None within the required persisted-field set.
- Blocking: no

### 4. Configuration wiring
- Status: RESOLVED
- Exact file and function: `app/api/routes.py` module-level `_ingestion_service` construction
- Code evidence: Batch size, document length, chunk length, and overlap settings are passed into `IngestionServiceConfig` and `ChunkingConfig`. Retrieval query and `top_k` settings are passed into `SqliteBM25Config`.
- Regression-test evidence: `test_environment_configured_limits_actually_control_the_service`; the complete suite also confirms older direct `Settings(...)` construction remains compatible through defaulted retrieval fields.
- Remaining risk: The regression test proves the configured service behavior but does not independently reload routes under alternate environment settings.
- Blocking: no

### 5. FTS5 AND false-negative behavior
- Status: RESOLVED
- Exact file and function: `app/retrieval/sqlite_bm25.py::_extract_safe_terms`, `_quote_fts5_term`, `_build_safe_match_query`, `SqliteBM25Retriever.search`
- Code evidence: Raw input is tokenized to bounded `\w+` terms. Every term is individually quoted, and only server-generated ` OR ` operators join them. The complete expression and `top_k` remain SQL parameters. Ranking uses `bm25()` followed by stable `chunk_id` ordering.
- Regression-test evidence: `test_build_safe_match_query_quotes_every_term`, `test_extra_irrelevant_query_term_does_not_suppress_previous_match`, `test_more_matching_terms_still_ranks_higher_under_or`, adversarial syntax tests, and `test_top_k_bounds_enforced`
- Remaining risk: Common-word OR queries may reduce precision, but response size remains bounded by `top_k`.
- Blocking: no

## Minor Findings Status
- Eager FTS5 validation: RESOLVED. `_retriever.initialize()` runs during route-module import and fails closed before serving requests.
- Safe 500 mapping: RESOLVED. Ingestion and retrieval return fixed messages with request IDs without exposing underlying exception text.
- Test/runtime database cleanup: PARTIALLY RESOLVED. Created documents are deleted at module teardown, but route tests still use and may create the configured runtime database file rather than an isolated temporary database. Interrupted test runs can bypass cleanup.
- Source-key normalization: RESOLVED. Source keys are stripped and lowercased before resolution and identity derivation.
- External-ID behavior: ACCEPTED AND DOCUMENTED. Surrounding whitespace is stripped, while case remains deliberately significant.

## Documentation and Implementation Consistency
ADR-002, implementation, regression tests, and the resolution document agree that safe terms use explicit OR semantics.

Two documentation inconsistencies remain:

- Root `README.md` still says terms are joined with implicit AND.
- `app/README.md` also still says implicit AND.
- `phase-12b-audit-resolution.md` claims recursive handling at any nesting depth, but lists-of-lists bypass both depth accounting and sanitization.

The source-policy split, unchanged comparison, configuration wiring, safe error mapping, source normalization, and deliberate case-sensitive external IDs otherwise agree across implementation and resolution documentation.

## Remaining Critical Issues
None

## Remaining Blocking Major Issues
Nested metadata spoofing remains possible through lists-of-lists. Prohibited trust, benchmark, and decision fields can be persisted while the audit count reports zero. Therefore Major finding #2 is not fully resolved.

## Final Verdict
REVISE