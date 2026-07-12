#!/usr/bin/env python3
"""Freeze the Phase 12D v2 benchmark: write a SHA-256 manifest
(`datasets/v2/manifests/benchmark-v2-manifest.json`) and verify it.

**Candidate freeze only (Code X Phase 12D audit, required-fixes item 7):**
every manifest this script writes carries `"manifest_status": "candidate"`
and every CLI message below says CANDIDATE explicitly. This is not yet a
defensible final freeze -- it becomes one only after Code X, Gemini, and
Grok all pass and a final regeneration is performed after all accepted
audit fixes land. Any artifact change (this whole Phase 12D fix pass
included) makes the previous manifest an obsolete candidate; re-run
`freeze` after any content change, never treat an old manifest as still
valid.

Two modes:

- `freeze` (default): computes a SHA-256 digest for every artifact file
  under `datasets/v2/corpus/`, `datasets/v2/cases/`, `datasets/v2/labels/`,
  `datasets/v2/design/` (the non-runtime authoring-provenance artifact --
  Code X Phase 12D re-audit, "candidate manifest policy integrity"), and
  the top-level `datasets/v2/contamination-exemptions.json` policy file
  (the manifest file itself, under `manifests/`, is never included in its
  own hash set -- see `_iter_artifact_files` below), and writes a manifest
  with relative POSIX paths, byte sizes, and hex digests, sorted by path
  for a stable, deterministic file. Every artifact that can change
  benchmark meaning, split independence, or validation exemptions is
  covered -- a mutated exemption file or authoring-provenance entry fails
  `verify` exactly like a mutated corpus/case/label file.

- `verify`: recomputes the same digests and compares them against an
  existing manifest, failing loudly (non-zero exit) if anything differs
  -- added file, removed file, or changed content. This is the same
  check `docs/decisions/ADR-003-v2-benchmark.md` requires a future Phase
  12E evaluation/ablation runner to perform at the start of every run
  before producing any report.

No timestamp is embedded in the manifest content, so `freeze` run twice
against an unchanged tree produces a byte-identical manifest file --
required for this script itself to be deterministic and for `verify` to
be meaningful as a pure content check, not a "did anyone re-run this"
check. No machine-specific absolute path appears anywhere in the
manifest -- every path is relative to `datasets/v2/`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "datasets" / "v2"
MANIFEST_PATH = OUT_DIR / "manifests" / "benchmark-v2-manifest.json"

ARTIFACT_SUBDIRS = ("corpus", "cases", "labels", "design")
# Top-level (non-subdirectory) files that carry validation policy and must
# therefore be integrity-bound by the manifest exactly like the generated
# corpus/case/label/provenance artifacts (Code X Phase 12D re-audit).
POLICY_FILES = ("contamination-exemptions.json",)
REQUIRED_ARTIFACT_PATHS = (
    "cases/development.jsonl",
    "cases/holdout.jsonl",
    "cases/validation.jsonl",
    "contamination-exemptions.json",
    "corpus/documents.jsonl",
    "design/authoring-provenance.jsonl",
    "labels/development.jsonl",
    "labels/holdout.jsonl",
    "labels/validation.jsonl",
)


def _iter_artifact_files() -> list[Path]:
    files: list[Path] = []
    for sub in ARTIFACT_SUBDIRS:
        subdir = OUT_DIR / sub
        if not subdir.exists():
            continue
        files.extend(sorted(p for p in subdir.rglob("*") if p.is_file()))
    for name in POLICY_FILES:
        path = OUT_DIR / name
        if path.exists():
            files.append(path)
    return sorted(files, key=lambda p: p.relative_to(OUT_DIR).as_posix())


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest() -> dict:
    entries = []
    for path in _iter_artifact_files():
        rel = path.relative_to(OUT_DIR).as_posix()
        entries.append(
            {
                "path": rel,
                "size_bytes": path.stat().st_size,
                "sha256": _sha256_of(path),
            }
        )
    entries.sort(key=lambda e: e["path"])
    return {
        "manifest_version": 1,
        "benchmark_version": "v2",
        "manifest_status": "candidate",
        "file_count": len(entries),
        "files": entries,
    }


def _missing_required_artifacts() -> list[str]:
    return [rel for rel in REQUIRED_ARTIFACT_PATHS if not (OUT_DIR / rel).is_file()]


def cmd_freeze() -> int:
    missing = _missing_required_artifacts()
    if missing:
        print("FAIL: required candidate artifact(s) missing:", file=sys.stderr)
        for rel in missing:
            print(f"  - {rel}", file=sys.stderr)
        return 1
    manifest = build_manifest()
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST_PATH.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    print(f"Froze {manifest['file_count']} artifact file(s) into {MANIFEST_PATH} (CANDIDATE FREEZE -- not yet final).")
    return 0


def cmd_verify() -> int:
    if not MANIFEST_PATH.exists():
        print(f"FAIL: manifest not found at {MANIFEST_PATH} -- run 'freeze' first.", file=sys.stderr)
        return 1
    with MANIFEST_PATH.open(encoding="utf-8") as f:
        frozen = json.load(f)

    current = build_manifest()
    frozen_by_path = {e["path"]: e for e in frozen["files"]}
    current_by_path = {e["path"]: e for e in current["files"]}

    errors: list[str] = []
    for path, entry in frozen_by_path.items():
        if path not in current_by_path:
            errors.append(f"missing file that was frozen: {path}")
            continue
        cur = current_by_path[path]
        if cur["sha256"] != entry["sha256"]:
            errors.append(f"content changed since freeze: {path}")
        if cur["size_bytes"] != entry["size_bytes"]:
            errors.append(f"size changed since freeze: {path}")
    for path in current_by_path:
        if path not in frozen_by_path:
            errors.append(f"new, unfrozen file present: {path}")

    if errors:
        print(f"FAIL: {len(errors)} manifest mismatch(es):", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print(f"OK: {len(frozen_by_path)} file(s) verified against the frozen CANDIDATE manifest, no drift detected.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode", nargs="?", default="freeze", choices=["freeze", "verify"],
        help="'freeze' (default) writes the manifest; 'verify' checks the tree against an existing manifest.",
    )
    args = parser.parse_args(argv)
    if args.mode == "freeze":
        return cmd_freeze()
    return cmd_verify()


if __name__ == "__main__":
    raise SystemExit(main())
