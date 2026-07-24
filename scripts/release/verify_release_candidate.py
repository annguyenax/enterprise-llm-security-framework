"""Verify a Phase 12G release candidate ZIP without modifying or extracting it.

Independently validates ``release-manifest.json`` (exact schema 3),
``SHA256SUMS.txt`` and ``FILE_SIZES.json`` with exact set-equality per the
control-file coverage rule, re-validates the embedded closed-world policy
identity (policy_id + schema + SHA-256), re-classifies every payload path under
that policy (rejecting unclassified/prohibited paths and unsafe nested-archive
names), and checks deterministic ZIP metadata.

Every candidate-controlled parsing failure is converted into a content-free
structured result. Returns PASS, FAIL or NOT_VERIFIABLE:

* PASS            — all mandatory invariants were mechanically verified.
* FAIL            — the candidate is malformed, inconsistent, unsafe or incomplete.
* NOT_VERIFIABLE  — the environment lacks a required capability and the candidate
                    itself has not been proven malformed. NOT_VERIFIABLE is never
                    treated as PASS and never uses the PASS exit code.
"""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path
from typing import Any

import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from release_common import (  # type: ignore
        CHECKSUMS_NAME, CLASS_ALLOWED_ARCHIVE, CLASS_GENERATED, FILE_ENTRY_KEYS,
        INCLUSION_CLASSES, MANIFEST_NAME, MANIFEST_SCHEMA_VERSION, MANIFEST_TOP_KEYS,
        SIZES_NAME, PAYLOAD_PREFIX, POLICY_ID_KEYS, POLICY_RELPATH, POLICY_SCHEMA_VERSION, REPO_KEYS,
        COUNTS_KEYS, COVERAGE_KEYS, CONTENT_CONTROL_KEYS, ZIP_POLICY_KEYS, SIZES_TOP_KEYS,
        SOURCE_VALUES, ZIP_CREATE_SYSTEM, ZIP_EXTERNAL_ATTR, ZIP_TIMESTAMP,
        ReleaseError, VerificationError, classify_tracked_path, is_hex40, is_hex64,
        is_symlink_or_reparse, load_json_no_dupes, parse_checksum_text, parse_release_policy,
        read_zip_entries, require_boolean, require_exact_keys, require_list,
        require_non_negative_integer, require_normalized_relative_path, require_sha256,
        require_string, scan_archive_names, sha256_bytes, validate_relative_posix,
    )
else:
    from .release_common import (  # noqa: F401
        CHECKSUMS_NAME, CLASS_ALLOWED_ARCHIVE, CLASS_GENERATED, FILE_ENTRY_KEYS,
        INCLUSION_CLASSES, MANIFEST_NAME, MANIFEST_SCHEMA_VERSION, MANIFEST_TOP_KEYS,
        SIZES_NAME, PAYLOAD_PREFIX, POLICY_ID_KEYS, POLICY_RELPATH, POLICY_SCHEMA_VERSION, REPO_KEYS,
        COUNTS_KEYS, COVERAGE_KEYS, CONTENT_CONTROL_KEYS, ZIP_POLICY_KEYS, SIZES_TOP_KEYS,
        SOURCE_VALUES, ZIP_CREATE_SYSTEM, ZIP_EXTERNAL_ATTR, ZIP_TIMESTAMP,
        ReleaseError, VerificationError, classify_tracked_path, is_hex40, is_hex64,
        is_symlink_or_reparse, load_json_no_dupes, parse_checksum_text, parse_release_policy,
        read_zip_entries, require_boolean, require_exact_keys, require_list,
        require_non_negative_integer, require_normalized_relative_path, require_sha256,
        require_string, scan_archive_names, sha256_bytes, validate_relative_posix,
    )

POLICY_ARCHIVE_PATH = f"{PAYLOAD_PREFIX}{POLICY_RELPATH}"


