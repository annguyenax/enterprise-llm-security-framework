# Phase 12F — Demo and Defense Script

**Duration:** 10–15 minutes demo + Q&A  
**Base candidate:** `93ad09ddea90eb9712e82f3df5beacbd94399b9a`  
**Mode:** offline-first (Mock Provider)

---

## 1. Demo goals (what success looks like)

By the end of the demo, examiners should understand:

1. What the gateway is (lab guardrail proxy in front of RAG).  
2. How evaluation is structured (C0–C7, frozen benchmark, mock provider).  
3. Why holdout is isolated and governance-heavy.  
4. Why exploratory holdout evidence is **not** the same as final PASS.  
5. How to re-verify freeze identity and tests without inventing metrics.

---

## 2. Pre-demo checklist (T−30 min)

- [ ] Clean checkout of demo SHA  
- [ ] `.venv` works  
- [ ] Frozen artifacts present; `freeze_v2_benchmark.py verify` OK  
- [ ] One terminal in repo root; one for notes  
- [ ] Screenshots or live windows prepared  
- [ ] Fallback path ready if network is unavailable (always use mock)  
- [ ] Decide whether to show **only** development diagnostic, or also **mention** exploratory holdout without opening raw cases  

**Do not** open `datasets/v2/cases/holdout.jsonl` or `labels/holdout.jsonl` for content display.

---

## 3. Minute-by-minute flow (12 minutes)

| Time | Screen / action | Oral point (1–2 sentences) |
|---|---|---|
| 0:00–1:00 | Title slide / repo root | “This is a lab-scale LLM security gateway for RAG, not a production product.” |
| 1:00–2:30 | Architecture diagram (`01_RELEASE_ARCHITECTURE.md`) | “Requests pass through configurable guards around retrieval and provider I/O.” |
| 2:30–4:00 | `git rev-parse HEAD` + clean status | “Evaluation is bound to an exact commit identity.” |
| 4:00–5:30 | `freeze_v2_benchmark.py verify` | “Benchmark v2 is frozen by SHA-256; we verify bytes, not vibes.” |
| 5:30–7:30 | GuardProfile / C0–C7 table (code or docs) | “Ablations are a fixed registry so comparisons stay fair.” |
| 7:30–9:30 | `verify_phase.ps1 -Focused` **or** short pytest excerpt | “Mechanical tests are scripted so we don’t quote numbers from memory.” |
| 9:30–11:00 | Development result **manifest** only (if available) | “Development is diagnostic under Mock Provider.” |
| 11:00–12:00 | Governance slide: exploratory vs final | “A holdout run without complete pre-authorization is exploratory only—not Phase 12E.4 PASS.” |
| 12:00–15:00 | Buffer / Q&A | See §5 |

If focused verify is slow, show a **saved transcript** of a prior clean run and say clearly it is historical mechanical evidence, then optionally re-run one fast command (freeze verify).

---

## 4. Commands to show (safe set)

```powershell
git rev-parse HEAD
git status --short
.\.venv\Scripts\python.exe scripts\freeze_v2_benchmark.py verify
.\scripts\verify_phase.ps1 -Focused
```

Optional (diagnostic only; external output root):

```powershell
# Only if time and environment allow; label as diagnostic
.\.venv\Scripts\python.exe scripts\run_v2_evaluation.py --help
```

**Avoid live holdout** in the demo unless examiners specifically require it **and** a governance-valid authorization exists. Prefer explaining the gate without executing.

---

## 5. Likely examiner questions and defensible answers

### Q1. Is this production-ready?

**A:** No. It is a university lab PoC with synthetic data and a mock provider. Production claims are out of scope.

### Q2. Why Mock Provider?

**A:** Determinism, offline reproducibility, zero external API cost/variance, and fair ablations. It does **not** model stochastic commercial LLMs; that is an explicit limitation.

### Q3. Why not just put holdout in `--split`?

**A:** To prevent accidental or casual loading of the blind set. Holdout requires an external authorization, separate schemas, and a capability gate—by design.

### Q4. Did you finish holdout evaluation?

**A (honest):** A technical one-shot was executed and produced complete artifacts, but it is classified as **exploratory/diagnostic** because governance (full pre-authorization adjudication) was incomplete. We do **not** claim final Phase 12E.4 PASS from that attempt.

### Q5. Can you show holdout case text?

**A:** No. Blind/holdout content is not inspected for demo or reports beyond byte-level identity when required. We show manifests and governance structure instead.

### Q6. What is AOMR / FPR?

**A:** Rates as implemented in the analyzer with min-n suppression and Wilson intervals; family rows may be non-reportable when n is small. We do not report ABR/macro/F1/p-values.

### Q7. Why is latency null?

**A:** Project decision L2: repetitions exist for decision determinism, not a scientific latency protocol. Latency is non-reportable.

### Q8. What if you change code after seeing holdout results?

**A:** That creates a new candidate. Old holdout evidence must not validate the new system. A new blind or independent set is required for holdout-grade claims.

### Q9. How do you stop silent overwrite?

**A:** Attempt roots refuse reuse; results refuse overwrite; no force flag; partial evidence is preserved; analyzer rejects incomplete matrices.

### Q10. Is the capability cryptographic?

**A:** No. It is a procedural barrier under a trusted-maintainer threat model.

---

## 6. Why holdout governance matters (oral paragraph)

“Holdout exists to reduce overfitting and researcher degrees of freedom. If we can load it like any other split, or authorize it after peeking at outcomes, we lose the scientific value of blindness. Our design makes holdout hard to touch accidentally—and we treat a technically successful but under-adjudicated run as diagnostic, not as a final grade.”

---

## 7. Why exploratory results are not final claims (oral paragraph)

“Technical completeness means the pipeline can write eight results and an analysis. Governance completeness means humans accepted residual risks and authorized before the fact. We had the first without a fully clean second, so the honest label is exploratory. That protects the thesis from overclaiming.”

---

## 8. Fallback demo (no network, slow disk, missing JSONL)

1. Show architecture + governance slides only.  
2. Show `git rev-parse` and a **pre-saved** freeze-verify transcript.  
3. Show GuardProfile definitions in code.  
4. Show analyzer claims_control structure from a **development** analysis if available.  
5. Explicitly skip live evaluation.  
6. Emphasize limitations and future real-LLM work.

---

## 9. Materials to print / project

- Architecture diagram (Mermaid export or text)  
- Claims matrix (allowed / prohibited)  
- One-page status: technical vs evaluation vs governance completion  
- This script’s Q&A section  

---

## 10. Anti-patterns during demo

- Quoting holdout AOMR numbers as final  
- Opening holdout JSONL  
- Installing random packages live  
- Running holdout “just to show it works” without authorization  
- Claiming production security  
