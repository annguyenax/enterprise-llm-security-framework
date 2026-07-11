# Report Integration Plan

Official title (must remain unchanged):

> Nghiên cứu và triển khai cơ chế Guardrails bảo vệ hệ thống RAG trước tấn công Prompt Injection và rò rỉ dữ liệu

The title is already defined exactly in `report-latex-template/thesis.sty` as
`\titlethesis`. Do not edit it during integration.

## Template Status and Integration Rule

The LaTeX directory preserves the official structure, but several chapter files
still describe an early periodic-report state (for example, statements that no
application code or measured results exist). Do not treat those passages as
current evidence. Integrate section by section, preserve template commands and
page structure, and replace stale project-status prose only after team review.

## Section-to-Evidence Map

| Report section | Target LaTeX location | Primary project evidence | Integration guidance and caution |
|---|---|---|---|
| Introduction | `chapters/chap-0.phan-mo-dau.tex` | `PROJECT_PLAN.md`; `reports/evidence/report-ready-summary.md` sections Mục tiêu/Phạm vi | Keep the problem statement and PoC framing. Do not imply a production deployment or complete RAG system. |
| Related work / background | `chapters/chap-1-background.tex` | `docs/research/related-work.md`; OWASP/LLMSVS docs under `docs/research/`; `refs.bib` | Use only sources the team has personally verified/read to the required level. Do not invent or upgrade citation claims. |
| System architecture | `chapters/chap-2-method.tex` | `docs/diagrams/architecture.md`; `docs/diagrams/data-flow.md`; `app/services/gateway.py`; evidence index Architecture section | Separate target architecture from implemented architecture. Mark vector retrieval/external provider as unimplemented; describe caller-supplied context and mock provider. |
| Threat model | `chapters/chap-2-method.tex` threat-model subsection | `docs/diagrams/threat-model.md`; `redteam/attack-categories.md` | Present STRIDE ratings as qualitative design judgments, not measured risk probabilities or formal assurance. |
| Dataset and red-team benchmark | `chapters/chap-3.tex` or a reviewed dataset subsection | `docs/dataset/dataset-methodology.md`; `dataset-validation-report.md`; `source-mapping.md`; frozen `datasets/` and `redteam/` | State 5 clean documents, 5 poisoned documents, and 40 prompts. State synthetic-only scope and pending full manual corpus review. |
| Guard implementation | `chapters/chap-3.tex` implementation subsection | `app/guards/input_guard.py`; `rag_guard.py`; `output_guard.py`; `reports/evaluation/failure-triage.md` | Explain rule categories, shared decision order, targeted sanitization, and Phase 7.1 calibration. Include regex/generalization limitations. |
| Provider adapter | `chapters/chap-3.tex` implementation subsection | `app/services/llm_provider.py`; `app/core/config.py`; provider tests | Describe typed adapter and deterministic offline mock only. Explicitly state no real provider SDK, key, network call, or model response. |
| Evaluation method | `chapters/chap4.tex` methodology subsection | `app/services/evaluation_runner.py`; `docs/evaluation/evaluation-plan.md`; `metrics-definition.md`; reproduction checklist | Explain direct-guard execution, exact-label comparison, FP/FN definitions, frozen source, and deterministic reports. Do not call proxy metrics end-to-end ASR. |
| Results | `chapters/chap4.tex` results subsection | `latest-evaluation.json/.md`; `failure-triage.md`; full pytest evidence | Report initial 35/40 and five FN, then calibrated 40/40 on the unchanged suite. Always attach the controlled-synthetic-benchmark qualifier. |
| Baseline comparison | `chapters/chap4.tex` comparison subsection | `baseline-vs-guarded.json/.md` | Report baseline 5/40 and guarded 40/40. Define baseline as always-allow decisions, not LLM response quality. |
| Limitations | `chapters/chap4.tex` and `chapters/conclusion.tex` | `report-ready-summary.md` Hạn chế; evidence cautions | Include regex semantics, small synthetic corpus, calibration bias, no real LLM, no vector DB/retrieval, no latency or real-world outcome measurement. |
| Future work | `chapters/conclusion.tex` | `report-ready-summary.md` Hướng phát triển; open `TASK_BOARD.md` items | Keep future work clearly unimplemented: independent holdout data, semantic classifier, real provider approval/key management, retrieval/vector evaluation, latency, manual review. |

## Required Stale-Content Review

Before final PDF compile, search the template and manually resolve these claims:

```powershell
rg -n "chưa có mã nguồn|chưa cài đặt package|chưa có bất kỳ số liệu|Chưa bắt đầu|dự kiến triển khai" report-latex-template
```

Known high-priority files include `chapters/chap-3.tex`, `chapters/chap4.tex`,
`chapters/conclusion.tex`, and `pages/group-work-plan.tex`. Replace status prose
with verified evidence; preserve any passage that is explicitly historical and
label it by reporting period.

## Tables and Figures to Prepare

1. Export implemented architecture and data-flow diagrams with captions that
   distinguish unimplemented target nodes.
2. Add a dataset composition table (5 clean, 5 poisoned, 40 prompts).
3. Add guarded evaluation and baseline comparison tables from generated JSON.
4. Add selected screenshots listed in `screenshot-guide.md`.
5. Cite each figure/table source as repository-generated evidence and record the
   command/date used to reproduce it.

## Integration Order

1. Freeze a reviewed branch/commit and regenerate evaluation artifacts.
2. Confirm citations and official title.
3. Integrate architecture, implementation, and dataset sections.
4. Integrate evaluation/results tables directly from generated artifacts.
5. Replace stale early-phase status statements.
6. Insert reviewed screenshots/diagrams.
7. Compile PDF, resolve LaTeX warnings/errors, and proofread Vietnamese.
8. Obtain supervisor review before tagging the final submission.

## Acceptance Checklist

- Official title remains byte-for-byte unchanged.
- Every numerical claim points to a generated artifact or reproducible command.
- Every `40/40` statement says controlled synthetic benchmark.
- No passage claims real LLM, vector database, embeddings, or retrieval exists.
- Baseline is defined as always-allow decisions.
- Template compiles and table/figure references resolve.
- Supervisor-reviewed PDF and final commit/tag are recorded.
