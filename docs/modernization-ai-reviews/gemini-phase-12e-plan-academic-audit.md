# Gemini Phase 12E Academic Plan Audit

## Repository Snapshot Inspected

* Bundle directly inspected: Yes.


* Branch from manifest: `phase-12e-ablation-evaluation`.


* Commit from manifest: `a5afcea2419d1ca3352b4978847d3b5d5e3dd054`.


* Exact commit independently verified: No.


* Verification limitations: Gemini is inspecting a maintainer-generated plain-text snapshot whose manifest identifies the branch and commit. Independent Git verification is performed separately by Code X and Grok.


* Relevant files inspected: `docs/ai-collaboration/06_PHASE_12E_MASTER_PLAN.md`, `docs/benchmark-v2-methodology.md`, `docs/decisions/ADR-003-v2-benchmark.md`, `app/core/pipeline.py`, `app/core/config.py`, `app/services/rag_query.py`, `app/schemas/requests.py`.



## Research-Question Alignment

* Status: PASS.
* Evidence: The plan defines 5 concrete Research Questions (RQs) targeting the attack block rate (RQ1), false positive rate (RQ2), necessity/redundancy of layers (RQ3), latency (RQ4), and residual risk (RQ5). Hypotheses (H1-H5) map cleanly to these RQs and the pipeline's capabilities.


* Blocking: No.

## Experimental Design

* Status: PASS with minor limitations.
* Ablation-matrix assessment: The choice of 8 configurations (`C0` to `C7`) is highly defensible. Removing all 2^5 (32) combinations is correctly avoided, as the small sample size per attack family cannot statistically support high-order interaction conclusions. The one-layer removal strategy (`C1` through `C5`) adequately measures marginal contribution ($\Delta_g$). `C7_no_context_no_output` specifically targets Hypothesis 4 regarding overlapping defenses.


* Control-condition assessment: `C0_all_on` provides a solid baseline for the fully protected system. `C6_none` is safely bounded by strict execution rules (in-process only, isolated SQLite DB, Mock Provider only) preventing exposure.


* Interaction-effect limitations: The plan appropriately notes that marginal contributions ($\Delta_g$) will not sum linearly to the total system effectiveness due to compensating controls (layers catching the same attack).


* Blocking: No.

## Metric and Statistical Validity

* Status: PASS.
* Metric concerns: `ABR` (Attack Block Rate), `ASR` (Attack Success Rate), and `FPR` (False Positive Rate) are operationally defined using a binary `correct` function. The plan mandates that ABR and FPR are reported jointly, preventing a trivial "block-everything" configuration from appearing optimal.


* Aggregation concerns: The plan explicitly forbids reporting percentages at the individual scenario family level (due to tiny 2-8 case samples per family in the holdout split). Reporting is strictly bound to macro aggregation or predefined broad groups (e.g., `direct_injection`).


* Sample-size concerns: The plan correctly acknowledges that 104 `end_to_end` cases (with only 60 total holdout cases) is insufficient for granular p-value claims or narrow confidence intervals.


* Blocking: No.

## Construct Validity

* Status: PASS.
* Findings: The plan successfully controls for construct validity risks by acknowledging that rule/lexical keyword matching does not equate to semantic understanding.


* Mock Provider limitations: The plan strictly boundaries leakage claims. Because the deterministic `MockLLMProvider` never echoes context, true generative leakage cannot be tested. The `C4_no_dlp` configuration is correctly identified as yielding `0` redactions natively. To counter this, the plan explicitly separates scripted provider-double results from the live pipeline metrics so leakage rates are not conflated with standard ABR.


* Blocking: No.

## Internal Validity

* Status: REVISE.
* Findings: Contamination controls are robust. The plan enforces a strict holdout blindness policy (run once, no tuning) and uses SHA-256 manifests to verify benchmark integrity before every run. Hermes-generated payloads are forbidden from automatically serving as ground truth.


