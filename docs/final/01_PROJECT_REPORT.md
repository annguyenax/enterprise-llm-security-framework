# Project Report — Enterprise LLM Security Framework  
## Lab-scale Guardrail Proxy for RAG (Academic PoC)

**Implementation base:** `93ad09ddea90eb9712e82f3df5beacbd94399b9a`  
**Release-engineering integration HEAD:** `409e5f3e0770d1bf908d217481994dac3e786c76`  
**Nature:** university thesis technical report body (documentation phase 12G)

---

## Abstract

This project designs and implements a **lab-scale LLM security gateway** that sits in front of a retrieval-augmented generation (RAG) path and applies configurable guard stages (input, provenance/context-related controls, DLP/output-related controls) under a fixed **C0–C7 ablation matrix**. Evaluation is driven by a fully **synthetic** benchmark (v2), frozen by a **FINAL SHA-256 manifest**, and executed offline through a **Mock Provider** for determinism and cost control.

The evaluation control plane separates **development**, **validation**, and **holdout**: ordinary CLI paths cannot load holdout; holdout requires an external canonical authorization, fail-closed preclaim checks, atomic attempt-root claim, start receipt, and separate analysis schemas. Release engineering (Phase 12F) adds **manifest-driven materialization** of git-ignored frozen artifacts with **atomic no-clobber** publication, opt-in redteam fixture governance, and **allowlist-based evidence inventory / sanitised auditor packet** tools gated on a real closure PASS.

Phase 12F mechanical and cross-review evidence records a green full suite (**1011 passed, 0 failed, 4 capability skips**), release-readiness PASS, and PASS verdicts from Claude, Codex, Grok (R2) and Gemini final audit—**without Critical or Major findings**. Those results measure **release integrity and tooling**, not production security effectiveness.

A historical Phase 12E.4 holdout execution is classified strictly as **POST-EXECUTION EXPLORATORY / DIAGNOSTIC EVIDENCE ONLY** because human adjudication was incomplete before run. It is **not** a final evaluation PASS and supplies **no** thesis-primary holdout metrics.

---

## 1. Problem statement

LLM-backed enterprise assistants face prompt injection, indirect injection via retrieved context, jailbreak-style instruction override, and data leakage. Academic evaluation often confounds **implementation completeness**, **reproducible offline testing**, and **blind evaluation governance**. This project addresses all three at lab scale: build a controllable gateway, measure ablations under a frozen synthetic benchmark, and enforce fail-closed evaluation and release procedures.

---

## 2. Objectives

1. Implement a modular guardrail proxy for a RAG query path.  
2. Define a fixed C0–C7 configuration registry with stable config hashes.  
3. Provide offline evaluation with Mock Provider and content-free result projection.  
4. Freeze benchmark v2 under FINAL manifest identity.  
5. Isolate holdout from ordinary splits via authorization and capability design.  
6. Harden release reproducibility (materialize ignored artifacts; no-clobber; evidence packets).  
7. Document claims control so the thesis does not over-claim.

---

## 3. Scope

### In scope

- Lab PoC architecture and implementation on the cited SHAs.  
- Synthetic benchmark methodology and freeze identity.  
- Evaluation governance (split isolation, one-shot rules, exploratory classification).  
- Mechanical test and Phase 12F release evidence **as recorded**.  
- Demo, defense Q&A, maintainer handoff.

### Out of scope

- Production multi-tenant deployment and compliance certification.  
- Equivalence to commercial frontier LLM behavior.  
- Final governance-valid holdout metrics (not available under current classification).  
- Cryptographic defense against malicious local administrators.

---

## 4. Architecture

See `02_ARCHITECTURE_AND_THREAT_MODEL.md`.

High level: Client/runner → pipeline + GuardProfile → lexical RAG retrieval → provider interface (mock in evaluation) → output/DLP-related controls → projected response. Evaluation control plane binds C0–C7 registry, FINAL manifest, and (for holdout) external authorization + attempt-root evidence outside git.

---

## 5. Threat model

