# Review W13: commit `0c56e28`, dev+val derived manifest and `--benchmark-mode dev-val`

**Verdict: PASS.** No blocking issues. I raise two FIX items: FIX-01 should be fixed before any dev-val result is cited as evidence for V2. The maintainer makes the final decision.

**Scope reviewed:** commit `0c56e2816514f551c2b8c4a9b612d1a24f2ff24b` (parent `ff41f92`). It changes 6 files (+789/−6): `scripts/run_v2_evaluation.py`, `scripts/derive_v2_dev_val_manifest.py`, `tests/test_v2_dev_val_manifest.py`, `tests/test_v2_holdout_authorization.py`, `scripts/README.md` and `docs/evaluation/phase3-w13-dev-val-manifest.md`.

**Method:** I read the diff and the related functions (`verify_frozen_manifest`, `_iter_frozen_artifact_paths`, `load_split_benchmark`, `_load_frozen_split`, `load_authorized_holdout_benchmark`, `preflight`, and the analyzer's manifest pin). I also read the whole new test file. I ran no tests and did not run val. I did not open the patch/stat files under `/workspace/deliverables/` because permission was denied, so I used `git show` on the commit directly.

---

## Issues

### P3W13-FIX-01: The derived manifest only checks itself and is not tied to the official V2 manifest
- **File:** `scripts/run_v2_evaluation.py`, functions `verify_dev_val_manifest` and `derive_dev_val_manifest`
- **Severity:** Major. It does not block the W13 merge, but it must be fixed before dev-val results are used as evidence.
- **What's wrong:**
  - `verify_dev_val_manifest` only checks that `source_manifest_sha256` matches the format `^[0-9a-f]{64}$`.
  - It never compares that digest with the hash of `datasets/v2/manifests/benchmark-v2-manifest.json` in the repo.
  - It never checks that the 6 entries (sha256 and size) match the 6 corresponding entries in the official manifest.
  - `derive_dev_val_manifest` also accepts any `--source-manifest` with status `final`.
- **Effect:** someone can edit dev/val content in the working set and then write a self-consistent derived manifest by hand (or derive it from a fake source manifest). The runner accepts it and labels the result `derived-dev-val`, as if it came from V2. The official analyzer rejects such results because it pins the repo manifest, but nothing else in the dev-val workflow catches it.
- **Suggested fix:** in `verify_dev_val_manifest`, read the repo's official manifest metadata (metadata only, no artifacts). Require:
  - `source_manifest_sha256` equals the official manifest's sha256;
  - the `files` table equals the 6-entry subset of the official table.
  
  For the derive CLI, either refuse a source that is not the official one, or mark it clearly as test-only. The tests can inject the source path through a parameter or hook. The doc ("The source digest records provenance… not signatures") states this limitation, but the fix is cheap and needs no new library.

### P3W13-FIX-02: The CLI now exposes `--benchmark-root` in `official` mode
- **File:** `scripts/run_v2_evaluation.py`, `build_parser` and `main` (`run_evaluation(request, benchmark_root=args.benchmark_root)`)
- **Severity:** Minor
- **What's wrong:** before W13, the CLI always used `datasets/v2`. Now `--benchmark-mode official --benchmark-root /other` is valid. `verify_frozen_manifest` reads the manifest from that root and only checks it against itself; there is no pinned hash. The run then produces artifacts labelled `benchmark_manifest_status: final` with a manifest sha that is not the official one.
- **Mitigations already in place:** the analyzer re-verifies `repo/datasets/v2` and compares the sha, and the holdout path refuses a root override. So official evaluation is not weakened in practice.
- **Suggested fix:** refuse `--benchmark-root` unless `--benchmark-mode dev-val` is set. Add a test for official mode with a root override, and a test for `--holdout-authorization` with only `--benchmark-root` (the current test only covers `--benchmark-mode dev-val`).

### P3W13-NEW-01: The doc contradicts the commit
- **File:** `docs/evaluation/phase3-w13-dev-val-manifest.md`, the paragraph "Commit creation was blocked before staging… no commit was created and the original HEAD is unchanged".
- **Severity:** Minor (doc accuracy)
- **What's wrong:** the paragraph is now inside a commit, so the statement is false. It should be removed, or moved into the handoff notes with the actual commit identity added.

---

## Non-blocking notes
1. `preflight` calls `.resolve()` on `benchmark_root` before `_check_dev_val_working_set`. As a result, the `benchmark_root.is_symlink()` check is skipped when the root itself is a symlink and the run goes through `preflight`; it only works on the direct API. Links inside the working set are still refused through `os.walk`. The doc's trust model already states this boundary, so it is acceptable.
2. `_iter_frozen_artifact_paths` only scans `corpus/`, `cases/`, `labels/`, `design/` and `contamination-exemptions.json`. Unlisted files outside those locations are not refused unless their names contain `holdout`, `ollama`, or equal `result.json`. The doc wording ("the frozen artifact directories must contain exactly…") is accurate, but readers should not take it to mean "the whole root".
3. When `benchmark_mode == "dev-val"`, `verify_dev_val_manifest` runs twice in `preflight`: once in the dispatcher and once in `load_split_benchmark`. This is safe: it re-checks the files close to when they are read. The cost is small.
4. The doc uses `.venv/bin/python`, while CLAUDE.md specifies `.venv\Scripts\python.exe` (Windows). The doc may need both commands.
5. The analyzer does not accept dev-val results, as the doc's Limits section says. That is consistent with "not an official FINAL freeze".

---

## Constraint checks

| Constraint | Result | Basis |
|---|---|---|
| **No holdout was read** (by this review) | **Confirmed** | I read only code, tests, the docs in the diff and analyzer code. I did not open `cases/holdout.jsonl`, `labels/holdout.jsonl`, any `result.json`, Ollama logs, holdout case IDs, or any artifact under `datasets/v2/`. |
| **No holdout is read** (by the code and tests in the commit) | **Confirmed** | An autouse fixture blocks `builtins.open` and `io.open` from reading under `datasets/v2`, any `*holdout*` name, and `result.json`, and blocks sockets. The official regression test uses empty sentinel files and stubs `_sha256_file` for `holdout.jsonl`. Derivation reads only manifest metadata. |
| **Official 9-file path intact** | **Confirmed** | The diff has no hunk inside `verify_frozen_manifest` or `load_authorized_holdout_benchmark`. The `official` mode dispatcher still calls `verify_frozen_manifest`. `load_split_benchmark` defaults to `official`, and the parameter is keyword-only (asserted in `test_v2_holdout_authorization.py`). `_holdout_request_from_args` only adds a check refusing mode/root overrides, which makes it stricter. `REQUIRED_FROZEN_PATHS` is unchanged. Test 359 checks that the official verifier still requires exactly 9 files and refuses a 6-entry table. Test 390 checks that a derived manifest cannot pass as official. Caveat: FIX-02 is a CLI exposure, mitigated by the analyzer pin. |
| **dev-val fails closed when it sees a holdout path** | **Confirmed** | `_check_dev_val_working_set` runs first in both `verify_dev_val_manifest` and `derive_dev_val_manifest`, before reading any manifest or hashing any artifact. It refuses names containing `holdout` (case-insensitive), `result.json`, `*ollama*`, and links. Then `_validate_manifest_table` validates the whole table, refusing `holdout` paths and anything outside the 6 allowed paths, before any artifact is hashed. Tests 186, 202, 246, 306, 317 and 335 patch `Path.open` / `_sha256_file` to fail if called, which shows the refusal happens before any open. Test 343 shows timeout recovery re-checks this. `load_split_benchmark(..., "holdout", benchmark_mode="dev-val")` is refused by the split check. A missing holdout is not an error (the fixture contains no holdout at all). |
| Not touched: `datasets/v2/`, `requirements.txt`, holdout P2/P3 | **Confirmed** | The commit's diffstat contains none of these paths. |