* Execution-path concerns: The runner uses in-process execution (`run_rag_query_uncommitted`) rather than HTTP execution (`POST /v1/rag/query`) to inject the `GuardProfile`. This bypasses FastAPI's Pydantic schema validation (`RagQueryRequest` with `extra="forbid"`). Schema validation is a security layer that rejects malformed inputs and unauthorized fields. Testing via in-process objects slightly reduces internal validity because the API boundary is not evaluated.


* Compensating-control concerns: The plan handles missing/errored runs dangerously. Section 25 states that any exception marks the run as `partial`, and "Run `partial` KHÔNG được dùng để báo cáo" (Partial runs cannot be used for reporting). Discarding an entire configuration run because one case crashed allows failing cases to silently disappear from the analysis, skewing ABR/FPR metrics.


* Blocking: Yes.

## External Validity and Claim Boundaries

* Status: PASS.
* Findings: The master plan extensively restricts over-interpretation. It identifies the use of a synthetic corpus, deterministic guards, SQLite FTS5/BM25, and a mock provider as hard limitations.


* Prohibited claims: The plan explicitly forbids claims of "production readiness," "real-world prompt injection prevention," and "semantic understanding".


* Blocking: No.

## Benchmark and Contamination Controls

* Status: PASS.
* Findings: Separation of duties is handled well.
* Holdout controls: Holdout runs are governed by a strict "Rule of Freezing" requiring maintainer approval.


* Shared-authorship controls: The plan acknowledges the inherent risk of the guard authors also writing the benchmark, mitigating this via the independent holdout split and ensuring validation targets `allowed_*` arrays rather than single forced values.


* Blocking: No.

## Critical Academic Issues

None.

## Major Academic Issues

* Component: Internal Validity (Missing/Errored Case Handling)
* Evidence: Section 25 dictates that any exception during a run marks it as `partial` and "Run `partial` KHÔNG được dùng để báo cáo" (Partial runs cannot be used for reporting).


* Threat to validity: Discarding an entire evaluation run because a specific ablation configuration caused a crash on one case introduces severe survivorship bias. Availability faults or internal errors must be counted as failures to properly evaluate the robustness of the system.
* Required correction: Update Section 25 to specify that exceptions on individual cases must be logged as `internal_error` (or `availability_fault`) and scored as `incorrect` (False Negative or False Positive depending on category), allowing the overall matrix run to complete and be reported.
* Component: Internal Validity (Execution-Path Divergence)
* Evidence: Sections 5 and 8 define that the evaluation will use the in-process `run_rag_query_uncommitted(...)` rather than the public HTTP `POST /v1/rag/query`.


* Threat to validity: While necessary for injecting the ablation `GuardProfile`, bypassing the HTTP boundary removes the FastAPI/Pydantic `extra="forbid"` schema protection.


* Required correction: Explicitly list the bypass of HTTP schema validation as an experimental limitation in the final thesis, acknowledging that the ablation measures the pipeline logic but not the API perimeter defense.

## Minor Issues

* The plan mentions `aggregate_context_guard` latency tracking, but notes that aggregate sanitization must fail-closed due to mapping issues. The evaluation scripts must carefully ensure that a fail-closed aggregate operation doesn't artificially inflate ABR if the payload was actually safe.



## Deferrable Recommendations

* Evaluating interaction effects higher than order-1 (e.g., all combinations of 2^5) remains deferred. This is academically acceptable for this thesis scope.


* Integration of a real LLM provider and vector database to replace the mock provider and FTS5 engine is deferred.



## Required Corrections Before Implementation

1. Modify Section 25 of the Master Plan so that individual case crashes map to a tracked failure metric (e.g., `internal_error`) rather than invalidating the entire `partial` run.
2. Add an explicit limitation acknowledging that the in-process ablation runner bypasses the Pydantic API boundary defenses (`extra="forbid"`).

## Final Verdict

REVISE