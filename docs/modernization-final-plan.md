# Modernization Final Plan (Phase 12A Scope Lock)

> **Status:** Approved scope lock, documentation/architecture only. No application code, test, script, dataset, red-team, or evaluation-artifact has been changed to produce this document. See `TASK_BOARD.md` for phase tracking.

## 1. Purpose

Phase 0-11 delivered a working lab-scale gateway (Input Guard, RAG Context Guard,
mock LLM Provider Adapter, Output Guard, audit logging) evaluated against a
frozen 40-case synthetic benchmark (40/40 exact decision match after
Phase 7.1 calibration). Three independent reviews of that state
(`docs/modernization-ai-reviews/codex-code-architecture-review.md`,
`gemini-phase-12a-academic-gate.md`, `grok-phase-12a-redteam-gate.md`) plus this
repository's own earlier `claude-repo-feasibility-review.md` converge on the
same core finding: the biggest credibility gap is that **retrieval is not
real** (context chunks are supplied directly by the caller) and the 40/40
result was reached by iteratively adding rules against the same 40 cases,
which is a textbook calibration-not-generalization pattern rather than a
flaw to hide.

This document is the single authoritative reconciliation of those four
reviews into one approved direction, one phase boundary structure, and one
set of required engineering decisions. It does not implement anything.

## 1a. Research Questions

Added per the Phase 12A audit (`docs/modernization-ai-reviews/gemini-phase-12a-audit.md`,
Major finding on missing baseline RQ), consolidating
`gemini-phase-12a-academic-gate.md`'s original RQ1-RQ4 plus one new RQ this
audit specifically requested. These frame what Phase 12E's evaluation must
be able to answer — they are questions to answer with real Phase 12E
measurements, not claims made now:

- **RQ1 (Efficacy):** To what extent does server-controlled provenance and
  metadata-aware context filtering reduce indirect-prompt-injection/RAG
  poisoning exposure, compared to a pipeline without those layers, on the
  v2 benchmark?
- **RQ2 (Trade-off):** What is the trade-off between security strictness
  (TPR) and usability (FPR on benign queries, including the "trap" queries
  in §4.E below) across the individual guard layers?
- **RQ3 (Ablation / layer value):** What is each layer's (Input, Retrieval/
  Provenance, RAG Context, Output/DLP) marginal contribution to overall
  system efficacy, per the `GuardProfile` ablation design in
  `docs/modernization-v2-architecture.md` §2 and §7 (Phase 12E)?
- **RQ4 (Performance overhead):** What is the latency overhead (p50/p95, in
  milliseconds) introduced by the multi-layer gateway during an end-to-end
  retrieval-and-generation cycle against the mock provider?
- **RQ5 (Baseline vulnerability, added by audit):** What is the baseline
  leakage rate and poisoned-context exposure of the retrieval pipeline with
  all guard layers disabled (the `no_guards` profile), when evaluated
  against the v2 holdout split? This establishes the "before" number that
  RQ1 and RQ3's "marginal contribution" claims are measured against — the
  same role v1's `baseline-vs-guarded` comparison already plays for the v1
  benchmark (`reports/evaluation/baseline-vs-guarded.md`), extended to v2.

## 2. Final Approved Direction

Adopted, in priority order:

1. SQLite FTS5/BM25 retrieval first (not vector/embeddings).
2. Persistent document ingestion (not caller-supplied context only).
3. Server-controlled provenance/trust (caller cannot assign trust).
4. End-to-end RAG query service (`Input Guard -> Retrieval -> RAG Guard -> Provider -> Output Guard`).
5. Centralized DLP (shared detector/redaction module, not duplicated per guard).
6. New v2 benchmark and holdout (frozen v1 stays untouched as a historical artifact).
7. Ablation, retrieval-security, leakage, and latency metrics.
8. Vector/hybrid retrieval — optional, later (Phase 12F).
9. Local LLM / semantic guard — optional, later (Phase 12G).
10. Dashboard — optional, and last (Phase 12H).

This ordering is intentional: items 1-7 are the core, defensible, laptop-feasible
v2 scope. Items 8-10 are explicitly deferred and require their own future
approval — they are not silently implied by this plan.

## 3. How the Three Reviews Were Reconciled

