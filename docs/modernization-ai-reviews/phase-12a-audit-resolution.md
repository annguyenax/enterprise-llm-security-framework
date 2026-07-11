# Phase 12A Audit Resolution

> Traceable record of how the two Phase 12A audits
> (`gemini-phase-12a-audit.md`, `grok-phase-12a-audit.md`) were evaluated
> and resolved against the Phase 12A planning documents committed at
> `a814a14`. This is a documentation-only correction pass — no file under
> `app/`, `tests/`, `scripts/`, `datasets/`, `redteam/`,
> `reports/evaluation/`, `report-latex-template/`, or `requirements.txt`
> was modified to produce this record. Phase 12B implementation has not
> begun.

## Audit verdicts

- **Gemini:** REVISE
- **Grok:** REVISE (with an explicit "strong foundation overall — proceed
  after fixes" framing; not a rejection of the direction, a request for
  specific strengthening before implementation starts)

Neither audit disputes the approved direction itself (SQLite FTS5/BM25
first, server-controlled provenance, centralized DLP, v2 benchmark with
holdout, vector/local-LLM/dashboard deferred). Both ask for the *documents*
to be more precise, measurable, and airtight before Phase 12B implementation
starts. No audit recommendation was accepted automatically — each was
evaluated against `AGENT_RULES.md`, undergraduate thesis scope,
reproducibility, offline-first requirements, scope-creep risk, and whether
it is measurable/testable, per this task's own instructions.

## Resolved Critical findings

### Gemini — Critical 1: overclaiming-language disclaimer

- **Reviewer:** Gemini
- **Finding:** Any wording implying absolute security or production
  readiness violates academic constraints; requested an explicit disclaimer
  in `docs/modernization-v2-threat-model.md`.
- **Accepted / Partially accepted / Rejected:** Accepted.
- **Files and sections changed:** `docs/modernization-v2-threat-model.md`
  §0 (new "Scope and Limitations" section, inserted before §1).
- **Correction:** Added an explicit disclaimer stating this is a lab-scale
  academic proof-of-concept evaluated only on synthetic data, with no claim
  of complete protection, production readiness, or generalization beyond
  the tested benchmark.
- **Rationale:** A targeted grep across all five Phase 12A documents found
  no actual overclaiming language (see resolution process notes below) —
  every existing mention of "solved"/"complete" appears inside an explicit
  *non-claim* ("not solved," "no claim of production readiness"). The
  finding is still accepted because an explicit, prominent disclaimer is
  cheap, strictly clarifying, and directly requested — consistent with
  `AGENT_RULES.md` rule 8.

### Gemini — Critical 2: benchmark statistical floor

- **Reviewer:** Gemini
- **Finding:** Deferring the exact v2 case count is acceptable, but no
  minimum floor renders FPR/TPR statistically weak; requested a hard
  minimum of >=100 cases (50/50).
- **Accepted / Partially accepted / Rejected:** Partially accepted.
- **Files and sections changed:** `docs/decisions/ADR-003-v2-benchmark.md`
  ("Split structure" and "Content rules" sections),
  `docs/modernization-final-plan.md` §4.E.
- **Correction:** Adopted a **minimum floor of at least 100 cases total**,
  approximately balanced. Did **not** adopt Gemini's exact named subcounts
  (20/20/10 malicious, 25/25 benign) as a locked requirement.
- **Rationale:** A minimum floor is a structural/design constraint, not an
  outcome claim — it does not create the fabrication-adjacent pressure
  `AGENT_RULES.md` rule 3 warns against, so it was accepted. Locking exact
  per-category subcounts before Grok's threat-category matrix is actually
  authored at Phase 12D was already rejected once, in Phase 12A itself, for
  a documented reason (risk of designing scenarios to hit a quota rather
  than to cover real cases) — that reasoning still applies and was
  preserved.

### Grok — Critical 1: FTS5 query escaping detail

- **Reviewer:** Grok
- **Finding:** ADR-002 mentions "safe" FTS5 parameterization but lacks
  explicit tokenization/escaping detail for `MATCH` operators; requested
  explicit requirements plus abuse test cases.
