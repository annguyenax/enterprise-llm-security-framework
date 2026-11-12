# Review Claude — W15 (cross-review, chưa commit)

1 lượt, 13:02–13:04 ngày 12/11/2026, Asia/Saigon. tokrun label `review-claude-w15`. stderr: claude-chain trying claude-opus-5-5, served by claude-sonnet-5-5 (fallback). Claude không ghi được file đích vì quyền workspace; coordinator lưu nguyên stdout.

I couldn't write the review file. Writing to `/workspace/deliverables/shield-phase3-rag-opt-20261111/review-claude-w15.md` was denied, and so was reading the two notes files `w15-coordinator-notes.txt` and `w15-implement-notes.md`. The full review is drafted; once you grant write access to that folder, I'll write it there unchanged.

I also didn't rerun pytest or the self-check, because those commands needed approval. The figures of 657 passed and self-check PASS are the coordinator's, not mine. I checked `git rev-parse HEAD` = `796ae25…` and touched no ledger, val, holdout or real data.

## Verdict: **PASS-WITH-FIXES**
Neither fix is blocking. Final adjudication is up to the maintainer.

**Issues**
- **P3W15-FIX-01:** `--self-check` is never called by the runner, by `verify_phase.ps1` or from `docs/`. The writer is already fixed, but the self-check only helps on An's machine if someone remembers to run it before a claim. Suggestion: add a mandatory runbook step for VAL2 that runs `.venv\Scripts\python.exe -m scripts.v2_validation_ledger --self-check` and keeps the output as evidence.
- **P3W15-FIX-02 (documentation only):** `app/services/audit_logger.py:167` writes in text mode (`"a"`). On Windows, the `audit-worker-*.jsonl` and `audit-ingestion.jsonl` files will therefore be CRLF. They aren't hashed or read strictly anywhere: the only reader (`run_v2_evaluation.py:4180`) scans for substrings, so this doesn't matter today. The handoff should state it as a known exception.
- **BLOCK:** none.
- **P3W15-NEW-01 (suggestion, outside W15):** have the dev-val preflight call `self_check_canonical_io()` before `claim_validation_slot`, so a bad environment fails before using up the cap. This changes the official path, so it needs its own go-ahead and audit.

**Required checks**
1. **Writer bytes — PASS.** At `v2_validation_ledger.py:109` the open call now includes `O_BINARY`. That fixes the root cause: in 796ae25 the file was opened in CRT text mode, so `os.write` turned LF into CRLF. This matches the 1860 vs 1859 byte difference. The receipt is opened with `open("xb")`, which CPython always opens as binary on Windows. Its `_canonical_json_bytes` produces the same bytes as `ledger.canonical`.
2. **`read_claims` — PASS.** It is unchanged, so CRLF lines are still rejected, and nothing repairs ledgers. The test confirms the new writer rejects an old CRLF ledger without changing a single byte.
3. **Reproduction — PASS.** The simulator correctly models CRT text descriptors, including returning `len(payload)`. The old-writer copy `_append_like_796ae25` matches the old code line for line. It writes CRLF and gets rejected as `malformed`, while the new writer passes under the same monkeypatch. A canary test confirms the simulator really translates newlines.
4. **Other writers — PASS, apart from FIX-02.**
   - These all write in binary mode or with an explicit LF terminator: receipt, derived manifest, evidence jsonl (`ab`), runtime (`wb` + replace), result/manifest, analysis/manifest, and the CSV table (`lineterminator="\n"`).
   - Freeze is only read and hashed on this path; it is written with `newline="\n"`.
   - One limit: these regression tests don't prove real CRT behaviour, because the simulator leaves binary file objects alone. Only the self-check on the target machine proves that, which is why FIX-01 matters.
5. **Self-check — PASS.**
   - It accepts no path.
   - It uses its own temporary directory, removed afterwards, with the real production claim and read functions.
   - It fails with exit 1 if it finds `\r` or the bytes differ from canonical.
   - The `break_binary` test confirms both the PASS and FAIL branches.
6. **Gates — PASS.** The diff only touches the ledger script plus the new test file. Cap 3, record keys and constraints, holdout, Judge, guard, runner and analyzer are all unchanged.
