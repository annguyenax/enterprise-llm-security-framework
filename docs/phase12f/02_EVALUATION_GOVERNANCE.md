# Phase 12F — Evaluation Governance

**Base candidate:** `93ad09ddea90eb9712e82f3df5beacbd94399b9a`  
**Purpose:** binding rules for what may be claimed from development, validation, and holdout evidence

---

## 1. Split separation (hard)

| Split | Ordinary CLI / loader | Purpose |
|---|---|---|
| `development` | Allowed via `SUPPORTED_SPLITS` | Diagnostic / iteration / smoke |
| `validation` | Allowed via `SUPPORTED_SPLITS` | Closed evaluation under Phase 12E.3 policy |
| `holdout` | **Not** in `SUPPORTED_SPLITS` | Blind one-shot; separate authorization path only |

Rules:

1. Ordinary `--split` must never accept `holdout`.
2. Ordinary loaders must never load holdout cases/labels.
3. No boolean `authorized=True` shortcut on the ordinary loader.
4. Holdout uses separate request types, schemas, CLI (`--holdout-authorization`), and analyzer path.
5. Holdout and ordinary analysis artifacts must not be interchangeable by schema identity.

---

## 2. One-shot holdout rules

1. **Human adjudication first** (complete residual-risk acceptance, explicit AUTHORIZE decision).
2. **External canonical authorization** (exact branch/commit, FINAL manifest, mock provider, C0–C7 hashes, contracts, attempt/lineage, `holdout_authorized: true`).
3. **Attempt root absent** before claim; runner claims atomically; no manual pre-create.
4. **Start receipt** written before authorized holdout load.
5. **Full C0–C7 only** — no partial config selection for holdout.
6. **No force / overwrite / silent retry**.
7. **Preserve burned roots** — never delete to free a path name.
8. **Retry** only via new authorization, new root, incremented attempt, honest `supersedes` lineage.
9. **Analyzer** requires complete eight configs; rejects partial matrices.
10. **Mock provider only** for authorized holdout.

---

## 3. Why the prior Phase 12E.4 attempt is not final

**Classification:** POST-EXECUTION EXPLORATORY / DIAGNOSTIC EVIDENCE

| Factor | Observation |
|---|---|
| Technical execution | One complete C0–C7 matrix + analysis was produced |
| Technical integrity | No evidence-integrity failure detected in mechanical review of structure |
| Governance order | Human adjudication / residual-risk acceptance was not fully completed **before** execution in the prescribed sense |
| Consequence | Cannot support **final Phase 12E.4 PASS** or thesis-primary evaluation claims |

This is a **governance** defect relative to the project’s own holdout plan, not a statement that result bytes are corrupt.

---

## 4. Post-execution ratification policy

**Ratification after looking at holdout results is not equivalent to pre-authorization.**

Allowed:

- Document the attempt honestly as exploratory/diagnostic.
- Use process lessons to improve runbooks and checklists.
- Decide **not** to base the thesis primary table on that attempt.

Prohibited:

- Retroactively labeling the attempt as governance-valid final evaluation solely by signing after the fact.
- Editing adjudication history to pretend pre-authorization existed.
- Patching system code after result visibility and still claiming the same holdout validates the new code.

**Preferred remediation for a final holdout claim:**

1. Freeze a **new** candidate (if any code change) or re-freeze process with full pre-auth adjudication on the same code only if no result-driven modification occurred **and** methodology accepts re-run risk; otherwise
2. Commission a **new blind set** or **external independent dataset**, and run under full pre-authorization governance.

---

## 5. New-candidate rule after result visibility

```text
IF system is modified after holdout results were observed
THEN candidate SHA changes
AND prior holdout evidence MUST NOT validate the new candidate
AND a new blind/independent evaluation is required for holdout-grade claims
```

“System” includes: guards, pipeline, metrics, mapping, runner, analyzer, schemas, or benchmark bytes.

Documentation-only changes (this Phase 12F package) do **not** by themselves create a new evaluation candidate for code claims, but they also **do not** convert exploratory holdout into final PASS.

---

## 6. Requirement for a new blind set or external independent dataset

When a final holdout-grade claim is desired **after** exploratory execution visibility or after code change:

| Option | When appropriate |
|---|---|
| New blind holdout v3 (or later) | Benchmark redesign; requires full re-freeze and multi-auditor protocol |
| External independent dataset | External peer or published suite; separate identity and ethics review |
| Explicit non-holdout thesis | Report stops at development/validation + exploratory diagnostics; no holdout PASS |

There is **no** free option that both (a) reuses the exploratory holdout as final and (b) modifies the system after seeing it.

---

## 7. No retroactive rewriting of history

Must preserve:

- Commit SHAs and timestamps of evidence.
- Authorization IDs and hashes if any were issued.
- Attempt roots as-is (including partial failures).
- The fact of exploratory classification for the prior attempt.

Must not:

- Delete burned attempts to hide failure.
- Overwrite results after analysis.
- Alter frozen benchmark bytes in place.
- Relabel development smoke as holdout.
- Relabel exploratory holdout as validation.

---

## 8. Allowed and prohibited claims

### 8.1 Allowed (with scope)

- The gateway and guard ablation framework are **implemented** as a lab PoC on candidate `93ad09d…`.
- Benchmark v2 is **synthetic**, frozen, and split 30/30/60 with a blind holdout **by design**.
- Ordinary evaluation paths enforce development/validation isolation from holdout.
- Mechanical tests and freeze verification **can** be re-run on a clean host (record current numbers from live runs only).
- Development matrices are **diagnostic** of operational function under Mock Provider.
- The holdout **machinery** is capable of one-shot execution under mock (exploratory attempt demonstrates reachability).
- Latency is **non-reportable** under L2 policy (`latency_reportable=false`; p50/p95 null when that policy holds).
- Primary rate metrics (as implemented) use min-n suppression and Wilson intervals without continuity correction; family rows may be non-reportable when n is small.

### 8.2 Prohibited

- Final **Phase 12E.4 PASS** based solely on the exploratory holdout.
- Production-security effectiveness claims.
- Real-world enterprise deployment readiness.
- Causal attribution of additive per-guard percentage “explaining” total gaps without methodology support.
- ABR / macro-average / F1 / p-value **metrics** (as evaluation outputs).
- Reportable latency claims under current L2 decision.
- Claims that Mock Provider results equal commercial LLM behavior.
- Claims that synthetic benchmark results equal production traffic.
- Using exploratory holdout numbers as **primary** thesis results without governance remediation.
- Presenting post-hoc signatures as pre-authorization.

### 8.3 Placeholder rule for report tables

Any numeric evaluation table in the thesis must be filled only from:

1. a governance-valid evidence set, or  
2. a clearly labeled **diagnostic** section that cites development/exploratory status.

Never from memory or invented values.

---

## 9. Roles (recap)

| Role | Authority |
|---|---|
| Maintainer | Sole final adjudicator; sole holdout authorizer |
| Implementer agents | Code/docs under assignment; never self-authorize holdout |
| Technical auditor | Security/integrity; no holdout authorization |
| Methodology auditor | Claims/statistics; no holdout authorization |
| Mechanical scripts | Deterministic verification only |

---

## 10. Relationship to Phase 12F

Phase 12F documents these rules so that release and defense materials remain consistent even though governance-final holdout evaluation is **not** asserted by this package.
