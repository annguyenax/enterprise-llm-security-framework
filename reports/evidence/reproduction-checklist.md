# Reproduction Checklist

Run from the repository root in PowerShell. The commands create only local
environment, cache, log, and report artifacts.

## 1. Create and Activate the Virtual Environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Expected: FastAPI, Pydantic, Uvicorn, pytest, and genuine `httpx` are available.
Do not install `httpx2`; it is not a project dependency.

## 2. Run the Full Test Suite

```powershell
python -m pytest -q --basetemp="$env:TEMP\enterprise-llm-security-framework-pytest"
```

Expected for the current checked-in code: `82 passed`. A Starlette deprecation
warning may mention `httpx2`; it is non-blocking and does not require installing
that package. The system temporary directory is used because pytest cleanup of
a workspace-local basetemp can be denied by Windows ACLs in managed shells.

## 3. Start the Local Gateway

Terminal 1:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

Expected: local server at `http://127.0.0.1:8000`; Swagger UI at `/docs`.

## 4. Run the Smoke Test

Terminal 2:

```powershell
.\.venv\Scripts\Activate.ps1
.\scripts\smoke_test_gateway.ps1
```

Expected: health is `ok`, benign input is `allow`, malicious input is `block`,
mock provider metadata appears for benign chat, and `SMOKE TEST PASSED` prints.

## 5. Run Guarded Evaluation

```powershell
python scripts\run_evaluation.py
```

Expected: 40 cases, 40 passed, 0 failed, 0 false positives, 0 false negatives.
Artifacts are regenerated at `reports/evaluation/latest-evaluation.json` and
`.md`.

## 6. Run Baseline vs Guarded Comparison

```powershell
python scripts\run_evaluation.py --comparison
```

or:

```powershell
.\scripts\run_evaluation.ps1 -Comparison
```

Expected: baseline 5/40 with 35 false negatives and proxy 1.0000; guarded 40/40
with 0 false negatives and proxy 0.0000. Artifacts are regenerated at
`reports/evaluation/baseline-vs-guarded.json` and `.md`.

## 7. Check Evidence and Scope

```powershell
Get-Content reports\evaluation\latest-evaluation.md | Select-Object -First 25
Get-Content reports\evaluation\baseline-vs-guarded.md | Select-Object -First 30
git status --short
```

Confirm that `datasets/` and `redteam/` are unchanged. Report all measurements
as controlled synthetic benchmark results, not real-world detection rates.
