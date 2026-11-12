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
This official path is pinned in production. The source digest must equal the
SHA-256 of the exact official manifest bytes, and every derived entry's path,
SHA-256 and size must match its entry in the official six-file subset.

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
explicit spelling of the official metadata path only; its resolved path must
equal the pinned official path. Alternate manifests are refused before any
source metadata or working-set artifact is opened, even if they are FINAL or
contain identical bytes. Tests monkeypatch `OFFICIAL_V2_MANIFEST_PATH` to a
temporary synthetic nine-file metadata fixture, without changing the repository
manifest or requiring official artifacts.

The runner CLI accepts `--benchmark-root` only with `--benchmark-mode dev-val`.
Both implicit and explicit `official` mode refuse that option before dispatch
or any artifact read, including when `--holdout-authorization` is present.

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
The source digest and the full six-entry hash/size table are checked against
the pinned official metadata before any working-set artifact is hashed.

The source official metadata can list the nine official paths; the derived
table cannot list either holdout path. Derivation never opens source artifact
files. Neither the official verifier nor the capability-based authorized
holdout loader was loosened. Dev-val mode/root overrides are refused with
`--holdout-authorization`; the derived status is not an official FINAL freeze.

## Validation evidence

Executed locally on 2026-11-12, using synthetic fixtures only:

- `.venv/bin/python -m pytest -q tests/test_v2_dev_val_manifest.py`:
  **79 passed, 0 failed**.
- Selected existing runner and authorization regression tests:
  **138 passed, 0 failed**. Selection used AST function line numbers from the
  test files: runner test definitions before line 379 or within 527–847;
  authorization test definitions through line 436, within 737–804, or within
  839–910. Binary and text reads of official datasets, any holdout JSONL,
  result JSON, and Ollama logs were blocked; socket connections were blocked.
- AST comparison against the starting commit confirmed
  `verify_frozen_manifest` and `load_authorized_holdout_benchmark` unchanged.

Coverage includes deterministic derivation, official source pinning, rejection
of a valid but unofficial source digest and a self-consistent altered six-file
table before artifact reads, source identity/table rejection,
manifest ordering/count/digests/sizes, every missing or modified allowed
artifact, direct development/validation loading, synthetic development
execution, refusal before opening holdout paths, links and unused provenance,
timeout revalidation, CLI dispatch, refusal of alternate source paths and
official-mode root overrides, and the official nine-file contract.
The official-path regression uses empty synthetic sentinel files and stubs
only their holdout hashes, so no holdout content is opened even for that test.

No real benchmark evaluation, validation run, holdout run, Ollama upgrade,
network call, push or merge was performed.

The original W13 implementation was committed as
`0c56e2816514f551c2b8c4a9b612d1a24f2ff24b`. This review follow-up addresses
P3W13-FIX-01 (official metadata pinning), P3W13-FIX-02 (CLI root restriction),
and P3W13-NEW-01 (corrected commit history and documentation).

## Limits

The existing result analyzer still requires an official FINAL manifest and is
not extended by W13. Derived diagnostics therefore cannot be passed to that
official analyzer workflow. The source digest and six-file table are pinned to
the local official manifest; manifests are integrity metadata, not signatures.
Name/link checks assume the same
trusted local filesystem model as the existing runner; concurrent hostile
filesystem replacement is outside this change's scope.
