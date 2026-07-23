# Final Report Template — Enterprise LLM Security Framework (Lab PoC)

> **Template status:** near-final structure for university thesis / technical report  
> **Implementation candidate placeholder:** `[[CANDIDATE_SHA]]`  
> **Do not fill metrics from memory.**  
> **Do not promote exploratory holdout numbers as final PASS.**  
> Replace every `[[PLACEHOLDER]]` before submission. Delete this callout box when finalizing.

---

## Cover / identity

| Field | Value |
|---|---|
| Project title | Enterprise LLM Security Framework — Lab-scale Guardrail Proxy for RAG |
| Candidate SHA | `[[CANDIDATE_SHA]]` |
| Report version | `[[REPORT_VERSION]]` |
| Author | `[[AUTHOR]]` |
| Institution | `[[INSTITUTION]]` |
| Date (UTC) | `[[REPORT_DATE_UTC]]` |
| Evaluation evidence sets used | `[[EVIDENCE_SET_LIST_AND_CLASSIFICATION]]` |

---

## 1. Executive summary

`[[EXECUTIVE_SUMMARY_3_TO_5_PARAGRAPHS]]`

Must state, in plain language:

1. What was built (lab PoC gateway + RAG + evaluation harness).  
2. What was evaluated and under which provider (mock).  
3. What is **not** claimed (production security, real-LLM parity).  
4. Status of holdout: if only exploratory evidence exists, say so explicitly.  
5. Main limitation bullets (synthetic data, mock provider, governance constraints).

---

## 2. Architecture

### 2.1 System overview

`[[ARCHITECTURE_PROSE]]`

Include: pipeline stages, GuardProfile, RAG retrieval, provider interface.

### 2.2 C0–C7 ablation matrix

| Config ID | Role | Notes |
|---|---|---|
| C0_all_on | Full guards | Primary baseline |
| C1…C7 | Ablations | `[[LIST_FROM_REGISTRY]]` |

### 2.3 Diagram

Insert diagram from `docs/phase12f/01_RELEASE_ARCHITECTURE.md` (Mermaid or text).

---

## 3. Threat model

### 3.1 In scope

`[[THREAT_MODEL_IN_SCOPE]]`

Suggested topics (edit to match project docs): prompt injection, indirect injection, jailbreak, leakage classes addressed by guards, evaluation integrity threats (wrong split, result rewrite, unauthorized holdout).

### 3.2 Out of scope

`[[THREAT_MODEL_OUT_OF_SCOPE]]`

Suggested: malicious local administrator, hostile in-process attacker, full OS adversary, production multi-tenant isolation.

### 3.3 Trusted-maintainer evaluation model

State that holdout authorization is a **procedural** gate for honest operator error, not a cryptographic enclave.

---

## 4. Benchmark methodology

### 4.1 Benchmark v2 identity

| Field | Value |
|---|---|
| Version | v2 |
| Manifest status | FINAL |
| Manifest SHA-256 | `[[BENCHMARK_MANIFEST_SHA256]]` |
| File count | 9 |
| Case counts (dev/val/holdout) | 30 / 30 / 60 (design) |
| Nature | Fully synthetic lab data |

### 4.2 Families and scopes

`[[FAMILY_AND_SCOPE_DESCRIPTION]]`

### 4.3 Freezing and contamination controls

`[[FREEZE_AND_CONTAMINATION_PROSE]]`

---

## 5. Evaluation governance

### 5.1 Split isolation

Describe development / validation / holdout separation and why holdout is not an ordinary `--split`.

### 5.2 Evidence classification used in this report

| Evidence set | Path / ID | Classification |
|---|---|---|
| `[[SET_1]]` | `[[PATH]]` | diagnostic / validation-closed / exploratory-holdout / governance-valid-holdout |
| `[[SET_2]]` | `[[PATH]]` | … |

### 5.3 Prior exploratory holdout (if mentioned)

If the post-`93ad09d` exploratory attempt is discussed:

- Classify as **POST-EXECUTION EXPLORATORY / DIAGNOSTIC EVIDENCE**.  
- State it is **not** final Phase 12E.4 PASS.  
- Do **not** use it as the primary results table unless governance remediation is documented and accepted by the maintainer and methodology auditor.

