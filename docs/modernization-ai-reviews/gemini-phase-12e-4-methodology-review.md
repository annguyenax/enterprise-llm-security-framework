> **Review type:** Independent methodology and thesis-claims review.
> **Scope limitation:** This is not a technical implementation audit.
> **Authorization limitation:** This verdict does not authorize holdout.

---

# Gemini Phase 12E.4 Methodology and Claims Review

## Candidate Identity

* **Branch:** `phase-12e-4-holdout-planning`
* **Baseline:** `c0b8f6d6fb9fb5faa24f58610368fdc50ca41b62`
* **Phase 12E.3 implementation identity:** `c6d91c78e11009e96a76db08c0dfbb710504c227`

## L2 Latency Decision

* **Scientifically defensible:** Yes. Deriving latency metrics from two repetitions meant for determinism checks on a local workstation with uncontrolled background loads (e.g., local LLMs) yields pseudo-precision, not reliable scientific data.
* **Grounded reasons:** The rationale provided is methodologically sound. Reporting p50/p95 requires a dedicated, isolated protocol (e.g., warm-ups, statistically significant iterations, controlled environments) which is absent here.
* **Prevention of misuse:** By strictly defining `reportable=false` and enforcing `p50=null`, `p95=null`, the plan successfully blocks the presentation of diagnostic timings as scientific evidence.
* **Required removals/reclassifications:** Master plan RQ4 (latency evaluation) must be completely removed from the reportable metrics. Hypothesis H5 must be explicitly reclassified as a non-metric/descriptive expectation. Relevant claims in `docs/modernization-final-plan.md` must be marked superseded.

## Remaining Research Questions

* **Coherence:** After removing RQ4, the remaining RQs (RQ1: AOMR, RQ2: FPR, RQ3: Layer necessity, RQ5: Residual risk) form a complete, coherent, and tightly scoped academic security evaluation.
* **Framing:** The RQs and hypotheses are correctly framed as benchmark-specific observations rather than universal causal claims or production-security guarantees.
* **Generalization:** There is no remaining wording in the approved plan that overstates generalization. The evaluation measures rule-based exact-match behavior on synthetic data, and the RQs reflect this boundary.

## Holdout Methodology

* **Tuning prevention:** The one-shot authorization protocol and mandatory retention of partial/failed attempts mathematically prevent "survivorship bias" and post-hoc guard tuning. Developers cannot silently discard a bad run.
* **Schema updates:** Using a distinct holdout schema (e.g., `HOLDOUT_RESULT_SCHEMA_VERSION=1`) while preserving the dev/val schemas is methodologically optimal. It prevents accidental cross-contamination or unauthorized processing by previous pipeline tools.
* **Dev-only smoke:** Relying on development-only smoke testing is sufficient and academically required. Validation data has already been observed; executing it again for infrastructure checks risks implicit tuning.
* **Retry policy:** The `supersedes_authorization_sha256` mechanism preserves the scientific chain of custody, ensuring that legitimate infrastructure retries maintain a strict, auditable lineage back to the initial failure.

## Metric Policy

* **Verified:** The plan enforces the AOMR construct and explicitly prohibits ABR and "Attack Block Rate" terminology.
* **Verified:** FPR construct is preserved.
* **Verified:** Small-N suppression is maintained (`RATE_REPORTING_MIN_N = 10`), suppressing percentages and rates for inadequate sample sizes.
* **Verified:** Wilson 95% confidence intervals are restricted to eligible metrics, without continuity correction.
* **Verified:** Micro pooled reporting is utilized; all macro metrics are forbidden.
* **Verified:** Family reporting is strictly limited to raw counts (no percentages, no F1, no p-values).

## Mock Provider Limitations

* **Verified:** Explicit caveats are required for `C4_no_dlp` and `C5_no_output`. The plan mandates documenting that these configurations may exhibit zero delta because the deterministic Mock Provider does not echo context, making live-mock end-to-end exfiltration physically untestable.
* **Verified:** The plan correctly partitions any future scripted-provider-double evidence away from the main ablation matrix to prevent conflating mocked constraints with true DLP/Output Guard redundancy.
* **Verified:** Generalization to external providers is explicitly disallowed.

## Retry and Evidence Retention

* **External canonical authorization file:** Operates under a trusted-maintainer model to prevent accidental agent execution or unintentional commands. It provides a formal, non-code mechanism to gate holdout exposure.
* **Exact binding:** Tying the run to specific commit, config, provider, and contract hashes guarantees that the code and rules evaluated are the exact versions intended, ensuring reproducibility.
* **Atomic attempt-root claim:** Prevents race conditions and accidental directory overwrites, securing the integrity of the output workspace.
* **Retention of attempts:** Retaining fatal/partial attempts is a critical academic control against selectively reporting only favorable outcomes (cherry-picking).
* **Authorized retry:** Enforces transparency. If infrastructure fails, a retry requires a new explicitly authorized lineage (`supersedes`), ensuring the failure remains part of the scientific record.

## Required Documentation Changes

The following updates identified in the plan are approved and required:

* `docs/ai-collaboration/00_PROJECT_STATE.md`: Update 12E.3 to CLOSED PASS.
* `CLAUDE.md`: Update stale status to CLOSED PASS.
* `docs/ai-collaboration/06_PHASE_12E_MASTER_PLAN.md`: Remove RQ4; reclassify H5.
* `docs/modernization-final-plan.md`: Mark RQ4 as superseded by L2.
* `docs/ai-collaboration/01_AGENT_ROLES.md`: Update primary implementer to Claude Code; Code X to reconciler/auditor.
* `docs/ai-collaboration/04_DECISIONS.md`: Record L2 selection and trusted-maintainer threat model.
* `docs/ai-collaboration/05_OPEN_QUESTIONS.md`: Close Q-001; open retry policy question.

## Permitted Claims

* "On the synthetic v2 benchmark, configuration [C_X] achieved an Allowed Outcome Match Rate (AOMR) of [Y] (N=[Z])."
* "False Positive Rate (FPR) for the benign control group was measured at [X] (N=[Y]) within the constraints of the rule-based evaluation."
* "Ablating [Guard G] resulted in an AOMR difference of [Delta] on the paired end-to-end subset."
* "The Mock Provider deterministic environment yielded [X] redactions for configuration [C_Y]; this does not evaluate end-to-end exfiltration capability."

## Prohibited Claims

* **Real-world or production effectiveness:** "The system prevents X% of prompt injections in production."
* **Causal guard contribution:** "Guard G provides X% of the overall security."
* **Additive ablation deltas:** "The sum of the marginal deltas explains the total system protection."
* **Statistical significance:** "The difference between C0 and C1 is statistically significant (p < 0.05)."
* **Latency performance:** "The pipeline latency is X ms" or "The p95 latency overhead is Y ms."
* **Universal or provider-independent security claims:** "The guards will successfully protect a live LLM against data exfiltration."

## Critical Issues

None.

## Major Issues

None.

## Minor Issues

None. The plan is rigorous, academically honest, and perfectly scoped to the limitations of the PoC architecture.

## Required Corrections

None. (The pre-commit plan-hygiene amendments regarding `scripts/verify_phase.ps1` and `modernization-final-plan.md` in Exact Allowed Files are acknowledged and approved).

## Final Verdict

PASS
