# Code X Phase 12D Final Malformed-Value Verification

## Reviewed State
- Branch: `phase-12d-v2-benchmark`
- Reviewed HEAD: `94f7bdefe166087a4edb6723558b888d7d062a06`
- Working-tree inventory: Phase 12D benchmark, validator, freeze/build scripts, tests, ADR, methodology, audit-resolution and status documentation
- Git status before: modified and untracked Phase 12D files; no prohibited artifact changes
- Git status after: unchanged from before
- Tests executed: focused Phase 12D suite; full unignored suite; six-file Python compile; validator; guard diagnostic; determinism; manifest verification; malformed-value probes
- Results: focused `246 passed`; full `569 passed, 1 warning`

## Implementation Presence
- Status: RESOLVED
- Helpers found: `_hashable`, `_safe_in`, `is_non_empty_string`, `safe_record_identifier`, `validate_string_field`, `validate_string_enum`, `validate_optional_string_enum`, `validate_string_list`, `validate_integer_field`, `validate_json_safe_value`
- Functions refactored: `check_schemas`, `check_authoring_provenance`, exemption handling and downstream set/dict/Counter consumers
- Test files and tests found: all requested malformed-value, combined-fixture, CLI, deterministic-order and valid-candidate regressions in `tests/test_benchmark_v2_integrity.py`
- Blocking: no

## Validation Ordering
- Status: RESOLVED
- Code evidence: Enum helpers reject non-string values before membership. List elements are type-checked before membership. Integer validation rejects booleans. Schema validation is a hard preflight before normalization, hashing, referential and contamination checks. Downstream collections filter keys by type or use `_safe_in`.
- Remaining unsafe operations: No list/dict value was found reaching a hash-dependent operation directly. Invalid provenance entries remain present in `by_artifact_id` and later safe comparisons despite documentation claiming otherwise.
- Blocking: no

## Corpus and Case Fail-Safe Handling
- Status: RESOLVED
- Probe results: The list/dict/bool/float matrix completed without unhandled exceptions. The combined malformed fixture returned `1`, reported all expected fields, and emitted no traceback, `TypeError`, `KeyError`, `AssertionError` or absolute path.
- Blocking: no

## Label Fail-Safe Handling
- Status: RESOLVED
- Probe results: `expected_stop_reason=[]` returned `1` with a field-specific type error. Optional enums, list elements, decisions, DLP fields and numeric fields are type-checked safely.
- Blocking: no

## Provenance and Exemption Fail-Safe Handling
- Status: RESOLVED
- Probe results: Provenance `split=[]`, malformed provenance fields and non-object records produced controlled errors. Malformed exemption scope, identifiers and rationale produced five deterministic validation errors without hash or membership exceptions.
- Blocking: no

## CLI Error Safety
- Status: RESOLVED
- expected_stop_reason probe: exit `1`; no traceback, exception class or absolute path
- provenance split probe: exit `1`; controlled field-specific error
- combined fixture: exit `1`; eleven deterministic output lines with all requested field identifiers
- deterministic ordering: regression test confirmed byte-identical, sorted error output across repeated runs
- path/content disclosure: no absolute temporary/repository path or raw query/document content observed
- Blocking: no

## Regression Preservation
- Status: RESOLVED
- Validator: `172` documents and `120` cases passed all guard-independent checks
- Guard diagnostic: non-gating; `44 agree, 0 disagree` for development and validation
- Determinism: two in-memory builds were byte-identical
- Candidate manifest: nine files verified; status remains `candidate`
- Artifact drift: counts remain 30/30/60, 23 families, 60 Vietnamese/40 English/20 bilingual, category totals 48/48/16/8, and scopes 104/8/4/4

## Test Results
- Phase 12D: `246 passed`
- Full suite: `569 passed`
- Compile: passed for three scripts and three Phase 12D test modules
- Warnings: one pre-existing Starlette `httpx2` deprecation warning

## Repository Invariants
- Status: RESOLVED
- Evidence: `git diff --check` clean; `requirements.txt` unchanged; no tracked `.db`, `.sqlite` or `.sqlite3`; no changes under `app/`, v1 datasets, red-team artifacts, evaluation reports or LaTeX report; Phase 12E not started

## Documentation Consistency
- Status: PARTIALLY RESOLVED
- Inconsistencies:
  - `phase-12d-audit-resolution.md` claims only fully preflight-valid provenance records enter `by_artifact_id`, but insertion occurs before validating the remaining provenance fields.
  - It also claims invalid provenance values are skipped by downstream checks; the implementation instead processes some of them through operations that are safe but not skipped.
  - The documented malformed matrices say 16 corpus and 25 label combinations; the current parameter lists contain 17 and 26 respectively.
  - Phase status, previous `REVISE`, executed totals, CANDIDATE status and final-verification recommendation are otherwise accurate.

## Remaining Critical Issues
None

## Remaining Blocking Major Issues
None

## Required Actions Before Commit
Correct the three audit-resolution/test-documentation inaccuracies above so the evidence describes the actual implementation and collected parameter counts.

## Final Verdict
REVISE