- **Accepted / Partially accepted / Rejected:** Accepted.
- **Files and sections changed:** `docs/decisions/ADR-002-retrieval-engine.md`
  (Decision section), `docs/modernization-v2-architecture.md` §7 Phase 12B
  (Tests).
- **Correction:** Specified the concrete approach — treat all user query
  text as a bag of plain terms, strip/escape a named list of FTS5 special
  characters and operators (`"`, `*`, `:`, `-`, `^`, parentheses, `NEAR`,
  column-filter syntax, standalone `AND`/`OR`/`NOT`) before constructing
  the `MATCH` argument. Added a matching required-test bullet for Phase 12B.
- **Rationale:** Directly measurable and testable, does not expand scope
  (it is a specification detail for work already approved), and closes a
  real gap the original ADR-002 wording left implicit.

### Grok — Critical 2: multi-chunk coordination has no mitigation plan

- **Reviewer:** Grok
- **Finding:** The threat model acknowledges multi-chunk coordination as a
  high residual risk but offers no mitigation beyond documentation;
  requested a mandatory per-ingestion/pre-retrieval cross-chunk
  co-occurrence heuristic in Phase 12C's acceptance criteria.
- **Accepted / Partially accepted / Rejected:** Partially accepted.
- **Files and sections changed:** `docs/modernization-v2-threat-model.md`
  §3 (Tampering row on multi-chunk coordination),
  `docs/modernization-v2-architecture.md` §7 Phase 12C (Acceptance
  criteria).
- **Correction:** Did **not** mandate that Phase 12C implement a working
  cross-chunk heuristic as a hard, blocking requirement — full resolution
  of cross-chunk reasoning remains out of scope for 12B-12E, consistent
  with the original Phase 12A plan. Instead, Phase 12C's acceptance
  criteria now require an **explicit decision and documented rationale**:
  either implement a lightweight, deterministic, best-effort co-occurrence
  check (with a named test if implemented) or explicitly document why it
  was deferred. Silently omitting this decision now fails the phase.
- **Rationale:** Mandating a specific new engineering deliverable
  (a working heuristic) inside a documentation-only audit-resolution task
  would itself be a form of scope creep — committing a future implementation
  phase to new work without that phase's own explicit go-ahead, which
  `AGENT_RULES.md` rule 1 cautions against. Converting "silently documented
  as unsolved" into "must be explicitly decided and justified" addresses
  Grok's real concern (don't just shrug and move on) without pre-committing
  Phase 12C's engineering scope from a docs-only phase.

### Grok — Critical 3: FTS5 fail-fast wording not absolute enough

- **Reviewer:** Grok
- **Finding:** The FTS5 capability check requirement did not fully
  eliminate silent-fallback risk in prose; requested "must fail hard at
  startup if FTS5 unavailable; no runtime fallback allowed anywhere."
- **Accepted / Partially accepted / Rejected:** Accepted.
- **Files and sections changed:** `docs/modernization-final-plan.md` §4.A,
  `docs/decisions/ADR-002-retrieval-engine.md` (Decision section),
  `docs/modernization-v2-architecture.md` §7 Phase 12B (Acceptance
  criteria).
- **Correction:** Rewrote the requirement in all three documents to state,
  verbatim in spirit, that there is no fallback of any kind (no `LIKE`, no
  degraded scan, no other scoring method), whether detected at startup or
  at any later runtime check, and that the system must serve zero
  retrieval-dependent requests if FTS5 is unavailable.
