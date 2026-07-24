"""Verify a Phase 12G release candidate ZIP without modifying it.

Returns PASS, FAIL or NOT_VERIFIABLE. NOT_VERIFIABLE is never treated as PASS.
It never extracts unsafe paths, never modifies the source ZIP, and never parses
benchmark records or ``result.json``.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from release_common import (  # type: ignore
        ReleaseError, classify_prohibited, is_hex40, is_hex64, is_symlink_or_reparse,
        read_zip_entries, sha256_bytes,
    )
else:
    from .release_common import (
        ReleaseError, classify_prohibited, is_hex40, is_hex64, is_symlink_or_reparse,
        read_zip_entries, sha256_bytes,
    )

MANIFEST_NAME = "release-manifest.json"
CHECKSUMS_NAME = "SHA256SUMS.txt"
SIZES_NAME = "FILE_SIZES.json"


def _fail(code: str, message: str) -> dict[str, Any]:
    return {"schema_version": 1, "tool": "verify_release_candidate",
            "status": "FAIL", "passed": False,
            "findings": [{"code": code, "message": message}], "not_verifiable": []}


def verify_release_candidate(zip_path: Path) -> dict[str, Any]:
    zip_path = zip_path.expanduser().resolve()
    if is_symlink_or_reparse(zip_path) or not zip_path.is_file():
        return _fail("zip_input", "release ZIP must be a regular non-link file")

    try:
        entries = read_zip_entries(zip_path)
    except ReleaseError as exc:
        return _fail(exc.code, exc.message)

    findings: list[dict[str, Any]] = []
    not_verifiable: list[dict[str, Any]] = []

    # Required control files present.
    for required in (MANIFEST_NAME, CHECKSUMS_NAME, SIZES_NAME):
        if required not in entries:
            findings.append({"code": "missing_control_file", "message": f"{required} is missing"})
    if findings:
        return {"schema_version": 1, "tool": "verify_release_candidate",
                "status": "FAIL", "passed": False, "findings": findings, "not_verifiable": []}

    # Manifest structure + commit-identity format.
    try:
        manifest = json.loads(entries[MANIFEST_NAME].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _fail("manifest_schema", "release-manifest.json is not strict UTF-8 JSON")
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        return _fail("manifest_schema", "release-manifest schema_version must be 1")
    if not is_hex40(manifest.get("repo_head")):
        return _fail("identity_format", "repo_head is not a 40-hex commit id")
    if manifest.get("base_sha") is not None and not is_hex40(manifest.get("base_sha")):
        return _fail("identity_format", "base_sha is present but malformed")
    manifest_files = manifest.get("files")
    if not isinstance(manifest_files, list):
        return _fail("manifest_schema", "manifest files must be a list")

    # Every payload entry (except control files) is prohibited-clean and safe.
    payload_names = set(entries) - {MANIFEST_NAME, CHECKSUMS_NAME, SIZES_NAME}
    for name in payload_names:
        pure = PurePosixPath(name)
        if pure.is_absolute() or ".." in pure.parts or name.startswith("/") or "\\" in name:
            findings.append({"code": "unsafe_path", "message": f"unsafe entry path: {name}"})
            continue
        # Payload entries live under repo/; classify the repo-relative tail.
        rel = name[len("repo/"):] if name.startswith("repo/") else name
        if name.casefold().endswith(".jsonl"):
            findings.append({"code": "jsonl_present", "message": f"JSONL entry present: {name}"})
        klass = classify_prohibited(rel)
        if klass is not None:
            findings.append({"code": "prohibited_present", "message": f"{name} is prohibited ({klass})"})

    # Manifest ↔ payload consistency: hashes and sizes.
    manifest_by_archive: dict[str, dict[str, Any]] = {}
    for item in manifest_files:
        if not isinstance(item, dict) or "archive_path" not in item:
            return _fail("manifest_schema", "manifest file entry is malformed")
        ap = item["archive_path"]
        if not is_hex64(item.get("sha256")) or type(item.get("size_bytes")) is not int:
            return _fail("manifest_schema", f"manifest integrity fields malformed: {ap}")
        manifest_by_archive[ap] = item

    if set(manifest_by_archive) != payload_names:
        findings.append({"code": "manifest_mismatch",
                         "message": "manifest file set does not match ZIP payload"})
    else:
        for ap, item in manifest_by_archive.items():
            data = entries[ap]
            if sha256_bytes(data) != item["sha256"]:
                findings.append({"code": "changed_file", "message": f"{ap} hash mismatch"})
            if len(data) != item["size_bytes"]:
                findings.append({"code": "changed_file", "message": f"{ap} size mismatch"})

    # SHA256SUMS.txt consistency for the control-file set.
    try:
        sums_lines = entries[CHECKSUMS_NAME].decode("ascii").splitlines()
    except UnicodeDecodeError:
        return _fail("checksums_schema", "SHA256SUMS.txt is not ASCII")
    listed: dict[str, str] = {}
    for line in sums_lines:
        parts = line.split("  ", 1)
        if len(parts) != 2:
            findings.append({"code": "checksums_schema", "message": "checksum line is malformed"})
            continue
        digest, name = parts
        if name in listed:
            findings.append({"code": "checksums_duplicate", "message": f"duplicate checksum entry: {name}"})
        listed[name] = digest
    for name, digest in listed.items():
        if name in entries and sha256_bytes(entries[name]) != digest:
            findings.append({"code": "changed_file", "message": f"{name} checksum mismatch"})

    # A structurally valid archive that carries no repository payload cannot be
    # confirmed as a real release candidate: NOT_VERIFIABLE, never PASS.
    if not findings and not payload_names:
        not_verifiable.append({"code": "empty_payload",
                               "message": "archive has no repository payload to verify"})

    if findings:
        status = "FAIL"
    elif not_verifiable:
        status = "NOT_VERIFIABLE"
    else:
        status = "PASS"
    return {"schema_version": 1, "tool": "verify_release_candidate",
            "status": status, "passed": status == "PASS",
            "repo_head": manifest.get("repo_head"),
            "entry_count": len(entries), "payload_count": len(payload_names),
            "findings": findings, "not_verifiable": not_verifiable}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = verify_release_candidate(args.zip)
    text = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False)
    if args.output is not None:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    if report["status"] == "PASS":
        return 0
    if report["status"] == "NOT_VERIFIABLE":
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
