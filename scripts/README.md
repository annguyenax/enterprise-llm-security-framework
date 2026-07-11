# scripts/

Offline development, inspection, smoke-test, and evaluation helpers.

## Evaluation

- `run_evaluation.py` validates and evaluates `redteam/prompts.jsonl` directly
  against the guards, then writes JSON and Markdown artifacts under
  `reports/evaluation/`.
- `run_evaluation.ps1` is the PowerShell wrapper for the same offline run.

```powershell
python scripts/run_evaluation.py
.\scripts\run_evaluation.ps1
```

Baseline versus guarded comparison:

```powershell
python scripts/run_evaluation.py --comparison
.\scripts\run_evaluation.ps1 -Comparison
```

## Other Helpers

- `run_dev.ps1` starts the local FastAPI application.
- `smoke_test_gateway.ps1` exercises health, guards, and gateway responses.
- `inspect_dataset.py` / `inspect_dataset.ps1` inspect the synthetic corpus.
- `test_rag_guard.ps1` performs a manual RAG Guard smoke test.

No evaluation script calls an LLM API, vector database, or external service.
Any future paid API call still requires explicit approval under
`AGENT_RULES.md` rule 4.
