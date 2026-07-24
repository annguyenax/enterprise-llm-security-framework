"""Deterministic Phase 12G release-candidate builder.

Builds a release ZIP from tracked Git files plus an explicit operator-supplied
generated-file allowlist. Fail-closed: any prohibited pattern, unsafe path,
symlink, tracked JSONL, dirty tree, or existing output aborts the build.

It never packages ignored files by discovery, never parses benchmark records or
``result.json``, and never prints record or secret content. Output is a
deterministic ZIP plus a canonical ``release-manifest.json``, ``SHA256SUMS.txt``
and ``FILE_SIZES.json``; the ZIP is reopened and verified before publication.

Usage:

    python scripts/release/build_release_candidate.py \
        --repo-root <REPO> --output-dir <OUT> \
        --expected-head <SHA> --expected-branch <BRANCH> --base-sha <SHA> \
        [--generated-allowlist <JSON>] [--summary-out <JSON>]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from release_common import (  # type: ignore
        ReleaseError, assert_within, checksum_text, classify_prohibited,
        deterministic_zip_bytes, exclusive_write, is_hex40, is_symlink_or_reparse,
        read_zip_entries, sha256_bytes, sha256_file, validate_relative_posix,
    )
else:
    from .release_common import (
        ReleaseError, assert_within, checksum_text, classify_prohibited,
        deterministic_zip_bytes, exclusive_write, is_hex40, is_symlink_or_reparse,
        read_zip_entries, sha256_bytes, sha256_file, validate_relative_posix,
    )

MANIFEST_NAME = "release-manifest.json"
CHECKSUMS_NAME = "SHA256SUMS.txt"
SIZES_NAME = "FILE_SIZES.json"
ZIP_NAME = "release-candidate.zip"
MANIFEST_SCHEMA_VERSION = 1


def _git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise ReleaseError("git_error", f"git {' '.join(args)} failed")
    return result.stdout


def _require_clean_tree(repo_root: Path) -> None:
    # Only tracked modifications and staged changes make the tree "dirty".
    # Untracked files are never packaged by discovery (the build sources tracked
    # files plus an explicit generated allowlist), so untracked operator files
    # such as a generated dependency inventory must not fail the build.
    status = _git(repo_root, "status", "--porcelain", "--untracked-files=no")
    if status.strip():
        raise ReleaseError("dirty_tree", "repository working tree has tracked modifications")


def _tracked_files(repo_root: Path) -> list[str]:
    raw = _git(repo_root, "ls-files", "-z")
    files = [item for item in raw.split("\0") if item]
    return sorted(files)


def _load_generated_allowlist(path: Path) -> list[dict[str, Any]]:
    if is_symlink_or_reparse(path):
        raise ReleaseError("generated_allowlist", "generated allowlist is a symlink/reparse point")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseError("generated_allowlist", "generated allowlist is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ReleaseError("generated_allowlist", "generated allowlist schema_version must be 1")
    files = payload.get("files")
    if not isinstance(files, list):
        raise ReleaseError("generated_allowlist", "generated allowlist 'files' must be a list")
    entries: list[dict[str, Any]] = []
    for item in files:
        if not isinstance(item, dict) or set(item) != {"path", "sha256", "size_bytes"}:
            raise ReleaseError("generated_allowlist", "each generated entry needs path/sha256/size_bytes")
        rel = validate_relative_posix(item["path"], label="generated path")
        size = item["size_bytes"]
        if type(size) is not int or size < 0:
            raise ReleaseError("generated_allowlist", f"size_bytes must be a non-negative int: {rel}")
        sha = item["sha256"]
        if not isinstance(sha, str) or len(sha) != 64:
            raise ReleaseError("generated_allowlist", f"sha256 must be 64 hex chars: {rel}")
        entries.append({"path": rel, "sha256": sha.lower(), "size_bytes": size})
    return entries


def _collect_entry(repo_root: Path, rel: str, *, source: str) -> dict[str, Any]:
    rel = validate_relative_posix(rel, label="tracked path")
    prohibited = classify_prohibited(rel)
    if prohibited is not None:
        raise ReleaseError("prohibited_artifact", f"{rel} is prohibited ({prohibited})")
    absolute = repo_root / Path(rel)
    assert_within(repo_root, absolute, label=rel)
    # Reject a symlink/reparse at any existing component.
    partial = repo_root
    for part in Path(rel).parts:
        partial = partial / part
        if partial.exists() and is_symlink_or_reparse(partial):
            raise ReleaseError("symlink_rejected", f"{rel} passes through a symlink/reparse point")
    if not absolute.is_file():
        raise ReleaseError("missing_source", f"declared file is absent: {rel}")
    digest, size = sha256_file(absolute)
    return {"path": rel, "sha256": digest, "size_bytes": size, "source": source,
            "_bytes": absolute.read_bytes()}


def build_release_candidate(
    *,
    repo_root: Path,
    output_dir: Path,
    expected_head: str | None = None,
    expected_branch: str | None = None,
    base_sha: str | None = None,
    generated_allowlist: Path | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    if not (repo_root / ".git").exists():
        raise ReleaseError("repo_root", "repo-root is not a Git repository")

    # Output must not already exist (no-clobber, no reuse).
    zip_path = output_dir / ZIP_NAME
    if output_dir.exists():
        raise ReleaseError("output_reuse", "output directory already exists")
    if zip_path.exists():
        raise ReleaseError("output_reuse", "release ZIP already exists")

    _require_clean_tree(repo_root)
    head = _git(repo_root, "rev-parse", "HEAD").strip()
    branch = _git(repo_root, "rev-parse", "--abbrev-ref", "HEAD").strip()
    if expected_head is not None and head != expected_head:
        raise ReleaseError("identity_mismatch", "HEAD does not match --expected-head")
    if expected_branch is not None and branch != expected_branch:
        raise ReleaseError("identity_mismatch", "branch does not match --expected-branch")
    if base_sha is not None and not is_hex40(base_sha):
        raise ReleaseError("identity_format", "--base-sha is not a 40-hex commit id")

    tracked = _tracked_files(repo_root)
    # Reject tracked JSONL explicitly (defence-in-depth over the prohibited scan).
    tracked_jsonl = [rel for rel in tracked if rel.casefold().endswith(".jsonl")]
    if tracked_jsonl:
        raise ReleaseError("tracked_jsonl", f"tracked JSONL is prohibited: {tracked_jsonl[:3]}")

    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rel in tracked:
        if classify_prohibited(rel) is not None:
            raise ReleaseError("prohibited_artifact",
                               f"tracked file is prohibited: {rel} ({classify_prohibited(rel)})")
        entry = _collect_entry(repo_root, rel, source="tracked")
        key = entry["path"].casefold()
        if key in seen:
            raise ReleaseError("duplicate_logical_path", f"duplicate logical path: {entry['path']}")
        seen.add(key)
        entries.append(entry)

    generated_entries: list[dict[str, Any]] = []
    if generated_allowlist is not None:
        for declared in _load_generated_allowlist(generated_allowlist.expanduser().resolve()):
            rel = declared["path"]
            entry = _collect_entry(repo_root, rel, source="generated")
            if entry["sha256"] != declared["sha256"] or entry["size_bytes"] != declared["size_bytes"]:
                raise ReleaseError("generated_mismatch", f"generated file does not match its pin: {rel}")
            key = entry["path"].casefold()
            if key in seen:
                raise ReleaseError("duplicate_logical_path", f"generated path duplicates a tracked path: {rel}")
            seen.add(key)
            generated_entries.append(entry)

    all_entries = sorted(entries + generated_entries, key=lambda item: item["path"])

    # Assemble the ZIP payload under a repo/ prefix; add manifest/sums/sizes.
    payload: dict[str, bytes] = {f"repo/{e['path']}": e["_bytes"] for e in all_entries}

    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "policy": "phase12g-release-allowlist-v1",
        "repo_head": head,
        "repo_branch": branch,
        "base_sha": base_sha,
        "expected_head": expected_head,
        "expected_branch": expected_branch,
        "file_count": len(all_entries),
        "tracked_count": len(entries),
        "generated_count": len(generated_entries),
        "files": [
            {"archive_path": f"repo/{e['path']}", "path": e["path"],
             "sha256": e["sha256"], "size_bytes": e["size_bytes"], "source": e["source"]}
            for e in all_entries
        ],
        "content_controls": {
            "jsonl_included": False,
            "result_json_included": False,
            "credentials_included": False,
            "databases_included": False,
            "git_metadata_included": False,
            "venv_included": False,
            "built_from": "git ls-files + explicit generated allowlist",
        },
        "zip_policy": {"entry_order": "lexical", "timestamp": "1980-01-01T00:00:00",
                       "permissions": "0644", "compression": "deflate-9"},
    }
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    payload[MANIFEST_NAME] = manifest_bytes
    sizes = {"schema_version": 1, "files": {name: len(data) for name, data in sorted(payload.items())}}
    payload[SIZES_NAME] = (json.dumps(sizes, indent=2, sort_keys=True) + "\n").encode("utf-8")
    payload[CHECKSUMS_NAME] = checksum_text(payload)

    zip_bytes = deterministic_zip_bytes(payload)

    # Publish atomically (no-clobber): create output dir exclusively, then the
    # ZIP and sidecars with exclusive create.
    try:
        output_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise ReleaseError("output_reuse", "output directory appeared during build") from exc
    exclusive_write(zip_path, zip_bytes)
    exclusive_write(output_dir / MANIFEST_NAME, manifest_bytes)
    exclusive_write(output_dir / SIZES_NAME, payload[SIZES_NAME])
    exclusive_write(output_dir / CHECKSUMS_NAME, checksum_text({
        ZIP_NAME: zip_bytes, MANIFEST_NAME: manifest_bytes, SIZES_NAME: payload[SIZES_NAME],
    }))

    # Reopen and verify the ZIP against the in-memory payload.
    reopened = read_zip_entries(zip_path)
    if set(reopened) != set(payload):
        raise ReleaseError("zip_verification", "ZIP entry allowlist is inconsistent after reopen")
    for name, data in payload.items():
        if sha256_bytes(reopened[name]) != sha256_bytes(data):
            raise ReleaseError("zip_verification", "ZIP entry bytes changed after reopen")

    return {
        "schema_version": 1,
        "tool": "build_release_candidate",
        "ok": True,
        "repo_head": head,
        "repo_branch": branch,
        "output_dir": str(output_dir),
        "zip_path": str(zip_path),
        "zip_sha256": sha256_bytes(zip_bytes),
        "zip_size_bytes": len(zip_bytes),
        "zip_entry_count": len(payload),
        "repo_file_count": len(all_entries),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--expected-head", default=None)
    parser.add_argument("--expected-branch", default=None)
    parser.add_argument("--base-sha", default=None)
    parser.add_argument("--generated-allowlist", type=Path, default=None)
    parser.add_argument("--summary-out", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        summary = build_release_candidate(
            repo_root=args.repo_root, output_dir=args.output_dir,
            expected_head=args.expected_head, expected_branch=args.expected_branch,
            base_sha=args.base_sha, generated_allowlist=args.generated_allowlist,
        )
    except ReleaseError as exc:
        payload = {"schema_version": 1, "tool": "build_release_candidate",
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
