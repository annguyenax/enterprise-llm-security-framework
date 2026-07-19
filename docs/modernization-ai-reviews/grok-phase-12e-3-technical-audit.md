# Grok Phase 12E.3 Technical Audit

## Candidate Identity
- **Branch:** `phase-12e-3-analyzer-audit`
- **Commit:** `47bd393d1a7ac9106ce5a64bb8edd736615ad038`
- **Working tree:** clean (`git status --porcelain` empty)
- **Exact diff reviewed:**  
  `1571db1cb928277b9c6c28166858d2fe72cf8ad3..47bd393d1a7ac9106ce5a64bb8edd736615ad038`  
  for:
  - `scripts/run_v2_evaluation.py`
  - `scripts/analyze_v2_results.py` (new)
  - `scripts/verify_phase.ps1`
  - `tests/test_v2_evaluation_runner.py`
  - `tests/test_v2_result_analyzer.py`  
  plus plan doc `docs/modernization-ai-reviews/grok-phase-12e-3-analyzer-plan.md` (also in range; not implementation surface)

## Mechanical Evidence Reviewed

As supplied for this exact commit (not re-run as a second evaluation matrix):

| Check | Reported result |
|---|---|
| Focused tests | 189 passed, 1 warning |
| Full suite | 712 passed, 1 warning |
| Benchmark validator | 172 documents, 120 cases, PASS |
| Determinism | byte-identical, PASS |
| Frozen FINAL manifest | 9/9, no drift |
| git diff / scope invariants | PASS |
| Temp / tracked DBs | clean / none |
| Warning | existing StarletteDeprecationWarning (`fastapi.testclient` / `httpx`) |

Targeted **non-evaluation** probes on this commit (local only):

- `load_split_benchmark(..., "holdout")` → rejected before evaluation load  
- `preflight(split="holdout")` → rejected; output path not created  
- Runner `_project_stage_results` with disabled guard → **`decision: null`**  
- Analyzer `_validate_stage_results` with that shape → **reject**  
- Rate policy matrix for den 0 / 1–9 / ≥10 behaves as specified  
- No `"Attack Block Rate"` string in analyzer source  

## Scope Integrity

**PASS for approved surface.**

Diff name-only shows only:

- plan doc under `docs/modernization-ai-reviews/`
- runner, analyzer, verify_phase, two test modules  

No changes under `datasets/`, `app/`, `requirements.txt`, `reports/`, `redteam/`, `report-latex-template/`.

`verify_phase.ps1` focused modules correctly add `tests/test_v2_result_analyzer.py`.

## Validation Extension

**PASS** for parameterization of prior development-only hardcodes.

| Requirement | Evidence |
|---|---|
| Executable splits only development/validation | `SUPPORTED_SPLITS`; CLI `choices=list(SUPPORTED_SPLITS)` |
| `request.split` threaded | preflight load, `_experiment_id`, case records, top-level `result.split`, run directory |
| Validation cases/labels | `load_split_benchmark` → `cases/{split}.jsonl`, `labels/{split}.jsonl` |
| Experiment identity includes split | `_experiment_id(..., split=request.split)` |
| C0 all scopes / C1–C7 e2e only | unchanged `_expected_case_sets` |
| Config-specific `expected_case_set_sha256` | unchanged `_case_set_hash` path |
| Compatibility | `load_development_benchmark` / `run_development_evaluation` remain development-only wrappers |

## Holdout Prohibition

**PASS**, with freeze-hash correctly distinguished.

| Path | Behavior |
|---|---|
| CLI `--split holdout` | argparse reject (not in choices) |
| `preflight` / `RunRequest(split="holdout")` | IntegrityError before manifest loader and before case/label evaluation load (test + code order) |
| `load_split_benchmark(..., "holdout")` | reject before opening holdout case/label files |
| Analyzer request / CLI | holdout prohibited; no output root created on early fail |
| `verify_frozen_manifest` | still requires nine FINAL paths including holdout file **byte hashes** only |

