# Phase 12E Plan Audit Adjudication and Resolution

**Status:** Planning correction completed; **G0 remains REVISE / pending independent re-audit**.
This document adjudicates the three reports committed at
`c35bc7dea422c413623ed3e45360e618cecc156c`. It does not approve implementation,
does not contain evaluation results, and does not authorize a holdout run.

## Audit inputs

- Code X: `codex-phase-12e-plan-technical-audit.md` — **REVISE**.
- Gemini: `gemini-phase-12e-plan-academic-audit.md` — **REVISE**.
- Grok: `grok-phase-12e-plan-red-team-audit.md` — **REVISE**.
- Audited plan commit: `a5afcea2419d1ca3352b4978847d3b5d5e3dd054`.
- Adjudication branch: `phase-12e-ablation-evaluation`.

All three auditors reported **no Critical finding**. Every Major, Minor, and
Deferrable item is accounted for below. Duplicate findings are grouped, but
attribution is preserved.

## Major findings

### M1. One comparable execution seam

- **Sources:** Code X Major 2; Gemini Major "Execution-Path Divergence";
  Grok Major 1.
- **Finding:** The benchmark methodology required HTTP execution while the
  ablation design required an internal profile that must never be public.
- **Disposition:** **Accepted.**
- **Rationale:** Mixing an HTTP C0 with in-process C1-C7 would confound the
  comparison; exposing profiles over HTTP would create a guard-bypass surface.
- **Affected sections:** Master Plan §§4, 8, 11a, 30; Methodology §§3, 6a, 16.
- **Exact resolution:** Every C0-C7 matrix observation uses
  `run_rag_query_uncommitted(..., guard_profile=...)` in-process. HTTP remains
  permanently `ALL_ON`. An optional C0 HTTP parity smoke is separate, non-metric
  evidence and cannot enter the matrix.
- **Implementation work later:** Yes — internal parameterization and parity tests.
- **Blocks G0:** Yes until re-audit confirms the corrected contract.

### M2. Per-scope execution and policy-correct corpus setup

- **Sources:** Code X Major 2; Grok Major 2.
- **Finding:** `component` and `availability_fault` lacked algorithms, and a
  direct storage upsert could bypass source-policy semantics or index documents
  intentionally marked for rejected ingestion.
- **Disposition:** **Accepted.**
- **Rationale:** A runner could otherwise skip difficult scopes or change the
  provenance behavior being evaluated.
- **Affected sections:** Master Plan §11a and §25.
- **Exact resolution:** The plan now defines separate algorithms for
  `end_to_end`, `component`, `availability_fault`, and `residual_risk_only`;
  only `end_to_end` enters ABR/FPR. Corpus setup must apply each document's
  declared `ingestion_mode`, server source policy, normal chunking, and
  transactional retrieval storage. Rejected-mode documents are never indexed.
- **Implementation work later:** Yes — scope dispatch and isolated corpus loader.
- **Blocks G0:** Yes until re-audit.

### M3. Disabled-stage data flow and non-ablated safety infrastructure

- **Sources:** Code X Major 1; Grok Majors 3 and 5.
- **Finding:** Guard booleans did not define pass-through values, and context
  budget/audit redaction could accidentally disappear with a guard.
- **Disposition:** **Accepted.**
- **Rationale:** An ablation must remove only the measured detector, not resource
  bounds, schema safety, error handling, audit redaction, or containment.
- **Affected sections:** Master Plan §§7, 7a, 8, 32.
- **Exact resolution:** Per-stage pass-through semantics are explicit. Aggregate
  size/separator accounting, bounded retrieval, bounded provider output, typed
  construction, fail-closed errors, audit redaction/fallback, temporary DB, and
  offline provider constraints are always on, including `C6_none`.
- **Implementation work later:** Yes — orchestration branches and safety tests.
- **Blocks G0:** Yes until re-audit.

### M4. C4/C5 construct validity

- **Sources:** Grok Major 4; Code X Major 3 (provider-mode metric sufficiency);
  Gemini's construct-validity PASS is retained as support for the existing
  provider-double separation.
- **Finding:** The deterministic Mock Provider cannot demonstrate DLP or Output
  Guard necessity, so a near-zero C4/C5 delta could be misreported as redundancy.
- **Disposition:** **Accepted.**
- **Rationale:** Mock output does not echo context and normally does not exercise
  output-only secret/prompt-leak rules.