def _report(status: str, findings: list[dict[str, Any]], not_verifiable: list[dict[str, Any]],
            **extra: Any) -> dict[str, Any]:
    return {"schema_version": 1, "tool": "verify_release_candidate", "status": status,
            "passed": status == "PASS", "findings": findings, "not_verifiable": not_verifiable, **extra}


def _fail(code: str, message: str) -> dict[str, Any]:
    return _report("FAIL", [{"code": code, "message": message}], [])


def _validate_manifest(manifest_bytes: bytes, payload: set[str]) -> dict[str, Any]:
    """Strict exact-schema validation of release-manifest.json (schema 3).
    Raises VerificationError on any defect; returns extracted facts."""
    manifest = load_json_no_dupes(manifest_bytes, MANIFEST_NAME)  # ReleaseError on JSON/UTF-8/dupes
    top = require_exact_keys(manifest, MANIFEST_TOP_KEYS, "manifest")
    if top["schema_version"] != MANIFEST_SCHEMA_VERSION:
        raise VerificationError("manifest_schema", f"manifest schema_version must be {MANIFEST_SCHEMA_VERSION}")

    repo = require_exact_keys(top["repository"], REPO_KEYS, "manifest.repository")
    head = repo["head"]
    if not is_hex40(head):
        raise VerificationError("identity_format", "manifest.repository.head is not a 40-hex commit id")
    require_string(repo, "branch", "manifest.repository")
    if repo["base_sha"] is not None and not is_hex40(repo["base_sha"]):
        raise VerificationError("identity_format", "manifest.repository.base_sha is malformed")

    pol = require_exact_keys(top["policy"], POLICY_ID_KEYS, "manifest.policy")
    policy_id = require_string(pol, "policy_id", "manifest.policy")
    if pol["schema_version"] != POLICY_SCHEMA_VERSION:
        raise VerificationError("manifest_schema", "manifest.policy.schema_version mismatch")
    policy_sha = require_sha256(pol, "sha256", "manifest.policy")

    counts = require_exact_keys(top["counts"], COUNTS_KEYS, "manifest.counts")
    for key in COUNTS_KEYS:
        require_non_negative_integer(counts, key, "manifest.counts")
    require_exact_keys(top["control_coverage"], COVERAGE_KEYS, "manifest.control_coverage")
    content = require_exact_keys(top["content_controls"], CONTENT_CONTROL_KEYS, "manifest.content_controls")
    for key in CONTENT_CONTROL_KEYS - {"built_from"}:
        require_boolean(content, key, "manifest.content_controls")
    require_string(content, "built_from", "manifest.content_controls")
    require_exact_keys(top["zip_policy"], ZIP_POLICY_KEYS, "manifest.zip_policy")

    files = require_list(top, "files", "manifest")
    by_archive: dict[str, dict[str, Any]] = {}
    for item in files:
        entry = require_exact_keys(item, FILE_ENTRY_KEYS, "manifest.files[]")
        path = require_normalized_relative_path(entry["path"], "manifest.files[].path")
        archive_path = require_string(entry, "archive_path", "manifest.files[]")
        if archive_path != f"{PAYLOAD_PREFIX}{path}":
            raise VerificationError("manifest_schema", "archive_path must equal repo/<path>")
        require_sha256(entry, "sha256", "manifest.files[]")
        require_non_negative_integer(entry, "size_bytes", "manifest.files[]")
        if entry["source"] not in SOURCE_VALUES:
            raise VerificationError("manifest_schema", "manifest.files[].source is invalid")
        if entry["classification"] not in (INCLUSION_CLASSES | {CLASS_GENERATED}):
            raise VerificationError("manifest_schema", "manifest.files[].classification is invalid")
        if (entry["source"] == "generated") != (entry["classification"] == CLASS_GENERATED):
            raise VerificationError("manifest_schema", "source/classification disagree")
        if archive_path in by_archive:
            raise VerificationError("manifest_schema", f"manifest lists a duplicate archive path: {archive_path}")
        by_archive[archive_path] = entry
    if counts["file_count"] != len(files):
        raise VerificationError("manifest_schema", "manifest.counts.file_count disagrees with files length")
    return {"head": head, "policy_id": policy_id, "policy_sha256": policy_sha,
            "by_archive": by_archive}


