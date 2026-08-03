# Limitations and Future Work

---

## 1. Limitations

### 1.1 Mock Provider

Evaluation uses a deterministic mock. It does not model commercial model stochasticity, long-context behavior, or provider-side safety. Results are not transferable as “GPT/Claude/Gemini security performance.”

### 1.2 Synthetic benchmark

Benchmark v2 is fully synthetic. External validity to production enterprise traffic is limited by construction.

### 1.3 Lexical / rule-oriented controls

Retrieval is lexical; many guards are rule/heuristic based. Evasion of brittle patterns is expected in the wild. This is a lab instrument, not a complete adaptive defender.

### 1.4 Real-model stochasticity absent

Determinism checks under mock do not estimate variance under temperature sampling or provider non-determinism.

### 1.5 Small family sample sizes

Min-n suppression leaves many family rates non-reportable. Do not invent family percentages.

### 1.6 Ignored externally materialized files

`*.jsonl` is git-ignored. Reproducibility requires materialization from a verified source or sealed bundle. Fresh worktrees without materialization are incomplete.

### 1.7 Hard-link support

No-clobber materialization uses `os.link`. Volumes without hard links fail closed (`no_clobber_unsupported`) rather than falling back to clobbering replace.

### 1.8 Windows directory-fsync

Directory-entry durability after crash is best-effort on Windows. File bytes may be fsynced; directory metadata flush is platform-limited.

### 1.9 Symlink skips

Hosts that forbid symlink creation skip related tests (capability skip, not silent pass).

### 1.10 No final valid holdout result

Phase 12E.4 attempt is exploratory/diagnostic only. **No governance-valid final holdout metrics** are claimed for the thesis primary results.

### 1.11 Need for independent blind evaluation

After exploratory visibility (or any code change), holdout-grade claims require a **new blind set** or **external independent dataset** under full pre-authorization governance.

### 1.12 CI private-artifact limitation

CI cannot magically possess git-ignored frozen JSONL without a private artifact channel. **EXPECTED AFTER PHASE 12G INTEGRATION** if a private sealed-bundle pipeline is added; until then, document manual/sealed materialization.

### 1.13 Not production security

No multi-tenant isolation, HSM, formal verification, or compliance certification claims.

---

## 2. Future work

1. Real-LLM evaluation protocol (new candidate, new claims).  
2. Independent/external benchmark or benchmark v3 freeze.  
3. Governance-valid holdout completion (or permanent non-holdout thesis scope).  
4. Dense/hybrid retrieval experiments with full re-evaluation.  
5. CI private artifact distribution + multi-OS matrix.  
6. Symlink-capable CI hosts.  
7. Optional audited latency protocol only if scientifically redesigned (otherwise keep L2).  
8. Stronger guards with re-bound config hashes and schemas.

---

## 3. Thesis writing rule

Every limitations item above that affects a claim must appear in the thesis limitations section—not only in an appendix.