**In scope (illustrative):** prompt injection classes, context-borne instruction injection, leakage via responses, evaluation integrity threats (wrong split, overwrite, unauthorized holdout, claims inflation).

**Out of scope / residual:** hostile in-process attackers, malicious administrators, full OS adversaries, hard-link/reparse races beyond trusted-maintainer best effort, Windows directory-fsync durability residual.

Holdout authorization is a **procedural misuse barrier**, not a cryptographic enclave.

---

## 6. Implementation

See `03_IMPLEMENTATION_AND_CONTROLS.md`.

Controls are profile-gated stages around retrieval and provider I/O. Evaluation runner builds temporary SQLite corpora from frozen documents, executes cases under mock, and publishes immutable-style result directories with identity fields (commit, config hash, provider behavior hash, benchmark manifest hash, expected case-set hash). Analyzer enforces matrix completeness, min-n rate suppression, Wilson intervals without continuity correction, and hard non-reportable latency under decision L2.

Phase 12F adds materializer (byte-level FINAL artifacts; opt-in redteam group), `verify_phase.ps1 -ReleaseReadiness`, and `scripts/phase12f/*` inventory/packet tools.

---

## 7. Release engineering

See `05_REPRODUCIBILITY_AND_RELEASE.md`.

Ignored `*.jsonl` means worktrees do not receive frozen files via git alone. Materialization is manifest-driven, verifies SHA-256/size, reuses byte-identical targets, refuses mismatch without force, and publishes with atomic **no-clobber** (`os.link`). Redteam `prompts.jsonl` stays untracked; a tracked one-file manifest enables governed materialization.

**EXPECTED AFTER PHASE 12G INTEGRATION:** any unified CI private-artifact delivery workflows not yet merged on this documentation branch.

---

## 8. Evaluation methodology

See `04_EVALUATION_METHODOLOGY.md`.

| Split | Ordinary path | Purpose |
|---|---|---|
| development | yes | diagnostic |
| validation | yes | closed 12E.3 policy historically |
| holdout | authorization path only | blind one-shot by design |

Phase 12F **did not** create new evaluation effectiveness evidence; it hardened release and evidence packaging.

---

## 9. Governance

Human maintainer alone authorizes holdout. Pre-authorization adjudication and residual-risk acceptance are required for governance-valid holdout. Post-hoc signature after seeing results is **not** equivalent. System modification after result visibility creates a new candidate; old holdout must not validate it. Prefer new blind set or external independent data for future holdout-grade claims.

---

## 10. Test evidence (recorded, not re-run here)

| Source | Result |
|---|---|
| Phase 12F Correction V1 full suite | 1011 passed, 0 failed, 4 skips |
| Release readiness | PASS |
| Claude / Codex / Grok R2 | PASS |
| Gemini final audit | PASS |
| Critical / Major | none reported |

During Correction V1, a focused command was **inadvertently run twice**; both green; **disclosed** (not a hidden failure retry).

These are **integrity and tooling** results, not attack-block-rate marketing metrics.

---

## 11. Limitations

See `07_LIMITATIONS_AND_FUTURE_WORK.md` (mock, synthetic data, lexical retrieval, rule limits, small family n, Windows FS, no final valid holdout result, CI private-artifact limits).

---

## 12. Conclusion

The project delivers a defensible **academic PoC**: a modular guardrail gateway, a frozen synthetic evaluation design with strict holdout isolation, and Phase 12F release-engineering controls that close real reproducibility gaps (ignored JSONL materialization, no-clobber publish, sanitised auditor packets).

Honest conclusion: **technical and release-integrity work is strong on `409e5f3…`; governance-valid final holdout evaluation is not claimed.** Thesis claims must stay inside the claims matrix (`10_CLAIMS_MATRIX.md`).

---

## References (internal)

- `docs/phase12f/**` — Phase 12F operator and governance docs  
- Phase 12F integration / remediation / correction external packages (historical)  
- Candidate evaluation scripts under `scripts/` on the integration HEAD  
