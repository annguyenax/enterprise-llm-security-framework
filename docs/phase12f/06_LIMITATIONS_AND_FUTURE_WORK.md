# Phase 12F — Limitations and Future Work

**Base candidate:** `93ad09ddea90eb9712e82f3df5beacbd94399b9a`  
**Tone:** explicit under-claiming preferred over optimism

---

## 1. Limitations (current system)

### 1.1 Synthetic benchmark

Benchmark v2 is fully synthetic lab data. It does not represent production user traffic, multi-tenant enterprise corpora, or adversarial internet-scale distributions. External validity is limited by construction.

### 1.2 Mock Provider

Authorized evaluation uses a deterministic Mock Provider. It does not reproduce:

- stochastic decoding  
- long-context commercial model behavior  
- tool-use or multi-turn agent stacks  
- provider-side safety layers  

Results must not be sold as “GPT/Claude/Gemini security performance.”

### 1.3 Rule / regex / heuristic guards

Many controls are rule- or heuristic-based. They are transparent and testable, but attackers can often evade brittle patterns. Coverage is incomplete by nature of pattern matching.

### 1.4 Lexical retrieval

RAG retrieval on the candidate is lexical (not dense embedding retrieval). Ranking quality, recall, and attack surface differ from modern vector RAG. Indirect injection via retrieved context is studied in a simplified retrieval regime.

### 1.5 Lack of real-model stochasticity

Decision determinism checks use fixed repetitions under mock. They do not measure variance under temperature sampling or provider non-determinism.

### 1.6 Small family sizes

Several scenario families have small n. Rate reporting applies min-n suppression; many family-level rates are non-reportable. Aggregate narrative must not invent family percentages when ineligible.

### 1.7 Windows filesystem limitations

On Windows:

- directory `fsync` may be unavailable (receipt durability residual)  
- path length can break tests without short basetemp  
- reparse/junction/hard-link edge cases are only best-effort under the trusted-maintainer model  

### 1.8 Symlink / junction coverage

Automated symlink escape tests may skip when the host denies symlink creation. Runtime path resolution still applies containment, but host-specific proof can be incomplete.

### 1.9 Evidence-governance limitation of the prior holdout attempt

A technical one-shot holdout was executed and produced complete C0–C7 + analysis artifacts, but pre-execution human adjudication was incomplete. That attempt is **POST-EXECUTION EXPLORATORY / DIAGNOSTIC EVIDENCE**, not final Phase 12E.4 PASS. This is a **process limitation** of the evaluation program as executed, separate from mechanical byte integrity of the artifacts.

### 1.10 Ignored frozen JSONL distribution

Because `*.jsonl` is gitignored, clean worktrees may lack frozen benchmark files until materialized. This is operational fragility for reproducibility, not a license to skip FINAL verification.

### 1.11 Not a production security control plane

No claim of:

- multi-tenant isolation  
- key management HSM  
- online abuse monitoring  
- formal verification of guards  
- compliance certification  

---

## 2. Future work

### 2.1 Real-LLM evaluation

- Define a new protocol for one or more real providers.  
- Handle non-determinism, cost, rate limits, and data-handling ethics.  
- New candidate, new authorization fields if needed, new claims matrix.  

### 2.2 Independent benchmark

- External or peer-supplied datasets.  
- Or benchmark v3 with new freeze and multi-auditor process.  
- Required if system changes after exploratory holdout visibility and holdout-grade claims are still desired.  

### 2.3 Governance-valid holdout completion

- Full pre-authorization adjudication and residual-risk acceptance.  
- Human-only active authorization.  
- Optional methodology auditor sign-off before and after run.  
- Explicit non-reuse of exploratory attempt as final PASS.  

### 2.4 Retrieval upgrades

- Dense embeddings / hybrid retrieval experiments.  
- Clear re-evaluation of indirect injection under new retrieval.  

### 2.5 Guard sophistication

- Structured detectors, model-based judges (with circularity controls), adaptive policies.  
- Always re-bind config hashes and schemas.  

### 2.6 CI and artifact distribution

- CI job with short basetemp on Windows and Linux.  
- Sealed artifact bundle for the nine FINAL files (and redteam fixtures if needed).  
- Optional long-path / symlink-enabled runners.  

### 2.7 Evidence tooling

- Integrated inventory and sanitized auditor packet generators (mark **EXPECTED AFTER INTEGRATION** until merged).  

### 2.8 Latency science (optional, separate decision)

- Only if a real latency protocol is funded and audited; otherwise keep L2 non-reportable.  

---

## 3. How limitations must appear in the thesis

1. Dedicated limitations chapter or section (not a footnote only).  
2. Claims matrix cross-check before submission.  
3. Exploratory holdout, if mentioned, always labeled.  
4. No “despite limitations, production ready” closing sentences.  

---

## 4. Mapping limitations → open items

| Limitation | Open item class |
|---|---|
| Exploratory holdout governance | Evaluation / governance completion |
| Mock / synthetic validity | Future real-LLM + independent data |
| JSONL materialization | Release packaging |
| Symlink skip / Windows FS | CI host matrix |
| Small n families | Reporting discipline / larger designs |
