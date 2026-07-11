# ADR-003: V2 Benchmark Structure, Splits, and Freezing Rules

- **Status:** Accepted
- **Date:** 2026-07-11
- **Deciders:** Nguyen Van An, Le Dinh Nghia (with Supervisor Nguyen Hoang Thanh)
- **Relationship to prior work:** Does not modify or supersede the v1 corpus
  (`datasets/clean/`, `datasets/poisoned/`, `redteam/prompts.jsonl`,
  `redteam/expected-behaviors.yaml`, `redteam/attack-categories.md`) or its
  freeze declared in `docs/dataset/dataset-methodology.md` §9. V1 remains a
  permanent, unmodified historical artifact.

## Context

`redteam/prompts.jsonl` (40 cases) was scored at 40/40 exact-decision-match
after Phase 7.1 calibration. `TASK_BOARD.md` §Phase 7.1 records, honestly,
that this result was reached by adding targeted rules in direct response to
observed failures on this same 40-case set. That is a legitimate calibration
process, but it means the 40/40 number cannot be presented as evidence of
generalization — it demonstrates that the rules were tuned to pass this
specific set, not that they would catch an unseen variant.

All three external reviews independently raise this exact concern
(`gemini-phase-12a-academic-gate.md` §6 "Rules Preventing Benchmark
Overfitting"; `grok-phase-12a-redteam-gate.md` §9 "Holdout Rules Preventing
Test Overfitting"; `codex-code-architecture-review.md` §7 "Ablation on the
current direct-guard benchmark would produce misleading contribution
claims"). A second, independently-governed benchmark is required before any
ablation or generalization claim can be made.

## Decision

Create a new, separately versioned **v2 benchmark** under a new folder
(target: `redteam/v2/`, finalized at Phase 12D implementation time), with
the following structure and rules. This ADR fixes the *rules*; Phase 12D
performs the actual authoring.

### Split structure

- **Development split** — may be referenced while authoring or tuning any
  detection rule or DLP pattern. Analogous in role to v1's existing 40
  cases (which effectively become part of the development history once v2
  exists).
- **Validation split** — used to check rule behavior during Phase 12B/12C
  implementation without being the final reported number.
- **Holdout split** — never referenced while authoring or tuning any rule,
  pattern, or detector. Used exactly once, at Phase 12E, to produce the
  headline evaluation numbers. If a holdout case is ever looked at to
  explain a failure and a rule is subsequently changed, that case (and
  ideally the whole holdout split) must be treated as contaminated and
  regenerated — this is a hard rule, not a guideline.

### Content rules (adopted from the three reviews, reconciled)

- **Approximately balanced benign and malicious scenarios** (per the
  approved direction), covering the category matrix in
  `docs/modernization-v2-threat-model.md` §4. Exact per-category counts are
  decided at Phase 12D authoring time, informed by that matrix — this ADR
  intentionally does not lock a specific total case count or exact
  percentage split in advance (see "Alternatives Considered" below for why
  Gemini's specific 100-case/50-50/named-subcounts proposal was not
  adopted verbatim).
- Malicious scenarios must include **obfuscated/synonym variants** of
  existing v1 attack patterns, not verbatim restatements — this is
  Gemini's "Rule of Variance," adopted because a benchmark that only
  restates v1 payloads would not actually test generalization at all.
- Malicious scenarios must include the v2-specific families named in
  `docs/modernization-v2-threat-model.md` §4, in particular **multi-chunk
  coordination** (an attack family that structurally cannot exist in v1,
  since v1 has no retrieval step).
- Benign scenarios must include **"trap" queries** that contain
  trigger-adjacent words or phrasing in an entirely legitimate context
  (e.g., a benign query that happens to contain the word "override" or
  "injection" in a non-attack sense) — needed to make the false-positive
  rate measurement meaningful rather than trivially zero.
- Both "clean content from a low-trust source" and "compromised content
  from a high-trust source" must be representable as distinct scenarios
  (required decision C), so trust and content-safety are measured as
  independent signals.
- Runtime code must never read v1's `is_poisoned` field or any v2
  equivalent ground-truth label — ground truth exists only for offline
  scoring by the evaluation runner, exactly as it already works for v1.

### Freezing and integrity rules

- Once Phase 12D authoring is complete, the v2 corpus is hashed (SHA-256
  per file, plus a manifest) and frozen, mirroring the pattern
  `tests/test_evaluation_runner.py` already enforces for v1.
- Once Phase 12E's evaluation run starts for the purpose of producing
  final-report numbers, **no further rule modification is permitted**,
  even if a specific case performs poorly — this is Gemini's "Rule of
  Freezing." A poor result is reported and analyzed, not quietly patched
  before the number is written down.
- v1's `latest-evaluation.{json,md}` and `baseline-vs-guarded.{json,md}`
  are never overwritten by v2 results. V2 produces new, separately named
  artifacts (`docs/modernization-v2-architecture.md` §7, Phase 12E). V1's
  40/40 remains visible in the final report as a labeled historical
  calibration-phase result, not silently replaced.

## Alternatives Considered

| Option | Why not adopted as-is |
|---|---|
| **Gemini's exact split** (>=100 cases; 50 malicious as 20 direct/20 indirect/10 jailbreak; 50 benign as 25 standard/25 trap) | Useful as a *reference design input* (recorded in `docs/modernization-v2-threat-model.md` §4) but not locked as a binding requirement in this ADR — fixing exact subcounts before Grok's threat-category content is actually authored risks designing scenarios to hit a quota rather than to genuinely cover the category matrix. The approved direction's own wording ("approximately balanced") is deliberately looser and is what this ADR follows. |
| **Grok's numeric acceptance thresholds** (ASR < 20%, FPR < 5%, provenance-block rate >= 80%, latency < 50ms) as pass/fail gates for the benchmark itself | Rejected as *acceptance criteria* per `AGENT_RULES.md` rule 3 and the reasoning in `docs/modernization-final-plan.md` §3 — preserved only as external interpretive reference points in `docs/modernization-v2-threat-model.md` §6, not as gates this ADR enforces. |
| **Extend v1's 40 cases in place** (add more cases to `redteam/prompts.jsonl` rather than create a new file) | Rejected outright — `docs/dataset/dataset-methodology.md` §9 already establishes that any content change to the frozen v1 corpus is a new corpus version, and the whole point of v2 is to be an *independently governed* set that the v1-tuned rules were never exposed to. Modifying v1 in place would destroy that independence. |
| **No holdout split (development/validation only)** | Rejected — without a holdout that is provably never used for rule tuning, the same calibration-not-generalization problem that affects v1 today would simply reappear one level up in v2. |

## Consequences

- Phase 12D is a documentation/data-authoring phase with no code changes,
  same as Phase 12A, and must itself follow the "development, then
  validation, then untouched holdout" discipline from the moment authoring
  begins.
- The final report gains a defensible "v1 was calibration, v2 is
  evaluation" narrative (directly requested by
  `gemini-phase-12a-academic-gate.md` §1's recommended contribution
  statement), instead of re-presenting the same 40/40 number as if it were
  a generalization result.
- Any future change to v2's frozen content after Phase 12D must itself be
  treated as a new corpus version (v3), following the same rule already
  established for v1 — this ADR's freezing rule applies recursively, not
  just once.