- **Affected sections:** Master Plan §§15, 19, 20, 31.
- **Exact resolution:** Live-mock C4/C5 values are completeness observations only.
  Scripted-double leakage/output experiments use separate run identities,
  artifacts, denominators, tables, and claims; provider modes cannot be mixed.
- **Implementation work later:** Yes — approved deterministic provider doubles
  and analyzer segregation.
- **Blocks G0:** Yes until re-audit confirms the claim boundary.

### M5. Metric meaning and schema sufficiency

- **Sources:** Code X Major 3; Grok Major 6; Gemini rated the original ABR/FPR
  definitions PASS.
- **Finding:** Exact decision/stop-reason agreement was called attack blocking,
  while standard confusion metrics, denominator behavior, stage attribution,
  and leakage observables were incomplete.
- **Disposition:** **Partially accepted as a terminology correction and fully
  accepted as a schema/definition expansion.**
- **Rationale:** Gemini is correct that the frozen `allowed_*` outcome contract
  is a defensible primary benchmark score. Code X is also correct that it is not
  a generic detector confusion matrix, especially for mixed cases that safely
  end with `allow`.
- **Affected sections:** Master Plan §§12-15, 17-20, 23.
- **Exact resolution:** The primary measure is renamed **Allowed Outcome Match
  Rate (AOMR)**. ABR is retained only as a benchmark-specific alias with that
  caveat; `1-AOMR` is mismatch rate, not real-world ASR. TP/FP/TN/FN and derived
  formulas are defined as secondary case-level outcome classification metrics,
  with `null` on zero denominators. Safe stage summaries and leakage booleans
  make the declared metrics computable.
- **Implementation work later:** Yes — analyzer formulas and schema validation.
- **Blocks G0:** Yes until re-audit.

### M6. Case errors, partial runs, and survivorship bias

- **Sources:** Gemini Major "Missing/Errored Case Handling"; Code X Major 4;
  Grok evaluation-gaming finding and Minor 5.
- **Finding:** Discarding a partial run could hide hard cases, while using it for
  causal guard comparison could also produce invalid conclusions.
- **Disposition:** **Gemini's diagnosis accepted; its proposed use of errored
  cases in ordinary effectiveness denominators is partially accepted.**
- **Rationale:** Every error must remain visible and count in an explicitly
  error-adjusted robustness view, but an unexpected infrastructure error is not
  evidence of a guard's causal contribution.
- **Affected sections:** Master Plan §§23, 25, 26, 38.
- **Exact resolution:** Every case gets exactly one record; errors/timeouts set
  `correct=false`, carry an `error_category`, and remain in diagnostic
  error-adjusted counts. Safe continuation is allowed. Any unexpected case error
  makes the config `partial`; partial artifacts are retained and reportable only
  diagnostically, never used for primary AOMR/ABR/FPR/marginal conclusions. A
  complete rerun is required before final comparison.
- **Implementation work later:** Yes — timeout handling, completeness checks,
  and retry lineage.
- **Blocks G0:** Yes until re-audit.

### M7. Run lifecycle and artifact integrity

- **Sources:** Code X Major 4; Grok result-integrity and completion findings.
- **Finding:** Run/config identity, atomic writes, retry semantics, completed-case
  proof, provider identity, and post-write integrity were insufficient.
- **Disposition:** **Accepted.**
- **Rationale:** Fixed filenames and process-only discipline cannot distinguish
  retries/provider modes or prove an artifact was not edited.
- **Affected sections:** Master Plan §§21-26, 29, 37-38.
- **Exact resolution:** Canonical experiment/run/config/provider identities,
  sorted case order, atomic temp-file replacement, no overwrite, immutable retry
  lineage, complete/partial status, expected-case set hash, analyzer consistency
  gates, and a result-file SHA-256 manifest are required implementation gates.
- **Implementation work later:** Yes.
- **Blocks G0:** Yes until re-audit.

### M8. Audit and latency boundary

- **Sources:** Code X Major 5.
- **Finding:** `run_rag_query_uncommitted` emits no audit event, and its existing
  `latency_ms.total` ends before `commit_rag_query_audit`.
- **Disposition:** **Accepted.**
- **Rationale:** The old plan incorrectly described audit as part of the measured
  internal total.
- **Affected sections:** Master Plan §§16, 22-23.
- **Exact resolution:** Every matrix case attempts one safe audit commit after
  the uncommitted result. Existing pipeline `total` is explicitly pre-audit;
  an outer `end_to_end_with_audit` timer separately measures orchestration plus
  audit. Both are labeled and never conflated.
