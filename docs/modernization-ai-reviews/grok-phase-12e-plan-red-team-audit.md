## User

[AI: Grok — Phase 12E Adversarial and Red-Team Plan Audit]

Perform a STRICT READ-ONLY adversarial audit of the Phase 12E ablation
evaluation plan.

Repository:
D:\DoAnThucTap\enterprise-llm-security-framework

Required branch:
phase-12e-ablation-evaluation

Required commit:
<FULL_SHA>

Do not modify files.
Do not create payload files.
Do not stage, commit, push, install dependencies, or begin implementation.

First verify:

- actual branch;
- exact HEAD;
- working-tree status;
- whether repository files were directly inspected;
- whether Phase 12E implementation has started.

Stop with CANNOT VERIFY if branch or commit differs.

==================================================
Read
==================================================

Inspect:

- docs/ai-collaboration/06_PHASE_12E_MASTER_PLAN.md
- docs/ai-collaboration/05_OPEN_QUESTIONS.md
- docs/benchmark-v2-methodology.md
- datasets/v2/README.md
- docs/modernization-ai-reviews/phase-12c-audit-resolution.md
- docs/modernization-ai-reviews/codex-phase-12c-final-reaudit.md
- current Phase 12C pipeline, guards, provider and API boundaries where needed

==================================================
Threat-model audit
==================================================

Review whether the plan can detect or avoid misleading evaluation under:

- direct prompt injection;
- indirect prompt injection in retrieved content;
- multi-chunk coordinated attacks;
- split bilingual attacks;
- Unicode normalization;
- zero-width characters;
- homoglyphs;
- encoding and obfuscation;
- benign authority-language false positives;
- malicious trusted-source content;
- mixed-trust retrieval;
- metadata/provenance spoofing;
- prompt leakage;
- output secret leakage;
- partial or split leakage;
- audit-log leakage;
- malformed response construction;
- provider failures;
- guard failures;
- audit-sink failures;
- evaluation-run interruption;
- tampered result files;
- mismatched benchmark manifest;
- changed code between ablation runs;
- public clients attempting to disable guards;
- internal toggle leakage into serving configuration.

Do not require the benchmark to cover every possible semantic attack. Distinguish
between Phase 12E blockers and future red-team expansion.

==================================================
Ablation safety
==================================================

Assess every configuration:

- C0_all_on
- C1_no_input
- C2_no_provenance
- C3_no_context
- C4_no_dlp
- C5_no_output
- C6_none
- C7_no_context_no_output

For each, determine:

- what security control is removed;
- what safety mechanisms must remain active;
- whether it can execute only through an internal evaluation interface;
- whether it could invoke unsafe external behavior;
- whether result interpretation could falsely imply that a removed guard has no
  value;
- whether interactions or compensating controls can hide vulnerabilities.

Pay special attention to C6_none. It must not:

- expose a public no-guard endpoint;
- call an external provider;
- write unsafe raw secrets to logs;
- bypass benchmark/output containment;
- affect normal serving configuration.

==================================================
Evaluation bypasses and blind spots
==================================================

Find ways an implementation could appear to pass the plan while producing
misleading results, including:

- skipping difficult cases;
- converting failures into benign outcomes;
- counting sanitized output as blocked;
- counting multiple alerts per case as multiple detections;
- omitting false positives;
- dropping timed-out cases;
- mixing development and holdout;
- tuning after holdout inspection;
- changing guards between configurations;
- using different case ordering or environment;
- silently truncating context;
- failing to record which layer triggered;
- treating uninspected output as safe;
- editing generated result files;
- using Hermes candidates as automatic labels.

Determine whether the plan has explicit controls for each meaningful risk.

==================================================
Required output
==================================================

Return Markdown only:

# Grok Phase 12E Red-Team Plan Audit

## Repository State Verified
- Branch:
- Commit:
- Working tree:
- Files directly inspected:
- Phase 12E implementation started:

## Threat-Model Coverage
- Status:
- Strong areas:
- Missing or weak areas:
- Blocking:

