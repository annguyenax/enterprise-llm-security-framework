# Shield AI — Enterprise LLM Security Framework

> A lab-scale **LLM Security Gateway** that sits in front of a Retrieval-Augmented
> Generation (RAG) application and enforces a defense-in-depth guard chain against
> prompt injection, indirect injection, jailbreaks, and data leakage.

![Status](https://img.shields.io/badge/status-PoC%20·%20lab--scale-6b7a8d)
![Python](https://img.shields.io/badge/python-3.11%2B-0e7c86)
![API](https://img.shields.io/badge/API-FastAPI-0e7c86)
![Tests](https://img.shields.io/badge/tests-pytest%20suite-15803d)
![Data](https://img.shields.io/badge/data-100%25%20synthetic-c2410c)
![License](https://img.shields.io/badge/license-academic-lightgrey)

**Đề tài:** *Nghiên cứu và triển khai cơ chế Guardrails bảo vệ hệ thống RAG trước
tấn công Prompt Injection và rò rỉ dữ liệu.*

This is a university graduation-internship **proof-of-concept**. It is built and
evaluated with **100% synthetic data** and **locally-hosted models**, and it makes
**no production or real-world security guarantees**.

---

## Key results

Measured on a synthetic evaluation set of **425 cases** (200 attacks inspired by
garak / PyRIT / InjecAgent + 225 benign, including 125 *hard-benign* traps). All
numbers are lab-scale and do not generalize to production.

| Configuration | TPR (recall) | FPR | Notes |
|---|:---:|:---:|---|
| **Rule-based guard** | **97.0%** | **0.0%** | Deterministic; balanced operating point |
| + Semantic Judge (`qwen3:4b`) | 100% | 26.7% | Opt-in, **default OFF** — precision ROI negative |
| Reference (`hermes3:8b`) | 100% | 66.7% | Over-blocks — not operable |

- **Clean-canary A/B demo:** with a secret canary seeded **only in the knowledge
  base**, the unguarded path leaked it in **12/18** trials while the guarded path
  leaked **0/18** (paired demo measured on the two-path setup; small `n`, not a
  statistical claim).

**Progressive rule ablation** — recall improved across three targeted, non-overfit
steps while FPR stayed at 0% (same 425 cases):

| Step | TPR | FPR | PyRIT | garak | InjecAgent |
|---|:---:|:---:|:---:|:---:|:---:|
| Baseline | 48.5% | 0.0% | 0% | 75.2% | 47.4% |
| + Anti-impersonation | 77.0% | 0.0% | 100% | 75.2% | 47.4% |
| + Unicode normalization | 81.5% | 0.0% | 100% | 83.8% | 47.4% |
| **+ Anti-indirect-injection** | **97.0%** | **0.0%** | **100%** | **94.3%** | **100%** |

**Confusion matrix** — rule-based, after optimization (`n = 425`):

|  | Blocked | Answered |
|---|:---:|:---:|
| **Attacks (200)** | 194 (TP) | 6 (FN) |
| **Benign (225)** | 0 (FP) | 225 (TN) |

> **Honest scope.** FPR 0% holds only on the synthetic benign set and does not
> generalize out-of-distribution. `100%` on the PyRIT family reflects its current
> template set (paraphrased evasions still bypass the rules). Latency is not
> reported (methodology decision). See [Limitations](#limitations--scope).

---

## Architecture

<p align="center">
  <img src="docs/report-figures/fig-kien-truc.png" width="900" alt="System architecture: user to gateway to guard chain to hybrid retrieval to LLM to controlled response">
</p>
<p align="center"><em>End-to-end request flow — FastAPI gateway → guard chain → hybrid retrieval → LLM → controlled response.</em></p>

Guards follow a **fail-closed** principle (the strictest decision wins) and wrap the
RAG pipeline at three points — input, retrieved context, and output. **Five guard
modules** live in `app/guards/` (Input · Provenance · RAG Context · DLP · Output),
plus **ACL/RBAC** enforced before retrieval and an optional Semantic Judge
(default OFF). Input is normalized (NFKC, zero-width stripping, homoglyph folding)
before rule matching to defeat Unicode evasion.

### Fail-closed decision flow

<p align="center">
  <img src="docs/report-figures/fig-phong-thu.png" width="560" alt="Fail-closed guard decision flow across Input, RAG Context, and Output/DLP guards">
</p>
<p align="center"><em>At every stage a Block/Reject stops the pipeline with a safe refusal; Allow/Sanitize continues to the next guard — the strictest decision wins.</em></p>

### Threat model

<p align="center">
  <img src="docs/report-figures/fig-threat-model.png" width="900" alt="Three attack surfaces mapped to defense guards">
</p>
<p align="center"><em>Three attack surfaces (OWASP LLM01 / LLM04 / LLM02) and the guard that defends each.</em></p>

### Retrieval with access control

<p align="center">
  <img src="docs/report-figures/fig-rag-rbac.png" width="900" alt="Hybrid retrieval with role-based access control">
</p>
<p align="center"><em>Role/department ACL is applied <strong>before</strong> retrieval; BM25 (keyword) and cosine-embedding (numpy) results are fused by Reciprocal Rank Fusion.</em></p>

---

## Features

- **Defense-in-depth guard chain** with a fixed severity order and fail-closed decisions.
- **Input normalization** (NFKC, zero-width stripping, Cyrillic→Latin homoglyph folding) to defeat Unicode evasion before rule matching.
- **Role/department access control (RBAC)** applied *before* retrieval, independent of content guards.
- **Hybrid retrieval:** BM25 (SQLite FTS5) + `float32` embeddings scored via a single `numpy` matrix multiply, fused with Reciprocal Rank Fusion.
- **Output DLP** for API keys, PEM blocks, bearer tokens, PII, and canary markers.
- **Deterministic, offline evaluation:** a Mock Provider and local models via Ollama — no paid API, no external network on the main path.
- **Provenance-stamped runs:** every evaluation records commit, model, config, and dataset hash for reproducibility.
- **Independently-governed 120-case benchmark** (`datasets/v2/`), SHA-256 frozen. Governance-valid holdout execution is not authorized. The 12E.3 closure recorded the holdout as not run; a later exploratory technical attempt is recorded in `docs/final/00_FINAL_STATUS.md` and is not a final or authorized result. See the reconciliation table in Evaluation.

---

## Quick start

```bash
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1   |   macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --reload      # then open http://127.0.0.1:8000/docs
pytest -q                          # run the test suite
```

The main path is **offline by default** (deterministic Mock Provider). Local
models run via [Ollama](https://ollama.com) in three distinct roles: RAG
generation (`qwen3:4b-instruct`), embeddings (`nomic-embed-text`), and — only
when explicitly enabled with `SEMANTIC_GUARD_USE_LLM=1` — the optional Semantic
Judge (`qwen3:4b`, the configuration evaluated in the results above).

**Reproduce the results:**

```bash
python scripts/run_v3_evaluation.py     # 425-case security evaluation → reports/v3/<run-id>/
python scripts/run_demo_ab_paired.py    # clean-canary A/B demo (guarded vs unguarded)
```

---

## Repository structure

```text
app/                    FastAPI gateway, guard chain, retrieval, RBAC workspace
  guards/               input · provenance · rag · dlp · output · acl · semantic
  retrieval/            SQLite FTS5/BM25 + ACL-aware retriever
  workspace/            RBAC store, hybrid retrieval, business-document seed
datasets/               synthetic corpora + v2 benchmark (SHA-256 frozen)
scripts/                evaluation runners, benchmark build/freeze, validators
tests/                  pytest unit + integration suite
chatbot/                minimal demo UI (guarded vs unguarded)
redteam/                synthetic attack prompt manifest
reports/                evaluation runs, evidence, A/B artifacts
docs/                   architecture, methodology, decisions (ADRs), diagrams
baocaodot2_fixed.zip    compiled thesis report (PDF + LaTeX source)
docs/report-figures/    report diagrams referenced by this README
```

---

## Evaluation & methodology

Two complementary datasets support the claims:

- **425-case effectiveness set** — measures TPR / FPR / Stop-before-LLM / exfil on
  three guard configurations (rule-based, Semantic Judge `qwen3:4b`, reference `hermes3:8b`).
- **Benchmark V2 (120 cases)** — 23 scenario families, 30/30/60 dev/val/holdout
  split, 172-document corpus, three independent content banks per family for
  contamination control, deterministic build, SHA-256 frozen. The 60-case holdout
  has no governance-valid execution and no authorization. The 12E.3 closure
  recorded it as not run. A later exploratory technical attempt is recorded
  in `docs/final/00_FINAL_STATUS.md` and is not a final PASS. Line citations
  are in the reconciliation table below.

### Document status reconciliation (2026-11-07)

Scope: status meaning only. Base `ff047623a265af3a99fe716b561de7eac3cc830f` (2026-08-16 10:38:56 +0700). This note does not re-run tests, does not change benchmark figures, does not open holdout cases or labels, and does not sign holdout authorization. Analyzer presence is not completion. Missing bytes stay UNKNOWN.

| Layer | What is true | Source and time | This 2026-11-07 pass |
|---|---|---|---|
| Analyzer implementation | `scripts/analyze_v2_results.py` is in the tree. Presence is not completion. | `ff047623:scripts/analyze_v2_results.py:1`. First commit `47bd393d1a7ac9106ce5a64bb8edd736615ad038` (2026-07-14 18:47:44 +0700). Alignment commit `c6d91c78e11009e96a76db08c0dfbb710504c227` (2026-07-14 20:20:37 +0700). | Path observed. Script not executed. |
| 12E.3 validation execution record | Line 6 names implementation `c6d91c78e11009e96a76db08c0dfbb710504c227`. Line 7 records `provider_id=mock` and `split=validation`. Line 16 records attempt 2 as eight complete validation runs and one analysis publication. Line 9 says that audit did not execute the runner or analyzer. Line 70 says the result artifacts are not tracked. Bytes in this worktree: UNKNOWN. | `94eafc686cb03262f77d7bd3572ee6557f7d6a98:docs/modernization-ai-reviews/code-x-phase-12e-3-validation-artifact-closure.md` lines 6, 7, 9, 16, 70. Absent at `ff047623` after `24e70831f077d2430387007a46148c99e5b5dc6d` (2026-08-15 13:42:45 +0700). | Not re-run. Not a new PASS. |
| Historical “12E.3 CLOSED PASS” sentence | The block headed 2026-07-19 records 12E.3 CLOSED PASS and validation artifact closure PASS, with the review dossier kept in git history. This pass does not re-adjudicate that sentence. | `ff047623:CLAUDE.md:29` and `:37-39` | Preserved as history. |
| Holdout at the 12E.3 closure | The same audit records that holdout execution was not authorized and was not executed, and that the audit does not authorize holdout. | `94eafc686cb03262f77d7bd3572ee6557f7d6a98:docs/modernization-ai-reviews/code-x-phase-12e-3-validation-artifact-closure.md` lines 63 and 65 | Preserved. Not an authorization. |
| Later exploratory holdout | Classification is `POST-EXECUTION EXPLORATORY / DIAGNOSTIC EVIDENCE ONLY`. Fully completed human adjudication before execution is recorded as No (governance gap). Final Phase 12E.4 PASS must not be claimed. Attempt bytes were not opened: UNKNOWN. | `ff047623:docs/final/00_FINAL_STATUS.md:63`, `:70`, and `:71`. Package commit `4da5d8ccc9e52da3384f3e8c6982bfdd6ea21857` (2026-07-24 14:23:42 +0700). Last change before this reconciliation: `8a5db083592473c8576090b691104b43b5000a73` (2026-07-25 10:05:14 +0700). | Not re-opened. No metrics added. |
| Authorization | This reconciliation signs no holdout authorization. The base rule says the maintainer is the only person who approves holdout. | `ff047623:CLAUDE.md:63` | Unchanged rule. No signature added. |

Every reported figure traces to an artifact under `reports/` produced by a
provenance-stamped run. See [`docs/`](docs/) for the architecture, benchmark
methodology, and Architecture Decision Records.

---

## Limitations & scope

- **Lab-scale PoC** — no production or enterprise-readiness claim.
- **Synthetic data and local models only** — never evaluated on a real commercial LLM or real enterprise data.
- **FPR 0% does not generalize** beyond the synthetic benign set; some legitimate out-of-distribution queries can still be blocked.
- **Residual recall gap:** 6/10 direct knowledge-base exfiltration prompts pass the input rules (an Input-Guard limitation; cross-user access control is the separate RBAC layer's job, measured independently).
- **A/B demo is qualitative** — system-level, repetitions are not statistically independent, small `n`.
- The rule layer is **not adaptive**: paraphrased attacks that drop the targeted lexical invariants can still evade it.

---

## Team

| Name | Student ID | Class |
|---|---|---|
| Nguyễn Văn An | N22DCAT001 | D22CQAT01-N |
| Lê Đình Nghĩa | N22DCAT038 | D22CQAT01-N |

**Supervisor:** ThS. Nguyễn Hoàng Thanh · Khoa Công nghệ Thông tin 2, Học viện
Công nghệ Bưu chính Viễn thông (PTIT).

---

## References & standards

The attack families and defenses are *inspired by* — not copied from — established
work: OWASP Top 10 for LLM Applications, OWASP LLMSVS, and NIST AI 600-1 for risk
framing; Perez & Ribeiro (2022) and Greshake et al. (2023) for prompt/indirect
injection; PoisonedRAG (Zou et al., 2024) and InjecAgent (Zhan et al., 2024) for
RAG poisoning; Llama Guard (Inan et al., 2023) and NeMo Guardrails (Rebedea et al.,
2023) for defenses; and Hackett et al. (2025) on guardrail evasion. Full citations
are in [`docs/references.bib`](docs/references.bib).

## License

Academic project — license to be determined by university/institution policy.