No evaluation path found that parses/scores holdout records.

## Runner Regression Safety

**PASS** for retained 12E.2 safety controls (no evidence of intentional removal in the small runner diff).

Preserved by construction: mock-only provider, credential env reject, network disable hooks, temp SQLite outside repo, spawn timeout kill, timeout state corruption abort, C6 projection safety, dual-repetition determinism, forbidden-content scan, canonical JSON, atomic no-overwrite publish, cleanup not masking publish error.

**Note (see Major):** runner still allows in-repo `reports/evaluation-v2` as an approved output root; analyzer does **not**. Plan required external-only for both.

## Analyzer Integrity

**Mostly strong; blocked by Critical stage-schema bug.**

| Requirement | Status |
|---|---|
| Exactly eight explicit manifests | `_validate_request` + append CLI; no directory walk |
| No wildcard / recursive discovery | yes |
| Sibling `result.json` only | `result_file == "result.json"`; parent-only resolve |
| Hash + size before parse | yes |
| Manifest key set exact | `RESULT_MANIFEST_KEYS` |
| Manifest SHA for analysis identity | computed from raw bytes |
| Symlink / traversal reject | `_resolve_manifest_path`, result symlink checks |
| Mixed identity reject | `_validate_common_inputs` |
| Partial matrix reject before primary metrics | `_validate_primary_matrix` after full result validation |
| No output after failed gates | `output_root` resolved only after integrity chain; early fails leave no dir |
| External output-root | analyzer rejects repo-internal, benchmark, production DB, input trees |

## Correctness and Completeness

**PASS** for recomputation and expected sets.

- Completed cases:  
  `correct ≟ (actual_final_decision ∈ allowed_final_decisions ∧ actual_stop_reason ∈ allowed_stop_reasons)`  
  mismatch → `stored_correct_mismatch`
- Error/timeout: require `correct is False` and fixed error categories  
- Expected IDs/hashes recomputed from frozen split + config via runner helpers  
- Family rows: C0 → 23; C1–C7 → 20  
- Non-matrix diagnostics only on C0  

## Mapping Integrity

**PASS.**

- Version `phase12e3-family-map-v2`  
- Groups: `direct_injection`, `indirect_injection`, `leakage_mechanisms`, `benign_control`  
- 20 e2e mapped, sorted lists, non-matrix three excluded  
- `data_exfiltration` explicitly rejected  
- `mapping_sha256` from canonical `_mapping_payload` via runner `_canonical_json_bytes`  
- Observed: `mapping_sha256 = 1de3b7d83f492a1a16df20d900c2f0523f210d713e9b84c6aa1369a9355a8d88`  

## Metric Implementation

**PASS** (formulas).

```text
M = malicious|mixed ∧ end_to_end
B = benign ∧ end_to_end
TP/FN/TN/FP as specified
AOMR = TP/(TP+FN)
MismatchRate = FN/(TP+FN)
FPR = FP/(FP+TN)
```

Confirmed absences:

- no ABR metric / no “Attack Block Rate”  
- no macro objects or macro CSV rows  
- no F1  
- family rows raw counts only  

`abr_enabled: false` is a claims-control/contract flag only (allowed).

## Statistical-Policy Enforcement

**PASS.**

| Rule | Code |
|---|---|
| `RATE_REPORTING_MIN_N = 10` | constant + `make_rate` |
| den 0 | defined=false, reporting_eligible=false, value=null, reason=`zero_denominator` |
| den 1–9 | defined=true, reporting_eligible=false, value=null, reason=`n_below_10` |
| den ≥10 | value populated; Wilson only if `wilson=True` (AOMR/FPR) |
| Mismatch / coverage / error | rate objects without Wilson eligibility |
| Family / marginal / latency | no CI |

Wilson: z≈1.95996, no continuity correction; fixed caveat string present.

## Marginal Comparisons

**PASS.**

