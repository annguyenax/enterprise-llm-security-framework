## Critical issues

**File:** `docs/modernization-v2-threat-model.md`
**Section:** Scope and Limitations
**Issue:** Any wording implying that the architecture provides absolute security or is "production-ready" violates academic constraints. Rule-based systems are inherently vulnerable to semantic obfuscation and zero-day paraphrasing.
**Correction:** Explicitly state that the framework is an academic proof-of-concept evaluated strictly on synthetic data. Add a disclaimer that the system does not guarantee "complete prompt-injection protection" or reflect "real-world detection rates."

**File:** `docs/decisions/ADR-003-v2-benchmark.md`
**Section:** Benchmark Methodology / V2 Split Strategy
**Issue:** While deferring the exact final scenario count is acceptable, failing to define a statistical minimum floor renders the holdout methodology unverifiable and scientifically weak.
**Correction:** Mandate a hard minimum floor of at least 100 cases (50 malicious / 50 benign) for the V2 benchmark to ensure FPR and TPR metrics carry statistical weight.

## Major issues

**File:** `docs/modernization-final-plan.md`
**Section:** Acceptance Criteria (Phase 12B–12E)
**Issue:** Criteria described using terms like "system successfully filters," "handles retrieval," or "reduces leakage" are circular and unverifiable.
**Correction:** Rewrite all Phase 12 acceptance criteria to be strictly measurable booleans or thresholds (e.g., "Phase 12B: FTS5 retrieval executes successfully in <100ms per query," "Phase 12E: Runner outputs a consolidated CSV mapping TPR/FPR to all 5 ablation states").

**File:** `docs/modernization-v2-architecture.md`
**Section:** Evaluation Metrics
**Issue:** Complex, domain-specific metrics such as `poisoned-hit-rate@k`, `clean-context retention`, `leakage rate`, and `benign over-redaction rate` are listed but lack explicit mathematical formulas, risking implementation bias during the evaluation phase.
**Correction:** Provide the exact mathematical equations (defining the Numerator and Denominator) for every listed metric to guarantee deterministic, reproducible calculation.

**File:** `docs/modernization-final-plan.md`
**Section:** Research Questions
**Issue:** The research questions cover ablation and latency well, but lack a measurable RQ establishing the baseline vulnerability necessary to prove the guardrails' marginal contribution.
**Correction:** Add a specific baseline RQ: "What is the baseline leakage rate and poisoned-context exposure of the unprotected FTS5 RAG pipeline when subjected to the V2 holdout benchmark?"

## Minor issues

**File:** `docs/decisions/ADR-002-retrieval-engine.md`
**Section:** Environment Support
**Issue:** Leaving the fallback behavior for unsupported SQLite FTS5 environments open risks silent pipeline degradation or invalid benchmark results during automated testing.
**Correction:** Specify a strict fail-fast mechanism (e.g., throwing a fatal `RuntimeError("SQLite FTS5 extension required")`) rather than attempting a custom or degraded fallback search.

**File:** `docs/decisions/ADR-003-v2-benchmark.md`
**Section:** Overfitting Controls
**Issue:** The mechanism to strictly enforce the separation of the calibration set (v1) and the holdout set (v2) relies on developer discipline rather than systemic controls.
**Correction:** Mandate that the evaluation runner script must validate the V2 dataset's integrity against a hardcoded SHA-256 manifest before executing the evaluation, aborting if the test set has been altered.

## Required corrections before Phase 12B

1. **Scrub Inappropriate Claims:** Remove all phrases implying "production readiness," "complete protection," or "independent real-world validation" across all five documents. Frame all outcomes around "synthetic benchmarking" and "academic prototype evaluation."
2. **Define Metric Formulas:** Update the architecture document to contain formal equations for all listed security and retrieval metrics to prevent ambiguous scoring.
3. **Lock the Calibration Set:** Explicitly document in `ADR-003-v2-benchmark.md` that the V1 40/40 benchmark is formally retired as a "historical calibration set" and is strictly prohibited from being merged into the V2 validation or holdout sets.
4. **Formalize Acceptance Criteria:** Replace all subjective adjectives in the Phase 12A-12E acceptance criteria with verifiable, threshold-based requirements.

## Decisions that may remain deferred

* **Exact V2 Benchmark Size:** It is academically acceptable to defer the final upper bound of test cases, provided the minimum statistical floor (e.g., 100 cases) is established now.
* **Exact V2 Folder/File Structure:** Deferring the specific JSON/YAML schema or folder naming until Phase 12D is acceptable.
* **Vector DB / Local LLMs / Semantic Guards:** Must remain strictly deferred. Do not invest engineering time into Phase 13+ until the deterministic SQLite FTS5 core, mock LLM pipeline, and evaluation runner are 100% complete and formally evaluated.

## Final verdict: REVISE