- **Implementation work later:** Yes — outer timing and audit-path tests.
- **Blocks G0:** Yes until re-audit.

## Minor findings

### N1. Stale planning state

- **Sources:** Code X Minor 1; Grok Minors 1-2.
- **Finding:** The plan named a stale branch/base, Open Questions still treated
  the completed Phase 12C re-audit as pending, and project status did not show
  the current Phase 12E planning gate.
- **Disposition:** **Accepted.**
- **Rationale:** Gate documentation must describe the repository actually under
  review and must not leave a closed predecessor phase as a false blocker.
- **Exact resolution:** Correct branch/base provenance, close stale Phase 12C Q-005,
  and mark G0 as REVISE/pending re-audit in the plan and project state.
- **Affected sections:** Master Plan header; Open Questions Q-001/Q-005;
  Project State Phase 12E row.
- **Implementation work later:** No. **Blocks G0:** No after correction.

### N2. Observation and execution counts

- **Source:** Code X Minor 2.
- **Finding:** The former "960 pipeline runs" wording conflated case/config
  observations with warm-ups and repeated timed executions.
- **Disposition:** **Accepted.**
- **Rationale:** Reproducibility requires separate counts for observations and
  actual executions.
- **Exact resolution:** The former `960` wording is removed. The primary matrix is
  explicitly `104 end_to_end cases × 8 configurations = 832 observations`, not
  the number of timed executions; repetitions, warm-ups, and out-of-matrix
  scopes are counted separately.
- **Affected section:** Master Plan §§4, 6, 16. **Implementation later:** Yes.
  **Blocks G0:** No.

### N3. Percentile edge behavior

- **Source:** Code X Minor 3.
- **Finding:** Nearest-rank indexing and empty-sample behavior were not explicit.
- **Disposition:** **Accepted.**
- **Rationale:** Different percentile conventions can otherwise produce
  irreproducible p50/p95 values, especially for small groups.
- **Exact resolution:** Nearest-rank uses zero-based index `ceil(q*n)-1`; `n=0` yields
  `null` plus an explicit zero sample count.
- **Affected section:** Master Plan §18. **Implementation later:** Yes.
  **Blocks G0:** No.

### N4. Dependency snapshot path safety

- **Source:** Code X Minor 4.
- **Finding:** Raw `pip freeze` output may expose absolute local paths.
- **Disposition:** **Accepted.**
- **Rationale:** Environment identity is needed, but machine paths are forbidden
  artifact content and reduce portability.
- **Exact resolution:** Store a sorted package/version inventory and its hash; reject
  or sanitize editable/direct-reference entries containing absolute paths.
- **Affected section:** Master Plan §22. **Implementation later:** Yes.
  **Blocks G0:** No.

### N5. Aggregate fail-closed interpretation

- **Source:** Gemini Minor 1.
- **Finding:** An aggregate fail-closed result could be credited as successful
  attack blocking without showing whether it also blocks safe inputs.
- **Disposition:** **Accepted.**
- **Rationale:** The frozen allowed-outcome contract and adjacent FPR reporting
  must distinguish a correct defense from indiscriminate fail-closed behavior.
- **Exact resolution:** Aggregate fail-closed outcomes remain visible in stage telemetry
  and must match the frozen allowed outcome; a safe-case block cannot silently
  inflate a malicious-case score or disappear from FPR.
- **Affected sections:** Master Plan §§12, 17, 20. **Implementation later:** Yes.
  **Blocks G0:** No.

### N6. Result hashing, group mapping, timeout, and joint reporting

- **Sources:** Grok Minors 3-6.
- **Finding:** Result files lacked a committed integrity hash; grouped-family
  mapping and timeout behavior were not locked; ABR and FPR were not required
  in the same comparison table.
- **Disposition:** **Accepted.**
- **Rationale:** These omissions permit post-run edits, selective grouping,
  silent case loss, or one-sided reporting without changing benchmark inputs.
- **Exact resolution:** Result hashing is a required implementation gate; family-group
  mapping is committed before holdout; timeout is a recorded case error; every
  config table places AOMR/ABR and FPR together.
- **Affected sections:** Master Plan §§20, 23-25, 34, 37. **Implementation later:**
  Yes. **Blocks G0:** No after documentation correction.

## Deferrable findings

### D1. Confidence intervals