- **Rationale:** This directly matches the user's own explicit approved
  decision list ("If FTS5 is unavailable, fail with a clear capability
  error. Do not silently fall back to LIKE or another scoring method.") —
  the audit correctly caught that the original prose was softer than the
  already-approved requirement. High-priority accept.

## Resolved Major findings

### Gemini — Major 1: unverifiable acceptance criteria wording

- **Reviewer:** Gemini
- **Finding:** Phrases like "successfully filters," "handles retrieval," or
  "reduces leakage" are circular and unverifiable; requested rewriting as
  measurable booleans/thresholds.
- **Accepted / Partially accepted / Rejected:** Partially accepted.
- **Files and sections changed:** `docs/modernization-v2-architecture.md`
  §7 Phase 12B and 12C (Acceptance criteria).
- **Correction:** Reworded Phase 12B and 12C acceptance criteria into
  explicit, checkable pass/fail conditions (e.g., "the returned rank order
  is identical across repeated runs," "every existing test in the current
  suite (82 tests) passes unmodified").
- **Rationale:** Accepted the *spirit* (verifiable, boolean-style criteria)
  but not Gemini's own example numeric target ("<100ms per query") as a
  literal gate — inventing a latency threshold before any measurement
  exists would repeat the exact fabrication-adjacent pattern rejected
  elsewhere in this plan (`AGENT_RULES.md` rule 3). The correction improves
  verifiability without adding an invented number.

### Gemini — Major 2: missing metric formulas

- **Reviewer:** Gemini
- **Finding:** Metrics like `poisoned-hit-rate@k`, `clean-context
  retention`, `leakage rate`, and `benign over-redaction rate` are named
  but not mathematically defined, risking implementation-time bias.
- **Accepted / Partially accepted / Rejected:** Accepted.
- **Files and sections changed:** `docs/modernization-v2-architecture.md`
  (new §8, "Metric Definitions (Formulas)"),
  `docs/modernization-final-plan.md` §4.F (cross-reference added).
- **Correction:** Added explicit numerator/denominator definitions for
  every metric listed in the final plan: TPR, FPR, FNR, precision, F1,
  Recall@k, poisoned-hit-rate@k, poisoned-context exposure, clean-context
  retention, leakage rate, redaction recall, benign over-redaction, p50/p95
  latency, per-layer marginal contribution, and unique catches.
- **Rationale:** Purely definitional, invents no result, directly improves
  reproducibility — exactly the kind of correction this task's own
  instructions list as acceptable ("clarify metric definitions").

### Gemini — Major 3: no baseline research question

- **Reviewer:** Gemini
- **Finding:** Research questions cover ablation/latency but lack a
  measurable RQ establishing baseline vulnerability, needed to prove the
  guardrails' marginal contribution.
- **Accepted / Partially accepted / Rejected:** Accepted.
- **Files and sections changed:** `docs/modernization-final-plan.md` (new
  §1a, "Research Questions").
- **Correction:** Added a Research Questions section consolidating
  `gemini-phase-12a-academic-gate.md`'s original RQ1-RQ4 plus a new RQ5
  ("What is the baseline leakage rate and poisoned-context exposure of the
  `no_guards` profile against the v2 holdout?").
- **Rationale:** `docs/modernization-final-plan.md` did not previously
  restate research questions at all; adding them costs nothing in scope and
  gives Phase 12E's evaluation an explicit target to answer.

### Gemini — "Required corrections before Phase 12B" item 3: lock the calibration set

- **Reviewer:** Gemini
- **Finding:** `ADR-003-v2-benchmark.md` must explicitly state that v1's
  40/40 is formally retired as a historical calibration set and is
  strictly prohibited from being merged into v2 validation or holdout.
- **Accepted / Partially accepted / Rejected:** Accepted.
- **Files and sections changed:** `docs/decisions/ADR-003-v2-benchmark.md`
  (Content rules), `docs/modernization-final-plan.md` §4.E.
- **Correction:** Added explicit prohibition language: v1 content may only
  ever appear in v2's development split, never validation or holdout.
- **Rationale:** Closes a real gap — the original ADR-003 said v1 "remains
  a permanent historical artifact" but did not explicitly forbid reuse in
  v2's validation/holdout, which is the actual overfitting risk.

### Grok — Major 1: provenance decisions lack audit logging

- **Reviewer:** Grok
- **Finding:** Server-controlled trust derivation is planned but lacks
  auditability details for assignment decisions; requested structured
  logging of source-policy mapping on every ingest.
- **Accepted / Partially accepted / Rejected:** Accepted.
- **Files and sections changed:** `docs/modernization-v2-architecture.md`
  §4 (Trust and Provenance Model).
- **Correction:** Added an explicit requirement that every ingestion's
  source-to-`trust_level` decision be recorded in the structured audit log,
  cross-referencing the Repudiation row already present in
  `docs/modernization-v2-threat-model.md` §3.
- **Rationale:** The mitigation already existed in the threat model; this
  restates it as a concrete architecture-document requirement so Phase 12B/
  12C implementers see it as a design obligation, not only a threat-model
  observation.

### Grok — Major 2: holdout independence not enforced

- **Reviewer:** Grok
- **Finding:** Holdout rules are strong but lack explicit prevention of
  indirect leakage (dev-set authoring habits shaping holdout design);
  requested a separate-author-or-time-gap rule.
- **Accepted / Partially accepted / Rejected:** Accepted (adapted for team
  size).
- **Files and sections changed:** `docs/decisions/ADR-003-v2-benchmark.md`
  (Split structure — Holdout split).
- **Correction:** Added a requirement that holdout authoring satisfy at
  least one of: different named author than the corresponding dev/
  validation scenarios, a documented time gap, or an independent review
  pass before freeze — with the satisfied condition recorded in Phase 12D
  evidence.
- **Rationale:** A strict "must be a different team member" rule is harder
  to guarantee reliably on a 2-person team for every category; offering
  three equally acceptable independence mechanisms keeps the safeguard
  meaningful and realistic without inventing a staffing requirement the
  team cannot actually satisfy.

### Grok — Major 3: DLP centralization lacks named regression test

- **Reviewer:** Grok
- **Finding:** Centralization risk is noted in the threat model, but no
  regression-testing mandate across all call sites is specified; requested
  pre/post-consolidation redaction parity tests on the full fixture set as
  a named Phase 12C criterion.
- **Accepted / Partially accepted / Rejected:** Accepted (already
  substantially covered; strengthened for precision).
- **Files and sections changed:** `docs/modernization-v2-architecture.md`
  §7 Phase 12C (Tests).
- **Correction:** Replaced the general test bullet with a named
  requirement: a regression suite that runs the centralized DLP module
  against every existing secret/PII fixture from all three current call
  sites (`rag_guard.py`, `output_guard.py`, `audit_logger.py`) and asserts
  byte-identical redaction output before and after consolidation.
- **Rationale:** The original Phase 12C acceptance criteria already implied
  this ("centralized DLP produces identical redaction behavior... on
  existing fixtures"); the correction makes it an explicitly named,
  unambiguous test requirement rather than a general statement.

## Minor findings

**Fixed now:**

- Gemini Minor — ADR-002 fail-fast mechanism should be a specific
  `RuntimeError`, not an open-ended "clear error." Fixed:
  `docs/decisions/ADR-002-retrieval-engine.md` now names the exception
  pattern explicitly (folded into the same edit as Grok Critical 3).
- Gemini Minor — holdout/dev separation should be checked by the evaluation
  runner itself (SHA-256 manifest verification at run start), not only by a
  separate pytest check. Fixed: `docs/decisions/ADR-003-v2-benchmark.md`
  (Freezing and integrity rules).
- Grok "likely bypass" — encoding-based obfuscation (zero-width/base64) was
  missing from the required indirect-injection variant families. Fixed:
  `docs/modernization-v2-threat-model.md` §4, added as variant family 6,
  cross-referencing existing `ZERO_WIDTH_PATTERN` prior art in
  `app/guards/rag_guard.py`.
- Grok "missing benign counterexample" — no benign *query*-form example
  (only document-form examples) existed to test the Input Guard side of
  weak-signal over-triggering. Fixed: `docs/modernization-v2-threat-model.md`
  §4, added a natural-language benign query example.
- Grok "missing benign counterexample" — the HR/PII benign example was not
  explicitly tied to a high-trust source label. Fixed: tightened wording in
  the same section to specify "approved, expected, high-trust-source"
  context.

**Deferred (explicitly optional, not addressed now):**

- Grok "useful but optional improvements": immutable ingestion receipts,
  content-hash + version checks for document replacement detection,
  including multilingual/paraphrasing variants earlier in benchmark design
  guidance. All three are explicitly labeled optional by Grok's own review
  and would add engineering/design scope beyond what this documentation
  correction pass should decide unilaterally — deferred to Phase 12B/12D
  implementation-time judgment.

**Rejected, with reason:**

- None. Every Critical and Major finding from both audits was at least
  partially accepted; no finding was rejected outright. Two findings
  (Grok Critical 2 on multi-chunk mitigation, Gemini Critical 2 on exact
  benchmark size) were *partially* accepted — the underlying concern was
  addressed, but the audit's specific proposed mechanism/number was not
  adopted verbatim, with rationale recorded above in each case.

**Already substantially covered (no-op, noted for traceability):**

- Grok "likely bypass" — BM25 ranking manipulation via keyword-stuffed
  documents was already present in `docs/modernization-v2-threat-model.md`
  §3's retrieval-poisoning Tampering row before this audit; no change
  needed.
- Grok "missing benign counterexample" — HR/compliance content with
  synthetic PII in an approved context was already present in §4 before
  this audit; only the high-trust-source tie-in was added (see "Fixed now"
  above).
- Grok "optional improvement" — deterministic tie-breaking's reproducibility
  impact was already explicit in `ADR-002-retrieval-engine.md` before this
  audit (`bm25()` score then `chunk_id`); no change needed.

## Deferred decisions

- **Exact benchmark v2 case count (upper bound):** deferred to Phase 12D
  authoring time; only a minimum floor (>=100 total) is now locked.
- **Exact benchmark v2 folder/file name:** target `redteam/v2/` remains a
  placeholder, finalized at Phase 12D.
- **Vector/hybrid retrieval:** deferred to optional Phase 12F, requires its
  own approval and (for vector) its own dependency-approval step per
  `AGENT_RULES.md` rule 11.
- **Local LLM / semantic guard:** deferred to optional Phase 12G, requires
  its own approval, and any paid API use would separately require
  `AGENT_RULES.md` rule 4 approval.
- **Dashboard:** deferred to optional Phase 12H, last in sequence.
- **Cross-chunk co-occurrence heuristic (implement vs. document-only):**
  deferred to Phase 12C's own explicit decision, per the resolution of
  Grok Critical 2 above — not decided by this audit-resolution pass.
- **Immutable ingestion receipts, document-replacement version checks,
  earlier multilingual/paraphrasing benchmark guidance:** deferred per
  Grok's own "optional improvements" labeling (see Minor findings above).

## Phase 12B entry gate

| Requirement | Status |
|---|---|
| Retrieval engine decision locked | PASS — `ADR-002-retrieval-engine.md`, SQLite FTS5/BM25, strengthened this pass |
| FTS5 capability policy locked | PASS — absolute no-fallback wording now consistent across `modernization-final-plan.md` §4.A, `ADR-002-retrieval-engine.md`, and `modernization-v2-architecture.md` §7 Phase 12B |
| Ingestion boundaries defined | PASS — `modernization-final-plan.md` §4.B, module table in `modernization-v2-architecture.md` §2 |
| Server-controlled trust defined | PASS — `modernization-final-plan.md` §4.C, `modernization-v2-architecture.md` §4 (now with mandatory audit logging) |
| Prohibited runtime use of `is_poisoned` defined | PASS — `modernization-final-plan.md` §4.C, `modernization-v2-architecture.md` §4, `modernization-v2-threat-model.md` §3 Spoofing row |
| Backward compatibility requirement defined | PASS — `modernization-final-plan.md` §4.D, `modernization-v2-architecture.md` §1 and §6 |
| Test and rollback requirements measurable | PASS — Phase 12B/12C acceptance criteria and tests rewritten as explicit checkable conditions this pass; rollback plan stated per phase in `modernization-v2-architecture.md` §7 |
| V1 immutability protected | PASS — `ADR-003-v2-benchmark.md`, now with explicit v1-prohibited-from-validation/holdout wording |
| No unresolved Critical issue | PASS — all 5 Critical findings (2 Gemini, 3 Grok) accepted or partially accepted with documented rationale |
| No unresolved blocking Major issue | PASS — all 6 Major findings (3 Gemini, 3 Grok) accepted; the one converted-to-decision-point item (multi-chunk) no longer silently unaddressed |

## Final recommendation

**APPROVE PHASE 12B** (audit gate satisfied).

This means the Phase 12A documentation set, as corrected in this pass, is
internally consistent, addresses every Critical and Major audit finding,
and defines measurable entry criteria for Phase 12B. It does **not** mean
Phase 12B implementation starts automatically — per `AGENT_RULES.md` rule
12 ("stop at phase boundaries") and this task's own explicit instruction,
Phase 12B still requires a separate, explicit go-ahead from the project
owner before any `app/` code is written.
