# Codex Phase 12B Independent Audit

## Reviewed state
- Base commit: `392d8ca5ac74b380da75813a5fbca937d1b112b2`
- Implementation commit: `6bfb7147a080346b1879bd8e05fd04efec5f36c5`
- Files inspected: Phase 12B diff; `app/retrieval/`; chunking, ingestion, source policy, config, schemas, routes; four Phase 12B test files; retrieval smoke script; relevant changed documentation
- Tests actually executed: yes
- Test result, only if executed: `59 passed in 0.63s` for `test_chunking.py`, `test_sqlite_bm25.py`, and `test_ingestion.py`. `test_retrieval_routes.py` was not executed because collection failed in the available shared environment: its modified Starlette installation requires unavailable `httpx2`, while genuine `httpx` is also absent. No dependency was installed.

## Critical issues
None.

## Major issues

### 1. Public caller can select a trusted source policy
- File and function: `app/schemas/requests.py::IngestionDocumentRequest`, `app/core/source_policy.py::resolve_source_policy`, `app/api/routes.py::documents_ingest`
- Evidence: `source_key` is caller-controlled. Supplying `synthetic_clean_corpus` maps directly to `trust_level="trusted_internal"`. The route test at `tests/test_retrieval_routes.py:121` demonstrates this through the public API.
- Failure/attack scenario: An API caller uploads arbitrary content while claiming `source_key="synthetic_clean_corpus"`; the stored and returned document is marked trusted even though the server did not authenticate its provenance.
- Minimal fix: Bind the public ingestion endpoint to an untrusted policy such as `api_upload`, or derive source policy from an authenticated/server-selected ingestion channel rather than request data.
- Blocking: yes

### 2. Reserved metadata filtering is shallow and unaudited
- File and function: `app/services/ingestion.py::_sanitize_metadata`
- Evidence: Only exact top-level keys are removed. Nested or differently-cased values such as `{"nested":{"trust_level":"trusted_internal","is_poisoned":true}}` persist and are returned. A temp-database probe confirmed this. Stripping attempts are not reported in the item result or audit event.
- Failure/attack scenario: Forged security labels or benchmark ground truth remain in persisted metadata and can mislead downstream consumers or reviewers, despite documentation claiming such fields cannot be carried.
- Minimal fix: Recursively reject or remove normalized reserved keys, including case/whitespace variants; bound metadata depth and record that a spoofing attempt occurred without logging its unsafe value.
- Blocking: yes

### 3. “Unchanged” detection ignores mutable and security-relevant state
- File and function: `app/services/ingestion.py::_content_hash`, `app/retrieval/sqlite_bm25.py::upsert_documents`
- Evidence: The document hash covers only raw text. If text is unchanged, the retriever skips title, metadata, classification, trust and source-policy updates. A probe replaying identical text with a new title/metadata returned `unchanged` and retained the old fields.
- Failure/attack scenario: A corrected source policy or classification does not propagate unless document text also changes. Stale metadata and trust assignments remain indefinitely.
- Minimal fix: Compare a canonical persistence fingerprint covering text, title, sanitized metadata and resolved policy fields, or update non-content fields even when chunks remain unchanged.
- Blocking: yes

### 4. Configured ingestion resource limits are not wired to the service
- File and function: `app/api/routes.py` module initialization
- Evidence: `_ingestion_service = IngestionService(_retriever)` uses default `IngestionServiceConfig`. `retrieval_max_document_chars`, `retrieval_chunk_max_chars`, and `retrieval_chunk_overlap_chars` from `Settings` are never passed to it. Only the route-level batch limit is consulted.
- Failure/attack scenario: An operator lowers document or chunk limits through environment configuration, but ingestion continues using the hard-coded defaults. Intended resource hardening is silently ineffective.
- Minimal fix: Construct `IngestionServiceConfig` and `ChunkingConfig` from validated settings when the service is created.
- Blocking: yes

### 5. Implicit AND permits trivial retrieval suppression
- File and function: `app/retrieval/sqlite_bm25.py::_build_safe_match_query`
- Evidence: Every extracted token is joined by implicit AND. Adding one absent token to an otherwise matching query changes the result to zero hits; the temp probe confirmed this.
- Failure/attack scenario: An attacker or ordinary verbose query adds an irrelevant term, suppressing all retrieval. This creates predictable false negatives and an availability/evasion primitive.
- Minimal fix: Build a safe, server-generated disjunctive candidate query and let BM25 rank matches, or define a bounded minimum-term-match policy. Never restore caller FTS syntax.
- Blocking: yes

## Minor issues

### 1. FTS5 capability verification is lazy
- File and function: `app/api/routes.py` singleton construction, `SqliteBM25Retriever::_ensure_ready`
- Evidence: Import and application startup perform no capability check. `/health` remains successful even if retrieval cannot initialize; failure appears only on the first retrieval-dependent request.
- Failure/attack scenario: Deployment appears healthy until first use.
- Minimal fix: Initialize the retriever during application lifespan or expose retrieval capability separately in health status.
- Blocking: no