- **Sources:** Code X; Grok; Open Question Q-002.
- **Finding:** Confidence intervals could improve uncertainty reporting for
  grouped rates on a small holdout.
- **Disposition:** **Deferred.** Wilson intervals may be omitted with a written
  small-sample rationale. No p-value or significance claim is allowed.
- **Rationale:** They improve presentation but are not required to make the
  predefined deterministic case-level metrics valid or reproducible.
- **Exact resolution:** The plan records CI as optional and requires explicit
  small-sample caveats when omitted.
- **Affected sections:** Master Plan §§27, 39. **Implementation later:** Optional.
  **Blocks G0:** No.

### D2. Higher-order and trusted-internal profiles

- **Sources:** Code X; Gemini; Grok.
- **Finding:** The eight profiles do not estimate all higher-order guard
  interactions and omit a separate trusted-internal ablation profile.
- **Disposition:** **Deferred.** The eight named configurations remain fixed;
  32 combinations and a trusted-internal profile require a future design.
- **Rationale:** The frozen sample is too small for defensible high-order claims,
  and neither extension is necessary for the declared main-effect questions.
- **Exact resolution:** Keep C0-C7 fixed and prohibit extrapolating high-order
  interactions or trusted-internal behavior from them.
- **Affected section:** Master Plan §39. **Implementation later:** No for 12E.
  **Blocks G0:** No.

### D3. Exploratory and semantic attack expansion

- **Sources:** Code X; Grok.
- **Finding:** Budget-edge Vietnamese splits, authority/canary mixes, homoglyphs,
  encoded payloads, and semantic variants would broaden red-team coverage.
- **Disposition:** **Deferred.** Budget-exact Vietnamese, authority/canary, and
  homoglyph/benign probes may run only as separately labeled exploratory work.
  Encoded, semantic, and broader Unicode families remain future benchmark work.
- **Rationale:** Adding them to the FINAL frozen benchmark would violate Phase
  12D integrity; separate exploratory probes cannot become labeled evidence.
- **Exact resolution:** Preserve the nine artifacts and keep any approved probe
  outside benchmark denominators, manifests, and primary reports.
- **Affected sections:** Master Plan §§32, 39. **Implementation later:** Optional.
  **Blocks G0:** No.

### D4. Real LLM, vector retrieval, and Phase 12F work

- **Sources:** Code X; Gemini; Grok.
- **Finding:** Real-provider and semantic/vector retrieval experiments would
  improve external validity.
- **Disposition:** **Deferred / out of scope.** No paid/external provider or new
  retrieval engine is required for Phase 12E.
- **Rationale:** Phase 12E evaluates the frozen offline Mock/FTS5 system; adding
  these dependencies would change the evaluated construct and project phase.
- **Exact resolution:** Keep provider and retrieval limitations explicit and
  make no real-world or real-LLM generalization claim.
- **Affected section:** Master Plan §§30, 39. **Implementation later:** No for 12E.
  **Blocks G0:** No.

### D5. C0 HTTP parity smoke

- **Source:** Grok.
- **Finding:** A C0-only HTTP-versus-in-process parity smoke could provide
  additional compatibility evidence without exposing ablation profiles.
- **Disposition:** **Accepted as optional, non-gating evidence.** It may compare
  C0 decisions only, must use `ALL_ON`, and must remain outside every ablation
  metric and latency table.
- **Rationale:** It is useful perimeter-parity evidence, but making it part of
  the matrix would reintroduce execution-path confounding.
- **Exact resolution:** Permit only a separately identified C0 decision/stop-
  reason parity smoke with no profile input and no matrix aggregation.
- **Affected sections:** Master Plan §§8, 11a. **Implementation later:** Optional.
  **Blocks G0:** No.

## Rejected findings

No auditor finding is fully rejected. The only rejected remedy component is
Gemini's proposal to use a partial run with unexpected infrastructure errors
for the primary causal/effectiveness matrix. The diagnosis of survivorship risk
is accepted, but infrastructure failure is not evidence of a guard's causal
effect. Such errors remain visible and count in diagnostic error-adjusted
robustness reporting; a complete rerun is required for primary comparison.

## Current gate decision

- All required planning corrections have been written for independent review.
- No application, test, script, benchmark, runtime configuration, or result
  artifact was changed by this adjudication.
- **G0 remains REVISE / pending Code X, Gemini, and Grok re-audit.** This
  adjudication does not mark the plan PASS and does not authorize Phase 12E.1.
