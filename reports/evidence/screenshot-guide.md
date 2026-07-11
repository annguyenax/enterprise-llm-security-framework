# Manual Screenshot Guide

Capture screenshots manually after reproducing the commands. Crop out usernames,
unrelated folders, tokens, local paths that should not be published, and any
private IDE content.

| Screenshot | What should be visible | Suggested source | Caution |
|---|---|---|---|
| Full pytest result | `82 passed` and command used. | PowerShell after `python -m pytest -q --basetemp="$env:TEMP\enterprise-llm-security-framework-pytest"`. | Keep the Starlette warning visible or mention it in the caption; do not imply zero warnings. |
| Smoke test | `SMOKE TEST PASSED` plus benign/malicious summary. | `scripts/smoke_test_gateway.ps1`. | Server must already be local; no external API is involved. |
| Guarded evaluation | 40 cases, 40 passed, 0 FP, 0 FN. | `python scripts/run_evaluation.py`. | Caption as controlled synthetic benchmark only. |
| Baseline comparison | Baseline and guarded summary table. | `reports/evaluation/baseline-vs-guarded.md` preview. | State that baseline is always-allow decisions, not LLM quality. |
| Blocked API attack | Input decision and final decision both `block`; provider/output absent. | Demo script malicious gateway call. | Use only the synthetic prompt shown in the demo. |
| Sanitized RAG context | `sanitize`, matched hidden rule, clean surrounding text, preserved metadata. | Demo script RAG endpoint call. | Ensure hidden instruction is absent from sanitized output. |
| Repository structure | `app/`, `tests/`, `datasets/`, `redteam/`, `reports/evidence/`. | IDE Explorer or `tree` output. | Avoid exposing unrelated local directories. |
| Git tag/commit | Final branch, commit hash, and release/tag name after the team creates them. | GitHub or `git log -1 --oneline`. | A tag does not exist merely because this guide mentions it; create it through the team's normal review process. |

Recommended captions should include the phase, command, date of capture, and the
phrase “controlled synthetic benchmark” for evaluation screenshots.