| Topic | Codex (code-architecture) | Gemini (academic-methodology) | Grok (red-team/security-scope) | Resolution |
|---|---|---|---|---|
| Retrieval engine | SQLite FTS5/BM25 — "best immediate option" | FTS5/BM25 "perfectly acceptable"; explicitly warns against chasing vector DB/local LLM if time is short | "Stick to BM25/FTS5"; vector/embeddings out of scope for now | **No conflict.** All three converge; adopted as-is (approved direction #1, #8). |
| Ablation profiles | 7 profiles: `no_guards`, `input_only`, `rag_only`, `output_dlp_only`, `full`, plus 3 `full_minus_<layer>` marginal-contribution profiles | 5 profiles: Baseline off / Input / RAG / Output / All | Not specified in detail; expects an ablation matrix vs v1 | **No real conflict** — Codex's 7 profiles are a strict superset of Gemini's 5 and additionally answer Gemini's own RQ3 (marginal per-layer contribution). Adopted Codex's full set. |
| Endpoint surface | `POST /v1/documents/ingest`, `POST /v1/rag/query`, `GET /v1/evaluation/summary` (read-only, fixed artifact) | Not specified at API level | Not specified at API level | The user's own final approved direction (item D below) additionally names `POST /v1/retrieve` as a lower-level primitive distinct from `/v1/rag/query`. This is **not a conflict** with Codex — `/v1/retrieve` cleanly maps onto Codex's own `Retriever.search()` contract, exposed directly for retrieval-only debugging/evaluation transparency, while `/v1/rag/query` remains the full guarded path. Both are adopted. |
| Benchmark v2 size/split | No fixed number; new `redteam/scenarios-v2.jsonl`, never touching the v1 40 labels | Prescriptive: >=100 cases, exact 50/50 split with named subcounts (20/20/10 malicious, 25/25 benign) | Category matrix (Direct/Indirect/Poisoning/Leakage x Injection/Bypass/Override/Exfil) plus a separate unseen-variant holdout; no fixed total | **Partial conflict, resolved in favor of the approved direction's own wording** ("approximately balanced benign and malicious scenarios," not an exact prescriptive split). Gemini's exact subcounts are recorded as a *reference design suggestion* for Phase 12D scenario authoring, not a locked requirement — locking exact per-category counts now, before Grok's threat-matrix content is actually authored, would be premature and could itself bias scenario design toward hitting a number rather than covering real cases. |
| Numeric acceptance thresholds | Not proposed | Not proposed as hard gates (asks for the metrics to be *computed and analyzed*, not for a pass/fail number) | Proposes hard thresholds: ASR < 20%, FPR < 5%, provenance-block rate >= 80%, latency < 50ms end-to-end | **Real conflict, resolved against Grok's hard thresholds.** `AGENT_RULES.md` rule 3 ("No fake benchmarks or results... never fabricate evaluation numbers... placeholder numbers must be TBD, never plausible-looking fake values") and this project's own consistent practice across Phase 7/7.1/7.2 (report only numbers from an actual run, never pre-commit to a target) both argue against adopting outcome-based acceptance thresholds before any v2 data exists. Pre-committing to "ASR < 20%" before the benchmark is even authored creates exactly the fabrication-adjacent pressure rule 3 exists to prevent (either the number gets hit through benchmark/rule tuning until it does, which reproduces the v1 calibration problem one level up, or it silently becomes a target quietly abandoned). **Adopted instead:** phase acceptance criteria are *procedural* ("metric X is computed and reported for every ablation profile," "holdout was not used to author or tune any rule") rather than *outcome thresholds*. Grok's proposed numbers are preserved in `docs/modernization-v2-threat-model.md` as *illustrative reference points from external red-team practice*, explicitly labeled as not binding acceptance gates for this project. |
| `is_poisoned` / ground-truth leakage into runtime | Explicitly flags that `DocumentChunk.is_poisoned` (`app/services/dataset_loader.py`) is benchmark-only ground truth and must never drive runtime trust decisions | Not addressed directly, but consistent with "client must not dictate trust level" | Not addressed directly | **No conflict** — Codex's finding is exactly what the user's own required decision C already states ("runtime must never use benchmark `is_poisoned`"). Recorded as a validated cross-check, not a new decision. |
| Phase 12A-12E lettering | N/A (reviews in PR terms, not phase letters) | Uses its own internal "12A-12E" lettering (12A=FTS5 retrieval, 12B=persistent ingestion+provenance, 12C=DLP, 12D=benchmark v2, 12E=evaluation runner) | N/A (reviews acceptance criteria for "Phase 12B-12E" without redefining letters) | **Conflict in lettering only, not in content.** Gemini's internal lettering does not match the phase boundaries approved by the project owner in this task (Section G below, where 12A is this documentation-only phase and 12B is the first implementation phase). This document uses the **project owner's approved lettering** as authoritative. Gemini's content (what each stage must prove) is preserved and mapped onto the correct phase letters. |
| Dashboard timing | Defer; Swagger + generated Markdown sufficient until retrieval/evaluation stable | Not addressed | Not addressed | **No conflict.** Matches approved direction item #10 exactly. |

## 4. Required Engineering Decisions

See `docs/modernization-v2-architecture.md` for full detail. Summary:

**A. Retrieval** — standard-library `sqlite3` only (no new dependency for the
core retrieval path); SQLite FTS5 virtual table with `bm25()` ranking; an
explicit capability check for FTS5 (some Python/SQLite builds omit it) that
runs before retrieval is used. **Strengthened per the Phase 12A audit
(both Gemini and Grok flagged the original wording as not absolute enough):
if FTS5 is unavailable, the system must fail with a clear capability error
and refuse to serve any retrieval-dependent request — there is no fallback
to `LIKE`, substring search, or any other degraded scoring method, at
startup or at any later runtime check.** This is a hard requirement, not a
preference, per the approved decisions list for this phase. A persistent
local `.db` file (not in-memory-only); short-lived connections per request
(SQLite + FastAPI threading risk, per Codex finding); parameterized SQL
throughout; safe FTS5 query construction (raw user text must never be
concatenated directly into a `MATCH` expression — FTS5 query syntax has its
own operators that a malicious query could inject, per Codex finding);
deterministic ranking with an explicit tie-breaking rule (e.g., `bm25()` then
`chunk_id` ascending) so evaluation results are reproducible.

**B. Ingestion** — validation and size limits on ingested text; deterministic
paragraph-aware chunking (not raw fixed-character windows, to avoid splitting
an attack indicator across a chunk boundary — a known risk already discovered
once in this repo's own Phase 5 loader design); stable, deterministic
document/chunk IDs; SHA-256 content hash per chunk for deduplication and
change detection; deduplication on ingest; transactional batch ingestion (a
failed batch must not leave a partially-indexed state); source policy
(trust/provenance) assigned **server-side** at ingestion time, never accepted
from the caller.

**C. Trust and provenance** — the caller cannot set `trust_level` on a
document or chunk; trust is derived only from a server-controlled source
policy (e.g., an allow-listed ingestion source/config, not a request field);
the runtime retrieval/guard path must never read or depend on the
benchmark-only `is_poisoned` field from `app/services/dataset_loader.py`;
the v2 benchmark design must be able to represent **both** "clean content
from a low-trust source" and "compromised content from a high-trust source"
as distinct cases, so trust and content-safety are evaluated as independent
signals, not conflated.

**D. API compatibility** — `POST /v1/gateway/chat` is preserved unchanged for
backward compatibility and regression testing. New, additive-only endpoints:
`POST /v1/documents/ingest`, `POST /v1/retrieve` (retrieval-only, no guard
pipeline — useful for retrieval-quality evaluation in isolation), `POST
/v1/rag/query` (full guarded path: retrieval -> RAG Guard -> provider ->
Output Guard). An optional read-only `GET /v1/evaluation/summary` (reads a
fixed, already-generated report artifact; never triggers a live evaluation
run or accepts an arbitrary filesystem path) is deferred to a later phase
once the v2 evaluation artifacts exist.

**E. Benchmark v2** — lives entirely under new folders (e.g.
`redteam/v2/`, exact layout finalized in `ADR-003-v2-benchmark.md`); the
existing `redteam/prompts.jsonl` and `datasets/clean|poisoned/` (v1) are
**never modified**; v2 has explicit development, validation, and holdout
splits; holdout cases are never used to author or calibrate a rule
(Gemini's "Rule of Separation," Grok's independent-holdout principle); once
evaluation starts for the final report, rules are frozen (Gemini's "Rule of
Freezing"); the v2 manifest is hashed (SHA-256) and frozen the same way v1
already is (`tests/test_evaluation_runner.py` already enforces this pattern
for v1 and should be extended, not replaced, for v2 — **per the Phase 12A
audit, the future v2 evaluation runner itself must also verify the manifest
hash at the start of every run and abort on mismatch, not rely solely on a
separate pytest check**); v1's 40/40 result remains a permanent historical
artifact and must never be re-presented as if it were a v2 result. **V1 is
formally retired as the historical calibration set as of this plan and is
strictly prohibited from being merged into, or reused as content for, the
v2 validation or holdout splits** (Gemini audit required correction — v1
content may only ever appear in v2's *development* split, if at all, since
development is the one split that may legitimately overlap with prior
calibration history). **The v2 corpus must contain at least 100 cases in
total** (a statistical floor for FPR/TPR to carry meaning, per the Phase
12A audit), approximately balanced between benign and malicious scenarios;
the exact upper bound and per-category subcounts remain deferred to Phase
12D authoring time, informed by the category matrix in
`docs/modernization-v2-threat-model.md` §4 — see `ADR-003-v2-benchmark.md`
for the full rule and why an exact prescriptive split is not locked now.

**F. Evaluation** — metrics to define and compute (not necessarily all in
the first evaluation phase, see phase boundaries): TPR, FPR, FNR, precision,
recall, F1 (per ablation profile); Recall@k and poisoned-hit-rate@k
(retrieval-quality and retrieval-security metrics, only meaningful once real
retrieval exists); poisoned-context exposure (fraction of retrieved poisoned
chunks that still reach the provider after the RAG Guard) and clean-context
retention (fraction of legitimate chunks preserved after sanitization — a
guard that "protects" by deleting everything is not useful, matching the
usability concern both Gemini and the earlier Claude review raised); leakage
rate and redaction recall (DLP-specific); benign over-redaction (DLP false
positives on legitimate content); p50/p95 latency; per-layer unique catches
and marginal contribution (ablation). **Exact numerator/denominator
formulas for every metric above are defined in**
`docs/modernization-v2-architecture.md` §8 (added per the Phase 12A audit,
Gemini's finding that metric names alone risk inconsistent implementation).

**G. Phase boundaries** — see `docs/modernization-v2-architecture.md` §7 and
the phase-by-phase acceptance criteria there. Summary list:

- **Phase 12A** — this phase: Modernization Scope Lock and V2 Architecture (documentation only, no code).
- **Phase 12B** — Retrieval Foundation (SQLite FTS5/BM25, ingestion, chunking).
- **Phase 12C** — RAG Query Service + Provenance + DLP.
- **Phase 12D** — Benchmark v2 Generation and Freeze.
- **Phase 12E** — Ablation, Retrieval-Security and Latency Evaluation.
- **Phase 12F** — Optional: Vector/Hybrid Retrieval.
- **Phase 12G** — Optional: Local LLM / Semantic Guard.
- **Phase 12H** — Optional: Dashboard.

## 5. Explicit Non-Goals for This Modernization Wave

Carried forward unchanged from `AGENT_RULES.md` and `docs/diagrams/architecture.md`
§5, and reaffirmed by all three external reviews:

- No Kubernetes, no SIEM integration, no local model fine-tuning/training.
- No production-scale vector database, no downloaded embedding model, unless
  and until Phase 12F is separately approved.
- No real external/paid LLM API call without explicit approval
  (`AGENT_RULES.md` rule 4) — the mock provider remains the default through
  at least Phase 12E.
- No multi-agent or autonomous tool-use security work.
- No modification of `datasets/`, `redteam/prompts.jsonl`,
  `redteam/expected-behaviors.yaml`, or any file under `reports/evaluation/`
  or `report-latex-template/` as part of this modernization wave's planning
  phase (Phase 12A). Later phases that add v2 content do so in **new**
  files only.
- No claim of production readiness, "solved" prompt injection, or
  generalization beyond the tested benchmark — `AGENT_RULES.md` rule 8 and
  the "Claims That Must Not Appear in the Report" list in
  `gemini-phase-12a-academic-gate.md` §7 both apply unchanged to v2 results.

## 6. Document Map

| Document | Purpose |
|---|---|
| `docs/modernization-final-plan.md` (this file) | Scope lock, reconciliation, required decisions summary, research questions, phase list. |
| `docs/modernization-v2-architecture.md` | Target v2 component/module/API design, metric formulas, and Phase 12B-12H boundaries in implementation-ready detail. |
| `docs/modernization-v2-threat-model.md` | STRIDE-style threat model for the v2 retrieval/ingestion/provenance/DLP surface. |
| `docs/decisions/ADR-002-retrieval-engine.md` | Formal decision record: SQLite FTS5/BM25 over vector/hybrid/mock-only. |
| `docs/decisions/ADR-003-v2-benchmark.md` | Formal decision record: v2 benchmark structure, splits, freezing rules. |
| `docs/modernization-ai-reviews/phase-12a-audit-resolution.md` | Traceable record of the Gemini and Grok Phase 12A audits and how each Critical/Major/Minor finding was resolved against this document set. |

## 7. Approval Gate

Per `AGENT_RULES.md` rule 12 ("stop at phase boundaries") and rule 1 ("no
scope creep"), Phase 12B (the first phase that touches `app/` code) does
**not** start automatically after this document is accepted. It requires an
explicit go-ahead referencing this plan, per the entry criteria listed in
`docs/modernization-v2-architecture.md` §7.
