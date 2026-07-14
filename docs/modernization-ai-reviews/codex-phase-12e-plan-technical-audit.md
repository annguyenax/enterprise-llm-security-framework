# Code X Phase 12E Plan Technical Audit

## Repository State Verified
- Branch: `phase-12e-ablation-evaluation`
- Commit: `a5afcea2419d1ca3352b4978847d3b5d5e3dd054`
- Working tree: Clean; `git status --short` and `git diff --name-only` returned no repository changes.
- Actual repository inspected: Yes; the requested commit, all authoritative documents, benchmark contracts, pipeline, routes, schemas, guards, services, settings, and relevant Phase 12C tests were inspected.
- Phase 12E implementation started: No. No `GuardProfile`, executable v2 runner, analyzer, Phase 12E configuration, result directory, or generated output exists.

## Technical Feasibility
- Status: REVISE
- Evidence: Existing retriever/provider injection points and typed pipeline telemetry make ablation feasible. However, the plan does not define the neutral/pass-through objects required when each guard is skipped. Current code subsequently depends on every guard result for effective text, severity, provenance summaries, audit data, and final output.
- Blocking: yes

## Ablation Configuration Design
- Status: REVISE
- Configuration assessment: The eight names and matrix are coherent. `C3_no_context` consistently disables per-chunk and aggregate inspection; `C7_no_context_no_output` is a defensible interaction profile. Exact disabled-stage dataflow remains ambiguous for all profiles.
- Public bypass risk: Low if the proposed function-only profile, `ALL_ON` default, forbidden request extras, and route regression tests are implemented exactly. No public bypass currently exists.
- Blocking: yes

## Metric and Telemetry Design
- Status: REVISE
- Formula issues: TP/FP/TN/FN, recall, precision, specificity, FNR, F1, sanitization rate, block rate, coverage, macro/micro aggregation, latency overhead, and zero-denominator behavior are undefined. `ABR=correct` and `ASR=1-ABR` measure joint decision/stop-reason agreement, not necessarily attack blocking/success. This is especially material for mixed cases whose secure final decision may be `allow`.
- Result-schema sufficiency: Insufficient. It omits run status, case attempt/error/skip status, safe per-stage results, leakage outcome, repetition completeness, configuration hash, provider-behavior identity, and artifact integrity fields.
- Blocking: yes

## Reproducibility and Integrity
- Status: REVISE
- Commit/config/manifest controls: Full commit capture, clean-tree enforcement, per-run FINAL-manifest verification, split separation, frozen-artifact protection, and mixed-commit rejection are correctly required. Run IDs, canonical configuration hashing, deterministic case order, scripted-provider identity, and post-write result hashes are missing.
- Incomplete-run handling: `partial` is named but absent from the proposed schema. Atomic writes, resume/retry semantics, idempotence, crash recovery, and holdout-partial-run adjudication are undefined. Fixed `<config>-<split>.json` names also collide across retries and provider modes.
- Blocking: yes

## Compatibility and Scope
- Status: REVISE
- Evidence: The plan preserves the Mock Provider limitation, avoids external LLMs and new dependencies, does not change frozen labels, and makes no unearned result claim. However, `end_to_end` is defined by the benchmark methodology as the HTTP workflow while the plan uses `run_rag_query_uncommitted`; `component` and `availability_fault` do not naturally return one `RagPipelineResult`. Corpus ingestion and internal-source handling are also unspecified.
- Blocking: yes

## Critical Issues
None.

## Major Issues
1. **Ablation pass-through and safety controls are underspecified.** The plan must define raw/effective query behavior, provenance acceptance, context forwarding, final-decision folding, and audit objects for every disabled stage. Aggregate bounds and a provider-output cap must remain always on; disabling DLP must not disable `dlp_max_inspect_chars` protection.
2. **Execution contracts do not cover the benchmark scopes.** The runner needs explicit workflows for `end_to_end`, `component`, `availability_fault`, and `residual_risk_only`, plus policy-correct corpus ingestion. Direct `upsert_documents` must not bypass source-policy behavior or index deliberately rejected documents.
3. **Metrics are incomplete and partly mislabeled.** Exact-label agreement must be separated from detection/blocking outcomes. Standard formulas, denominator rules, complete family counts, leakage eligibility, and provider-double semantics must be declared before holdout.
4. **Run lifecycle cannot yet prove reproducibility.** There is no experiment/run ID, canonical config hash, atomic artifact protocol, retry/resume policy, completed-case proof, output-integrity manifest, or safe way to distinguish Mock and scripted-provider runs.
5. **Audit/latency assumptions contradict the current call graph.** `run_rag_query_uncommitted` deliberately emits no terminal audit, and `latency_ms.total` ends before `commit_rag_query_audit`. The plan must either commit audit explicitly and measure an outer total, or state that audit latency is excluded.

## Minor Issues
- The master plan and audit template still name `phase-12e-planning` and an obsolete base commit; `05_OPEN_QUESTIONS.md` still describes the already-passed Phase 12C re-audit as pending.
- “960 pipeline runs” counts observations only. With five repetitions and ten warm-ups per configuration, actual executions are greater.
- Nearest-rank needs explicit `ceil(q*n)-1` implementation indexing and `n=0` behavior.
- Raw `pip freeze` may contain absolute local paths, conflicting with the artifact prohibition.

## Deferrable Recommendations
- Confidence intervals, all 32 guard combinations, and higher-order interactions may remain deferred.
- Grok’s exploratory probes may remain separate from frozen benchmark metrics.
- Semantic retrieval, real LLMs, and Phase 12F work are not Phase 12E blockers.

## Required Corrections Before Implementation
1. Specify canonical named profiles and exact pass-through/final-decision semantics for every disabled layer, while retaining validation, bounds, retrieval, audit, and failure controls.
2. Define policy-correct corpus loading and a separate executor/result contract for each `evaluation_scope`.
3. Replace the metric section with complete formulas, denominator behavior, exact-match versus security-success terminology, and a computable leakage protocol.
4. Expand artifacts with experiment/run IDs, canonical config/provider hashes, deterministic ordering, per-case/stage status, completeness evidence, atomic writes, retry rules, and a final result-integrity manifest.
5. Correct the audit-latency boundary and stale Phase 12C/branch documentation before G0 is reconsidered.

## Final Verdict
REVISE