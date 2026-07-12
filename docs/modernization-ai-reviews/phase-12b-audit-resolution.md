# Phase 12B Code X Audit Resolution

## Audit information

- **Original audit file:** `docs/modernization-ai-reviews/codex-phase-12b-security-audit.md`
- **Original verdict:** REVISE
- **Base commit reviewed:** `392d8ca5ac74b380da75813a5fbca937d1b112b2`
- **Implementation commit reviewed:** `6bfb7147a080346b1879bd8e05fd04efec5f36c5`
- **First-pass resolution date:** 2026-07-11
- **Re-audit file:** `docs/modernization-ai-reviews/codex-phase-12b-resolution-reaudit.md`
- **Re-audit verdict:** REVISE — 1 remaining blocking Major finding (Major #2,
  partially resolved), 0 Critical, all other Major findings confirmed
  resolved, Minor findings mostly resolved with one partial (accepted with
  documented rationale) and one further tightened this pass
- **Re-audit reviewed commits:** original implementation `6bfb7147a080346b1879bd8e05fd04efec5f36c5`,
  first-pass fix `04f68dd9fda9f8e58553fad844a27384de96aa21`
- **Final resolution date:** 2026-07-11 (same day, second pass)
- **Resolution branch:** `phase-12b-retrieval-foundation`