def _check_zip_metadata(zip_path: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    with zipfile.ZipFile(zip_path, "r") as archive:
        for info in archive.infolist():
            if info.is_dir():
                findings.append({"code": "zip_directory_entry", "message": f"{info.filename} is a directory entry"})
                continue
            if info.date_time != ZIP_TIMESTAMP:
                findings.append({"code": "nondeterministic_metadata", "message": f"{info.filename} timestamp not fixed"})
            if info.create_system != ZIP_CREATE_SYSTEM:
                findings.append({"code": "nondeterministic_metadata", "message": f"{info.filename} create_system not unix"})
            if info.external_attr != ZIP_EXTERNAL_ATTR:
                findings.append({"code": "nondeterministic_metadata", "message": f"{info.filename} mode not 0644"})
            if info.extra != b"":
                findings.append({"code": "nondeterministic_metadata", "message": f"{info.filename} has extra field"})
            if info.compress_type != zipfile.ZIP_DEFLATED:
                findings.append({"code": "nondeterministic_metadata", "message": f"{info.filename} not deflate"})
    return findings


def _verify(zip_path: Path) -> dict[str, Any]:
    zip_path = zip_path.expanduser().resolve()
    if is_symlink_or_reparse(zip_path) or not zip_path.is_file():
        return _fail("zip_input", "release ZIP must be a regular non-link file")

    entries = read_zip_entries(zip_path)  # ReleaseError -> caught by caller
    findings: list[dict[str, Any]] = []
    not_verifiable: list[dict[str, Any]] = []

    for required in (MANIFEST_NAME, CHECKSUMS_NAME, SIZES_NAME):
        if required not in entries:
            findings.append({"code": "missing_control_file", "message": f"{required} is missing"})
    if findings:
        return _report("FAIL", findings, [])

    payload = {n for n in entries if n.startswith(PAYLOAD_PREFIX)}
    control = {MANIFEST_NAME, CHECKSUMS_NAME, SIZES_NAME}
    for name in sorted(set(entries) - payload - control):
        findings.append({"code": "unexpected_entry", "message": f"unaccounted archive entry: {name}"})

    findings.extend(_check_zip_metadata(zip_path))

    facts = _validate_manifest(entries[MANIFEST_NAME], payload)  # VerificationError -> caught by caller
    by_archive = facts["by_archive"]
    if set(by_archive) != payload:
        findings.append({"code": "manifest_payload_mismatch", "message": "manifest file set != ZIP payload set"})
    else:
        for ap, item in by_archive.items():
            data = entries[ap]
            if sha256_bytes(data) != item["sha256"]:
                findings.append({"code": "changed_file", "message": f"{ap} hash mismatch"})
            if len(data) != item["size_bytes"]:
                findings.append({"code": "changed_file", "message": f"{ap} size mismatch"})

    sizes = load_json_no_dupes(entries[SIZES_NAME], SIZES_NAME)
    stop = require_exact_keys(sizes, SIZES_TOP_KEYS, "FILE_SIZES")
    if stop["schema_version"] != 1:
        raise VerificationError("sizes_schema", "FILE_SIZES.schema_version must be 1")
    sfiles = stop["files"]
    if not isinstance(sfiles, dict):
        raise VerificationError("sizes_schema", "FILE_SIZES.files must be an object")
    expected_size_keys = payload | {MANIFEST_NAME}
    if set(sfiles) != expected_size_keys:
        findings.append({"code": "sizes_set_mismatch", "message": "FILE_SIZES key set != payload + manifest"})
    else:
        for name, sz in sfiles.items():
            if type(sz) is not int or type(sz) is bool or sz < 0:
                findings.append({"code": "sizes_schema", "message": f"invalid size for {name}"})
            elif len(entries[name]) != sz:
                findings.append({"code": "changed_file", "message": f"{name} size disagreement"})

    sums = parse_checksum_text(entries[CHECKSUMS_NAME])
    expected_sum_keys = payload | {MANIFEST_NAME, SIZES_NAME}
    if set(sums) != expected_sum_keys:
        findings.append({"code": "checksums_set_mismatch",
                         "message": "SHA256SUMS key set != payload + manifest + FILE_SIZES"})
    else:
        for name, digest in sums.items():
            if sha256_bytes(entries[name]) != digest:
                findings.append({"code": "changed_file", "message": f"{name} checksum disagreement"})

    # Embedded closed-world policy identity + re-classification.
    if not payload:
        not_verifiable.append({"code": "empty_payload", "message": "archive has no repository payload to verify"})
    elif POLICY_ARCHIVE_PATH not in entries:
        findings.append({"code": "policy_absent", "message": "embedded release policy is absent"})
    else:
        try:
            policy = parse_release_policy(entries[POLICY_ARCHIVE_PATH])
        except ReleaseError as exc:
            findings.append({"code": "policy_invalid", "message": f"embedded policy invalid: {exc.code}"})
            policy = None
        if policy is not None:
            if policy.sha256 != facts["policy_sha256"]:
                findings.append({"code": "policy_identity_mismatch", "message": "policy SHA-256 != manifest"})
            if policy.policy_id != facts["policy_id"]:
                findings.append({"code": "policy_identity_mismatch", "message": "policy_id != manifest"})
            for name in sorted(payload):
                rel = name[len(PAYLOAD_PREFIX):]
                if name.casefold().endswith(".jsonl"):
                    findings.append({"code": "jsonl_present", "message": f"JSONL entry present: {name}"})
                try:
                    klass = classify_tracked_path(rel, policy)
                except ReleaseError as exc:
                    findings.append({"code": exc.code, "message": f"{name}: {exc.code}"})
                    continue
                claimed = by_archive.get(name, {}).get("classification") if set(by_archive) == payload else None
                if claimed is not None and claimed != CLASS_GENERATED and claimed != klass:
                    findings.append({"code": "classification_mismatch",
                                     "message": f"{name} manifest classification != policy classification"})
                if klass == CLASS_ALLOWED_ARCHIVE:
                    # Names only, no extraction, no nested content read.
                    import io
                    try:
                        with zipfile.ZipFile(io.BytesIO(entries[name]), "r") as nested:
                            nested_names = nested.namelist()
                    except (zipfile.BadZipFile, OSError):
                        findings.append({"code": "archive_unreadable", "message": f"{name} is not a readable ZIP"})
                        continue
                    from release_common import classify_prohibited  # local import; module already on path
                    for nn in nested_names:
                        norm = nn.replace("\\", "/")
                        if norm.endswith("/"):
                            continue
                        if classify_prohibited(norm, policy) is not None:
                            findings.append({"code": "prohibited_nested_entry",
                                             "message": f"{name} contains a prohibited nested name"})
                            break

    if findings:
        status = "FAIL"
    elif not_verifiable:
        status = "NOT_VERIFIABLE"
    else:
        status = "PASS"
    return _report(status, findings, not_verifiable, repo_head=facts["head"],
                   payload_count=len(payload), control_count=len(control), entry_count=len(entries))


def verify_release_candidate(zip_path: Path) -> dict[str, Any]:
    """Top-level entry: never raises for candidate-controlled input. Maps every
    parsing failure to a content-free structured FAIL (or NOT_VERIFIABLE)."""
    try:
        return _verify(zip_path)
    except ReleaseError as exc:  # includes VerificationError, JSON/UTF-8/ZIP/duplicate-key
        return _fail(exc.code, exc.message)
    except (KeyError, TypeError, ValueError) as exc:  # unhashable/missing/coerce failures
        return _fail("schema_type", "candidate manifest/control structure is malformed")
    except OSError:
        return _fail("io_error", "release ZIP could not be read")


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