- Paired **M** e2e cases only  
- C0 vs C1–C5 per `MARGINAL_DEFINITIONS`  
- Paired case-set hash, transition counts, raw numerators/denominators  
- `delta_value` only when both AOMR values reporting-eligible; **no CI**  
- Non-additivity caveat + claim template  
- `mock_provider_limitation` true for dlp / output_guard  

## Latency Containment

**PASS.**

- `reportable=false`, `p50=null`, `p95=null`  
- `repetitions_observed=2`, `warmup_observed=0`  
- Protocol note = determinism repetitions only  
- No latency percentile CSV fields  

## Output and Serialization Safety

**PASS** (schema/publish path).

- Exact analysis / CSV / analysis-manifest construction with fixed key sets  
- Canonical JSON, UTF-8 LF CSV, no BOM  
- Forbidden recursive scan (runner shared)  
- NaN/Inf rejected (`parse_constant`, finite checks)  
- Exactly three published files; atomic rename; no overwrite; cleanup preserves original exception  
- No timestamps; path basenames only in analysis inputs  

## Adversarial Probes

Performed only local unit probes (no validation matrix, no holdout run, no external provider):

1. Holdout load/preflight rejection without output  
2. Stage `decision: null` from real runner projection vs analyzer schema  
3. Rate eligibility matrix  
4. Mapping/group name and ABR string scan  

## Critical Issues

1. **Analyzer rejects legitimate runner stage telemetry for disabled guards (`decision: null`).**  
   - Runner `_project_stage_results` emits `decision: null` for disabled ablation stages (confirmed probe).  
   - Analyzer `_validate_stage_results` forces `_string(item["decision"], ...)` → non-null safe string only.  
   - Probe: disabled stage record → `AnalysisIntegrityError: ...decision must be a non-empty string`.  
   - Synthetic analyzer fixtures use `stage_results=()`, so the full suite can PASS while **real C1–C7 (and any disabled-stage) result artifacts cannot be analyzed**.  
   - This blocks the primary purpose of Phase 12E.3 on authentic runner outputs.

## Major Issues

1. **Runner output-root policy not aligned with reconciled plan “external-only”.**  
   Analyzer forbids any path under the repository. Runner still permits `reports/evaluation-v2` inside the repo (`_validate_output_root`). Plan required consistent external output-root for runner and analyzer during implementation/smoke/pre-audit.

2. **Test gap for disabled-stage schema contract.**  
   No runtime test feeds a real disabled-stage projection (or fixture with `decision: null`, `enabled: false`) through analyzer validation. This allowed Critical #1 to land behind green tests.

## Minor Issues

1. Redundant latency sample branch: both arms accept length set `{0, 2}` (`_validate_latency_samples`). Harmless, but noisy.  
2. Console success message prints only `output_directory.name` (basename). Safe, but slightly less useful for operators.  
3. CSV includes extra marginal identity columns beyond the minimal plan header sketch; consistent and tested, not a defect—document as intentional superset only if regenerating plan text.

## Required Corrections

1. **Allow `stage_results[].decision` to be `null` when `enabled is false`** (and keep non-null decision string when enabled), matching runner projection and master-plan disabled-stage contract; reject non-null garbage when disabled if desired.  
2. Add **runtime tests** that:  
   - project/build a disabled-stage record with `decision: null`;  
   - accept it in analyzer validation;  
   - reject `enabled: false` with a non-null unexpected decision **or** accept only the runner contract—whichever is chosen, encode it.  
3. **Align runner output-root** with external-only policy **or** explicitly re-adjudicate plan text if in-repo `reports/evaluation-v2` remains intentionally allowed for runner only (not recommended without written exception).  
4. Re-run focused + full verify on the correction commit; no validation matrix until after re-audit PASS and human authorization.

## Final Verdict

**REVISE**

Applies only to exact commit  
`47bd393d1a7ac9106ce5a64bb8edd736615ad038`.

- Phase 12E.3 is **not** closed.  
- Validation is **not** authorized.  
- Holdout was **not** run and remains prohibited.
