"""Materialize the FINAL-frozen benchmark v2 artifacts into a target repository.

Eight of the nine FINAL-frozen artifacts are ``*.jsonl`` and are intentionally
git-ignored, so a freshly created worktree does not receive them. This script
replaces the previous ad-hoc manual copy with a fail-closed, manifest-driven
materialization.

It reads only the existing FINAL manifest metadata (path / size / SHA-256). It
copies only the artifacts the manifest lists, verifying each file's SHA-256 and
byte size on the source before copying and on the target after copying. It
publishes atomically, refuses to overwrite a mismatching target, and leaves a
byte-identical existing target untouched.

Safety properties:

* It never parses a benchmark record. Artifacts are opened in binary mode and
  hashed; no ``json.loads`` is ever applied to a ``*.jsonl`` artifact.
* It never prints benchmark record content. The JSON summary contains only
  paths, byte sizes, SHA-256 identities and per-file actions.
* It rejects manifest paths that are absolute, contain ``..``, escape the
  benchmark subtree, or resolve through a symlink / reparse point.
* It has no retry and no force-overwrite. A mismatch fails closed.

Usage:

    python scripts/materialize_v2_frozen_artifacts.py \
        --source-root D:/path/to/repo-with-artifacts \
        --target-root D:/path/to/fresh/worktree \
        [--manifest <path>] [--dry-run] [--summary-out <path>]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any

# Benchmark subtree, relative to a repository root.
BENCHMARK_SUBDIR = Path("datasets") / "v2"
# The FINAL manifest, relative to a repository root. It is tracked in git
# (it is a ``.json`` file) and is the authority for what must be materialized.
MANIFEST_RELPATH = BENCHMARK_SUBDIR / "manifests" / "benchmark-v2-manifest.json"

# Governed auxiliary release-test fixture: a single git-ignored JSONL that the
# v1 evaluation-runner tests require but that predates (and is not covered by)
# the benchmark v2 FINAL manifest. Its own tiny FINAL manifest is tracked in git
# and pins exactly one repository-root-relative path. This is an opt-in group;
# the trusted artifact allowlist is NOT broadened for the default run.
REDTEAM_MANIFEST_RELPATH = Path("redteam") / "prompts-manifest.json"
REDTEAM_EXPECTED_PATHS = frozenset({"redteam/prompts.jsonl"})
REDTEAM_ARTIFACT_CLASS = "release_test_fixture"

_CHUNK = 65536
_HEX64 = frozenset("0123456789abcdef")


class MaterializationError(Exception):
    """Fail-closed error carrying a stable machine-readable ``code``."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _sha256_of(path: Path) -> str:
    """SHA-256 of a file, read in binary chunks. Never parses content."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_symlink_or_reparse(path: Path) -> bool:
    """True if ``path`` is a symlink or a Windows reparse point (e.g. junction).

    ``Path.is_symlink`` misses Windows directory junctions, so the reparse
    attribute is checked explicitly via ``lstat``.
    """
    try:
        if path.is_symlink():
            return True
    except OSError:
        return True
    try:
        attrs = os.lstat(path).st_file_attributes  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        return False
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attrs & reparse)


def _validate_relpath(rel: str) -> Path:
    """Validate a manifest-declared relative path. Reject unsafe shapes."""
    if not isinstance(rel, str) or not rel.strip():
        raise MaterializationError("manifest_path", "manifest entry path must be a non-empty string")
    rel_path = Path(rel)
    if rel_path.is_absolute() or (rel_path.drive != "") or (rel_path.anchor != ""):
        raise MaterializationError("path_absolute", f"manifest path must be relative: {rel!r}")
    if any(part == ".." for part in rel_path.parts):
        raise MaterializationError("path_traversal", f"manifest path must not contain '..': {rel!r}")
    if any(part in ("", ".") for part in rel_path.parts):
        raise MaterializationError("path_shape", f"manifest path has an empty or '.' component: {rel!r}")
    return rel_path


def _safe_resolved(base_benchmark_dir: Path, rel_path: Path, *, label: str) -> Path:
    """Resolve ``rel_path`` under the benchmark dir and confirm containment.

    Also rejects any component that is a symlink / reparse point, so a copy can
    never follow a link outside the benchmark subtree.
    """
    base = base_benchmark_dir.resolve()
    candidate = (base / rel_path)

    # Reject a symlink/reparse point at any existing component under the base.
    partial = base
    for part in rel_path.parts:
        partial = partial / part
        if partial.exists() and _is_symlink_or_reparse(partial):
            raise MaterializationError(
                "symlink_rejected",
                f"{label} path passes through a symlink/reparse point: {rel_path.as_posix()}",
            )

    resolved = candidate.resolve()
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise MaterializationError(
            "path_escape",
            f"{label} path escapes the benchmark subtree: {rel_path.as_posix()}",
        ) from exc
    return candidate


def load_manifest(
    manifest_path: Path,
    *,
    expected_paths: frozenset[str] | None = None,
    require_artifact_class: str | None = None,
) -> dict[str, Any]:
    """Load and structurally validate the FINAL manifest metadata only.

    ``expected_paths`` (when given) requires the manifest's path set to equal it
    exactly, rejecting any extra or missing entry — a strict one-line allowlist
    for the auxiliary fixture. ``require_artifact_class`` (when given) requires a
    matching top-level ``artifact_class``.
    """
    if not manifest_path.exists():
        raise MaterializationError("manifest_missing", f"manifest not found: {manifest_path}")
    if _is_symlink_or_reparse(manifest_path):
        raise MaterializationError("manifest_symlink", "manifest path is a symlink/reparse point")
    try:
        raw = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise MaterializationError("manifest_unreadable", "manifest could not be read") from exc
    try:
        manifest = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MaterializationError("manifest_json", "manifest is not valid JSON") from exc
    if not isinstance(manifest, dict):
        raise MaterializationError("manifest_json", "manifest must be a JSON object")

    status = manifest.get("manifest_status")
    if status != "final":
        raise MaterializationError(
            "manifest_not_final",
            f"manifest_status must be 'final' to materialize; got {status!r}",
        )

    artifact_class = manifest.get("artifact_class")
    if require_artifact_class is not None and artifact_class != require_artifact_class:
        raise MaterializationError(
            "manifest_artifact_class",
            f"artifact_class must be {require_artifact_class!r}; got {artifact_class!r}",
        )

    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise MaterializationError("manifest_files", "manifest 'files' must be a non-empty list")

    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in files:
        if not isinstance(entry, dict):
            raise MaterializationError("manifest_entry", "each manifest file entry must be an object")
        path = entry.get("path")
        rel_path = _validate_relpath(path)
        key = rel_path.as_posix()
        if key in seen:
            raise MaterializationError("manifest_duplicate", f"duplicate manifest path: {key}")
        seen.add(key)
        size = entry.get("size_bytes")
        # bool is a subclass of int; exclude it explicitly.
        if type(size) is not int or size < 0:
            raise MaterializationError("manifest_size", f"size_bytes must be a non-negative int: {key}")
        sha = entry.get("sha256")
        if not isinstance(sha, str) or len(sha) != 64 or not set(sha.lower()) <= _HEX64:
            raise MaterializationError("manifest_sha", f"sha256 must be 64 lowercase hex chars: {key}")
        entries.append({"path": key, "size_bytes": size, "sha256": sha.lower()})

    file_count = manifest.get("file_count")
    if type(file_count) is int and file_count != len(entries):
        raise MaterializationError(
            "manifest_count",
            f"file_count {file_count} does not match {len(entries)} listed files",
        )

    if expected_paths is not None:
        actual_paths = {entry["path"] for entry in entries}
        if actual_paths != set(expected_paths):
            raise MaterializationError(
                "manifest_unexpected_paths",
                "manifest path set does not match the expected allowlist: "
                f"expected {sorted(expected_paths)}, got {sorted(actual_paths)}",
            )
    return {"manifest_status": status, "artifact_class": artifact_class, "entries": entries}


def _publish_no_clobber(
    source: Path, target: Path, *, expected_sha: str, expected_size: int
) -> str:
    """Atomically publish ``source`` bytes to ``target`` WITHOUT clobbering.

    Publication uses ``os.link`` (hard link) as the atomic no-clobber primitive:
    it fails with ``FileExistsError`` if ``target`` already exists, so a target
    that appears during the check→publish window is never overwritten. This
    closes the check-then-``os.replace`` TOCTOU race — ``os.replace`` is never
    used for the final artifact destination, and no existing destination is ever
    unlinked, truncated or replaced.

    Returns ``"published"`` on success, or ``"raced"`` when a target appeared
    concurrently (the caller re-verifies and never overwrites). Raises
    ``MaterializationError`` (fail closed) if the temporary bytes fail
    verification or if the filesystem does not support atomic no-clobber linking.

    Trusted-administrator assumptions (documented, not defended against): a local
    administrator or hostile process with write access to the destination
    directory could still interfere; and directory-entry durability after a crash
    is best-effort on filesystems without directory ``fsync`` (e.g. Windows).
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".materialize-", dir=str(target.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as out, source.open("rb") as src:
            for chunk in iter(lambda: src.read(_CHUNK), b""):
                out.write(chunk)
            out.flush()
            os.fsync(out.fileno())
        # Verify the temporary file is complete BEFORE publishing it.
        if _sha256_of(tmp_path) != expected_sha or tmp_path.stat().st_size != expected_size:
            raise MaterializationError(
                "temp_verify_failed", "temporary file failed verification before publication"
            )
        try:
            os.link(tmp_path, target)
        except FileExistsError:
            # A target appeared during the race. Never overwrite it.
            return "raced"
        except (OSError, NotImplementedError, AttributeError) as exc:
            raise MaterializationError(
                "no_clobber_unsupported",
                "atomic no-clobber link is not supported on this filesystem",
            ) from exc
        return "published"
    finally:
        # Remove the temporary link on success and on ordinary failure. A raced
        # or published target is a distinct directory entry and is untouched.
        # A genuine cleanup OSError (other than 'already gone') is not suppressed.
        tmp_path.unlink(missing_ok=True)


def _materialize_entries(
    *,
    entries: list[dict[str, Any]],
    source_base: Path,
    target_base: Path,
    selected: set[str],
    dry_run: bool,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Core byte-level loop shared by every manifest group.

    ``source_base`` / ``target_base`` are the directories the manifest paths are
    relative to (``datasets/v2`` for the benchmark group, the repository root for
    the redteam group). Fail-closed on any integrity or path-safety condition.
    """
    file_results: list[dict[str, Any]] = []
    counts = {"materialized": 0, "reused": 0, "would_materialize": 0, "skipped_not_selected": 0}

    for entry in entries:
        rel = entry["path"]
        expected_sha = entry["sha256"]
        expected_size = entry["size_bytes"]
        rel_path = Path(rel)

        if rel not in selected:
            counts["skipped_not_selected"] += 1
            file_results.append({"path": rel, "action": "skipped_not_selected",
                                 "expected_sha256": expected_sha, "expected_size_bytes": expected_size})
            continue

        source_file = _safe_resolved(source_base, rel_path, label="source")
        target_file = _safe_resolved(target_base, rel_path, label="target")

        if not source_file.exists():
            raise MaterializationError("source_missing", f"source artifact is missing: {rel}")
        if _is_symlink_or_reparse(source_file):
            raise MaterializationError("symlink_rejected", f"source artifact is a symlink/reparse point: {rel}")
        if not source_file.is_file():
            raise MaterializationError("source_not_file", f"source artifact is not a regular file: {rel}")

        # Verify source identity BEFORE any copy.
        source_size = source_file.stat().st_size
        if source_size != expected_size:
            raise MaterializationError(
                "source_size_mismatch",
                f"source size {source_size} != manifest {expected_size} for {rel}",
            )
        source_sha = _sha256_of(source_file)
        if source_sha != expected_sha:
            raise MaterializationError(
                "source_hash_mismatch",
                f"source SHA-256 does not match manifest for {rel}",
            )

        # A matching existing target is reused without rewriting.
        if target_file.exists():
            if _is_symlink_or_reparse(target_file):
                raise MaterializationError("target_symlink", f"target artifact is a symlink/reparse point: {rel}")
            if not target_file.is_file():
                raise MaterializationError("target_not_file", f"target artifact is not a regular file: {rel}")
            target_sha = _sha256_of(target_file)
            if target_sha == expected_sha and target_file.stat().st_size == expected_size:
                counts["reused"] += 1
                file_results.append({"path": rel, "action": "reused",
                                     "sha256": expected_sha, "size_bytes": expected_size})
                continue
            # Fail closed: never overwrite a mismatching existing target.
            raise MaterializationError(
                "target_mismatch",
                f"existing target differs from manifest and will not be overwritten: {rel}",
            )

        if dry_run:
            counts["would_materialize"] += 1
            file_results.append({"path": rel, "action": "would_materialize",
                                 "sha256": expected_sha, "size_bytes": expected_size})
            continue

        outcome = _publish_no_clobber(
            source_file, target_file, expected_sha=expected_sha, expected_size=expected_size
        )

        if outcome == "raced":
            # A target appeared during the check→publish window. Never overwrite:
            # re-verify it, accept only if byte-identical, otherwise fail closed.
            if not target_file.exists():
                raise MaterializationError(
                    "race_inconsistent",
                    f"no-clobber link reported an existing target that is now absent: {rel}",
                )
            if _is_symlink_or_reparse(target_file) or not target_file.is_file():
                raise MaterializationError(
                    "target_mismatch",
                    f"a target appeared during the race and is not a regular file: {rel}",
                )
            raced_sha = _sha256_of(target_file)
            if raced_sha == expected_sha and target_file.stat().st_size == expected_size:
                counts["reused"] += 1
                file_results.append({"path": rel, "action": "reused_concurrent",
                                     "sha256": expected_sha, "size_bytes": expected_size})
                continue
            raise MaterializationError(
                "target_mismatch",
                f"a target appeared during the race and differs; not overwritten: {rel}",
            )

        # Verify the published target identity AFTER publication.
        after_size = target_file.stat().st_size
        after_sha = _sha256_of(target_file)
        if after_size != expected_size or after_sha != expected_sha:
            raise MaterializationError(
                "target_verify_failed",
                f"post-publication verification failed for {rel}",
            )
        counts["materialized"] += 1
        file_results.append({"path": rel, "action": "materialized",
                             "sha256": expected_sha, "size_bytes": expected_size})

    return file_results, counts


def materialize_frozen_artifacts(
    *,
    source_root: Path,
    target_root: Path,
    manifest_path: Path | None = None,
    only_paths: list[str] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Materialize every benchmark-v2 FINAL-frozen artifact from source to target.

    Backward-compatible single-group entry point. Returns a content-free summary.
    Raises ``MaterializationError`` (fail closed) on any integrity, path-safety
    or mismatch condition.
    """
    source_root = source_root.expanduser().resolve()
    target_root = target_root.expanduser().resolve()
    if not source_root.is_dir():
        raise MaterializationError("source_root", f"source root is not a directory: {source_root}")
    if not target_root.is_dir():
        raise MaterializationError("target_root", f"target root is not a directory: {target_root}")

    resolved_manifest = (
        manifest_path.expanduser().resolve()
        if manifest_path is not None
        else target_root / MANIFEST_RELPATH
    )
    manifest = load_manifest(resolved_manifest)
    allow = {entry["path"] for entry in manifest["entries"]}

    if only_paths is not None:
        extra = sorted(set(only_paths) - allow)
        if extra:
            raise MaterializationError(
                "extra_selected",
                f"requested paths are not in the FINAL manifest allowlist: {extra}",
            )
        selected = set(only_paths)
    else:
        selected = allow

    file_results, counts = _materialize_entries(
        entries=manifest["entries"],
        source_base=source_root / BENCHMARK_SUBDIR,
        target_base=target_root / BENCHMARK_SUBDIR,
        selected=selected,
        dry_run=dry_run,
    )

    return {
        "schema_version": 1,
        "tool": "materialize_v2_frozen_artifacts",
        "manifest_status": manifest["manifest_status"],
        "manifest_path": str(resolved_manifest),
        "source_root": str(source_root),
        "target_root": str(target_root),
        "dry_run": dry_run,
        "artifact_count": len(manifest["entries"]),
        "counts": counts,
        "files": file_results,
        "ok": True,
    }


def _materialize_group(
    *,
    source_root: Path,
    target_root: Path,
    manifest_path: Path,
    base_subdir: Path,
    dry_run: bool,
    expected_paths: frozenset[str] | None = None,
    require_artifact_class: str | None = None,
) -> dict[str, Any]:
    """Load one manifest and materialize its group; return a content-free summary."""
    resolved_manifest = manifest_path.expanduser().resolve()
    manifest = load_manifest(
        resolved_manifest,
        expected_paths=expected_paths,
        require_artifact_class=require_artifact_class,
    )
    selected = {entry["path"] for entry in manifest["entries"]}
    file_results, counts = _materialize_entries(
        entries=manifest["entries"],
        source_base=source_root / base_subdir,
        target_base=target_root / base_subdir,
        selected=selected,
        dry_run=dry_run,
    )
    return {
        "manifest_status": manifest["manifest_status"],
        "artifact_class": manifest["artifact_class"],
        "manifest_path": str(resolved_manifest),
        "artifact_count": len(manifest["entries"]),
        "counts": counts,
        "files": file_results,
    }


def materialize(
    *,
    source_root: Path,
    target_root: Path,
    include_redteam_prompts: bool = False,
    benchmark_manifest_path: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Orchestrate materialization of one or more governed manifest groups.

    Always processes the benchmark-v2 group. When ``include_redteam_prompts`` is
    set, additionally processes the governed redteam release-test-fixture group
    (a strict one-file allowlist). Returns a content-free summary that separates
    ``benchmark_v2`` and ``redteam_prompts``. The trusted artifact allowlist is
    not broadened for the default (flag-absent) run.
    """
    source_root = source_root.expanduser().resolve()
    target_root = target_root.expanduser().resolve()
    if not source_root.is_dir():
        raise MaterializationError("source_root", f"source root is not a directory: {source_root}")
    if not target_root.is_dir():
        raise MaterializationError("target_root", f"target root is not a directory: {target_root}")

    groups: dict[str, Any] = {}
    groups["benchmark_v2"] = _materialize_group(
        source_root=source_root,
        target_root=target_root,
        manifest_path=(benchmark_manifest_path if benchmark_manifest_path is not None
                       else target_root / MANIFEST_RELPATH),
        base_subdir=BENCHMARK_SUBDIR,
        dry_run=dry_run,
    )
    if include_redteam_prompts:
        groups["redteam_prompts"] = _materialize_group(
            source_root=source_root,
            target_root=target_root,
            manifest_path=target_root / REDTEAM_MANIFEST_RELPATH,
            base_subdir=Path("."),
            dry_run=dry_run,
            expected_paths=REDTEAM_EXPECTED_PATHS,
            require_artifact_class=REDTEAM_ARTIFACT_CLASS,
        )

    return {
        "schema_version": 1,
        "tool": "materialize_v2_frozen_artifacts",
        "source_root": str(source_root),
        "target_root": str(target_root),
        "dry_run": dry_run,
        "include_redteam_prompts": include_redteam_prompts,
        "groups": groups,
        "ok": True,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path,
                        help="Repository root that already contains the frozen artifacts.")
    parser.add_argument("--target-root", required=True, type=Path,
                        help="Repository root (e.g. a fresh worktree) to materialize into.")
    parser.add_argument("--manifest", type=Path, default=None,
                        help="Optional explicit benchmark FINAL manifest path (defaults to the target's manifest).")
    parser.add_argument("--include-redteam-prompts", action="store_true",
                        help="Also materialize the governed redteam/prompts.jsonl release-test fixture.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Verify source identities and report actions without writing.")
    parser.add_argument("--summary-out", type=Path, default=None,
                        help="Optional path to write the content-free JSON summary.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.include_redteam_prompts:
            summary = materialize(
                source_root=args.source_root,
                target_root=args.target_root,
                include_redteam_prompts=True,
                benchmark_manifest_path=args.manifest,
                dry_run=args.dry_run,
            )
        else:
            # Backward-compatible default: benchmark-only flat summary.
            summary = materialize_frozen_artifacts(
                source_root=args.source_root,
                target_root=args.target_root,
                manifest_path=args.manifest,
                dry_run=args.dry_run,
            )
    except MaterializationError as exc:
        payload = {"schema_version": 1, "tool": "materialize_v2_frozen_artifacts",
                   "ok": False, "error_code": exc.code, "error": exc.message}
        text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
        if args.summary_out is not None:
            args.summary_out.write_text(text + "\n", encoding="utf-8")
        print(text, file=sys.stderr)
        return 1

    text = json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False)
    if args.summary_out is not None:
        args.summary_out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