The original audit reported **zero Critical issues**, **5 Major issues**
(all marked blocking), and **4 Minor issues** (all marked non-blocking).
Every Major finding was independently re-verified against the actual code
before being accepted — none was accepted purely on the audit's say-so.
An independent **re-audit** of the first-pass fix commit then found that
one Major finding (#2, reserved metadata filtering) was only **partially**
resolved: a list-of-lists structure bypassed the recursive sanitization
entirely, and the metadata-size limit was checked after sanitization
rather than before, letting a large value hidden under a reserved key
evade it. This document has been corrected in place (see Major #2 below)
rather than left overstating the original fix's completeness, and records
both rounds of resolution.

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

- **Code X evidence (original audit):** Only exact top-level keys were
  removed; nested or differently-cased values such as
  `{"nested": {"trust_level": "trusted_internal"}}` persisted unmodified,
  and no stripping attempt was reported anywhere.
- **Decision:** Accepted.
- **First-pass fix (2026-07-11, this section as originally written):**
  reserved-key matching was made to normalize case/whitespace/hyphen/
  underscore variants, and to recurse into nested dicts and into dicts
  that were direct elements of a list, up to `MAX_METADATA_DEPTH` (then
  4). This section originally stated the finding was "Resolved and
  regression-tested" based on that fix.
- **Independent re-audit finding (Code X, `codex-phase-12b-resolution-reaudit.md`,
  verdict REVISE):** the first-pass fix was **incomplete**. It only
  recursed into a list element when that element was itself a `dict`, so
  a **list-of-lists** — e.g. the reviewer's probe
  `{"wrapper": [[{" TrUsT-LeVeL ": "trusted_internal", "is_poisoned": true, "expected_decision": "allow"}]]}` —
  bypassed sanitization entirely: it was persisted unmodified and
  `metadata_keys_stripped` incorrectly reported `0`. The re-audit also
  found the metadata-size check ran on the **sanitized** metadata rather
  than the raw submission, so a caller could place an arbitrarily large
  value under a reserved key (removed before the size was ever measured)
  and bypass `MAX_METADATA_JSON_CHARS` entirely. This document's earlier
  claim of "recursive handling at any nesting depth" was therefore
  premature — corrected here rather than left standing.
- **Final fix applied (this pass):** `_sanitize_metadata` was rewritten
  to recurse **uniformly** over every JSON-compatible value — dict, list,
  nested lists, dicts inside lists, lists inside dicts, any combination —
  rather than special-casing only "list of dict." `_metadata_depth` was
  corrected so a list increments depth exactly like a dict does (the
  original only incremented for dicts, so list nesting never tripped the
  depth pre-check no matter how deep). The ingestion pipeline in
  `IngestionService.ingest_batch` was reordered so the raw, caller-
  submitted metadata's JSON size is validated **before** any key is
  stripped (closing the size-limit-bypass-via-reserved-key gap), followed
  by the raw depth check, then sanitization. `MAX_METADATA_DEPTH` was
  raised from 4 to 6: with list nesting now correctly counted, a
  realistic 5-container structure (e.g. dict-list-dict-list-dict) needs a
  6th unit of depth budget to reach its own leaf values without being
  truncated by the safety cutoff — 4 left essentially no headroom once
  list nesting was counted correctly. `_sanitize_metadata` never mutates
  its input (every level constructs new dict/list objects).
- **Files and functions changed:** `app/services/ingestion.py`
  (`_metadata_depth`, `_sanitize_metadata` rewritten for uniform dict/list
  recursion; `MAX_METADATA_DEPTH` raised 4→6; `ingest_batch` reordered to
  check raw metadata JSON size and depth before sanitizing).
- **Regression tests added (this pass, all in `tests/test_ingestion.py`):**
  `test_prohibited_key_inside_list_of_list_of_dict_is_stripped` (the exact
  reviewer probe), `test_prohibited_key_inside_dict_list_dict_list_dict_is_stripped`,
  `test_multiple_prohibited_keys_across_separate_nested_branches_all_stripped`,
  `test_mixed_safe_and_prohibited_values_preserve_safe_data`,
  `test_metadata_keys_stripped_reports_exact_total_through_service`,
  `test_lists_contribute_to_depth_calculation`,
  `test_excessive_list_nesting_is_rejected`,
  `test_sanitize_metadata_does_not_mutate_caller_object`,
  `test_raw_metadata_over_limit_rejected_even_when_large_value_is_under_prohibited_key`,
  `test_prohibited_values_do_not_appear_in_persisted_metadata_via_service`
  (service-level, through `IngestionService.ingest_batch`, not just the
  helper function directly), `test_prohibited_values_do_not_appear_in_audit_log`.
  Also added in `tests/test_retrieval_routes.py`:
  `test_public_ingestion_strips_prohibited_key_inside_list_of_list`
  (HTTP-level, through the real `POST /v1/documents/ingest` route).
- **Rationale:** Confined to the sanitization/depth helpers and the
  validation ordering inside `ingest_batch` — no architectural change.
  The `MAX_METADATA_DEPTH` increase is a parameter tuning decision
  directly required by correctly counting list depth, not a scope
  expansion, and is still far below what any legitimate metadata payload
  would need (verified by `test_excessive_list_nesting_is_rejected`, which
  still rejects 10+ levels of nesting).
- **Residual risk:** `MAX_METADATA_DEPTH=6` and `MAX_METADATA_JSON_CHARS=2000`
  remain fixed constants, not configurable via `Settings` — judged
  acceptable for Phase 12B's scope. No further metadata-traversal bypass
  is known; the recursion now covers every JSON-compatible container type
  uniformly rather than special-casing specific combinations, which is
  what allowed the list-of-list gap to exist in the first place.
- **Resolution status:** Resolved and regression-tested (confirmed only
  after this pass — the original "Resolved" status recorded during the
  first audit was inaccurate and has been corrected in place, per the
  instruction not to claim resolution before code and tests actually
  demonstrate it).

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
  **First-pass fix (partial, per re-audit):** an autouse, module-scoped
  cleanup fixture deleted every document created by this module's tests
  (tracked by ID) at teardown, via a fresh `SqliteBM25Retriever` pointed
  at the same configured database file — this reduced state growth but
  still used `data/retrieval.db` directly, and the re-audit correctly
  noted an interrupted test run could skip the cleanup. **Final fix (this
  pass):** `tests/test_retrieval_routes.py` now has an autouse,
  module-scoped fixture that replaces `app.api.routes`'s module-level
  `_retriever`/`_ingestion_service` singletons with fresh instances
  pointed at a `pytest`-managed temporary file (`tmp_path_factory`) for
  the duration of the module, restoring the originals at teardown. This
  works reliably regardless of import order (a `RETRIEVAL_DB_PATH`
  environment override does not, since `app.core.config.settings` is
  built once at first import and cached in `sys.modules`) because it
  replaces the already-constructed objects directly. No other route reads
  those two names, so this has no effect outside this test module. The
  route tests genuinely no longer touch `data/retrieval.db` at all — this
  was directly verified by running the test file and then querying
  `data/retrieval.db` for a document count (0, only the empty schema the
  application itself creates on any startup).

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
  is a documented trade-off, confirmed unchanged by the re-audit
  ("ACCEPTED AND DOCUMENTED"), not an oversight.

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
  `IngestionService.ingest_batch`, all per-document validations run and
  prepare valid items *before* any database mutation begins, in this
  explicit order (re-audit fix: the raw metadata's JSON size and
  structure are now validated **before** sanitization, not after — see
  Major #2): duplicate-in-batch → unknown/internal-only source key → raw
  metadata JSON-compatibility and size → raw metadata nesting depth →
  metadata sanitization → chunking/document-length limits.
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
  free-form `metadata` value — at any nesting depth, through any
  combination of dicts and lists (dict-in-list, list-in-dict, list-of-
  lists, etc.), in any case/whitespace/hyphen/underscore variant — is
  silently stripped (not a full-request rejection); this matches the
  free-form nature of `metadata` (which cannot be schema-validated
  key-by-key without disallowing arbitrary legitimate caller metadata).
  This recursion is now uniform across container types (re-audit fix —
  the first-pass implementation only recursed into a list element when
  that element was itself a dict, missing list-of-lists entirely).
- **Persistence behavior:** The stripped value is never persisted, at any
  nesting depth or container combination, regardless of key case/
  whitespace variant (Major #2 fix, corrected after re-audit). Metadata
  deeper than `MAX_METADATA_DEPTH` (6, raised from 4 after re-audit — see
  Major #2) is rejected outright (whole document, not truncated). The
  metadata's raw JSON size is checked **before** sanitization (re-audit
  fix), so a large value cannot evade `MAX_METADATA_JSON_CHARS` by being
  placed under a key that would later be stripped.
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

**Updated after the re-audit** (original first-pass numbers superseded):

| Requirement | Status |
|---|---|
| All Critical findings resolved | PASS — none reported in either audit round |
| All blocking Major findings resolved | PASS — all 5 accepted and fixed; Major #2 required a second pass after the re-audit found the first fix incomplete (list-of-lists bypass), now fixed and regression-tested |
| Regression tests added | PASS — 95 Phase 12B tests total across `test_chunking.py` (14), `test_sqlite_bm25.py` (34), `test_ingestion.py` (34), `test_retrieval_routes.py` (13); 12 of these were added this re-audit pass |
| Full pytest passed | PASS — **177/177** in the project-local `.venv` (82 pre-Phase-12B + 95 Phase 12B) |
| Smoke test passed | PASS — `scripts/smoke_test_retrieval.ps1` against a live local server, testing the stale-content invariant directly (not AND-only suppression semantics, which Major #5 removed) |
| FTS5 has no fallback | PASS — unchanged; `check_capability()` still has zero fallback path, invoked eagerly at import time (Minor #1) |
| Batch semantics are consistent | PASS — code, tests, API responses, and this document agree on the "partial success per document, atomic per accepted batch" model; validation ordering within a document (raw metadata size → raw depth → sanitize → chunking) is now also explicit and tested |
| Trust remains server-controlled | PASS — Major #1 closed the public-source-key-selects-trust gap; trust/classification/source_type are still only ever assigned in `source_policy.py` |
| No benchmark label is used at runtime | PASS — unchanged; `is_poisoned` still appears nowhere in any Phase 12B runtime code path |
| No stale FTS rows remain after updates | PASS — unchanged mechanism (manual delete-then-insert against `chunks_fts` by rowid), correctly triggered for metadata/title-only changes (Major #3) |
| Existing gateway regression passes | PASS — `/health` and `/v1/gateway/chat` byte-identical behavior reconfirmed |
| No prohibited path changed | PASS — verified via `git diff --name-only` and `git diff --name-only 392d8ca...HEAD -- datasets redteam reports/evaluation report-latex-template` (empty) |
| No runtime database tracked | PASS — verified via `git ls-files "*.db" "*.sqlite" "*.sqlite3"` (empty); route tests independently verified to leave `data/retrieval.db` with zero test documents |
| No dependency added | PASS — `sqlite3` remains standard library; `requirements.txt` untouched |
| No raw prohibited metadata value persisted or logged | PASS — verified for the list-of-list case specifically, at the helper, service, and route/HTTP levels, plus the audit-log event |

## Final recommendation

**APPROVE PHASE 12B.**

This recommendation reflects the state **after** the re-audit's finding
was fixed and regression-tested — the identically-worded recommendation
recorded after the first pass (before the re-audit) was premature, since
Major #2 was not actually fully resolved at that time. All findings from
both the original Code X audit and the independent re-audit were
evaluated on their own evidence, not accepted by default; every accepted
Critical/Major finding was fixed with the smallest safe change and a
regression test that specifically exercises the scenario demonstrated;
every Minor finding was fixed, or deferred/accepted with a concrete,
documented rationale. No mandatory Phase 12B invariant was violated by any
fix. Phase 12C still requires a separate, explicit go-ahead — this
approval is scoped to Phase 12B only.
