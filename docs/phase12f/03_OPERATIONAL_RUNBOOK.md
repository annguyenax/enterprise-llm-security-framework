# Phase 12F — Operational Runbook

**Base candidate:** `93ad09ddea90eb9712e82f3df5beacbd94399b9a`  
**Purpose:** operator procedures for verify, evidence inventory, and release prep  
**Holdout:** not authorized by this document  

Commands that depend on tooling expected from other Phase 12F branches are marked:

> **EXPECTED AFTER INTEGRATION**

Do not pretend unmerged tools already exist on this documentation branch.

---

## 0. Safety rules (always)

1. Prefer a **clean** worktree at an exact SHA.  
2. Do **not** modify frozen benchmark bytes.  
3. Do **not** run holdout without a human-issued active authorization.  
4. Do **not** run `validate_v2_benchmark.py` or `build_v2_benchmark.py` as holdout **preclaim** (semantic processing). Preclaim freeze identity is **byte-level** only.  
5. Do **not** overwrite evidence roots.  
6. Do **not** use `--force`.  
7. Do **not** invent metrics.  
8. On Windows, use **short** external basetemp paths for large pytest runs.

---

## 1. Fresh clone / worktree setup

### 1.1 Clone (or use existing primary)

```powershell
# TEMPLATE — DO NOT RUN until you intend to set up a machine
git clone <REPO_URL> D:\path\to\enterprise-llm-security-framework
cd D:\path\to\enterprise-llm-security-framework
git checkout 93ad09ddea90eb9712e82f3df5beacbd94399b9a
```

### 1.2 Documentation worktree (example)

```powershell
# TEMPLATE
git -C D:\path\to\primary worktree add -b phase-12f-grok-documentation D:\p12f-grok 93ad09ddea90eb9712e82f3df5beacbd94399b9a
```

### 1.3 Python environment

```powershell
# TEMPLATE
cd <REPO_ROOT>
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Use `.venv\Scripts\python.exe` explicitly. Do not install `httpx2` (typosquat decoy; Starlette may warn).

---

## 2. Materialize frozen artifacts

Observed issue: `*.jsonl` is gitignored; worktrees may lack frozen JSONL files.

### 2.1 Inventory required nine paths

From FINAL manifest under `datasets/v2/manifests/benchmark-v2-manifest.json` (status must be `final`):

- cases/development.jsonl, cases/validation.jsonl, cases/holdout.jsonl  
- labels/development.jsonl, labels/validation.jsonl, labels/holdout.jsonl  
- corpus/documents.jsonl  
- design/authoring-provenance.jsonl  
- contamination-exemptions.json  

### 2.2 Materialize

```powershell
# TEMPLATE — copy only if missing; preserve bytes
# Source: a previously verified primary tree or sealed archive
# Destination: <REPO_ROOT>\datasets\v2\...
# Do not open/parse holdout case/label records for content review.
```

**INTEGRATED (Phase 12F):** the dedicated helper `scripts/materialize_v2_frozen_artifacts.py` now performs manifest-governed, byte-verified materialization. Do **not** use `copy`/`Copy-Item` for these artifacts.

A fresh worktree must materialize **both**:

- the nine benchmark-v2 FINAL artifacts (governed by `datasets/v2/manifests/benchmark-v2-manifest.json`), and
- the manifest-governed redteam release-test fixture `redteam/prompts.jsonl` (governed by `redteam/prompts-manifest.json`), which the v1 evaluation-runner tests require.

```powershell
# Dry-run first, then run once. Materialize BEFORE release-readiness and full-suite testing.
python scripts\materialize_v2_frozen_artifacts.py `
  --source-root "<GOVERNED_SOURCE_REPO>" `
  --target-root "<FRESH_TARGET_WORKTREE>" `
  --include-redteam-prompts --dry-run
python scripts\materialize_v2_frozen_artifacts.py `
  --source-root "<GOVERNED_SOURCE_REPO>" `
  --target-root "<FRESH_TARGET_WORKTREE>" `
  --include-redteam-prompts
