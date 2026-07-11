# Evaluation Plan (Phase 2 continuation — "Phase 2.5")

> **Status: planning document only.** Describes how the MVP *will* be evaluated once it exists (Phase 3–7). No gateway, guard, or evaluation harness has been built yet — this document contains no results, only methodology. No code was written and no packages were installed to produce this document.

## 1. Purpose

Tie together the test design (`red-team-test-design.md`) and the metric definitions (`metrics-definition.md`) into a single methodology the team can follow in Phase 7, so evaluation isn't designed ad hoc under deadline pressure later.

## 2. What Is Being Evaluated

| Target | Test cases used | Metrics used |
|---|---|---|
| Input Guard | Prompt injection categories 1–7 (`red-team-test-design.md` §4) | ASR, Block Rate, FPR (against benign queries), FNR, Latency Overhead |
| RAG Guard | Clean documents RT-CLEAN-001…005 + poisoned documents RT-POISON-001…005 (`red-team-test-design.md` §2–3) | ASR, Block Rate, FPR (against clean docs), FNR, Latency Overhead |
| Output Guard | Any case where Input/RAG Guard is bypassed or a poisoned document reaches the LLM (backstop role, e.g. RT-POISON-003) | ASR, FNR, Latency Overhead |
| Logging subsystem | All of the above, every decision made during a run | Reason Logging Completeness |

## 3. Evaluation Approach

1. **Baseline run (guards disabled/bypassed):** Send the full test set through the gateway with all guards turned off, recording raw LLM behavior and response times. Establishes the "do nothing" reference point for both ASR (expected to be high without guards) and Latency (baseline for Latency Overhead).
2. **Guarded run (guards enabled):** Send the same test set through the gateway with all guards active, recording guard decisions (per the taxonomy in `red-team-test-design.md` §5), final outputs, and response times.
3. **Compare:** Compute all six metrics from `metrics-definition.md` for the guarded run, and compute the Latency Overhead delta against the baseline run.
4. **Per-category breakdown:** Report every metric broken down by test category (clean docs, each poisoned-document type, each prompt-injection type), not only as one blended number — per `metrics-definition.md` §8.

This baseline-vs-guarded structure is already anticipated in `TASK_BOARD.md` Phase 7 ("Baseline (no-guard) vs guarded comparison run"); this document specifies exactly what that comparison run should measure and how.

## 4. Execution Process (planned, Phase 7 — not implemented)

The following steps describe intended future automation; none of it exists yet:

1. A batch runner (planned under `scripts/`, per `scripts/README.md`) reads test cases from `redteam/` and `datasets/` (once those are materialized from the design in `red-team-test-design.md`).
2. Each test case is sent through the gateway (or bypassed for the baseline run).
3. The runner records: guard decision per stage, reason code, timestamp, request ID, final output, and elapsed time.
4. Results are compared against the expected-behavior mapping in `red-team-test-design.md` §5.1 to classify each case as a true positive, true negative, false positive, or false negative.
5. Aggregate metrics are computed per `metrics-definition.md` and written to an evaluation report (format TBD — likely a Markdown or JSONL summary under `docs/evaluation/` or a dedicated results directory, to be decided at Phase 7).

## 5. Roles

| Task | Owner |
|---|---|
| Batch runner implementation (Phase 7) | Both (per `TASK_BOARD.md` Phase 7: "Automated red-team runner against gateway") |
| Metrics collection + reporting scripts (Phase 7) | Le Dinh Nghia (per `TASK_BOARD.md`) |
| Baseline vs. guarded comparison run (Phase 7) | Nguyen Van An (per `TASK_BOARD.md`) |
| Maintaining this evaluation plan and the test design as guards evolve (Phase 4–6) | Both |

## 6. Constraints Carried Forward

- **Synthetic data only** — the evaluation run must never touch real PII, secrets, or production systems (`AGENT_RULES.md` rule 5).
- **No paid API call without approval** — if the chosen LLM provider is metered, running the full test set repeatedly during development must be pre-approved; prefer a dry-run/mock LLM response mode while iterating on guard logic, reserving real API calls for actual evaluation runs (`AGENT_RULES.md` rule 4).
- **No fabricated results** — every number that eventually appears in the report must come from an actual, reproducible run checked into the repo; this document itself contains zero results (`AGENT_RULES.md` rule 3).
- **Reproducibility** — the exact test-set version, gateway configuration, and LLM provider/model used for any reported run must be recorded alongside the results (`AGENT_RULES.md` rule 9, `metrics-definition.md` §8).

## 7. Explicitly Out of Scope for Evaluation (MVP)

- Load/stress testing or Denial-of-Service resilience — consistent with `docs/diagrams/threat-model.md`, DoS is an accepted MVP risk, not something the evaluation harness measures.
- Multi-turn/conversational attack evaluation — the test design (`red-team-test-design.md` §7) is single-turn only for the MVP.
- Real end-user usability testing — this is a security evaluation plan, not a UX study.
- Any evaluation requiring Kubernetes, SIEM, or a fine-tuned local model — consistent with `docs/diagrams/architecture.md` §5, these remain future thesis scope, not MVP evaluation scope.

## 8. Status

This is a **planning document**. No baseline run, no guarded run, and no metric values exist. The next concrete step is Phase 3 (Gateway Skeleton) before any of the process in §4 can actually execute.
