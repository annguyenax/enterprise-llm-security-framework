# Defense Q&A (Examiner Pack)

Concise, defensible answers. Prefer under-claiming.

---

### Q1. Is this production-ready?

**A:** No. It is a university lab PoC with synthetic data and a Mock Provider. Production multi-tenant security is out of scope.

### Q2. Why Mock Provider?

**A:** Determinism, offline reproducibility, zero API cost, and fair ablations. It does not simulate commercial stochastic models.

### Q3. Why can’t holdout be a normal `--split`?

**A:** To prevent accidental loading of the blind set. Holdout requires external authorization, separate schemas, capability, and one-shot attempt roots.

### Q4. Did you finish holdout evaluation?

**A:** A technical one-shot ran and produced complete artifacts, but it is classified as **post-execution exploratory/diagnostic evidence only** because pre-run human adjudication was incomplete. We do **not** claim final Phase 12E.4 PASS.

### Q5. Then what do your “1011 tests passed” mean?

**A:** They measure **integration and release-tooling integrity** after Phase 12F (materialization, no-clobber, packets, etc.), not a new attack-success rate on real models.

### Q6. What is AOMR/FPR in your system?

**A:** Rates implemented in the analyzer with min-n suppression and Wilson intervals. Family rows may be non-reportable when n is small. We do not report ABR, macro-average, F1, or p-value metrics.

### Q7. Why are latency p50/p95 null?

**A:** Decision L2: two repetitions support decision determinism, not a scientific latency protocol. Latency is non-reportable.

### Q8. How do you reproduce frozen data if JSONL is git-ignored?

**A:** Manifest-driven materialization verifies SHA-256/size and publishes without clobbering. Integrity is the FINAL manifest, not git tracking of JSONL.

### Q9. What if two processes materialize at once?

**A:** Publication uses hard-link no-clobber. If a target appears concurrently, identical content can be reused after re-verify; differing content fails closed and is never overwritten.

### Q10. Can CI always run full tests?

**A:** Only if ignored artifacts are supplied via a private sealed channel. That channel is **EXPECTED AFTER PHASE 12G INTEGRATION** if not yet merged; otherwise document offline materialization.

### Q11. Did Gemini run your pytest?

**A:** No. Gemini’s PASS is an audit/claims verdict record. Local mechanical evidence is separate.

### Q12. What happens if you change code after seeing holdout results?

**A:** New candidate SHA. Old holdout must not validate the new system. Prefer a new blind or independent dataset for holdout-grade claims.

### Q13. Is the capability cryptographic?

**A:** No. It is a procedural barrier under a trusted-maintainer threat model.

### Q14. Why keep exploratory evidence at all?

**A:** Historical honesty: the machinery ran. Mislabeling it as final PASS would be worse than keeping it labeled diagnostic.

### Q15. What is your strongest contribution?

**A:** Combining a modular lab gateway + frozen synthetic evaluation design with **fail-closed evaluation governance** and **release reproducibility controls** that treat ignored artifacts and evidence packaging as first-class engineering—not afterthoughts.