### 5.4 One-shot and no-rewrite rules

Summarize: no overwrite, no silent retry, preserve burned roots, new candidate after system change post-visibility.

---

## 6. Implementation

### 6.1 Components

`[[IMPLEMENTATION_COMPONENTS]]`

### 6.2 Mock Provider

Explain determinism and non-equivalence to commercial LLMs.

### 6.3 Metrics as implemented

| Metric / policy | Behavior |
|---|---|
| Primary rate | AOMR (as implemented) |
| Supported secondary | FPR (as implemented) |
| Min-n | `RATE_REPORTING_MIN_N = 10` (as implemented) |
| Interval | Wilson 95% without continuity correction (as implemented) |
| ABR / macro / F1 / p-values | Not used as metrics |
| Latency | Non-reportable under L2 (`latency_reportable=false`; p50/p95 null) |

Do not invent additional metrics.

---

## 7. Test and verification evidence

Paste **only live command outputs** (or summarized tables derived from them):

| Check | Command | Result |
|---|---|---|
| Focused verify | `[[CMD]]` | `[[PASS_COUNTS]]` |
| Full pytest | `[[CMD]]` | `[[PASS_COUNTS]]` |
| Freeze verify | `freeze_v2_benchmark.py verify` | `[[RESULT]]` |
| Git identity | `git rev-parse HEAD` | `[[SHA]]` |

Skipped tests and known warnings (e.g. Starlette/httpx deprecation; symlink skip) must be listed.

---

## 8. Aggregate results

### 8.1 Section gate

```text
IF evidence classification is not governance-valid for evaluation claims
THEN replace this entire section with:

  "No governance-valid aggregate evaluation table is reported.
   Diagnostic evidence, if any, is summarized qualitatively in Appendix D
   without numeric promotion to final claims."
```

### 8.2 Primary results table (only if governance-valid)

| Config | AOMR | FPR | Notes |
|---|---|---|---|
| C0 | `[[ ]]` | `[[ ]]` | |
| C1 | `[[ ]]` | `[[ ]]` | |
| … | `[[ ]]` | `[[ ]]` | |

### 8.3 Family / group rows

Report only when `n` meets policy; otherwise show raw counts / ineligible flags as emitted by the analyzer.

### 8.4 Latency

State non-reportable under L2. Do not invent p50/p95.

---

## 9. Limitations

See also `06_LIMITATIONS_AND_FUTURE_WORK.md`. Summarize:

`[[LIMITATIONS_SUMMARY]]`

---

## 10. Reproducibility

| Item | How to reproduce |
|---|---|
| Code | checkout `[[CANDIDATE_SHA]]` clean |
| Benchmark | materialize ignored JSONL; `freeze_v2_benchmark.py verify` |
| Env | `.venv` + `requirements.txt` |
| Windows | short basetemp |
| Evidence roots | external absolute paths; never reuse holdout roots |

Archive identity: `[[RELEASE_ARCHIVE_SHA256]]`

---

## 11. Ethics and claims control

### 11.1 Synthetic data

No real user data; synthetic lab corpus.

### 11.2 Prohibited claims checklist (must remain true)

- [ ] No production security guarantee  
- [ ] No real-LLM equivalence  
- [ ] No ABR/macro/F1/p-value metrics  
- [ ] No reportable latency under L2  
- [ ] Exploratory holdout not labeled as final PASS  

### 11.3 Dual-use

`[[BRIEF_DUAL_USE_STATEMENT]]`

---

## 12. Final decision

| Decision | Selection |
|---|---|
| Technical implementation acceptable for academic defense of PoC | `[[YES/NO]]` |
| Governance-valid holdout evaluation complete | `[[YES/NO]]` |
| Thesis primary claims limited to … | `[[SCOPE]]` |
| Maintainer sign-off | `[[NAME / UTC]]` |

**This template does not itself issue PASS.**

---

## Appendices (optional)

- Appendix A: GuardProfile boolean tables  
- Appendix B: Authorization field list (no secrets)  
- Appendix C: Command transcripts (sanitized)  
- Appendix D: Diagnostic-only evidence notes (clearly labeled)  
