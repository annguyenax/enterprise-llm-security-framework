# Phase 12B Code X Audit Resolution

## Audit information

- **Audit file:** `docs/modernization-ai-reviews/codex-phase-12b-security-audit.md`
- **Original verdict:** REVISE
- **Base commit reviewed:** `392d8ca5ac74b380da75813a5fbca937d1b112b2`
- **Implementation commit reviewed:** `6bfb7147a080346b1879bd8e05fd04efec5f36c5`
- **Resolution date:** 2026-07-11
- **Resolution branch:** `phase-12b-retrieval-foundation`

The audit reported **zero Critical issues**, **5 Major issues** (all
marked blocking), and **4 Minor issues** (all marked non-blocking), plus a
"Missing regression tests" list and an "Ingestion atomicity conclusion" /
"Metadata spoofing conclusion" / "FTS5 query-safety conclusion" section.
Every Major finding was independently re-verified against the actual code
before being accepted (see each finding below) — none was accepted purely
on the audit's say-so.

## Critical findings

None reported by the audit. Nothing to resolve.

## Major findings

### Major #1 — Public caller can select a trusted source policy

- **Code X evidence:** `source_key` is caller-controlled in
  `IngestionDocumentRequest`; supplying `synthetic_clean_corpus` mapped
  directly to `trust_level="trusted_internal"` with no authentication
  boundary in between. `tests/test_retrieval_routes.py:121` (pre-fix)
  demonstrated this through the public API.
- **Decision:** Accepted.
- **Files and functions changed:** `app/core/source_policy.py`
  (`PUBLIC_SOURCE_POLICIES` / `_INTERNAL_ONLY_SOURCE_POLICIES` split,
  `resolve_source_policy(..., allow_internal: bool = False)`).
  `app/services/ingestion.py`'s call site is unchanged — it already called
  `resolve_source_policy(normalized_source_key)` with no extra argument,
  so the new default (`allow_internal=False`) applies automatically.
- **Fix applied:** Elevated-trust policies (`synthetic_clean_corpus`,
  `synthetic_external_feed`) were moved out of the table `resolve_source_policy()`
  consults by default. `IngestionService` — the only caller reachable from
  the public `POST /v1/documents/ingest` route — never passes
  `allow_internal=True`, so those two source keys are now unreachable
  through public request input; a caller supplying them is rejected as an
  "unknown source_key", identically to any other unrecognized value.
  `allow_internal=True` remains available for tests and a future
  authenticated/internal ingestion channel (not implemented in Phase 12B).
- **Regression tests added:** `tests/test_ingestion.py::test_public_ingestion_cannot_claim_trusted_synthetic_source_key`
  (service-level, both elevated keys), `tests/test_retrieval_routes.py::test_public_ingestion_cannot_claim_trusted_synthetic_source`
  (HTTP-level, via the actual route). Also re-verified live against a
  running server with `curl` (see Validation section).
- **Rationale:** Phase 12B has no authentication layer, so there is no
  server-side signal other than "this request came through the one public
  route" to base a trust decision on. Binding the public endpoint to only
  the non-elevated policy (matching the audit's own suggested minimal
  fix) closes the gap without inventing new infrastructure (an auth
  system) that would be a large, out-of-scope addition to a retrieval-
  foundation phase.
- **Residual risk:** If a future authenticated ingestion channel is added
  (Phase 12C+), it must deliberately opt into `allow_internal=True` and
  must not simply relax the default — this is now a documented decision
  point, not an oversight, per the module docstring in `source_policy.py`.
- **Resolution status:** Resolved and regression-tested.

### Major #2 — Reserved metadata filtering is shallow and unaudited

- **Code X evidence:** Only exact top-level keys were removed; nested or
  differently-cased values such as `{"nested": {"trust_level": "trusted_internal"}}`
  persisted unmodified, and no stripping attempt was reported anywhere.
