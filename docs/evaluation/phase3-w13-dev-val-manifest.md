# Phase 3 W13: derived dev+val benchmark mode

Implements the approved PLAN-P3-v6 W13 scope. The default runner continues to
use the FINAL official nine-file verifier. A separate `dev-val` mode accepts a
working set containing exactly these six runtime artifacts:

```text
cases/development.jsonl
cases/validation.jsonl
contamination-exemptions.json
corpus/documents.jsonl
labels/development.jsonl
labels/validation.jsonl
```

`design/authoring-provenance.jsonl` is excluded because the split loader does
not consume it. Its presence is refused by path, without opening it or needing
to inspect a split field. The shared corpus remains included.

## Derivation and use

Prepare the six allowed artifacts in a separate working directory. The tool
does not materialize or copy artifacts. It reads the official manifest metadata
at `datasets/v2/manifests/benchmark-v2-manifest.json`, validates its FINAL identity
and exact sorted nine-entry table, selects six entries, and verifies only those
six working-set files against the source hashes and sizes.

```bash
.venv/bin/python scripts/derive_v2_dev_val_manifest.py \
  --benchmark-root /absolute/path/to/clean-dev-val-v2

.venv/bin/python scripts/run_v2_evaluation.py \
  --benchmark-mode dev-val \
  --benchmark-root /absolute/path/to/clean-dev-val-v2 \
  --split development --config C6_none \
  --expected-branch feat/p3-rag-opt \
  --expected-commit "$(git rev-parse HEAD)" \
  --output-root /absolute/path/to/new-diagnostic-output
```

The output manifest is `manifests/benchmark-v2-dev-val-manifest.json`, with
`manifest_status: derived-dev-val`, `benchmark_mode: dev-val`, the SHA-256 of
the exact source manifest bytes, a sorted six-entry table, and matching
`file_count`. Its own SHA-256 identifies the derived manifest bytes and binds
the runner's experiment identity. Derivation is deterministic, offline, and
refuses to overwrite an existing manifest. `--source-manifest` allows an
explicit source metadata path (used with synthetic fixtures in tests).

Both supported splits use the derived verifier when this mode is selected,
including direct calls to
`load_split_benchmark(root, split, benchmark_mode="dev-val")`. The existing
clean-tree, branch, commit, provider, split-size, scope and runtime checks still
apply. Timeout recovery also rechecks the derived identity.

## Refusal boundaries

Before opening a manifest or hashing an artifact, dev-val verification scans
working-set names. A name containing `holdout` (case insensitive), `result.json`,
an Ollama-named artifact, or any symbolic link is refused. The frozen artifact
directories must contain exactly the six allowed paths; extra provenance and
other unlisted runtime files are refused without reading them. The complete
manifest table is validated before any listed artifact is opened. Missing
holdout artifacts are expected and never requested.

The source official metadata can list the nine official paths; the derived
table cannot list either holdout path. Derivation never opens source artifact
files. Neither the official verifier nor the capability-based authorized
holdout loader was loosened. Dev-val mode/root overrides are refused with
`--holdout-authorization`; the derived status is not an official FINAL freeze.

## Validation evidence

Executed locally on 2026-11-12, using synthetic fixtures only:

- `.venv/bin/python -m pytest -q tests/test_v2_dev_val_manifest.py`:
  **60 passed, 0 failed**.
- Selected existing runner and authorization regression tests:
  **138 passed, 0 failed**. Selection used AST function line numbers from the
  test files: runner test definitions before line 379 or within 527–847;
  authorization test definitions through line 436, within 737–804, or within
  839–910. Binary and text reads of official datasets, any holdout JSONL,
  result JSON, and Ollama logs were blocked; socket connections were blocked.
- AST comparison against the starting commit confirmed
  `verify_frozen_manifest` and `load_authorized_holdout_benchmark` unchanged.

Coverage includes deterministic derivation, source identity/table rejection,
manifest ordering/count/digests/sizes, every missing or modified allowed
artifact, direct development/validation loading, synthetic development
execution, refusal before opening holdout paths, links and unused provenance,
timeout revalidation, CLI dispatch, and the official nine-file contract.
The official-path regression uses empty synthetic sentinel files and stubs
only their holdout hashes, so no holdout content is opened even for that test.

No real benchmark evaluation, validation run, holdout run, Ollama upgrade,
network call, push or merge was performed.

Commit creation was blocked before staging: `git add` could not create
`.git/index.lock` because the Git metadata filesystem is read-only. The six
changed files remain unstaged for the coordinator; no commit was created and
the original HEAD is unchanged. Use the configured author and commit message:

```text
feat(p3): add dev+val derived manifest and runner compatibility mode

Co-authored-by: Codex (Astra) <codex@shield-team.local>
```

## Limits

The existing result analyzer still requires an official FINAL manifest and is
not extended by W13. Derived diagnostics therefore cannot be passed to that
official analyzer workflow. The source digest records provenance; manifests
are integrity metadata, not signatures. Name/link checks assume the same
trusted local filesystem model as the existing runner; concurrent hostile
filesystem replacement is outside this change's scope.
