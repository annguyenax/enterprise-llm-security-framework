# Phase 12E.2 Runner Implementation Plan

## Repository State
Branch `phase-12e-ablation-evaluation` (development split only). GuardProfile and pipeline implemented (Phase 12E.1). No runner, analyzer, or evaluation artifacts exist. Manifest and frozen v2 benchmark ready for read-only dispatch.

## Scope
Implement `scripts/run_v2_evaluation.py` and supporting tests only for development split. Runner dispatches configured profiles (C0-C7) against frozen v2 cases via in-process seam. No metric aggregation, holdout, validation split execution, analyzer, or Phase 12E.3+ work.

## Files to Add or Modify
- **Add**: `scripts/run_v2_evaluation.py`
- **Add**: `tests/test_v2_evaluation_runner.py`
- **Minimal update**: `scripts/verify_phase.ps1` (add runner smoke call only)
- **No other changes**

## Runner Architecture
- Single entrypoint `run_v2_evaluation.py --scope <development> --profile <C0..C7>`
- Loads frozen v2 dev split cases/manifest
- Uses in-process `run_rag_query_uncommitted(..., guard_profile=...)` seam
- Collects `RagPipelineResult` + stage telemetry per case
- Writes canonical JSON artifact (no overwrite)
- Enforces all integrity gates

## Configuration Registry
- Hard-coded C0-C7 with exact boolean combinations and SHA-256 profile_id hashes
- `ALL_ON` (C0) default
- Registry frozen in code with comments matching master plan

## Integrity Gates
- Git dirty-tree check (fail if dirty)
- Manifest SHA-256 verification for dev split
- Commit SHA pinning
- Case-set identity hash
- Forbidden raw fields scan on all artifacts

## Scope Dispatch
- `end_to_end`: C0-C7 full pipeline
- `component`: C0 only (specific stage isolation)
- `availability_fault`: C0 only
- `residual_risk_only`: C0 only
- All scopes use development split only

## Provider and C6 Isolation
- Mock/offline provider allowlist enforced (C6 restricted to temporary SQLite + mock)
- No network, external provider, or unsafe paths for any profile
- C6 explicitly gated with checklist assertion

## Result Schema
- Per-case `CaseResult` with request_id, profile_id, final_decision, stage_results, telemetry (safe summaries only), latency
- Canonical JSON with byte-size manifest

## Error and Partial-Run Semantics
- Exactly one safe case record for error/timeout cases
- Fatal integrity failure aborts entire run
- Case-level failures recorded but do not halt run
- Complete run = every expected case executed exactly once
- Partial runs rejected for primary claims

## Determinism
- Seeded random if needed; profile_id and case order deterministic
- Verification of identical results on re-run with same commit/manifest

## Artifact Writing
- Atomic write to timestamped dir
- SHA-256 + byte size manifest
- No-overwrite (fail if exists)
- Safe redaction scan before write

## Required Tests
- `test_v2_evaluation_runner.py`: registry, integrity gates, dispatch, C6 isolation, safe results, determinism, error cases, forbidden fields
- Smoke in `verify_phase.ps1`

## Mechanical Verification
- `python scripts/run_v2_evaluation.py --scope development --profile C0` (dev only)
- Git diff --check, pytest on new tests, manifest verification

## Explicit Non-Goals
- No analyzer, metrics, holdout, validation split execution
- No Phase 12E.3+ work
- No real LLM, vector, or external calls

## Code X Implementation Task
Implement per this plan only; verify all 20 points above.

## Grok Audit Checklist
- All 20 points documented and verifiable in code/tests
- No scope drift
- Development split only

Do not claim implementation has started.