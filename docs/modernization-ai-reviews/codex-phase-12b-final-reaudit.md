# Phase 12B Final Bounded-Metadata Re-audit

## Reviewed commits
- Previous commit: `7693662c237a33a1efbda0d2200f6dad182bef2d`
- Final fix commit: `28b67d7dccdbaf343770ba5d5709d7350913a86f`
- Tests executed by reviewer: yes — focused ingestion/route suite and full pytest suite, with database, audit log, bytecode, pytest cache, and basetemp redirected outside the repository
- Test result: focused suite `58 passed, 1 warning`; full suite `188 passed, 1 warning`

## Iterative Metadata Preflight
- Status: RESOLVED
- Exact files/functions: `app/services/ingestion.py::_preflight_metadata`, `_metadata_byte_size`, `IngestionService.ingest_batch`
- Code evidence: `_preflight_metadata` uses an explicit stack containing value, depth, and per-path ancestor IDs. Dictionary and list descent both increment depth. It rejects excessive depth, non-string keys, unsupported types, NaN/Infinity, and cyclic references before serialization or recursive sanitization. Per-path cycle tracking accepts shared non-cyclic objects. Caller metadata is copied and sanitization creates new containers.
- Regression-test evidence: Tests cover 900-level lists, deep mixed dict/list structures, direct cycles, shared non-cyclic lists, caller non-mutation, and controlled service rejection. Reviewer probes additionally confirmed rejection of non-string keys, sets, NaN, and positive/negative Infinity.
- Remaining risk: Dedicated committed tests for non-string keys, unsupported types, and non-finite floats would improve regression coverage, although code and reviewer probes confirm the behavior.
- Blocking: no

## UTF-8 Byte Enforcement
- Status: RESOLVED
- Exact files/functions: `app/services/ingestion.py::_metadata_byte_size`, `IngestionService.ingest_batch`
- Code evidence: Preflight runs first. Raw metadata is then serialized with `ensure_ascii=False`, `sort_keys=True`, and compact deterministic separators, encoded as UTF-8, and compared with `MAX_METADATA_JSON_BYTES=2000` before sanitization.
- Regression-test evidence: Tests cover Vietnamese metadata, exact 2,000-byte acceptance, 2,001-byte rejection, oversized values under prohibited keys, and HTTP-route rejection. Reviewer probe measured the same payload as 1,211 characters but 2,411 UTF-8 bytes.
- Remaining risk: None within the Phase 12B metadata-size contract.
- Blocking: no

## Cycle and Deep-Nesting Safety
- Status: RESOLVED
- Evidence: Both 900-level list-only and mixed dict/list probes return a controlled depth rejection. Direct cycles are rejected, while repeated shared objects are accepted. Defensive `RecursionError` catches remain around serialization and sanitization. Rejected documents are never added to the prepared persistence batch.
- Remaining risk: Extremely wide metadata can still require work proportional to its number of elements before byte measurement, but request and batch controls bound the documented local PoC usage.
- Blocking: no

## Recursive Security-Key Sanitization
- Status: RESOLVED
- Evidence: Normalization handles case, surrounding whitespace, whitespace runs, hyphens, and underscores. All required security keys are reserved. The exact list-of-lists probe removed four prohibited fields, preserved the safe sibling and list order, reported `metadata_keys_stripped=4`, left caller metadata unchanged, persisted only sanitized metadata, and did not log the prohibited value.
- Remaining risk: Future additions to security-sensitive metadata fields must also be added to the centralized reserved-key set.
- Blocking: no

## Route-Level Protection
- Status: RESOLVED
- Evidence: `POST /v1/documents/ingest` constructs `IngestionDocument` values and calls the corrected `IngestionService.ingest_batch`. Route tests cover all four specified prohibited fields, UTF-8 oversize rejection, and excessive depth. Validation failures return controlled per-item results without raw metadata. Unexpected failures map to generic responses with request IDs.
- Remaining risk: HTTP JSON cannot represent cycles, so cycle protection is necessarily verified at the direct service boundary.
- Blocking: no

## Test Database Isolation
- Status: RESOLVED with non-blocking caveats
- Evidence: `tests/conftest.py` executes before test-module imports and uses `tempfile.mkdtemp`, producing a unique path outside the repository. Route tests additionally replace both route singletons with a module-specific temporary retriever and restore the originals in `finally`. Reviewer verification confirmed eager initialization created only the temporary database and left `data/retrieval.db` absent.
- Remaining risk: A pre-existing `RETRIEVAL_DB_PATH` is intentionally preserved, so a caller can explicitly opt out of default isolation. The session-level `mkdtemp` directory has no explicit cleanup hook, although unique naming prevents stale-state reuse and concurrent filename collisions.
- Blocking: no

## Documentation Consistency
- Status: RESOLVED
- Inconsistencies, if any: Current-state documentation consistently describes iterative preflight before serialization, deterministic UTF-8 byte measurement, bounded dict/list depth, sanitization after enforcement, explicit server-generated FTS5 `OR`, and Phase 12B as In Review. Character-count, unbounded-recursion, and implicit-AND references are clearly historical audit descriptions. The only minor qualification is that test-isolation wording is unconditional while `conftest.py` preserves an explicitly pre-set `RETRIEVAL_DB_PATH`.

## Remaining Critical Issues
None

## Remaining Blocking Major Issues
None

## Final Verdict
PASS