- **Decision:** Accepted.
- **Files and functions changed:** `app/services/ingestion.py`
  (`_normalize_metadata_key`, `_metadata_depth`, `_sanitize_metadata`
  rewritten to be recursive and case/whitespace-normalized and to return
  `(clean_metadata, stripped_count)`; `_RESERVED_METADATA_KEYS` extended
  with `expected_decision` and `policy_result` per this task's own
  required list). `app/retrieval/models.py` (`IngestionItemResult` gained
  `metadata_keys_stripped: int = 0`). `app/schemas/responses.py`
  (`IngestionItemResponse` gained the same field). `app/api/routes.py`
  (response mapping includes it).
- **Fix applied:** Reserved-key matching now normalizes case and
  whitespace/hyphen/underscore variants before comparison, and recurses
  into nested dicts and lists of dicts up to `MAX_METADATA_DEPTH` (4);
  metadata nested deeper than that is rejected outright (the whole
  document, not silently truncated) via a new `_metadata_depth` pre-check.
  Every ingestion result item now carries `metadata_keys_stripped`, an
  auditable count of how many reserved keys were removed — propagated
  into the audit log event (`_log_ingestion_event`) as a count only, never
  the stripped key names or values.
- **Regression tests added:**
  `test_nested_reserved_metadata_key_is_rejected_or_sanitized`,
  `test_case_and_whitespace_varied_reserved_metadata_key_is_sanitized`,
  `test_metadata_spoof_attempt_is_auditable_without_persisting_unsafe_value`,
  `test_metadata_depth_over_limit_is_rejected` (all in
  `tests/test_ingestion.py`), plus the updated
  `test_sanitize_metadata_strips_all_reserved_keys` unit test.
- **Rationale:** This is a direct, narrow fix to the sanitization
  function's own logic — no architectural change, fully covered by unit
  tests that exercise the exact bypasses the audit demonstrated.
- **Residual risk:** `MAX_METADATA_DEPTH=4` and `MAX_METADATA_JSON_CHARS=2000`
  are fixed constants, not currently configurable via `Settings` — judged
  acceptable for Phase 12B's scope (they exist as safety bounds, not as
  operator-tunable resource limits like the ones Major #4 fixes).
- **Resolution status:** Resolved and regression-tested.

### Major #3 — "Unchanged" detection ignores mutable and security-relevant state

- **Code X evidence:** `upsert_documents` compared only `content_hash`; a
  probe replaying identical text with a new title/metadata returned
  `unchanged` and silently left the old title/metadata/policy fields in
  place.
- **Decision:** Accepted.
- **Files and functions changed:** `app/retrieval/sqlite_bm25.py`
  (`_is_unchanged` new helper; `_metadata_json` new helper with
  `sort_keys=True` for canonical comparison; `upsert_documents`'s
  existing-row `SELECT` widened to fetch `title`, `metadata_json`,
  `source_type`, `classification`, `trust_level` in addition to
  `content_hash`; `_insert_document`/`_replace_document`/`_insert_chunks`
  switched to the canonical `_metadata_json` helper for both writing and
  comparison).
- **Fix applied:** A document is now reported `unchanged` only if content
  hash, title, metadata (canonically serialized), source_type,
  classification, and trust_level all match the stored row; any
  difference now correctly triggers `_replace_document`, which already
  updates every one of those fields (that part of the code was already
  correct — only the branch condition deciding whether to call it was
  wrong).
- **Regression tests added:**
  `tests/test_sqlite_bm25.py::test_unchanged_detection_covers_title_metadata_and_policy_fields`
  (retriever-level, identical text/different metadata),
  `tests/test_ingestion.py::test_same_text_replay_with_changed_title_and_metadata_is_updated`
  (service-level, end to end through `IngestionService`).
- **Rationale:** Confined to the comparison predicate; no schema
  migration needed since `_replace_document`'s `UPDATE` statement already
  covered every relevant column.
