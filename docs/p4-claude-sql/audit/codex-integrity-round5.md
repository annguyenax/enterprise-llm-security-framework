| ID | Severity | file:line | finding | evidence | fix |
|---|---|---|---|---|---|
| F1 | Minor | [HANDOFF.md](/E:/TTTN/enterprise-llm-security-framework/docs/p4-claude-sql/HANDOFF.md:25) | Furniture seed and manifest determinism was not independently verified in this read-only audit. | The generator’s documented outputs are tracked files, but running it would write them. The HEAD verification artifact covers benchmark v2 determinism, not this generator. | Run the generator comparison in a writable audit environment and capture byte-for-byte results. |

Other checks:

- **Frozen artifacts:** `git diff 64e4b04..HEAD -- datasets/v2 datasets/v3` was empty. The scoped changed-path list contained no holdout paths.
- **Fixture counts:** `.venv\Scripts\python.exe scripts\eval_indirect_fixtures.py` reproduced `dev 24/24`, `holdout 9/14`, `benign 0/32`. HANDOFF lines 120–123 disclose same-author fixtures and disclaim tuning history, causal explanations, and reportable rates.
- **Tests:** the requested focused suite passed: **172 passed, 1 warning**.
- **Contract and policy:** schema 1.1, builder, ACL, and manifest references appear consistent by inspection; `requirements.txt` is unchanged. Anthropic is opt-in, and the smoke runner requires `--allow-paid`. Synthetic-data and non-reportable smoke terminology are appropriately qualified. `verify_phase.ps1` changes only array-wrapping `$pyFiles`.
- **Round 3 scope:** `git diff --name-only ec68cf3..HEAD` contains only `docs/p4-claude-sql/` files and `scripts/p4_audit_codex.bat`, as permitted. `git diff --check 64e4b04..HEAD` was clean.
- **Earlier findings:** Round 1 F1–F4 are resolved. Round 2 F5–F7 are resolved or properly qualified. Round 3 F6 and F8 are resolved: HANDOFF no longer reports the unsupported historical counts. Round 4 F6 and F8 are therefore **RESOLVED**. Its other findings remain resolved or qualified as recorded in the report.
- The worktree has a pre-existing modification to `scripts/seed_enterprise_knowledge_base.py`; it was not changed.

VERDICT: REVISE