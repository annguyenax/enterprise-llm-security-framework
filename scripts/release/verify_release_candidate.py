"""Verify a Phase 12G release candidate ZIP without modifying or extracting it.

Independently parses and validates ``release-manifest.json``, ``SHA256SUMS.txt``
and ``FILE_SIZES.json`` with exact set-equality per the explicit control-file
coverage rule, re-validates the embedded release-policy identity, and confirms no
prohibited/JSONL/result entry. Returns PASS, FAIL or NOT_VERIFIABLE; NOT_VERIFIABLE
is never treated as PASS.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from release_common import (  # type: ignore
        CHECKSUMS_NAME, MANIFEST_NAME, PAYLOAD_PREFIX, POLICY_RELPATH, POLICY_SCHEMA_VERSION,
        SIZES_NAME, ReleaseError, classify_prohibited, is_hex40, is_hex64, is_symlink_or_reparse,
        load_json_no_dupes, parse_checksum_text, parse_release_policy, read_zip_entries, sha256_bytes,
    )
else:
    from .release_common import (  # noqa: F401
        CHECKSUMS_NAME, MANIFEST_NAME, PAYLOAD_PREFIX, POLICY_RELPATH, POLICY_SCHEMA_VERSION,
        SIZES_NAME, ReleaseError, classify_prohibited, is_hex40, is_hex64, is_symlink_or_reparse,
        load_json_no_dupes, parse_checksum_text, parse_release_policy, read_zip_entries, sha256_bytes,
    )

POLICY_ARCHIVE_PATH = f"{PAYLOAD_PREFIX}{POLICY_RELPATH}"


def _report(status: str, findings: list[dict[str, Any]], not_verifiable: list[dict[str, Any]],
            **extra: Any) -> dict[str, Any]:
    return {"schema_version": 1, "tool": "verify_release_candidate", "status": status,
            "passed": status == "PASS", "findings": findings, "not_verifiable": not_verifiable, **extra}


def _fail(code: str, message: str) -> dict[str, Any]:
    return _report("FAIL", [{"code": code, "message": message}], [])


def verify_release_candidate(zip_path: Path) -> dict[str, Any]:
    zip_path = zip_path.expanduser().resolve()
    if is_symlink_or_reparse(zip_path) or not zip_path.is_file():
        return _fail("zip_input", "release ZIP must be a regular non-link file")
    try:
        entries = read_zip_entries(zip_path)  # rejects duplicate/unsafe paths
    except ReleaseError as exc:
        return _fail(exc.code, exc.message)

    findings: list[dict[str, Any]] = []
    not_verifiable: list[dict[str, Any]] = []

    for required in (MANIFEST_NAME, CHECKSUMS_NAME, SIZES_NAME):
        if required not in entries:
            findings.append({"code": "missing_control_file", "message": f"{required} is missing"})
    if findings:
        return _report("FAIL", findings, [])

    payload = {n for n in entries if n.startswith(PAYLOAD_PREFIX)}
    control = {MANIFEST_NAME, CHECKSUMS_NAME, SIZES_NAME}
    unexpected = set(entries) - payload - control
    for name in sorted(unexpected):
        findings.append({"code": "unexpected_entry", "message": f"unaccounted archive entry: {name}"})

    try:
        manifest = load_json_no_dupes(entries[MANIFEST_NAME], "release-manifest.json")
    except ReleaseError as exc:
        return _fail(exc.code, exc.message)
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 2:
        return _fail("manifest_schema", "release-manifest schema_version must be 2")
    if not is_hex40(manifest.get("repo_head")):
        return _fail("identity_format", "repo_head is not a 40-hex commit id")
    if manifest.get("base_sha") is not None and not is_hex40(manifest.get("base_sha")):
        return _fail("identity_format", "base_sha is present but malformed")
    if not is_hex64(manifest.get("policy_sha256")):
        return _fail("manifest_schema", "policy_sha256 is malformed")
    if manifest.get("policy_schema_version") != POLICY_SCHEMA_VERSION:
        return _fail("manifest_schema", "policy_schema_version mismatch")
    mfiles = manifest.get("files")
    if not isinstance(mfiles, list):
        return _fail("manifest_schema", "manifest files must be a list")

    manifest_by_archive: dict[str, dict[str, Any]] = {}
    for item in mfiles:
        if not isinstance(item, dict) or "archive_path" not in item:
            return _fail("manifest_schema", "manifest file entry is malformed")
        ap = item["archive_path"]
        if not is_hex64(item.get("sha256")) or type(item.get("size_bytes")) is not int or item["size_bytes"] < 0:
            return _fail("manifest_schema", f"manifest integrity fields malformed: {ap}")
        if ap in manifest_by_archive:
            return _fail("manifest_schema", f"manifest lists a duplicate archive path: {ap}")
        manifest_by_archive[ap] = item

    if set(manifest_by_archive) != payload:
        findings.append({"code": "manifest_payload_mismatch",
                         "message": "manifest file set != ZIP payload set"})
    else:
        for ap, item in manifest_by_archive.items():
            data = entries[ap]
            if sha256_bytes(data) != item["sha256"]:
                findings.append({"code": "changed_file", "message": f"{ap} hash mismatch"})
            if len(data) != item["size_bytes"]:
                findings.append({"code": "changed_file", "message": f"{ap} size mismatch"})

    try:
        sizes = load_json_no_dupes(entries[SIZES_NAME], "FILE_SIZES.json")
    except ReleaseError as exc:
        return _fail(exc.code, exc.message)
    sfiles = sizes.get("files") if isinstance(sizes, dict) else None
    if not isinstance(sfiles, dict):
        return _fail("sizes_schema", "FILE_SIZES.files must be an object")
    expected_size_keys = payload | {MANIFEST_NAME}
    if set(sfiles) != expected_size_keys:
        findings.append({"code": "sizes_set_mismatch",
                         "message": "FILE_SIZES key set != payload + manifest"})
    else:
        for name, sz in sfiles.items():
            if type(sz) is not int or sz < 0:
                findings.append({"code": "sizes_schema", "message": f"invalid size for {name}"})
            elif len(entries[name]) != sz:
                findings.append({"code": "changed_file", "message": f"{name} size disagreement"})

    try:
        sums = parse_checksum_text(entries[CHECKSUMS_NAME])
    except ReleaseError as exc:
        return _fail(exc.code, exc.message)
    expected_sum_keys = payload | {MANIFEST_NAME, SIZES_NAME}
    if set(sums) != expected_sum_keys:
        findings.append({"code": "checksums_set_mismatch",
                         "message": "SHA256SUMS key set != payload + manifest + FILE_SIZES"})
    else:
        for name, digest in sums.items():
            if sha256_bytes(entries[name]) != digest:
                findings.append({"code": "changed_file", "message": f"{name} checksum disagreement"})

    if POLICY_ARCHIVE_PATH not in entries:
        not_verifiable.append({"code": "policy_absent",
                               "message": "embedded release policy not present; cannot validate policy identity"})
    else:
        policy = None
        try:
            policy = parse_release_policy(entries[POLICY_ARCHIVE_PATH])
        except ReleaseError as exc:
            findings.append({"code": "policy_invalid", "message": f"embedded policy invalid: {exc.code}"})
        if policy is not None:
            if policy.sha256 != manifest.get("policy_sha256"):
                findings.append({"code": "policy_identity_mismatch",
                                 "message": "embedded policy SHA-256 != manifest policy_sha256"})
            for name in payload:
                rel = name[len(PAYLOAD_PREFIX):]
                if name.casefold().endswith(".jsonl"):
                    findings.append({"code": "jsonl_present", "message": f"JSONL entry present: {name}"})
                klass = classify_prohibited(rel, policy)
                if klass is not None:
                    findings.append({"code": "prohibited_present", "message": f"{name} prohibited ({klass})"})

    if not findings and not payload:
        not_verifiable.append({"code": "empty_payload",
                               "message": "archive has no repository payload to verify"})

    if findings:
        status = "FAIL"
    elif not_verifiable:
        status = "NOT_VERIFIABLE"
    else:
        status = "PASS"
    return _report(status, findings, not_verifiable, repo_head=manifest.get("repo_head"),
                   payload_count=len(payload), control_count=len(control), entry_count=len(entries))


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
