"""Verify a Phase 12G release candidate ZIP without modifying or extracting it.

Independently validates ``release-manifest.json`` (exact schema 4),
``SHA256SUMS.txt`` and ``FILE_SIZES.json`` with exact set-equality; reconciles
all counts; re-parses the embedded disjoint closed-world policy and (when a
trusted expected identity is supplied) anchors it to that identity; re-classifies
every payload path by COUNTING rule matches and re-checks the recorded rule ID;
confirms the policy's REQUIRED paths are present; re-inspects each allowed archive
from its exact packaged bytes via the shared inspector; verifies deterministic ZIP
metadata; and applies outer resource bounds.

Every candidate-controlled failure becomes a content-free structured result:

* PASS            — all mandatory invariants were mechanically verified.
* FAIL            — the candidate is malformed, inconsistent, unsafe or incomplete.
* NOT_VERIFIABLE  — the environment lacks a required capability and the candidate
                    itself has not been proven malformed. Never treated as PASS
                    and never uses the PASS exit code.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import release_common as rc  # type: ignore
else:
    from . import release_common as rc  # noqa: F401

POLICY_ARCHIVE_PATH = f"{rc.PAYLOAD_PREFIX}{rc.POLICY_RELPATH}"


def _report(status: str, findings: list[dict[str, Any]], not_verifiable: list[dict[str, Any]],
            **extra: Any) -> dict[str, Any]:
    return {"schema_version": 1, "tool": "verify_release_candidate", "status": status,
            "passed": status == "PASS", "findings": findings, "not_verifiable": not_verifiable, **extra}


def _fail(code: str, message: str) -> dict[str, Any]:
    return _report("FAIL", [{"code": code, "message": message}], [])


def _validate_archive_inspection(obj: Any, entry_sha: str, entry_size: int, rule_id: str) -> dict[str, Any]:
    ai = rc.require_exact_keys(obj, rc.ARCHIVE_INSPECTION_KEYS, "archive_inspection")
    rc.require_exact_string(ai, "format", "zip", "archive_inspection")
    for key in ("entry_count", "total_name_bytes", "max_name_bytes", "max_depth", "comment_length"):
        rc.require_non_negative_integer(ai, key, "archive_inspection")
    if rc.require_sha256(ai, "payload_sha256", "archive_inspection") != entry_sha:
        raise rc.VerificationError("archive_binding_mismatch", "archive_inspection.payload_sha256 != entry sha")
    if rc.require_non_negative_integer(ai, "payload_size", "archive_inspection") != entry_size:
        raise rc.VerificationError("archive_binding_mismatch", "archive_inspection.payload_size != entry size")
    if rc.require_string(ai, "rule_id", "archive_inspection") != rule_id:
        raise rc.VerificationError("archive_binding_mismatch", "archive_inspection.rule_id != entry rule_id")
    rc.require_exact_int_value(ai, "limits_version", rc.ARCHIVE_INSPECTION_VERSION, "archive_inspection")
    rc.require_exact_string(ai, "result", "SAFE", "archive_inspection")
    return ai


def _validate_manifest(manifest_bytes: bytes, payload: set[str]) -> dict[str, Any]:
    manifest = rc.load_json_no_dupes(manifest_bytes, rc.MANIFEST_NAME)
    top = rc.require_exact_keys(manifest, rc.MANIFEST_TOP_KEYS, "manifest")
    rc.require_exact_int_value(top, "schema_version", rc.MANIFEST_SCHEMA_VERSION, "manifest")

    builder = rc.require_exact_keys(top["builder"], rc.BUILDER_KEYS, "manifest.builder")
    rc.require_exact_string(builder, "tool", rc.BUILDER_TOOL, "manifest.builder")
    rc.require_exact_int_value(builder, "manifest_schema_version", rc.MANIFEST_SCHEMA_VERSION, "manifest.builder")
    rc.require_exact_int_value(builder, "archive_inspection_version", rc.ARCHIVE_INSPECTION_VERSION, "manifest.builder")

    repo = rc.require_exact_keys(top["repository"], rc.REPO_KEYS, "manifest.repository")
    if not rc.is_hex40(repo["head"]):
        raise rc.VerificationError("identity_format", "manifest.repository.head is not a 40-hex commit id")
    rc.require_string(repo, "branch", "manifest.repository")
    if repo["base_sha"] is not None and not rc.is_hex40(repo["base_sha"]):
        raise rc.VerificationError("identity_format", "manifest.repository.base_sha is malformed")

    pol = rc.require_exact_keys(top["policy"], rc.POLICY_ID_KEYS, "manifest.policy")
    policy_id = rc.require_string(pol, "policy_id", "manifest.policy")
    rc.require_exact_int_value(pol, "schema_version", rc.POLICY_SCHEMA_VERSION, "manifest.policy")
    policy_sha = rc.require_sha256(pol, "sha256", "manifest.policy")

    counts = rc.require_exact_keys(top["counts"], rc.COUNTS_KEYS, "manifest.counts")
    for key in rc.COUNTS_KEYS:
        rc.require_non_negative_integer(counts, key, "manifest.counts")

    cov = rc.require_exact_keys(top["control_coverage"], rc.COVERAGE_KEYS, "manifest.control_coverage")
    for key, expected in rc.CONTROL_COVERAGE_CANON.items():
        rc.require_exact_string(cov, key, expected, "manifest.control_coverage")

    content = rc.require_exact_keys(top["content_controls"], rc.CONTENT_CONTROL_KEYS, "manifest.content_controls")
    for key in rc.CONTENT_CONTROL_KEYS - {"built_from"}:
        if rc.require_boolean(content, key, "manifest.content_controls") is not False:
            raise rc.VerificationError("content_control", f"manifest.content_controls.{key} must be false")
    rc.require_string(content, "built_from", "manifest.content_controls")

    zp = rc.require_exact_keys(top["zip_policy"], rc.ZIP_POLICY_KEYS, "manifest.zip_policy")
    for key, expected in rc.ZIP_POLICY_CANON.items():
        rc.require_exact_string(zp, key, expected, "manifest.zip_policy")

    files = rc.require_list(top, "files", "manifest")
    by_archive: dict[str, dict[str, Any]] = {}
    tracked_n = generated_n = 0
    for item in files:
        entry = rc.require_exact_keys(item, rc.FILE_ENTRY_KEYS, "manifest.files[]")
        path = rc.require_normalized_relative_path(entry["path"], "manifest.files[].path")
        archive_path = rc.require_string(entry, "archive_path", "manifest.files[]")
        if archive_path != f"{rc.PAYLOAD_PREFIX}{path}":
            raise rc.VerificationError("manifest_schema", "archive_path must equal repo/<path>")
        entry_sha = rc.require_sha256(entry, "sha256", "manifest.files[]")
        entry_size = rc.require_non_negative_integer(entry, "size_bytes", "manifest.files[]")
        if entry["source"] not in rc.SOURCE_VALUES:
            raise rc.VerificationError("manifest_schema", "manifest.files[].source is invalid")
        if entry["classification"] not in (rc.INCLUSION_CLASSES | {rc.CLASS_GENERATED}):
            raise rc.VerificationError("manifest_schema", "manifest.files[].classification is invalid")
        if (entry["source"] == "generated") != (entry["classification"] == rc.CLASS_GENERATED):
            raise rc.VerificationError("manifest_schema", "source/classification disagree")
        rc.require_string(entry, "rule_id", "manifest.files[]")
        if entry["rule_form"] not in (rc.RULE_FORMS | {"generated"}):
            raise rc.VerificationError("manifest_schema", "manifest.files[].rule_form is invalid")
        # archive_inspection present iff ALLOWED_ARCHIVE
        if entry["classification"] == rc.CLASS_ALLOWED_ARCHIVE:
            _validate_archive_inspection(entry["archive_inspection"], entry_sha, entry_size, entry["rule_id"])
        elif entry["archive_inspection"] is not None:
            raise rc.VerificationError("manifest_schema", "archive_inspection on a non-archive payload")
        if entry["source"] == "generated":
            generated_n += 1
        else:
            tracked_n += 1
        if archive_path in by_archive:
            raise rc.VerificationError("manifest_schema", f"manifest lists a duplicate archive path: {archive_path}")
        by_archive[archive_path] = entry

    n = len(files)
    if not (counts["file_count"] == counts["payload_count"] == n):
        raise rc.VerificationError("counts_mismatch", "file_count/payload_count disagree with files length")
    if counts["tracked_count"] != tracked_n or counts["generated_count"] != generated_n:
        raise rc.VerificationError("counts_mismatch", "tracked/generated counts disagree with rows")
    if counts["tracked_count"] + counts["generated_count"] != n:
        raise rc.VerificationError("counts_mismatch", "tracked + generated != file_count")
    if counts["control_count"] != 3 or counts["entry_count"] != n + 3:
        raise rc.VerificationError("counts_mismatch", "control_count/entry_count are inconsistent")
    return {"head": repo["head"], "policy_id": policy_id, "policy_sha256": policy_sha,
            "by_archive": by_archive, "content": content}


def _check_zip_metadata(zip_path: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    with zipfile.ZipFile(zip_path, "r") as archive:
        for info in archive.infolist():
            if info.is_dir():
                findings.append({"code": "zip_directory_entry", "message": f"{info.filename} is a directory entry"})
                continue
            if info.date_time != rc.ZIP_TIMESTAMP:
                findings.append({"code": "nondeterministic_metadata", "message": f"{info.filename} timestamp not fixed"})
            if info.create_system != rc.ZIP_CREATE_SYSTEM:
                findings.append({"code": "nondeterministic_metadata", "message": f"{info.filename} create_system not unix"})
            if info.external_attr != rc.ZIP_EXTERNAL_ATTR:
                findings.append({"code": "nondeterministic_metadata", "message": f"{info.filename} mode not 0644"})
            if info.extra != b"":
                findings.append({"code": "nondeterministic_metadata", "message": f"{info.filename} has extra field"})
            if info.compress_type != zipfile.ZIP_DEFLATED:
                findings.append({"code": "nondeterministic_metadata", "message": f"{info.filename} not deflate"})
    return findings


def _verify(zip_path: Path, expected_policy_sha256: str | None, expected_policy_id: str | None,
            expected_head: str | None) -> dict[str, Any]:
    zip_path = zip_path.expanduser().resolve()
    if rc.is_symlink_or_reparse(zip_path) or not zip_path.is_file():
        return _fail("zip_input", "release ZIP must be a regular non-link file")

    entries = rc.read_zip_entries(zip_path)  # bounded; ReleaseError -> caught by caller
    findings: list[dict[str, Any]] = []
    not_verifiable: list[dict[str, Any]] = []

    for required in (rc.MANIFEST_NAME, rc.CHECKSUMS_NAME, rc.SIZES_NAME):
        if required not in entries:
            findings.append({"code": "missing_control_file", "message": f"{required} is missing"})
    if findings:
        return _report("FAIL", findings, [])

    payload = {n for n in entries if n.startswith(rc.PAYLOAD_PREFIX)}
    control = {rc.MANIFEST_NAME, rc.CHECKSUMS_NAME, rc.SIZES_NAME}
    for name in sorted(set(entries) - payload - control):
        findings.append({"code": "unexpected_entry", "message": f"unaccounted archive entry: {name}"})

    findings.extend(_check_zip_metadata(zip_path))

    facts = _validate_manifest(entries[rc.MANIFEST_NAME], payload)
    by_archive = facts["by_archive"]
    if expected_head is not None and facts["head"] != expected_head:
        findings.append({"code": "head_mismatch", "message": "repo head != expected head"})
    if set(by_archive) != payload:
        findings.append({"code": "manifest_payload_mismatch", "message": "manifest file set != ZIP payload set"})
    else:
        for ap, item in by_archive.items():
            data = entries[ap]
            if rc.sha256_bytes(data) != item["sha256"]:
                findings.append({"code": "changed_file", "message": f"{ap} hash mismatch"})
            if len(data) != item["size_bytes"]:
                findings.append({"code": "changed_file", "message": f"{ap} size mismatch"})

    sizes = rc.load_json_no_dupes(entries[rc.SIZES_NAME], rc.SIZES_NAME)
    stop = rc.require_exact_keys(sizes, rc.SIZES_TOP_KEYS, "FILE_SIZES")
    rc.require_exact_int_value(stop, "schema_version", 1, "FILE_SIZES")
    sfiles = stop["files"]
    if not isinstance(sfiles, dict):
        raise rc.VerificationError("sizes_schema", "FILE_SIZES.files must be an object")
    expected_size_keys = payload | {rc.MANIFEST_NAME}
    if set(sfiles) != expected_size_keys:
        findings.append({"code": "sizes_set_mismatch", "message": "FILE_SIZES key set != payload + manifest"})
    else:
        for name, sz in sfiles.items():
            if not rc.is_exact_int(sz) or sz < 0:
                findings.append({"code": "sizes_schema", "message": f"invalid size for {name}"})
            elif len(entries[name]) != sz:
                findings.append({"code": "changed_file", "message": f"{name} size disagreement"})

    sums = rc.parse_checksum_text(entries[rc.CHECKSUMS_NAME])
    expected_sum_keys = payload | {rc.MANIFEST_NAME, rc.SIZES_NAME}
    if set(sums) != expected_sum_keys:
        findings.append({"code": "checksums_set_mismatch",
                         "message": "SHA256SUMS key set != payload + manifest + FILE_SIZES"})
    else:
        for name, digest in sums.items():
            if rc.sha256_bytes(entries[name]) != digest:
                findings.append({"code": "changed_file", "message": f"{name} checksum disagreement"})

    policy_trust = "candidate_anchored"
    if not payload:
        not_verifiable.append({"code": "empty_payload", "message": "archive has no repository payload to verify"})
    elif POLICY_ARCHIVE_PATH not in entries:
        findings.append({"code": "policy_absent", "message": "embedded release policy is absent"})
    else:
        try:
            policy = rc.parse_release_policy(entries[POLICY_ARCHIVE_PATH])
        except rc.ReleaseError as exc:
            findings.append({"code": "policy_invalid", "message": f"embedded policy invalid: {exc.code}"})
            policy = None
        if policy is not None:
            if policy.sha256 != facts["policy_sha256"]:
                findings.append({"code": "policy_identity_mismatch", "message": "policy SHA-256 != manifest"})
            if policy.policy_id != facts["policy_id"]:
                findings.append({"code": "policy_identity_mismatch", "message": "policy_id != manifest"})
            if expected_policy_sha256 is not None:
                if policy.sha256 != expected_policy_sha256.lower():
                    findings.append({"code": "policy_untrusted", "message": "policy SHA-256 != expected trusted policy"})
                else:
                    policy_trust = "expected_anchored"
            if expected_policy_id is not None and policy.policy_id != expected_policy_id:
                findings.append({"code": "policy_untrusted", "message": "policy_id != expected trusted policy"})
            # REQUIRED paths must be present in the payload.
            for req in sorted(policy.required_paths):
                if f"{rc.PAYLOAD_PREFIX}{req}" not in payload:
                    findings.append({"code": "required_path_absent", "message": f"required path missing: {req}"})
            # Re-classify every payload path and re-check the recorded rule ID.
            if set(by_archive) == payload:
                for name in sorted(payload):
                    rel = name[len(rc.PAYLOAD_PREFIX):]
                    item = by_archive[name]
                    if name.casefold().endswith(".jsonl"):
                        findings.append({"code": "jsonl_present", "message": f"JSONL entry present: {name}"})
                    try:
                        result = rc.classify_path(rel, policy)
                    except rc.ReleaseError as exc:
                        findings.append({"code": exc.code, "message": f"{name}: {exc.code}"})
                        continue
                    if item["source"] == "generated":
                        if item["classification"] != rc.CLASS_GENERATED or item["rule_id"] != rc.GENERATED_RULE_ID:
                            findings.append({"code": "classification_mismatch", "message": f"{name} generated metadata"})
                        if result.classification == rc.CLASS_ALLOWED_ARCHIVE:
                            findings.append({"code": "generated_archive", "message": f"{name} generated archive"})
                    else:
                        if (item["classification"] != result.classification
                                or item["rule_id"] != result.rule_id
                                or item["rule_form"] != result.rule_form):
                            findings.append({"code": "classification_mismatch",
                                             "message": f"{name} manifest rule != policy rule"})
                        if result.classification == rc.CLASS_ALLOWED_ARCHIVE:
                            data = entries[name]
                            try:
                                recomputed = rc.inspect_archive_bytes(
                                    data, policy, rule_id=result.rule_id,
                                    payload_sha=rc.sha256_bytes(data), payload_size=len(data))
                            except rc.ReleaseError as exc:
                                findings.append({"code": exc.code, "message": f"{name}: archive inspection failed"})
                            else:
                                if recomputed != item["archive_inspection"]:
                                    findings.append({"code": "archive_scan_mismatch",
                                                     "message": f"{name} archive inspection != manifest"})

    if findings:
        status = "FAIL"
    elif not_verifiable:
        status = "NOT_VERIFIABLE"
    else:
        status = "PASS"
    return _report(status, findings, not_verifiable, repo_head=facts["head"],
                   policy_trust=policy_trust, payload_count=len(payload),
                   control_count=len(control), entry_count=len(entries))


def verify_release_candidate(zip_path: Path, *, expected_policy_sha256: str | None = None,
                             expected_policy_id: str | None = None,
                             expected_head: str | None = None) -> dict[str, Any]:
    """Top-level entry: never raises for candidate-controlled input. Maps every
    parsing failure to a content-free structured FAIL (or NOT_VERIFIABLE)."""
    try:
        return _verify(zip_path, expected_policy_sha256, expected_policy_id, expected_head)
    except rc.ReleaseError as exc:  # includes VerificationError, JSON/UTF-8/ZIP/duplicate-key/resource
        return _fail(exc.code, exc.message)
    except (KeyError, TypeError, ValueError) as exc:
        return _fail("schema_type", "candidate manifest/control structure is malformed")
    except (NotImplementedError, RuntimeError):
        return _fail("unsupported_candidate", "candidate uses an unsupported archive feature")
    except OSError:
        return _fail("io_error", "release ZIP could not be read")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--expected-policy-sha256", default=None)
    parser.add_argument("--expected-policy-id", default=None)
    parser.add_argument("--expected-head", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = verify_release_candidate(
        args.zip, expected_policy_sha256=args.expected_policy_sha256,
        expected_policy_id=args.expected_policy_id, expected_head=args.expected_head)
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
