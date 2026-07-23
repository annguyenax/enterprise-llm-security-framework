# Phase 12F — Release Checklist

**Base candidate (implementation):** `93ad09ddea90eb9712e82f3df5beacbd94399b9a`  
**Use:** gate a public archive, thesis appendix, or demo freeze  
**Rule:** tick only from live observation; never from memory

---

## A. Repository cleanliness

- [ ] `git status --short --untracked-files=all` empty (or only explained ignored materializations)  
- [ ] `git diff --check` clean  
- [ ] No secrets in tree (keys, tokens, `.env` with credentials)  
- [ ] No accidental evaluation results committed under git  

## B. Exact commit identity

- [ ] `git rev-parse HEAD` recorded: `________________`  
- [ ] Matches intended release tag/SHA: `________________`  
- [ ] Tag message (if any) does not claim Phase 12E.4 PASS without governance  

## C. Tests

- [ ] `verify_phase.ps1 -Focused` live result: `________________`  
- [ ] Full pytest (short basetemp on Windows) live result: `________________`  
- [ ] Skipped tests listed with reasons: `________________`  
- [ ] Known warnings documented (e.g. Starlette/httpx deprecation; do not install `httpx2`)  

## D. Frozen artifacts

- [ ] Nine FINAL artifacts present on the release machine  
- [ ] `freeze_v2_benchmark.py verify` OK  
- [ ] Manifest status `final`  
- [ ] Manifest SHA-256 recorded: `________________`  
- [ ] A fresh worktree materialized with `scripts/materialize_v2_frozen_artifacts.py --include-redteam-prompts` (both the nine benchmark-v2 FINAL artifacts and the manifest-governed `redteam/prompts.jsonl` release-test fixture) **before** release-readiness and full-suite testing  
- [ ] Materialization was manifest-governed and byte-verified (no manual copy; no raw JSONL committed; only `.json` manifests tracked)  

## E. Documentation

- [ ] `docs/phase12f/00`–`07` present and reviewed  
- [ ] Claims match `02_EVALUATION_GOVERNANCE.md`  
- [ ] Exploratory holdout classified correctly if mentioned  
- [ ] No invented metrics in docs  

## F. Evidence inventory

- [ ] Each evidence root listed with classification (diagnostic / exploratory / governance-valid)  
- [ ] SHA-256 of analysis trios (if any) recorded without dumping raw cases  
- [ ] Authorization paths (if any) external; hashes recorded  
- [ ] No claim that exploratory holdout is final PASS  

## G. License / dependency review

- [ ] `requirements.txt` reviewed  
- [ ] Licenses acceptable for thesis distribution  
- [ ] No typosquat packages (`httpx2` not installed)  
- [ ] Third-party notices included if required  

## H. Secrets scan

- [ ] Repo scan for API keys / private URLs  
- [ ] Shell history / report attachments checked  
- [ ] Authorization files not committed  

## I. Demo readiness

- [ ] Demo script dry-run completed (`05_DEMO_AND_DEFENSE_SCRIPT.md`)  
- [ ] Fallback offline path works  
- [ ] Freeze verify demo works  
- [ ] Q&A answers consistent with limitations  

## J. Release archive

- [ ] Archive contents listed (code SHA + docs + optional sealed benchmark bundle)  
- [ ] Archive SHA-256: `________________`  
- [ ] External evidence **not** silently mixed into code archive without labeling  

## K. Cross-review

- [ ] Phase 12F documentation packages reviewed by peers (Claude/Codex/Grok as assigned)  
- [ ] Blocking findings resolved or accepted by maintainer in writing  

## L. Final Gemini (or methodology) audit

- [ ] Sanitized claims packet prepared  
- [ ] Auditor verdict recorded: `________________`  
- [ ] No prohibited claims remain in thesis PDF  

## M. Final maintainer decision

- [ ] Technical PoC acceptable for defense: yes/no  
- [ ] Governance-valid holdout complete: yes/no  
- [ ] Primary thesis claims scope written: `________________`  
- [ ] Signature / UTC: `________________`  

---

## Release decision block

```text
Release candidate SHA: ________________
Archive SHA-256: ________________
Maintainer: ________________
UTC: ________________

[ ] APPROVE academic release / thesis freeze
[ ] BLOCK — open items remain (list below)

Open items:
-
-
```

**This checklist does not itself constitute Phase 12F PASS.**
