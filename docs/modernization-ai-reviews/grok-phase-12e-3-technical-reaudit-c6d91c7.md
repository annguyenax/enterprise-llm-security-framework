# Grok Phase 12E.3 Technical Correction Re-Audit

## Candidate Identity
- **Branch:** `phase-12e-3-analyzer-audit`
- **Commit:** `c6d91c78e11009e96a76db08c0dfbb710504c227`
- **Working tree:** clean
- **Correction diff reviewed:**  
  `d62d0a98f5b01191666f3258f344095107953364..c6d91c78e11009e96a76db08c0dfbb710504c227`  
  — only:
  - `scripts/analyze_v2_results.py`
  - `scripts/run_v2_evaluation.py`
  - `tests/test_v2_evaluation_runner.py`
  - `tests/test_v2_result_analyzer.py`  
  (~157 insertions / 22 deletions; no `datasets/`, `app/`, `requirements.txt`, reports/redteam/template changes)

## Mechanical Evidence

As supplied for this exact commit:

| Check | Result |
|---|---|
| Focused tests | 194 passed, 1 warning |
| Full suite | 717 passed, 1 warning |
| Validator | 172 documents, 120 cases, PASS |
| Determinism | byte-identical, PASS |
| Frozen FINAL manifest | 9/9, no drift |
| git diff / scope | PASS |
| Temp dirs / tracked DBs | clean / none |
| Working tree | clean |
| Warning | existing Starlette/`httpx` deprecation |

Targeted non-evaluation probes on this HEAD confirmed stage contract, rejection paths, and external output-root policy (below).

## Previous Critical Finding
- **Status:** **RESOLVED**
- **Evidence:**
  - Prior Critical: analyzer required non-null `stage.decision` while runner emitted `null` for disabled stages.
  - Now `_project_stage_results` sets `decision=None` and `execution_time_ms=None` when `enabled=false`.
  - Analyzer `_validate_stage_results`: if `enabled`, require Decision taxonomy string; if not enabled, require `decision is None`.
  - Probe of authentic C1 projection (disabled `input_guard` + informational `retrieval` + enabled context guard) → analyzer accepts.
  - Disabled stage with `decision="allow"` → rejected (`must be null when the stage is disabled`).
  - Enabled stage with `decision=None` or `"unexpected"` → rejected.

## Disabled-Stage Contract

| Rule | Status |
|---|---|
| `enabled=false` ⇒ `decision=null` | enforced runner + analyzer |
| `enabled=true` ⇒ valid `Decision` value | `VALID_STAGE_DECISIONS` from `Decision` enum |
| Authentic disabled-stage runner records accepted | probe + tests |
| Disabled + non-null decision rejected | probe + `test_analyzer_rejects_non_null_decision_for_disabled_stage` |
| Enabled + null / invalid rejected | probe + parametrized test |
| Unrelated schema not weakened | still exact `STAGE_KEYS`; reason_code still required safe string; timing still finite nullable |

## Retrieval-Stage Projection

Inspected change:

```text
decision = (stage.decision or Decision.ALLOW).value  if enabled else None
execution_time = latency[stage] if enabled else None
reason_code unchanged
```

| Question | Assessment |
|---|---|
| Consistent with analyzer enabled-stage schema? | **Yes** — enabled stages need non-null Decision |
| Preserves original reason code? | **Yes** — e.g. `retrieval_completed` kept |
| Falsely claims a security guard allowed content? | **No** — retrieval is not in `GUARD_STAGE_TO_FIELD`; `enabled=True` means “stage ran,” not “guard on”; interpretation must use `stage` + `reason_code` |
| Consistently validated? | **Yes** — analyzer accepts `allow` + `retrieval_completed` |
| Alters case-level correctness / primary metrics? | **No** — `correct` / AOMR / FPR still from final decision + stop reason + label sets only |

**Not treated as blocking.** Neutral `ALLOW` fill is limited to telemetry for stages that already executed with a null internal decision (typical informational retrieval). Disabled guards still project `null`.

**Minor residual note:** `(stage.decision or Decision.ALLOW)` would also normalize an unexpected `None` on an *enabled guard* stage to `allow` in telemetry only. That does not change case metrics; it softens stage integrity signaling. Acceptable as Minor, not a re-open of Critical.

## Runner-to-Analyzer Contract Tests

**PASS.**

- `_runner_projected_ablation_stages()` builds a real `RagPipelineResult` and calls **`runner._project_stage_results`** with `C1_no_input` profile (not empty synthetic stages only).
- Synthetic matrix injects that projection into **C1 first case**.
- Tests cover: accept authentic projection; reject disabled non-null; reject enabled null/invalid; assert C1 result file contains authentic projected stages after full analysis path.

## External Output-Root Policy

**PASS (previous Major resolved).**

Runner `_validate_output_root` now rejects:

| Path | Result |
|---|---|
| repository root | outside repository |
| any path under repo (incl. `reports/evaluation-v2`, `data/`) | outside repository |
| `datasets/v2` / under benchmark | overlaps protected input |
| existing file (not directory) | must be a directory |

Accepts explicit external directory (probe: temp dir outside repo).  
Analyzer remains external-only (unchanged policy, not weakened).

## Regression Review

Correction diff limited to stage projection, stage validation, output-root, and tests.

| Area | Unchanged (spot-checked) |
|---|---|
| Metric formulas / `_confusion` / `make_rate` | yes |
| `RATE_REPORTING_MIN_N = 10` | yes |
| Wilson policy | yes |
| Family mapping `phase12e3-family-map-v2` | yes |
| ABR / macro / F1 absence | contract flags still false; no ABR metric |
| Holdout prohibition | `SUPPORTED_SPLITS` development/validation only |
| Frozen artifacts | no dataset diff |
| Mock provider only | `SUPPORTED_PROVIDER_ID = mock` |
| Public API / guard internals | no `app/` diff |
| Atomic publication | not touched in this diff |

## Critical Issues

**None**

## Major Issues

**None**

## Minor Issues

1. **Enabled-stage null coalesce to `Decision.ALLOW` in projection** applies to any enabled stage with `decision is None`, not only retrieval. Safe for metrics; slightly weaker stage-level integrity signal if a guard ever omitted a decision. Optional harden: only fill ALLOW for known non-guard stages (e.g. `retrieval` / `provider`), and fail closed on null for guard stages that are enabled.

## Required Corrections

**None** for re-audit PASS of this commit.

Optional (non-blocking) follow-up for Minor #1 only.

## Final Verdict

**PASS**

Applies only to exact commit  
`c6d91c78e11009e96a76db08c0dfbb710504c227`.

- Phase 12E.3 is **not** declared closed by this re-audit.  
- Validation is **not** authorized here.  
- Holdout was **not** run and remains prohibited.