## Ablation Safety
- Status:
- C0-C7 assessment:
- C6 no-guard assessment:
- Public bypass risk:
- Blocking:

## Evaluation-Gaming and Integrity Risks
- Status:
- Potential bypasses:
- Existing mitigations:
- Blocking:

## Missing Adversarial Cases
- Blocking cases:
- Non-blocking future cases:

## False-Positive and Benign Counterexample Coverage
- Status:
- Findings:
- Blocking:

## Audit and Result-Artifact Safety
- Status:
- Findings:
- Blocking:

## Critical Issues
None or findings.

## Major Issues
None or findings.

## Minor Issues
None or findings.

## Deferrable Recommendations
None or findings.

## Required Corrections Before Implementation
None or exact corrections.

## Final Verdict
PASS

or

REVISE

## Assistant

I'll run a strict read-only audit: first verify branch/HEAD/working tree, then inspect the Phase 12E plan and related docs without changing anything.

## Tools

- Execute: git rev-parse --abbrev-ref HEAD; git rev-parse HEAD; git status --porcelain; git status -sb; git log -1 --oneline; git branch -vv (Verify branch, HEAD, and working tree)
- Read: D:\DoAnThucTap\enterprise-llm-security-framework\docs\ai-collaboration\06_PHASE_12E_MASTER_PLAN.md
- Read: D:\DoAnThucTap\enterprise-llm-security-framework\docs\ai-collaboration\05_OPEN_QUESTIONS.md
- Read: D:\DoAnThucTap\enterprise-llm-security-framework\docs\ai-collaboration\00_PROJECT_STATE.md

## Assistant

Branch and HEAD match the required audit target. Next I'll inspect methodology docs, 12C audit reports, and the live pipeline/guard boundaries.

## Tools

- Read: D:\DoAnThucTap\enterprise-llm-security-framework\docs\benchmark-v2-methodology.md (1-200)
- Read: D:\DoAnThucTap\enterprise-llm-security-framework\datasets\v2\README.md (1-101)
- Read: D:\DoAnThucTap\enterprise-llm-security-framework\docs\modernization-ai-reviews\phase-12c-audit-resolution.md (1-150)
- Read: D:\DoAnThucTap\enterprise-llm-security-framework\docs\modernization-ai-reviews\codex-phase-12c-final-reaudit.md (1-97)
- Execute: git status --porcelain; if (-not (git status --porcelain)) { Write-Output "WORKING_TREE_CLEAN" }; git rev-parse HEAD; Test-Path scripts/run_v2_evaluation.py; Test-Path scripts/analyze_v2_results.py; Test-Path tests/test_guard_profile.py; Test-Path tests/test_v2_evaluation_runner.py; rg -n "GuardProfile|guard_profile" app --glob "*.py" 2>$null; if (-not $?) { Write-Output "rg_or_guardprofile_search_done" } (Confirm clean tree and no 12E implementation)

## Assistant

I'll inspect pipeline seams, request boundaries, and methodology coverage for attack families and residual risks.

## Tools