- **Residual risk:** None identified beyond the already-accepted general
  limitation that SQLite contention is bounded only by the busy timeout
  (see audit's own "Residual risks acceptable for Phase 12B").
- **Resolution status:** Resolved and regression-tested.

### Major #4 — Configured ingestion resource limits are not wired to the service

- **Code X evidence:** `app/api/routes.py` constructed
  `IngestionService(_retriever)` with an all-default `IngestionServiceConfig`;
  `retrieval_max_document_chars`, `retrieval_chunk_max_chars`, and
  `retrieval_chunk_overlap_chars` from `Settings` had no effect.
- **Decision:** Accepted.
- **Files and functions changed:** `app/api/routes.py` (module-level
  `_ingestion_service` construction).
- **Fix applied:** `_ingestion_service` is now constructed with an
  explicit `IngestionServiceConfig(max_batch_size=settings.retrieval_max_batch_size,
  chunking=ChunkingConfig(max_chunk_chars=settings.retrieval_chunk_max_chars,
  overlap_chars=settings.retrieval_chunk_overlap_chars,
  max_document_chars=settings.retrieval_max_document_chars))`.
- **Regression tests added:**
  `tests/test_ingestion.py::test_environment_configured_limits_actually_control_the_service`
  (proves a tightened `IngestionServiceConfig` actually rejects an
  oversized document at the service layer that the route now correctly
  wires from `settings`). A route-level end-to-end test using a modified
  environment variable was not added, for the same `sys.modules`-caching
  reason `tests/test_retrieval_routes.py`'s own docstring already
  documents for Minor #4 — the service-level test proves the wiring
  mechanism `routes.py` now uses is correct.
- **Rationale:** A pure wiring bug — the settings and the config classes
  they should feed already existed and were already tested independently;
  only the connection between them at the one call site was missing.
- **Residual risk:** None identified.
- **Resolution status:** Resolved and regression-tested.

### Major #5 — Implicit AND permits trivial retrieval suppression

- **Code X evidence:** Every extracted token was joined by implicit AND;
  adding one absent/irrelevant token to an otherwise-matching query
  changed the result to zero hits (verified by the audit's own temp-DB
  probe).
- **Decision:** Accepted.
- **Files and functions changed:** `app/retrieval/sqlite_bm25.py`
  (`_build_safe_match_query`), `docs/decisions/ADR-002-retrieval-engine.md`
  (term-combining behavior documentation updated to match).
- **Fix applied:** Sanitized terms are now joined with explicit `OR`
  instead of implicit AND (space-joined quoted tokens). A chunk matching
  *any* extracted term is now a candidate hit; `bm25()` ranking still
  rewards chunks matching more terms (BM25 sums per-term scores and
  down-weights very common terms via document frequency), so precision is
  not abandoned, only the all-or-nothing suppression failure mode.
- **Regression tests added:**
  `tests/test_sqlite_bm25.py::test_extra_irrelevant_query_term_does_not_suppress_previous_match`
  (the exact scenario the audit's probe demonstrated),
  `tests/test_sqlite_bm25.py::test_more_matching_terms_still_ranks_higher_under_or`
  (proves BM25 ranking preference for term coverage survives the change).
  Updated `test_build_safe_match_query_quotes_every_term` to assert the
  new `OR`-joined expression.
- **Rationale for accepting a behavior change (not just a bug fix):** this
  is not a pure defect fix — ADR-002 had explicitly documented AND-joining
  as "a deliberate precision-favoring choice, not FTS5's only option," so
  the audit's finding is a legitimate reconsideration of an earlier
  Phase 12A design decision, not an obvious oversight. It was accepted
  because (a) it does not violate any of the Phase 12B mandatory
  invariants (SQLite FTS5/BM25 remains the engine, no new dependency, no
  fallback, raw input still never reaches `MATCH` unescaped, still fully
  parameterized), (b) the smallest safe fix (changing the join separator)
  is small and mechanical, not a broad algorithmic rewrite, and (c) the
  alternative of a bounded "minimum-term-match" policy would have been
  more complex for the same practical benefit.
- **Residual risk:** A query built entirely from very common words could,
  in principle, return a large low-relevance result set under OR — bounded
  in practice by `top_k` and BM25's own document-frequency down-weighting.
  Not treated as blocking for a lexical-only, local, synthetic-corpus PoC.
- **Resolution status:** Resolved and regression-tested. `scripts/smoke_test_retrieval.ps1`
  was also updated (its original "stale content gone" check assumed
  AND-only suppression semantics and needed to test the actual invariant —
  no stale text in any returned hit — directly instead; see Validation
  section).

## Minor findings

### Fixed now

- **Minor #1 — FTS5 capability verification is lazy.** `app/api/routes.py`
  now calls `_retriever.initialize()` immediately after constructing the
  module-level retriever singleton, so the capability check and schema
  creation run at import time (i.e. at application startup, since
  `app.main` imports this module), not only on the first retrieval-
  dependent request. Regression coverage: the existing
  `tests/test_sqlite_bm25.py::test_no_fallback_when_capability_check_fails`
  already proves `initialize()` fails closed when capability is
  unavailable; combined with `routes.py` now calling `initialize()` eagerly,
  import-time failure is a direct, already-tested consequence. A dedicated
  subprocess-isolated test simulating a genuinely FTS5-less Python build at
  app-import time was judged disproportionate effort for a non-blocking
  Minor finding.
- **Minor #2 — Unexpected storage exceptions lack a stable API mapping.**
  `app/api/routes.py`'s `documents_ingest` and `retrieve` handlers now
  catch `IngestionBatchError` (ingest only) and a generic `Exception`
  safety net (both routes), returning a fixed HTTP 500 message plus the
  request_id — never the raw underlying exception text, which could
  otherwise reach the caller since `IngestionBatchError` embeds it for
  server-side logs. Regression test:
  `tests/test_retrieval_routes.py::test_storage_failure_maps_to_safe_generic_error_without_leaking_cause`
  (mocks the retriever to raise an `IngestionBatchError` containing a
  fabricated internal path/error string and asserts neither appears in
  the HTTP response).
- **Minor #4 — Route tests persist state in the default runtime database.**
  `tests/test_retrieval_routes.py` gained an autouse, module-scoped
  cleanup fixture that deletes every document created by this module's
  tests (tracked by ID) at teardown, via a fresh `SqliteBM25Retriever`
  pointed at the same configured database file. Full per-test database
  isolation (Code X's suggested "override settings with a tmp_path
  database before importing the application") was not implemented — see
  "Deferred" below for why.

### Deferred

- **Minor #3 — Canonical identity is stable but not normalized (partially
  fixed, remainder deferred).** Whitespace was stripped from both
  `source_key` and `external_id`, and `source_key`'s case was folded
  (small, server-defined vocabulary, safe to normalize) before duplicate
  detection and ID derivation — see
  `tests/test_ingestion.py::test_external_id_and_source_key_whitespace_normalized_before_dedup`
  and `test_duplicate_within_batch_detected_across_whitespace_case_variants`.
  **`external_id`'s case is deliberately left as-is after stripping** —
  not force-lowercased — and this part of the finding is not further
  addressed. Rationale: external identifiers may legitimately be
  case-sensitive in a real source system; blindly lowercasing them risks
  silently merging two genuinely distinct documents (e.g. `Invoice-001`
  vs `invoice-001` from a case-sensitive external system), which is a
  worse correctness failure than the amplification risk being fixed. This
  is a documented trade-off, not an oversight.
- **Minor #4 (remainder) — full per-test database isolation.** The
  cleanup-fixture approach (see "Fixed now" above) solves the actual
  concern raised ("repeated test runs grow local state") without a
  broader refactor. Full isolation via dependency injection or a
  reload-based settings override was not implemented because (a) a plain
  `RETRIEVAL_DB_PATH` environment override does not reliably isolate this
  test module from others in the same pytest session (Python caches
  `app.main`/`app.core.config` in `sys.modules` after whichever test
  module imports them first), and (b) restructuring `app/api/routes.py`
  around dependency injection to support per-test override would be a
  broader refactor than this Minor, non-blocking finding warrants (task
  instruction: "Avoid broad refactors unrelated to the finding").

### Rejected

None. Every Minor finding was addressed (fixed) or partially addressed
with a documented, deliberate rationale for the deferred remainder — none
was dismissed outright.

## Ingestion atomicity decision

Unchanged from the audit's own accurate description, preserved by every
fix above:

- **Validation behavior:** Pydantic validates the complete HTTP request
  before the route function runs; any schema-invalid item (including an
  attempted top-level `trust_level`/`classification`/etc. field, rejected
  by `extra="forbid"`) causes the entire request to return `422` with no
  mutation. Route-level batch-size overflow returns `400`. Inside
  `IngestionService.ingest_batch`, all per-document validations
  (duplicate-in-batch, unknown/internal-only source key, metadata depth,
  metadata size, chunking/document-length limits) run and prepare valid
  items *before* any database mutation begins.
- **Duplicate behavior:** For duplicate `(normalized_source_key,
  normalized_external_id)` pairs within one batch, the first occurrence
  is prepared for persistence and later occurrences are rejected
  per-item, not the whole batch.
- **Transaction boundary:** All prepared, valid items are written within
  one `BEGIN IMMEDIATE` transaction in `SqliteBM25Retriever.upsert_documents`.
- **Rollback behavior:** Any unexpected storage failure during that
  transaction rolls back the entire prepared mutation and raises
  `IngestionBatchError`; no partial write is ever committed.
- **API response behavior:** A successful call returns per-item status
  (`indexed`/`updated`/`unchanged`/`rejected`) with aggregate counts; an
  `IngestionBatchError` now maps to a safe, generic HTTP 500 (Minor #2
  fix) instead of an unmapped framework error.
- **Whether partial success is possible:** **Yes, by design** — this is
  the "preferred semantics" described in the task's own instructions only
  insofar as request-level Pydantic validation is whole-request-rejecting;
  per-document business-rule validation (unknown source, oversized
  content, duplicates, metadata problems) remains intentionally
  partial-success, exactly as the audit's own "Ingestion atomicity
  conclusion" already documented and did not itself flag as a defect.
  This was not changed, because changing it would be the kind of broad,
  unrelated refactor the task instructs against, and no Major/Critical
  finding required it — the findings that *were* accepted (Major #1-#5)
  are about which documents *should* be rejected/detected-as-changed, not
  about the batch's overall accept/reject granularity.

## Metadata-spoofing decision

- **Prohibited keys:** `trust_level`, `classification`, `source_type`,
  `is_poisoned`, `expected_decision`, `security_decision`, `policy_result`,
  `document_id`, `chunk_id` (the first seven map directly to this task's
  required list; `document_id`/`chunk_id` were already reserved in Phase
  12B's original implementation and are kept).
- **Rejection behavior:** A prohibited key sent as a **top-level** request
  field (a sibling of `external_id`/`text`, not inside `metadata`) causes
  the entire HTTP request to be rejected with `422` (`extra="forbid"` on
  `IngestionDocumentRequest`). A prohibited key found **inside** the
  free-form `metadata` dict — at any nesting depth, in any case/whitespace
  variant — is silently stripped (not a full-request rejection); this
  matches the free-form nature of `metadata` (which cannot be schema-
  validated key-by-key without disallowing arbitrary legitimate caller
  metadata).
- **Persistence behavior:** The stripped value is never persisted, at any
  nesting depth, regardless of key case/whitespace variant (Major #2 fix).
  Metadata deeper than `MAX_METADATA_DEPTH` (4) is rejected outright
  (whole document, not truncated).
- **Audit behavior:** Every ingestion result item carries
  `metadata_keys_stripped: int`, propagated into the JSONL audit log
  event — a count only, never the stripped key names or the unsafe values
  themselves (verified by
  `test_metadata_spoof_attempt_is_auditable_without_persisting_unsafe_value`).
- **Server-assigned fields:** `trust_level`, `classification`,
  `source_type` come exclusively from `app/core/source_policy.py`,
  resolved from a caller-supplied `source_key` that, as of the Major #1
  fix, can only resolve to the single non-elevated `api_upload` policy
  through the public ingestion endpoint. `document_id`/`chunk_id` are
  always derived server-side (`_derive_document_id`/`_derive_chunk_id`)
  from the normalized `(source_key, external_id)` pair, never accepted
  from any request field.

## FTS5 query-safety decision

- **Normalization:** Control characters (`\x00`-`\x1f` excluding common
  whitespace handling, `\x7f`) are stripped; the result is Unicode
  NFKC-normalized.
- **Token extraction:** `\w+` runs only (Unicode-aware), so every FTS5
  special character/operator is excluded from any extracted term by
  construction.
- **Token limits:** Query text is truncated to `max_query_chars` (default
  500) before tokenization; only the first `max_query_terms` (default 12)
  extracted terms, in original order, are kept.
- **Quoting:** Every surviving term is individually wrapped in double
  quotes (embedded quotes doubled per FTS5's own escaping rule), so a
  term that happens to spell a reserved word (`NEAR`, `AND`, `OR`, `NOT`)
  is treated as a literal token, not an operator.
- **Operator handling:** `AND`/`OR`/`NOT`/`NEAR`, column-filter syntax
  (`column:term`), wildcards (`*`), and parentheses cannot retain FTS5
  syntax meaning, because they are never part of any extracted `\w+` term
  in the first place.
- **Empty-query behavior:** A query that yields zero terms after
  sanitization raises `EmptySearchQueryError`, mapped to HTTP 400.
- **Query construction semantics (changed this pass — Major #5):** terms
  are joined with explicit `OR` (previously implicit AND). SQL
  parameterization is used throughout for the `MATCH` value itself; this
  is a distinct protection layer from term sanitization, not a
  substitute for it (SQL parameterization alone does not stop FTS5
  query-syntax manipulation, since FTS5 has its own query language inside
  the parameterized string).
- **Residual limitations:** Lexical retrieval only — no semantic
  similarity; ranking/tokenization behavior can vary with the bundled
  SQLite version; retrieval responses expose full matched chunk text and
  metadata (acceptable only at the current synthetic, local PoC scope, per
  the audit's own "Residual risks acceptable for Phase 12B").

## Phase 12B acceptance gate

| Requirement | Status |
|---|---|
| All Critical findings resolved | PASS — none reported |
| All blocking Major findings resolved | PASS — all 5 accepted and fixed, each with a regression test |
| Regression tests added | PASS — 14 new tests across `test_ingestion.py`, `test_sqlite_bm25.py`, `test_retrieval_routes.py` |
| Full pytest passed | PASS — 165/165 in the project-local `.venv` (151 pre-audit + 14 new) |
| Smoke test passed | PASS — `scripts/smoke_test_retrieval.ps1` against a live local server, updated to test the stale-content invariant directly rather than relying on AND-only suppression semantics that Major #5 removed |
| FTS5 has no fallback | PASS — unchanged; `check_capability()` still has zero fallback path, now also invoked eagerly at import time (Minor #1) |
| Batch semantics are consistent | PASS — code, tests, API responses, and this document now agree on the "partial success per document, atomic per accepted batch" model (see Ingestion atomicity decision above) |
| Trust remains server-controlled | PASS — Major #1 closed the public-source-key-selects-trust gap; trust/classification/source_type are still only ever assigned in `source_policy.py` |
| No benchmark label is used at runtime | PASS — unchanged; `is_poisoned` still appears nowhere in any Phase 12B runtime code path (verified again this pass) |
| No stale FTS rows remain after updates | PASS — unchanged mechanism (manual delete-then-insert against `chunks_fts` by rowid), now also correctly triggered for metadata/title-only changes (Major #3) |
| Existing gateway regression passes | PASS — `/health` and `/v1/gateway/chat` byte-identical behavior reconfirmed by `tests/test_retrieval_routes.py`'s regression tests |
| No prohibited path changed | PASS — verified via `git diff --name-only` (see Validation) |
| No runtime database tracked | PASS — verified via `git ls-files "*.db" "*.sqlite" "*.sqlite3"` (empty) |
| No dependency added | PASS — `sqlite3` remains standard library; `requirements.txt` untouched |

## Final recommendation

**APPROVE PHASE 12B.**

All findings from the Code X audit were evaluated on their own evidence,
not accepted by default; every accepted Critical/Major finding was fixed
with the smallest safe change and a regression test that specifically
exercises the scenario the audit demonstrated; every Minor finding was
either fixed or deferred with a concrete, documented rationale. No
mandatory Phase 12B invariant was violated by any fix. Phase 12C still
requires a separate, explicit go-ahead — this approval is scoped to Phase
12B only.
