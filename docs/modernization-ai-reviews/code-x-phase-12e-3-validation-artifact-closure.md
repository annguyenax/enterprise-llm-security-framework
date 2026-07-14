# Code X Phase 12E.3 Validation Artifact Closure Audit

## Candidate Identity

- Main repository: `phase-12e-3-analyzer-audit` at `bf87161a9f5b4ecdfcfb90c072a66f4d0af169a6`; clean before this requested audit report was added.
- Execution worktree: `D:\p12e3-wt-c6d91c7`, branch `phase-12e-3-validation-exec-c6d91c7`, exact implementation commit `c6d91c78e11009e96a76db08c0dfbb710504c227`, clean.
- Every result records `git_dirty=false`, the exact execution branch and commit, `provider_id=mock`, and `split=validation`.
- Common experiment identity independently recomputed as `9864d5773933dec2962e67ffb60de90d5de0dad6417a3ba04769ac4500ad41cb`.
- No runner or analyzer was executed during this audit. This verdict applies only to the exact implementation commit and attempt 2 root named above.

## Attempt History

- Attempt 1 authorization permitted validation C0-C7 once with the Mock Provider and explicitly prohibited holdout.
- Its transcript contains one terminal `manifest_missing_artifact` failure for `cases/development.jsonl`.
- Independent inventory found only `authorization.txt` and `validation-transcript.txt`; neither `runs/` nor `analysis/` exists. No case record or runner result artifact exists.
- Attempt 2 had separate explicit authorization. Its transcript and outputs record exactly eight complete validation runs followed by one analysis publication; further rerun and holdout remained unauthorized.

## Matrix Completeness

- Exactly eight `result-manifest.json` and eight sibling `result.json` files exist, with no duplicate or unknown configuration and no extra run files.
- The configuration set and order are exactly C0-C7. Every run and every case record is `complete`; error, timeout, and skipped counts are zero.
- `C0_all_on` contains 30 cases across the four declared scopes. C1-C7 each contain 26 `end_to_end` cases.
- Case ordinals, unique IDs, per-scope counts, per-scope hashes, and expected-case-set hashes were independently reconstructed and matched.

## Per-Config Artifact Integrity

| Config | Run ID | Result SHA-256 / bytes | Result-manifest SHA-256 |
|---|---|---|---|
| C0_all_on | `C0_all_on-01784038256335655300-27040` | `2bbe8a578e0e135b8666491d8726fa7e043fce49e14d2528649322d47bb1d487` / 85173 | `2ae098d720bd0f323a00eb2fe840aabad0174902f92efc8a0744c642b3630f54` |
| C1_no_input | `C1_no_input-01784038256902940600-27040` | `d8482927b9ac56f9bf89a82eccf49c106543909221465d96d6d971dcafac92c5` / 79475 | `c5f9142a92cad0be1b3324940863bd0e9f89bed17a771c6c285139b33f762a02` |
| C2_no_provenance | `C2_no_provenance-01784038257426706300-27040` | `d39f64b95da86ed2029b8d8115f6b01826f8b56577963d8042f517b5f112ca85` / 78237 | `b41cee8cd53d77d96a15dc33ca8b6930a4d430fa455ad5ec73f81c21bf9d3fe5` |
| C3_no_context | `C3_no_context-01784038257863291100-27040` | `69483d68bd5f15bf533f02baa65976f77cbbae0998c1935ee1d5837f0b997283` / 63565 | `6d044e8e1bf59df55bb11b4db20e2a0c71ded19085ed96318b5fe8fc1f55d260` |
| C4_no_dlp | `C4_no_dlp-01784038258295141200-27040` | `b2be49b8e0f2c0ccc3d5a9e5b6e53c4749b12370d79a59d5b49986548754c7c1` / 77914 | `fc37540c832395f3ec830f553c97130f70805846ad45b2f16796bf50ab15a104` |
| C5_no_output | `C5_no_output-01784038258779836400-27040` | `3db2aa69dbfa84cac7ae1e697cb6b4a47ed496b2a55dcbfbf649e4decc6a584d` / 78085 | `76834c0172928811d8bb947006ea1ed5389b667f464d63088114143c5c529ec7` |
| C6_none | `C6_none-01784038259224638300-27040` | `055a9955535b2624ec4d3304312f73928bcf419d663bfab50359d3e9bc0e8e69` / 63637 | `af63c09b270ee602c2a1b32647f0deb91de0c95e5f9ec00fd12214a5d21f630d` |
| C7_no_context_no_output | `C7_no_context_no_output-01784038259620412300-27040` | `60bf0fa7221354b0fd20861932c105bc7cd8c869009d7c2c0c45ae9b55a274d1` / 63725 | `94e1956fdef295acc4510ce65ac04117a63ea07d3d6c27f99b9c97eb9d71b204` |