### 2. Unexpected storage exceptions lack a stable API mapping
- File and function: `app/api/routes.py::documents_ingest`, `retrieve`
- Evidence: Routes handle validation and FTS capability errors but not `IngestionBatchError` or general SQLite operational failures. `IngestionBatchError` also embeds the raw database exception in its message.
- Failure/attack scenario: Operational failures become generic framework 500 responses and potentially expose internal details under debug/error middleware.
- Minimal fix: Map storage failures to a fixed project error code and request ID; keep detailed causes server-side only.
- Blocking: no

### 3. Canonical identity is stable but not normalized
- File and function: `app/services/ingestion.py::_derive_document_id`
- Evidence: IDs hash exact `source_key:external_id` strings. Whitespace and case variants can create distinct logical documents, and duplicate detection uses the same exact-string comparison.
- Failure/attack scenario: Repeated variants such as `policy-1`, `policy-1 ` and `POLICY-1` can amplify duplicate content in retrieval.
- Minimal fix: Define and validate canonical source-key/external-ID normalization before duplicate detection and hashing.
- Blocking: no

### 4. Route tests persist state in the default runtime database
- File and function: `tests/test_retrieval_routes.py` module setup
- Evidence: Tests intentionally use the module-level retriever at `data/retrieval.db` and rely on UUID identifiers instead of isolation.
- Failure/attack scenario: Repeated test runs grow local state and can conceal order-dependent behavior.
- Minimal fix: Override route dependencies/settings with a `tmp_path` database before importing the application.
- Blocking: no

## Ingestion atomicity conclusion
Pydantic validates the complete request before the route runs; any schema-invalid item causes the entire HTTP request to return `422` with no mutation. Route-level batch overflow returns `400`.

Inside `IngestionService`, all service validations and chunk preparation complete before database mutation. Unknown sources, empty/oversized documents, oversized metadata and exact duplicate keys are rejected per item. Valid items remain eligible and are committed even when other items are rejected.

For duplicate `(source_key, external_id)` values, the first occurrence wins and later occurrences are rejected. The identifiers are not normalized.

All prepared valid items are written in one `BEGIN IMMEDIATE` transaction. An unexpected storage failure rolls back the entire prepared mutation. Therefore, storage atomicity is batch-wide, but validation semantics are intentionally partial-success rather than whole-request rejection.

## Metadata spoofing conclusion
Direct top-level request fields such as `trust_level` or `classification` are rejected by `extra="forbid"`, causing a whole-request `422`. Exact top-level reserved keys inside `metadata` are silently removed.

Nested, case-varied or whitespace-varied reserved keys are preserved, persisted and returned. Their removal attempts are not audited. More importantly, the caller can indirectly control the effective trust assignment by selecting an allow-listed `source_key`, including the trusted synthetic source. The implemented behavior does not fully satisfy server-controlled trust.

## FTS5 query-safety conclusion
Partially safe.

Raw user input is not passed directly to `MATCH`. Input is bounded, NFKC-normalized, tokenized to `\w+`, individually quoted, and supplied through a SQL parameter. Quotes, colons, wildcards, parentheses and most control characters cannot retain FTS syntax. `AND`, `OR`, `NOT` and `NEAR` become quoted literal terms. SQL statements are parameterized.

However, all retained terms are combined with implicit AND. This is syntactically safe but creates trivial false-negative and retrieval-suppression behavior. Query length and term count are bounded, so excessive FTS work from malformed input is reasonably constrained.

## Missing regression tests
- Public ingestion cannot claim `synthetic_clean_corpus` or otherwise obtain `trusted_internal`.
- Nested, case-varied and whitespace-varied reserved metadata is rejected or sanitized.
- Metadata spoof attempts produce an auditable result without persisting unsafe values.
- Same-text replay with changed title, metadata or source policy updates persisted state correctly.
- Environment-configured document and chunk limits actually control the route-level ingestion service.
- App startup/health behavior when FTS5 is unavailable.
- Natural-language retrieval and adversarial extra-term behavior under the intended term-combination policy.
- External ID normalization and duplicate detection across whitespace/case variants.
- Mixed valid/invalid HTTP batches explicitly assert the documented partial-success behavior.
- Route tests use an isolated temporary database.
- Storage failure returns a stable, non-leaking API error.

## Residual risks acceptable for Phase 12B
- Lexical retrieval remains sensitive to paraphrasing and vocabulary mismatch.
- Chunk-boundary evasion and coordinated instructions spanning multiple chunks remain possible.
- Character overlap does not guarantee preservation of every multi-token attack signature.
- SQLite contention is bounded only by a five-second busy timeout and is suitable only for the documented local PoC scale.
- Ranking and tokenization can vary with the bundled SQLite version.
- Retrieval responses expose complete matched chunk text and metadata; this remains acceptable only under the synthetic, local PoC scope.

## Final verdict
REVISE