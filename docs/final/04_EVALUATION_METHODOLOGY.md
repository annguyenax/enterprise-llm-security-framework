# Evaluation Methodology

**Identities:** base `93ad09d…` · Phase 12F HEAD `409e5f3…`

---

## 1. Benchmark

- Fully **synthetic** lab benchmark v2.  
- Design split: development 30 / validation 30 / holdout 60 cases (design totals).  
- **FINAL** freeze of nine artifacts under SHA-256 manifest.  
- Many artifacts are `*.jsonl` and **git-ignored**; integrity is via manifest + materialization, not git tracking of JSONL.  
- Holdout case/label files must not be semantically inspected for scoring discussions beyond byte identity when required.

---

## 2. Split separation

| Split | Ordinary runner/analyzer | Purpose |
|---|---|---|
| development | yes | diagnostic iteration |
| validation | yes | historically closed under 12E.3 policy |
| holdout | **no** ordinary path | blind one-shot under authorization |

Hard rules:

1. `SUPPORTED_SPLITS` excludes holdout.  
2. No `authorized=` boolean on ordinary loaders.  
3. Separate holdout schemas and CLI (`--holdout-authorization`).  
4. Ordinary analysis rejects holdout artifacts; holdout analysis rejects ordinary matrices.

---

## 3. Ablation matrix C0–C7

All configs share frozen cases (with scope rules: C0 covers configured scopes; ablations typically end-to-end). Comparisons use fixed config hashes. Primary narrative metrics (as implemented) center on rates such as AOMR and FPR with:

- `RATE_REPORTING_MIN_N = 10` style suppression;  
- Wilson 95% without continuity correction;  
- no ABR / macro / F1 / p-value **metrics**;  
- latency **non-reportable** under L2 (`latency_reportable=false`, p50/p95 null).

---

## 4. One-shot evaluation (holdout)

1. Human adjudication + residual risk acceptance **before** authorize.  
2. External canonical authorization (`holdout_authorized: true`).  
3. Preclaim: clean SHA, branch match, byte FINAL verify, root absent.  
4. Claim root + receipt → capability → authorized load.  
5. Full C0–C7 only; per-config publish; no force; no silent retry.  
6. Analyzer once on complete matrix.  
7. Preserve burned roots; retry only with new auth, new root, lineage.

---

## 5. Claims suppression

Analyzer emits `claims_control` flags (e.g. abr_enabled false, macro false, no_p_values true, latency_reportable false). Thesis text must not contradict these flags.

---

## 6. Exploratory-attempt classification (Phase 12E.4)

A technical holdout run occurred and produced complete artifacts, but pre-execution human adjudication was incomplete.

**Binding label:**  
`POST-EXECUTION EXPLORATORY / DIAGNOSTIC EVIDENCE ONLY`

Consequences:

- Not final Phase 12E.4 PASS.  
- Not primary thesis evaluation table.  
- May illustrate that the machinery can run under mock.  
- Must not be “ratified” into final status merely by signing after seeing results.

---

## 7. Why Phase 12F did not create new evaluation evidence

Phase 12F delivered:

- release materialization and Windows hardening;  
- redteam fixture governance;  
- evidence inventory/packet automation;  
- documentation and cross-review/correction integrity work.

It deliberately **did not** re-open validation or produce a new governance-valid holdout matrix. Mechanical green tests measure **tooling and integration integrity**, not new attack-effectiveness numbers.

---

## 8. Future evaluation (methodology only)

For governance-valid holdout-grade claims after exploratory visibility or code change:

- new candidate if code changed;  
- new blind set or external independent dataset preferred;  
- full pre-authorization adjudication;  
- independent methodology audit of claims.

---

## 9. What this methodology forbids

- Mixing development smoke numbers into “holdout results.”  
- Inventing metrics.  
- Reporting latency under L2.  
- Claiming production security from synthetic + mock evaluation.