- Each result and manifest is strict, duplicate-free canonical JSON. Result hashes and byte sizes match the sibling manifests and attempt-2 evidence.
- Run IDs and all manifest/result identity fields match. Every configuration hash was independently recomputed from its config ID and guard profile.
- C0 expected-case-set SHA-256 is `2b40bd444bd2ff7affbd2d27f35cbf41be0e64b412e4487b5787b1aa3e81dfcc`; C1-C7 share `a19e9630a5cf4d70b2f6743b7fb9903452af7958c2ce2d138a69e29079c53083`.

## Analyzer Artifact Integrity

- The analysis directory contains exactly `analysis.json`, `analysis-table.csv`, and `analysis-manifest.json`.
- `analysis.json`: SHA-256 `d518c4a674661b636395a07081ac8d56cffd832730931e281e7452e3ca50a7ae`, 60528 bytes.
- `analysis-table.csv`: SHA-256 `cbd176fcc8b9753729ef765fd66fa40506d6800193eb44607182455f2b71096a`, 40043 bytes.
- `analysis-manifest.json`: SHA-256 `7a90fbc328588113c04a512e135122d46e04db46d7b57b97da2d92f21601d3c6`, 3783 bytes.
- Manifest references, sizes, input-manifest hashes, result hashes, run IDs, config hashes, and statuses all match independently recomputed values.
- `analysis_contract_sha256=c5bff80eb007c4dbd1b8e2bf122fb14de560aa37668b759924cfb075d51143f2`, `mapping_sha256=1de3b7d83f492a1a16df20d900c2f0523f210d713e9b84c6aa1369a9355a8d88`, and `benchmark_manifest_sha256=c91da60b8cc5730446568f8809290171f3e139ef3613169deb41c5284050335a` were independently reconstructed or hashed and match.

## Analysis Contract

- All eight complete inputs are represented in C0-C7 order. C0 has 23 family rows; C1-C7 each have 20.
- Every family row has only `scenario_family`, `evaluation_scope`, `analysis_group`, `matched`, `total`, and `error_count`.
- No `abr` metric key, `Attack Block Rate` string, macro metric, macro CSV row, family rate, or family percentage is present. Required policy flags remain false.
- Every rate object obeys `RATE_REPORTING_MIN_N=10`, including zero-denominator and small-n suppression and Wilson eligibility rules.
- Latency is non-reportable, with `p50=null` and `p95=null`.
- Strict recursive scans of all result and analysis JSON plus all 208 CSV rows found no forbidden raw field, canary/secret value, retrieved content, answer, or absolute machine path.

## Holdout Prohibition

- No run, result, manifest, analysis file, or artifact path has holdout identity; all eight results and the analysis identify `validation`.
- Holdout execution was not authorized and is recorded as not executed in both transcript and evidence.
- The two frozen holdout files were byte-hashed, not parsed, solely while independently verifying all nine files against the FINAL benchmark manifest.
- This audit does not authorize holdout.

## Repository Hygiene

- Main repository and validation worktree were clean before the requested report was added. The worktree remains clean.
- No result manifest, analysis manifest, analysis table, or `reports/evaluation-v2` artifact is tracked.
- The execution branch contains zero commits beyond `c6d91c7`; generated artifacts remain external and there is no validation-execution commit to merge.
- Main is one documentation commit ahead of the implementation commit. No code, benchmark, mapping, metric policy, or generated evaluation artifact was modified during this audit.

## Critical Issues

None.

## Blocking Major Issues

None.

## Required Corrections

None.

## Final Verdict

PASS

This verdict applies only to implementation commit `c6d91c78e11009e96a76db08c0dfbb710504c227` and validation attempt `D:\p12e3-validation-c6d91c7-attempt2`. It does not authorize holdout and makes no final thesis or production-security claim.