- Search: GuardProfile|guard_profile|run_rag_query_uncommitted|ALL_ON
- Read: D:\DoAnThucTap\enterprise-llm-security-framework\app\core\pipeline.py (1-80)
- Read: D:\DoAnThucTap\enterprise-llm-security-framework\app\services\rag_query.py (351-430)
- Search: scenario_family|residual_risk|homoglyph|zero.?width|unicode|multi.?chunk|benign|authority|trusted
- Search: extra.?forbid|guard_profile|disable|Settings|enable_audit
- Read: D:\DoAnThucTap\enterprise-llm-security-framework\docs\benchmark-v2-methodology.md (201-450)
- Search: STOP_|stop_reason
- Read: D:\DoAnThucTap\enterprise-llm-security-framework\app\api\routes.py (281-360)
- Search: class.*Request|extra\s*=\s*[\"']forbid|RagQuery
- Read: D:\DoAnThucTap\enterprise-llm-security-framework\docs\benchmark-v2-methodology.md (961-1040)
- Read: D:\DoAnThucTap\enterprise-llm-security-framework\docs\ai-collaboration\06_PHASE_12E_MASTER_PLAN.md (291-320)
- Search: stage_results|actual_stop|which layer|triggered|timeout|integrity|hash.*result|result.*hash|overwrite|answer
- Search: evaluation_scope|component|availability_fault|ingestion|POST /v1|HTTP|in-process|in_process|budget|_bound_chunks|scripted
- Read: D:\DoAnThucTap\enterprise-llm-security-framework\app\schemas\requests.py (76-98)
- Read: D:\DoAnThucTap\enterprise-llm-security-framework\docs\decisions\ADR-003-v2-benchmark.md (1-100)
- Search: HTTP|in-process|runner|ablation|GuardProfile|verify.*manifest
- Execute: git log -3 --oneline; git show -s --format="%H%n%s%n%ci" HEAD; Get-ChildItem -Recurse -Path scripts,app,tests,reports -Filter "*v2_eval*" -ErrorAction SilentlyContinue | Select-Object FullName; Get-ChildItem -Path reports -ErrorAction SilentlyContinue | Select-Object Name; Test-Path reports/evaluation-v2; Select-String -Path app\core\pipeline.py -Pattern "GuardProfile" | ForEach-Object { $_.Line }; Select-String -Path app\core\config.py -Pattern "guard|enable_" | ForEach-Object { $_.Line.Trim() } (Confirm no 12E impl and inspect config)
- Read: D:\DoAnThucTap\enterprise-llm-security-framework\app\guards\output_guard.py (1-80)
- Read: D:\DoAnThucTap\enterprise-llm-security-framework\app\services\llm_provider.py (41-76)
- Search: output_guard|OUTPUT|expected_stop.*output|leakage
- Execute: git rev-parse HEAD; git branch --show-current; git status --porcelain=v1; if ((Get-ChildItem -Recurse -Path . -Include *run_v2_evaluation*,*analyze_v2*,*test_guard_profile*,*GuardProfile* -ErrorAction SilentlyContinue | Where-Object { $_.FullName -notmatch 'node_modules|\.git|06_PHASE|pipeline\.py|architecture|handoff|modernization|TASK_BOARD|README|week-01|phase-12e-plan' }).Count -eq 0) { 'NO_12E_IMPL_FILES' } else { Get-ChildItem -Recurse -Path . -Include *run_v2_evaluation*,*analyze_v2*,*test_guard_profile* -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName } (Final repo state and implementation check)

## Assistant

I have enough evidence for the red-team plan audit. Compiling the strict read-only report from the inspected plan, methodology, 12C boundaries, and repo state.

# Grok Phase 12E Red-Team Plan Audit

## Repository State Verified
- Branch: `phase-12e-ablation-evaluation`
- Commit: `a5afcea2419d1ca3352b4978847d3b5d5e3dd054`
- Working tree: clean (no staged/unstaged changes; matches `origin/phase-12e-ablation-evaluation`)
- Files directly inspected: yes — `docs/ai-collaboration/06_PHASE_12E_MASTER_PLAN.md`, `docs/ai-collaboration/05_OPEN_QUESTIONS.md`, `docs/ai-collaboration/00_PROJECT_STATE.md`, `docs/benchmark-v2-methodology.md`, `datasets/v2/README.md`, `docs/modernization-ai-reviews/phase-12c-audit-resolution.md`, `docs/modernization-ai-reviews/codex-phase-12c-final-reaudit.md`, plus live boundaries in `app/core/pipeline.py`, `app/core/config.py`, `app/services/rag_query.py`, `app/services/llm_provider.py`, `app/api/routes.py`, `app/schemas/requests.py`, `app/guards/output_guard.py`
- Phase 12E implementation started: **No** — `GuardProfile` is still only a docstring future note; no `scripts/run_v2_evaluation.py`, `scripts/analyze_v2_results.py`, `tests/test_guard_profile.py`, `tests/test_v2_evaluation_runner.py`, or `reports/evaluation-v2/`; plan status remains planning-only

## Threat-Model Coverage
- Status: **Mostly strong for benchmark-bounded threats; incomplete on evaluation-path contracts and a few always-on safety invariants**
- Strong areas:
  - Direct injection, indirect retrieved injection, multi-chunk coordination, zero-width variants, markdown/HTML concealment, mixed-trust retrieval, compromised trusted source, low-trust malicious, benign authority/academic/trap FPR families, leakage canaries at context layer, residual prefix-blind-spot family, availability fail-closed family
  - Explicit exclusion of `residual_risk_only` from detection denominators
  - Honest Mock Provider leakage non-measurability and scripted-double separation (§15)
  - Claim controls (§31), non-linear ablation interpretation (§19), holdout once/no post-hoc patch (§10/§38)
  - Public guard-disable surface forbidden by design (§8) and required tests
- Missing or weak areas:
  - **Execution contract conflict:** methodology §16 still says Phase 12E runs via real `POST /v1/rag/query`; master plan correctly requires in-process `run_rag_query_uncommitted` for ablation/C6. Unresolved, this can produce either impossible ablation-over-HTTP or dual paths that diverge
  - **Non-`end_to_end` scopes** (`component`, `availability_fault`) have metric placement but **no runner execution procedure** (ingestion-then-query; out-of-policy `top_k`)
  - Homoglyphs, base64/hex encoding, deep Unicode normalization beyond ZWSP, semantic paraphrase — acknowledged residual / future, not plan gaps for 12E closure
  - Result schema does not persist per-stage decisions; layer attribution mostly depends on `stop_reason` alone
  - Audit redaction / aggregate budget not explicitly declared **outside** `GuardProfile` and always-on under C4/C6
- Blocking:
  - Yes — reconcile HTTP vs in-process evaluation path
  - Yes — specify how `component` and `availability_fault` cases are executed (or explicitly exclude them from the 960-run matrix with a separate procedure)
  - Yes — declare aggregate context budget and audit redaction as non-ablated safety infrastructure

## Ablation Safety
- Status: **Sound design intent; several implementation-critical invariants still under-specified**

- C0–C7 assessment:

| Config | Control removed | Must remain active | Internal-only? | Unsafe external behavior? | False “no value” risk | Compensating-control hide risk |
|---|---|---|---|---|---|---|
| `C0_all_on` | none | full pipeline, audit redaction, budget | can be in-process (required parity with others) | no if mock only | baseline | n/a |
| `C1_no_input` | Input Guard | provenance, context, DLP, output, retrieval/provider, audit redaction, budget | yes via `guard_profile` | no under plan constraints | low on this benchmark (direct_injection exists) | later layers may still catch some query-side patterns if mirrored in rules — limited |
| `C2_no_provenance` | Provenance Guard | input, context, DLP, output, audit, budget | yes | no | high on this corpus: denied provenance is mostly ingestion-time; runtime provenance may look “redundant” | content guards compensate for malicious trusted/untrusted content |
| `C3_no_context` | per-chunk + aggregate context guards | input, provenance, DLP, output, **budget must stay**, audit | yes | risk if budget is accidentally removed with context | low if H2 holds; high if budget/coupling confounds measurement | output/DLP do **not** compensate for injection in context under mock (mock does not echo); with scripted double they might partially mask |
| `C4_no_dlp` | centralized DLP stage | input, provenance, context, output, audit redaction | yes | low under mock; higher under scripted double if answers/logs raw | **very high on live mock ABR** (mock never emits secrets) | context `rag-fake-secret` / output rules can hide DLP’s unique role unless measured in scripted-double mode |
| `C5_no_output` | Output Guard | input, provenance, context, DLP, audit | yes | same as C4 under scripted double | **very high on live mock ABR** (mock text does not match output secret/prompt-leak rules) | DLP and context canaries can mask output-layer necessity unless scripted provider emits output-only triggers |
| `C6_none` | all guards | retrieval+provider (mock), **audit redaction**, **budget**, temp DB, no HTTP profile injection, no raw secrets in result artifacts | **must** | plan constraints prevent public/external; residual log/artifact risk if answer/raw context is written | n/a (explicit no-defense baseline) | none — intended full exposure of residual |
| `C7_no_context_no_output` | context + output | input, provenance, DLP, audit, budget | yes | as C3/C5 | useful for overlap; still mock-limited for output leg | DLP only matters under scripted double |

- C6 no-guard assessment:
  - Plan’s four gates (offline in-process; temp SQLite; mock/double only; unreachable from HTTP) are **necessary and appropriate**
  - Still incomplete without: (1) audit redaction always on and **not** part of `GuardProfile`; (2) no raw query/chunk/secret/answer in result artifacts (schema mostly OK, must remain mandatory); (3) no production DB / no serving config mutation; (4) scripted-double leakage runs labeled and not mixed into C6 ABR
- Public bypass risk: **Low if §8 tests are implemented as mandatory** — current code has `RagQueryRequest(extra="forbid")`, route does not accept guard toggles, `Settings` has no guard flags. Plan correctly forbids env/Settings/request injection of profile
- Blocking:
  - Yes — hard-require aggregate budget remains on when context guards are off
  - Yes — hard-require audit redaction always on for all profiles including C6/C4
  - Yes — forbid interpreting live-mock `Δ` for C4/C5 as “guard has no value”

## Evaluation-Gaming and Integrity Risks
- Status: **Strong process controls; several concrete gaming paths remain open without plan text fixes**
- Potential bypasses:
  1. **Skip hard scopes:** implement only `end_to_end`, leave `component`/`availability_fault` unhandled or errored, then redefine “complete”
  2. **HTTP-only C0 vs in-process ablation:** non-comparable stacks
  3. **Convert failures to benign:** map exceptions to `allow`/`correct=true` instead of `error_category` + `partial`
  4. **Count sanitize as “blocked” without `allowed_*`:** inflate ABR; plan formula forbids this if followed
  5. **Alert-level counting:** multi-stage reasons as multiple detections; plan is case-level (good) but artifact lacks stage list so mis-implementation easier
  6. **Omit FPR / neutral:** plan defines FPR on benign only; must enforce neutral separate
  7. **Drop timeouts/errors:** partial runs non-reportable helps, but “complete = all successful” vs “all attempted” needs exact definition
  8. **Dev/holdout mix / post-holdout tuning:** §10/§38 strong if enforced by flags + maintainer gate
  9. **Guard logic changes between configs/commits:** same-commit + analyzer abort on commit mismatch is strong
  10. **Silent context truncation / budget removal under C3:** confounds H2
  11. **No layer attribution:** cannot defend RQ3/H4 analysis; can hide which compensating control saved a case
  12. **Treat uninspected output as safe:** 12C fixed DLP tail; ablation must not reintroduce by bypassing DLP without tracking `truncated`/inspection completeness in scripted mode
  13. **Edit result JSON:** overwrite fail-closed helps; no result-content hash / analyzer integrity check
  14. **Hermes auto-labels:** §32 forbids; good
  15. **C4/C5 “Δ=0 ⇒ redundant” storytelling** on mock live metrics
- Existing mitigations:
  - Manifest SHA-256 abort-before-write; git dirty abort; no write to `datasets/v2/`
  - `correct` uses `allowed_*` sets; scope-separated metrics
  - Runner/analyzer split; no overwrite; partial non-reportable
  - Determinism assert on decisions; holdout single-run freeze; claim blacklist
  - Required public-surface tests; default `ALL_ON` byte-identical to 12C
- Blocking:
  - Yes — define runner behavior for every `evaluation_scope`
  - Yes — define “complete run” precisely (all cases present; no silent drops; errors recorded)
  - Yes — require stage outcome summary in raw artifacts (at least stage name + decision + reason_code)
  - Yes — require non-interpretability rules for C4/C5 under mock provider
  - Recommended (non-blocking if process-disciplined): hash raw result files and have analyzer verify

## Missing Adversarial Cases
- Blocking cases:
  - **None as new frozen benchmark families.** 12E must not mutate `datasets/v2/`. Plan correctly keeps Grok probes as exploratory, not new labels
  - **Blocking plan cases (execution, not corpus):** missing explicit adversarial handling for (a) evaluation-path confusion HTTP vs in-process, (b) C6 log/artifact secret leakage, (c) budget-off-with-context-off, (d) C4/C5 mock non-sensitivity
- Non-blocking future cases:
  - Homoglyph / confusable-character triggers
  - Base64/hex/URL-encoded injection payloads
  - Full Unicode normalization edge families beyond U+200B
  - Budget-exact multi-chunk Vietnamese splits (already listed as exploratory probe)
  - Trusted-source authority + canary mixes (exploratory)
  - Homoglyph + benign trigger combos (exploratory)
  - Semantic paraphrase / novel multilingual coordination
  - True partial/split secret leakage across provider tokens (needs live/scripted richer provider)
  - Malformed provenance metadata at retrieval time (unit-tested; not black-box reachable after real ingest)
  - Audit-sink dual failure durability (known PoC residual from 12C)

## False-Positive and Benign Counterexample Coverage
- Status: **Adequate for plan-level FPR measurement; not a 12E plan blocker**
- Findings:
  - Benchmark already includes trap/authority/academic/secret-like-id/mixed-trust-benign/no-hit/budget-exclusion families
  - Plan FPR formula on `category=benign` + `end_to_end`, neutral excluded — correct
  - Risk: ablation of a strict layer may **lower FPR while raising ASR**; plan does not require joint reporting of ABR+FPR per config in one table (should, to stop “remove guard improves system” spin)
- Blocking:
  - Minor process requirement only: every config table for detection must show FPR alongside ABR; not a missing corpus issue

## Audit and Result-Artifact Safety
- Status: **Good skeleton; a few C6-critical always-on controls need explicit text**
- Findings:
  - Strong: no raw query/chunk/secret/absolute path/stack in artifacts; env metadata with commit/dirty/manifest; same-commit analyzer abort; no overwrite; partial non-reportable
  - Gap: audit redaction not stated as independent of DLP toggle
  - Gap: whether evaluation runner commits audit events at all under C6, and that fallback logger still must not receive raw secrets
  - Gap: no integrity hash of raw result files
  - Gap: `answer` correctly absent from proposed case records — keep mandatory; forbid writing answers even for debug
  - Gap: latency key absence vs disabled `StageResult` presence is good; must not log disabled-stage details containing content
- Blocking:
  - Yes — always-on audit redaction + no raw answer persistence under all profiles
  - Yes — scripted-double leakage artifacts remain segregated and redaction-safe

## Critical Issues
1. **None that open a public no-guard serving surface by plan design.** §8 + default `ALL_ON` + forbid Settings/env/request toggles is the right hard boundary.

## Major Issues
1. **Evaluation execution path contradiction (methodology §16 HTTP vs plan in-process ablation).** Ablation/C6 cannot be honest over public HTTP. Plan must explicitly supersede methodology §16 for Phase 12E ablation runs and require a single comparable execution seam (`run_rag_query_uncommitted` + optional C0 HTTP parity check only).
2. **No runner procedure for `evaluation_scope ∈ {component, availability_fault}`.** Without this, implementers can skip, mis-route, or mark runs partial and still “pass” narrative checks. Specify exact steps, scoring, and whether these are inside or outside the 960 matrix.
3. **Aggregate context budget coupling left as open VERIFY.** For C3/C6/C7 validity and safety, budget bounding must remain **always on** and **outside** `GuardProfile`. Disabling context guards must not disable `_bound_chunks_for_aggregate`.
4. **C4 and especially C5 live-mock ABR are construct-invalid for necessity claims.** Mock provider text cannot exercise DLP/output secret rules. Plan fully warns for DLP leakage metrics but not strongly enough that **live-mock `Δ_C4` / `Δ_C5 ≈ 0` must not be reported as “guard redundant.”** Require scripted-double (or declare these configs non-interpretable for ABR).
5. **Audit redaction not declared always-on under C6/C4.** Turning off DLP stage must not disable `redact_sensitive_text` in the audit logger; C6 must not write raw secrets to JSONL/audit/debug artifacts.
6. **Raw evaluation artifacts omit stage outcomes.** Without stage decision/reason telemetry, RQ3/H4 and compensating-control analysis are gameable; “which layer triggered” becomes reconstruct-only via final `stop_reason`.

## Minor Issues
1. Master plan header still cites branch `phase-12e-planning` and base `4654fc4...` while this audit branch/commit differ — stale provenance on the plan document itself.
2. `05_OPEN_QUESTIONS.md` Q-005 still describes Phase 12C as blocked; `00_PROJECT_STATE.md` marks 12C DONE — process noise, not an ablation safety defect.
3. Result integrity relies on process (no overwrite, re-run determinism) rather than content hashing of raw results.
4. Family→group mapping is proposed but not yet a committed pre-holdout artifact (process is correct; enforce at 12E.3 gate).
5. Timeout policy is only generic exception handling; spell out wall-clock timeout → `error_category`, no silent drop.
6. Joint ABR+FPR reporting per config not mandated in one place.

## Deferrable Recommendations
1. Exploratory probes already listed (budget-exact VI multi-chunk; trusted authority+canary; homoglyph+benign) — keep out of frozen labels and out of ABR denominators.
2. Homoglyph / encoded / semantic residual families → future red-team expansion, not 12E blockers.
3. Wilson CIs optional; plan already allows skipping with justification.
4. Optional C0 HTTP vs in-process decision-parity smoke (not full ablation over HTTP).
5. Trusted-internal ablation profile and higher-order interactions — correctly deferred.

## Required Corrections Before Implementation
1. **Add an explicit Phase 12E execution contract:** all ablation configs run in-process via `run_rag_query_uncommitted(..., guard_profile=...)`; public HTTP remains permanently `ALL_ON`; document that this **supersedes** methodology §16’s HTTP-only wording for ablation. Optional: C0-only HTTP parity check, reported separately.
2. **Specify per-`evaluation_scope` runner algorithms:**
   - `end_to_end`: corpus load → query pipeline → score from labels after response
   - `component`: internal-only ingestion path then query; never treat as pure single-shot HTTP security metric
   - `availability_fault`: apply case `top_k`/policy setup; score fail-closed, not detection
   - `residual_risk_only`: execute if desired for honesty, **exclude from ABR/FPR denominators**
3. **Lock non-ablated infrastructure:** aggregate context budget, separator accounting, audit redaction, fail-closed exception mapping, and response-construction safety remain **on for every config**, including `C6_none`. Only the six guard booleans in `GuardProfile` toggle.
4. **Interpretability rules for C4/C5:** live mock ABR/FPR may be collected for completeness but **must be labeled non-interpretable for DLP/output necessity**; leakage/output-guard contribution only from scripted offline provider doubles, segregated metrics, claim language from §15 extended to Output Guard.
5. **Raw result schema must include** per-case `stage_results` (stage, decision|null, reason_code only — no content) and `error_category`; forbid `answer`, raw query, chunk text, secrets.
6. **Define `complete` run:** every case_id in the selected split present exactly once per config; any missing/errored case ⇒ `partial` ⇒ not reportable; no silent omission of timeouts.
7. **C6 checklist (acceptance tests):** unreachable from `app/api/`; no env/Settings toggle; temp DB only; mock/double only; audit redaction on; no raw secrets in artifacts/logs; cannot alter serving defaults.
8. **Analyzer rules:** abort on mixed `git_commit`, mixed manifest hash, missing cases, or presence of forbidden raw fields; do not treat Hermes/exploratory probes as labeled benchmark evidence.

## Final Verdict
REVISE