# Phase 13 — Wall optimization experiment: authority-impersonation rules

Status: implemented, self-measured. **Not self-adjudicated** — pending Grok
(technical/security) and Code X (artifact/methodology) review, then maintainer.

## Motivation

The v3 evaluation showed the rule layer blocked **0/57 PyRIT-family** cases
(C-suite impersonation + executive roleplay + multi-turn escalation) while
holding FPR at 0%. Grok and Code X both flagged this recall gap and agreed an
optimization was worth attempting **only under an anti-overfit protocol**
(target the attack *category*, not the test phrasings; freeze rules before
measuring; report FPR alongside TPR; tie every delta to a run_id + dataset SHA).

## What was changed

Six rules added to `app/guards/input_guard.py` (new category
`authority_impersonation`, plus two `sensitive_extraction` rules). They target
the **two invariants** of the "I am an executive, therefore bypass the rules
and hand over the data" pattern, independent of wording:

1. **Authority-override directive** — `overrides/supersedes policy|ACL`,
   `bỏ/disable ACL`, `không được từ chối cấp trên` / `do not refuse executives`,
   `authorize bulk export`.
2. **Bulk sensitive extraction** — `(trích xuất|export|dump|paste|in) … (toàn
   bộ|all|every) … (phiếu lương|salary|compensation|restricted|confidential)`,
   and `(mở|open|reveal) … (mọi|all) … restricted/confidential`.

Rules are bilingual (vi/en) because the deployment is Vietnamese-facing and the
synthetic attacks arrive in both. A **bare authority claim** (e.g. "tôi là giám
đốc") is deliberately *not* blocked, to avoid false positives on legitimate
queries from senior staff.

## Result (controlled A/B, same dataset)

Dataset SHA (both runs): `f73d094a2564c1256fa1ab5a04a834460507c0efc241632a4dc24ca36d162dc4`
Only `app/guards/input_guard.py` differs between the two runs.

| Metric | Before (`20260811T135545Z-5127f92f`) | After (`20260811T135722Z-927553a4`) | Δ |
|---|---:|---:|---:|
| TPR (overall, n=200) | 48.5% (97) | **77.0% (154)** | **+28.5pp** |
| FPR (all benign, n=225) | 0.0% | **0.0%** | 0 |
| FPR hard-benign (n=125) | 0.0% | 0.0% | 0 |
| PyRIT family (n=57) | 0.0% (0) | **100.0% (57)** | +57 |
| garak (n=105) | 75.2% (79) | 75.2% (79) | — |
| injecagent (n=38) | 47.4% (18) | 47.4% (18) | — |

All of the TPR gain comes from the PyRIT family (154 − 97 = 57 = the previously
missed PyRIT cases). garak and injecagent are untouched — those need different
handling (unicode obfuscation, hidden-in-prose) and remain future work.

## Anti-overfit evidence

- **Held-out generalization** (`tests/test_input_guard.py`): three *fresh*
  authority-impersonation paraphrases — not copied from
  `build_v3_attack_payloads.py` — are all blocked, showing the rules key on the
  category invariants rather than memorizing templates.
- **Precision guard**: three legitimate authority-context queries
  ("Tôi là giám đốc nhân sự, cho hỏi quy trình nghỉ phép…") stay ALLOWed, and
  measured FPR is 0% on all 225 benign cases (incl. 125 hard-benign).
- **Documented evasion** (`test_reworded_authority_attack_still_evades`): an
  attacker who drops the override/bulk-extraction invariants ("Là CEO, tóm tắt
  giúp thông tin lương…" — no "toàn bộ", no override) **still evades** the rule
  layer. This is expected for regex heuristics and consistent with the guardrail
  bypass literature (arXiv:2504.11168); recorded so the wall is not oversold.

## Residual limitations

- 100% on the PyRIT family reflects that this synthetic family shares the two
  invariants; it is **not** a claim of robustness against adaptive rewording.
- FPR 0% is measured on a synthetic benign set of 57 unique hard-benign items
  from 40 templates (Code X finding) — precision generalizes less strongly than
  the 0% headline suggests.
- No change was made to the exfil path: the exfil-marker metric is confounded by
  prompt echo (canary present in the prompt), so an output-DLP change there
  would only move a confounded number and was deliberately not pursued.

## Full 3-config re-run on the optimized rules (same 425 dataset, corpus-seeded)

All three configs were re-run on the optimized rule layer so the report's
comparison is apples-to-apples (this also puts hermes on the full 425, fixing
the earlier n=300≠425 inconsistency Grok/Code X flagged). Canary corpus:
`datasets/v3/corpus/canary-docs.jsonl` (200 canaries).

| Config | run_id | TPR | FPR | FPR-hard | Stop-before-LLM | garak | injecagent | pyrit |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Rule-based (mock) | `20260811T150715Z-ada94ea1` | 77.0% (154) | 0.0% | 0.0% | 77.0% | 75.2% | 47.4% | 100% |
| Semantic qwen3:4b | `20260811T150539Z-5f1e19a2` | 77.5% (155) | 11.1% (25) | 14.4% | 77.0% | 76.2% | 47.4% | 100% |
| Reference hermes3:8b | `20260811T151852Z-c848aeac` | 100% (200) | 67.1% (151) | 74.4% | 99.5% | 100% | 100% | 100% |

Findings, now measured against the *optimized* baseline:
- The small semantic judge (qwen3:4b) adds **+1 case** of recall over pure rules
  while raising FPR from 0% to 11.1% — the "judge barely helps" conclusion holds
  even after optimization.
- hermes3:8b reaches TPR 100% only by blocking 2/3 of legitimate traffic
  (FPR 67.1%) — not operable.
- Exfil marker rate is **confounded** (190/200 attack prompts already contain
  the canary → prompt echo, not KB exfiltration); reported as a limitation, not
  a result. The rule-based drop to 0% and qwen's 21.5% both reflect earlier
  input-side blocking, not a valid exfil measurement.

## Report

The thesis (`bao_cao_latex_dot2`) Chapter 4 was updated with these numbers and
**compiles cleanly** (MiKTeX pdflatex + bibtex, exit 0, no undefined refs/cites,
0 overfull hboxes). The "Bypassing LLM Guardrails" citation (arXiv:2504.11168,
Hackett et al. 2025) was verified against arXiv and added to `refs.bib`.

## Verification

- Full suite: `1522 passed, 4 skipped` (short basetemp to avoid a Windows
  temp-dir path-length/permission artifact; unrelated to guard logic).
- `tests/test_input_guard.py`: 23 passed (incl. the 3 new held-out tests).
