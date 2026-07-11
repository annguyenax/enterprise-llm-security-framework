# Project Evidence Index

This index packages reproducible evidence for internship report writing and the
local demo. The project is a lab-scale proof of concept evaluated only on a
controlled synthetic benchmark.

## Project Overview

| File path | What it proves | How to reproduce/check | Limitation or caution |
|---|---|---|---|
| `README.md` | Current implemented phases, local commands, and explicit non-goals. | Read the Phase 4-8 sections and follow the linked commands. | Use `TASK_BOARD.md` as the authoritative source for task-level status. |
| `PROJECT_PLAN.md` | Original MVP objective, roadmap, and non-goals. | Compare roadmap phases with `TASK_BOARD.md`. | Planning document; some target technologies remain unimplemented. |
| `TASK_BOARD.md` | Phase-by-phase implementation status and verification evidence. | Check Done/In Review rows against linked files and commands. | Manual research/report tasks outside the implemented gateway remain open. |

## Architecture Evidence

| File path | What it proves | How to reproduce/check | Limitation or caution |
|---|---|---|---|
| `docs/diagrams/architecture.md` | Target component boundaries and guard ordering. | Render the Mermaid diagram; compare module table with `app/`. | Written as target/planning architecture; vector store and external provider nodes are not implemented. |
| `docs/diagrams/data-flow.md` | Intended request, guard, logging, and ingestion flows. | Render Mermaid sequence/flow diagrams and compare with `app/services/gateway.py`. | Retrieval/vector-store portions remain planning-level. |
| `app/services/gateway.py` | Implemented Input -> optional RAG -> mock provider -> Output -> audit pipeline and stopping decisions. | Run gateway tests or the smoke script. | Uses caller-supplied context and a deterministic mock provider. |

## Threat Model Evidence

| File path | What it proves | How to reproduce/check | Limitation or caution |
|---|---|---|---|
| `docs/diagrams/threat-model.md` | STRIDE-oriented assets, trust boundaries, threats, and mitigations considered during design. | Review threat rows against guard categories and audit logging. | Threat coverage is qualitative and does not establish formal assurance. |
| `redteam/attack-categories.md` | Mapping between synthetic attack categories and expected guard behavior. | Cross-check category names with `redteam/prompts.jsonl`. | Synthetic taxonomy is intentionally small and not exhaustive. |

## Dataset Evidence

| File path | What it proves | How to reproduce/check | Limitation or caution |
|---|---|---|---|
| `docs/dataset/dataset-validation-report.md` | Structural validation of 5 clean documents, 5 poisoned documents, and 40 prompts; no detected real PII/secrets in the controlled corpus. | Run `python scripts/inspect_dataset.py` and inspect frozen source files. | Automated validation is not a substitute for the still-pending full human review. |
| `docs/dataset/dataset-methodology.md` | Synthetic-data rationale, provenance, intended use, and scope boundaries. | Compare methodology with `datasets/` and `redteam/`. | The corpus cannot support real-world prevalence or generalization claims. |
| `redteam/prompts.jsonl` | Frozen 40-case prompt benchmark and expected decisions. | Run `python scripts/run_evaluation.py`. | Exact-label benchmark; labels were not changed during calibration. |

## Guard Implementation Evidence

| File path | What it proves | How to reproduce/check | Limitation or caution |
|---|---|---|---|
| `app/guards/input_guard.py` | Explainable rules for prompt injection, jailbreak, extraction, RAG manipulation, and tool misuse. | Run `pytest tests/test_input_guard_calibration.py -q`. | Regex rules can miss semantic, encoded, multi-turn, or unseen variants. |
| `app/guards/rag_guard.py` | Detection-only normalization, targeted context sanitization, metadata preservation, and severity aggregation. | Run `pytest tests/test_rag_guard.py -q`. | No retrieval engine or semantic classifier is present. |
| `app/guards/output_guard.py` | Rule-based output leakage checks and redaction. | Run `pytest tests/test_output_guard.py -q`. | Evaluated with deterministic/synthetic outputs, not real model completions. |
| `reports/evaluation/failure-triage.md` | Root-cause analysis and narrow fixes for the five initial false negatives. | Compare initial failures with regenerated latest report and calibration tests. | Calibration improves the frozen suite; it does not prove broad generalization. |

## Provider Adapter Evidence

| File path | What it proves | How to reproduce/check | Limitation or caution |
|---|---|---|---|
| `app/services/llm_provider.py` | Typed provider contract, fail-closed factory, and deterministic offline mock implementation. | Run `pytest tests/test_llm_provider.py tests/test_gateway_provider.py -q`. | No external provider SDK, API key, or real LLM call is implemented. |
| `app/core/config.py` | Safe default provider/model configuration without requiring `.env`. | Inspect defaults or run provider configuration tests. | Timeout is configuration metadata for future real providers. |

## Evaluation Evidence

| File path | What it proves | How to reproduce/check | Limitation or caution |
|---|---|---|---|
| `app/services/evaluation_runner.py` | Offline JSONL validation, guarded/baseline modes, controlled metrics, and deterministic report generation. | Run evaluation and comparison commands below. | Calls guards directly; does not measure LLM output quality or latency. |
| `reports/evaluation/latest-evaluation.json` | Machine-readable guarded results and per-case rule/reason evidence. | Regenerate with `python scripts/run_evaluation.py`. | 40/40 is scoped only to the frozen synthetic suite. |
| `reports/evaluation/latest-evaluation.md` | Human-readable guarded summary: 40/40, 0 FP, 0 FN after Phase 7.1. | Regenerate and compare the summary. | Not a real-world detection rate or security guarantee. |

## Baseline Comparison Evidence

| File path | What it proves | How to reproduce/check | Limitation or caution |
|---|---|---|---|
| `reports/evaluation/baseline-vs-guarded.json` | Machine-readable comparison: always-allow baseline versus current guarded decisions. | Run `python scripts/run_evaluation.py --comparison`. | Baseline models decisions only; it is not a real LLM quality baseline. |
| `reports/evaluation/baseline-vs-guarded.md` | Baseline 5/40 and guarded 40/40 table with scoped interpretation. | Regenerate using either comparison command. | Attack-success proxy is decision-based, not harmful-output ASR. |

## Test Evidence

| File path | What it proves | How to reproduce/check | Limitation or caution |
|---|---|---|---|
| `tests/` | Unit/integration coverage for guards, provider, routes, audit logging, evaluation, calibration, and corpus immutability. | `.venv\Scripts\python.exe -m pytest -q --basetemp="$env:TEMP\enterprise-llm-security-framework-pytest"` | Current verified result is 82 passed with one Starlette deprecation warning; dependency versions may change warnings. |
| `tests/test_evaluation_runner.py` | All 40 cases, baseline/guarded comparison, report output, and SHA-256 immutability of frozen benchmark files. | Run the module directly with pytest. | Tests correctness on the checked-in synthetic corpus only. |

## Demo Commands

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
# In a second terminal:
.\scripts\smoke_test_gateway.ps1
python scripts\run_evaluation.py
python scripts\run_evaluation.py --comparison
```

For the timed narrative and individual API calls, use
`reports/evidence/demo-script.md`. For clean setup and expected outputs, use
`reports/evidence/reproduction-checklist.md`.