```

Rules: no manual copying; no raw JSONL commit (both `*.jsonl` stay git-ignored; only their `.json` manifests are tracked); byte-level SHA-256/size verification only; the tool never parses JSONL records.

---

## 3. Byte-level FINAL verification

```powershell
# TEMPLATE — byte identity only (allowed before evaluation)
cd <REPO_ROOT>
.\.venv\Scripts\python.exe scripts\freeze_v2_benchmark.py verify
```

Expected: OK for 9 files, FINAL status, no drift.

**Do not** treat the following as holdout preclaim:

```powershell
# NOT for holdout preclaim (semantic / rebuild)
.\.venv\Scripts\python.exe scripts\validate_v2_benchmark.py
.\.venv\Scripts\python.exe scripts\build_v2_benchmark.py --verify-determinism
```

Those remain useful as **historical / offline hygiene** checks on a clean tree, not as substitutes for the fail-closed preclaim order of holdout.

---

## 4. Windows short-basetemp handling

```powershell
# TEMPLATE
$bt = "D:\t\f"   # short path outside repo
New-Item -ItemType Directory -Force -Path $bt | Out-Null
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider -o "addopts=" --basetemp=$bt
```

Focused phase script (existing on candidate):

```powershell
# TEMPLATE
.\scripts\verify_phase.ps1 -Focused
```

Full:

```powershell
# TEMPLATE
.\scripts\verify_phase.ps1
```

Record: pass/fail counts, skipped tests (e.g. symlink permission), warnings (Starlette/httpx deprecation is known).

---

## 5. Focused and full verification (existing candidate tools)

| Check | Command class | Notes |
|---|---|---|
| Compile / focused tests | `verify_phase.ps1 -Focused` | Existing |
| Full pytest | `pytest` with short basetemp | Existing |
| Validator | `validate_v2_benchmark.py` | Hygiene; not holdout preclaim |
| Determinism | `build_v2_benchmark.py --verify-determinism` | Hygiene |
| FINAL freeze | `freeze_v2_benchmark.py verify` | Byte-level |

Always paste numbers from live command output; never from memory.

---

## 6. Evidence inventory generation

### 6.1 Manual inventory (available now)

```powershell
# TEMPLATE — content-free inventory of an evidence root
# List result-manifest.json files; hash manifests and analysis trio only.
# Do not print raw result.json case content for reports.
Get-ChildItem <EVIDENCE_ROOT> -Recurse -Filter result-manifest.json |
  ForEach-Object { $_.FullName }
Get-FileHash <ANALYSIS>\analysis.json,<ANALYSIS>\analysis-table.csv,<ANALYSIS>\analysis-manifest.json -Algorithm SHA256
```

### 6.2 Structured inventory tool

> **EXPECTED AFTER INTEGRATION**  
> If Phase 12F adds `scripts/inventory_evaluation_evidence.py` (or similar), use it to emit a machine-readable inventory. Until merged, use §6.1.

---

## 7. Sanitized Gemini packet generation

Purpose: methodology/claims auditor packet without raw prompts, secrets, or holdout case text.

### 7.1 Manual packet contents (available now)

Include only:

- candidate SHA and branch  
- claims-control flags from analysis (if governance-valid evidence)  
- schema identities  
- test totals from live verify  
- governance classification of each evidence set  
- open limitations  

Exclude:

- raw holdout JSONL records  
- full result.json case dumps  
- API keys  

### 7.2 Automated sanitizer

> **EXPECTED AFTER INTEGRATION**  
> A packet builder script, if provided by another branch, should enforce an allowlist of fields. Mark its output with evidence classification (diagnostic vs final).

---

## 8. Ordinary development smoke (diagnostic only)

```powershell
# TEMPLATE — diagnostic; not holdout
cd <REPO_ROOT>
.\.venv\Scripts\python.exe scripts\run_v2_evaluation.py `
  --split development --all-configs `
  --output-root <EXTERNAL_DEV_ROOT> `
  --expected-branch <BRANCH> `
  --expected-commit 93ad09ddea90eb9712e82f3df5beacbd94399b9a `
  --provider mock
```

Then ordinary analyzer with `--split development` and eight `--result-manifest` paths.

Label all outputs **diagnostic**.

---

## 9. Holdout execution (reference only — not authorized here)

High-level order (see historical holdout plan and one-shot runbook materials):

1. Complete human adjudication and residual risks.  
2. Mint **new** external canonical authorization (never reuse inactive draft bytes).  
3. Preclaim: clean SHA, branch match, freeze verify, root absent.  
4. Runner: `--holdout-authorization <PATH> --all-configs --output-root <BOUND_ROOT> --provider mock`.  
5. Analyzer: holdout mode with eight manifests; no `--split`.  
6. Preserve everything; no second run on same root.

This documentation package **does not** authorize holdout.

---

## 10. Failure handling

| Failure | Action |
|---|---|
| Dirty tree / wrong SHA | Abort; fix offline |
| Missing frozen JSONL | Materialize; freeze verify |
| Long path pytest failures | Shorten basetemp; re-run |
| Holdout preclaim fail | No root/receipt expected; do not invent evidence |
| Receipt fail after claim | Root burned; preserve; new auth + new root for retry |
| Mid-matrix fail | Preserve completed configs; do not fabricate rest; analyzer must reject incomplete matrix |
| Analyzer fail | Do not overwrite results; fix inputs or accept partial diagnostic narrative |

**No silent retry. No overwrite. No deletion of burned roots.**

---

## 11. Operator checklist (short)

- [ ] Exact SHA checked out and clean  
- [ ] Frozen artifacts present + freeze verify OK  
- [ ] venv ready  
- [ ] Short basetemp on Windows  
- [ ] Live verify numbers recorded  
- [ ] Evidence roots external to git  
- [ ] Claims labels correct (diagnostic vs final)  
- [ ] No holdout without human authorization  
