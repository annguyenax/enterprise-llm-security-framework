"""Verify a Phase 12G release candidate ZIP without modifying or extracting it.

Trust model (mandatory external anchor): a candidate may never establish its own
trust root. PASS requires an EXTERNAL trusted policy FILE supplied independently
of the candidate (``--expected-policy-file``); the embedded policy bytes and
manifest identity must equal those trusted bytes exactly and classification is
performed with the trusted bytes. A trusted SHA alone, or no anchor, yields
NOT_VERIFIABLE (never PASS). When generated payloads exist, PASS additionally
requires an external trusted generated-allowlist anchor.

Content-free failures: candidate-controlled names/paths/values are NEVER emitted
in findings, summaries, stderr or exceptions. Findings carry only a stable reason
code plus safe indices/counts and optional SHA-256 of the offending value.

Returns PASS / FAIL / NOT_VERIFIABLE; NOT_VERIFIABLE is never PASS and never uses
the PASS exit code.
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
            "passed": status == "PASS", "content_free": True,
            "findings": findings, "not_verifiable": not_verifiable, **extra}


def _f(code: str, **safe: Any) -> dict[str, Any]:
    """A content-free finding: stable code plus only safe fields (index/count/hash)."""
    return {"code": code, "content_free": True, **safe}


def _fail(code: str) -> dict[str, Any]:
    return _report("FAIL", [_f(code)], [])


def _vh(value: object) -> str:
    return rc.value_sha256(value)


def _validate_archive_inspection(obj: Any, entry_sha: str, entry_size: int, rule_id: str) -> None:
    ai = rc.require_exact_keys(obj, rc.ARCHIVE_INSPECTION_KEYS, "archive_inspection")
    rc.require_exact_string(ai, "format", "zip", "archive_inspection")
    for key in ("entry_count", "total_name_bytes", "max_name_bytes", "max_depth", "comment_length"):
        rc.require_non_negative_integer(ai, key, "archive_inspection")
    if rc.require_sha256(ai, "payload_sha256", "archive_inspection") != entry_sha:
        raise rc.VerificationError("archive_binding_mismatch", "archive_inspection.payload_sha256 mismatch")
    if rc.require_non_negative_integer(ai, "payload_size", "archive_inspection") != entry_size:
        raise rc.VerificationError("archive_binding_mismatch", "archive_inspection.payload_size mismatch")
    if rc.require_string(ai, "rule_id", "archive_inspection") != rule_id:
        raise rc.VerificationError("archive_binding_mismatch", "archive_inspection.rule_id mismatch")
    rc.require_exact_int_value(ai, "limits_version", rc.ARCHIVE_INSPECTION_VERSION, "archive_inspection")
    rc.require_exact_string(ai, "result", "SAFE", "archive_inspection")


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
        raise rc.VerificationError("identity_format", "manifest.repository.head invalid")
    rc.require_string(repo, "branch", "manifest.repository")
    if repo["base_sha"] is not None and not rc.is_hex40(repo["base_sha"]):
        raise rc.VerificationError("identity_format", "manifest.repository.base_sha invalid")

    pol = rc.require_exact_keys(top["policy"], rc.POLICY_ID_KEYS, "manifest.policy")
    policy_id = rc.require_string(pol, "policy_id", "manifest.policy")
    rc.require_exact_int_value(pol, "schema_version", rc.POLICY_SCHEMA_VERSION, "manifest.policy")
    policy_sha = rc.require_sha256(pol, "sha256", "manifest.policy")

    gen = rc.require_exact_keys(top["generated"], rc.GENERATED_MANIFEST_KEYS, "manifest.generated")
    gen_count = rc.require_non_negative_integer(gen, "count", "manifest.generated")
    gen_sha = gen["allowlist_sha256"]
    if gen_count == 0:
        if gen_sha is not None:
            raise rc.VerificationError("generated_state", "zero-generated state must have null allowlist_sha256")
    else:
        if not rc.is_hex64(gen_sha):
            raise rc.VerificationError("generated_state", "nonzero generated requires a 64-hex allowlist_sha256")
        gen_sha = gen_sha.lower()

    counts = rc.require_exact_keys(top["counts"], rc.COUNTS_KEYS, "manifest.counts")
    for key in rc.COUNTS_KEYS:
        rc.require_non_negative_integer(counts, key, "manifest.counts")

    cov = rc.require_exact_keys(top["control_coverage"], rc.COVERAGE_KEYS, "manifest.control_coverage")
    for key, expected in rc.CONTROL_COVERAGE_CANON.items():
        rc.require_exact_string(cov, key, expected, "manifest.control_coverage")

    content = rc.require_exact_keys(top["content_controls"], rc.CONTENT_CONTROL_KEYS, "manifest.content_controls")
    for key in rc.CONTENT_CONTROL_KEYS - {"built_from"}:
        if rc.require_boolean(content, key, "manifest.content_controls") is not False:
            raise rc.VerificationError("content_control", "content_controls flag must be false")
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
        source = entry["source"]
        classification = entry["classification"]
        rule_id = entry["rule_id"]
        rule_form = entry["rule_form"]
        if not isinstance(rule_id, str) or not rule_id:
            raise rc.VerificationError("manifest_schema", "rule_id must be a non-empty string")
        # Canonical source/classification/rule_id/rule_form reconciliation (Major 2).
        if source == "generated":
            if not (classification == rc.CLASS_GENERATED and rule_id == rc.GENERATED_RULE_ID
                    and rule_form == "generated"):
                raise rc.VerificationError("generated_semantic", "generated row metadata is not canonical")
            generated_n += 1
        elif source == "tracked":
            if (classification not in rc.INCLUSION_CLASSES or rule_form not in rc.RULE_FORMS
                    or classification == rc.CLASS_GENERATED or rule_id == rc.GENERATED_RULE_ID
                    or rule_form == "generated"):
                raise rc.VerificationError("tracked_semantic", "tracked row carries generated markers")
            tracked_n += 1
        else:
            raise rc.VerificationError("manifest_schema", "manifest.files[].source is invalid")
        if classification == rc.CLASS_ALLOWED_ARCHIVE:
            _validate_archive_inspection(entry["archive_inspection"], entry_sha, entry_size, rule_id)
        elif entry["archive_inspection"] is not None:
            raise rc.VerificationError("manifest_schema", "archive_inspection on a non-archive payload")
        if archive_path in by_archive:
            raise rc.VerificationError("manifest_schema", "duplicate manifest archive path")
        by_archive[archive_path] = entry

    n = len(files)
    if not (counts["file_count"] == counts["payload_count"] == n):
        raise rc.VerificationError("counts_mismatch", "file_count/payload_count disagree with files length")
    if counts["tracked_count"] != tracked_n or counts["generated_count"] != generated_n:
        raise rc.VerificationError("counts_mismatch", "tracked/generated counts disagree with rows")
    if counts["generated_count"] != gen_count:
        raise rc.VerificationError("counts_mismatch", "manifest.generated.count disagrees with counts")
    if counts["tracked_count"] + counts["generated_count"] != n:
        raise rc.VerificationError("counts_mismatch", "tracked + generated != file_count")
    if counts["control_count"] != 3 or counts["entry_count"] != n + 3:
        raise rc.VerificationError("counts_mismatch", "control_count/entry_count inconsistent")
    return {"head": repo["head"], "policy_id": policy_id, "policy_sha256": policy_sha,
            "by_archive": by_archive, "generated_count": gen_count, "generated_allowlist_sha256": gen_sha}


def _check_zip_metadata(zip_path: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    with zipfile.ZipFile(zip_path, "r") as archive:
        for idx, info in enumerate(archive.infolist()):
            if info.is_dir():
                findings.append(_f("zip_directory_entry", entry_index=idx))
                continue
            if (info.date_time != rc.ZIP_TIMESTAMP or info.create_system != rc.ZIP_CREATE_SYSTEM
                    or info.external_attr != rc.ZIP_EXTERNAL_ATTR or info.extra != b""
                    or info.compress_type != zipfile.ZIP_DEFLATED):
                findings.append(_f("nondeterministic_metadata", entry_index=idx))
    return findings


def _load_trusted_policy(expected_policy_file, expected_policy_sha256):
    """Return (trust_mode, trusted_bytes_or_None, trusted_policy_or_None,
    trusted_sha_or_None). Never trusts the candidate."""
    if expected_policy_file is not None:
        path = Path(expected_policy_file).expanduser()
        if rc.is_symlink_or_reparse(path) or not path.is_file():
            raise rc.VerificationError("trusted_policy_unreadable", "external policy file is missing")
        try:
            trusted_bytes = path.read_bytes()
        except OSError as exc:
            raise rc.VerificationError("trusted_policy_unreadable", "external policy file unreadable") from exc
        trusted_policy = rc.parse_release_policy(trusted_bytes)  # FAIL if malformed
        return "external_file", trusted_bytes, trusted_policy, trusted_policy.sha256
    if expected_policy_sha256 is not None:
        if not rc.is_hex64(expected_policy_sha256):
            raise rc.VerificationError("trusted_policy_sha_invalid", "expected policy sha is malformed")
        return "hash_only", None, None, expected_policy_sha256.lower()
    return "unanchored", None, None, None


def _verify(zip_path: Path, expected_policy_file, expected_policy_sha256, expected_policy_id,
            expected_head, expected_generated_sha256) -> dict[str, Any]:
    zip_path = zip_path.expanduser().resolve()
    if rc.is_symlink_or_reparse(zip_path) or not zip_path.is_file():
        return _fail("zip_input")

    # Establish the external trust anchor BEFORE trusting any candidate byte.
    trust_mode, trusted_bytes, trusted_policy, trusted_sha = _load_trusted_policy(
        expected_policy_file, expected_policy_sha256)

    entries = rc.read_zip_entries(zip_path)  # bounded; ReleaseError -> caught by caller
    findings: list[dict[str, Any]] = []
    not_verifiable: list[dict[str, Any]] = []

    for required in (rc.MANIFEST_NAME, rc.CHECKSUMS_NAME, rc.SIZES_NAME):
        if required not in entries:
            findings.append(_f("missing_control_file", control=required))
    if findings:
        return _report("FAIL", findings, [], policy_trust=trust_mode)

    payload = {n for n in entries if n.startswith(rc.PAYLOAD_PREFIX)}
    control = {rc.MANIFEST_NAME, rc.CHECKSUMS_NAME, rc.SIZES_NAME}
    for name in sorted(set(entries) - payload - control):
        findings.append(_f("unexpected_payload_entry", value_sha256=_vh(name)))

    findings.extend(_check_zip_metadata(zip_path))

    facts = _validate_manifest(entries[rc.MANIFEST_NAME], payload)
    by_archive = facts["by_archive"]
    ordered_payload = sorted(payload)
    index_of = {name: i for i, name in enumerate(ordered_payload)}

    if expected_head is not None and facts["head"] != expected_head:
        findings.append(_f("head_mismatch"))
    if expected_policy_id is not None and facts["policy_id"] != expected_policy_id:
        findings.append(_f("policy_identity_mismatch"))

    if set(by_archive) != payload:
        findings.append(_f("manifest_payload_mismatch"))
    else:
        for ap, item in by_archive.items():
            data = entries[ap]
            if rc.sha256_bytes(data) != item["sha256"] or len(data) != item["size_bytes"]:
                findings.append(_f("changed_file", entry_index=index_of[ap]))

    sizes = rc.load_json_no_dupes(entries[rc.SIZES_NAME], rc.SIZES_NAME)
    stop = rc.require_exact_keys(sizes, rc.SIZES_TOP_KEYS, "FILE_SIZES")
    rc.require_exact_int_value(stop, "schema_version", 1, "FILE_SIZES")
    sfiles = stop["files"]
    if not isinstance(sfiles, dict):
        raise rc.VerificationError("sizes_schema", "FILE_SIZES.files must be an object")
    if set(sfiles) != payload | {rc.MANIFEST_NAME}:
        findings.append(_f("sizes_set_mismatch"))
    else:
        for name, sz in sfiles.items():
            if not rc.is_exact_int(sz) or sz < 0 or len(entries[name]) != sz:
                findings.append(_f("size_disagreement", value_sha256=_vh(name)))

    sums = rc.parse_checksum_text(entries[rc.CHECKSUMS_NAME])
    if set(sums) != payload | {rc.MANIFEST_NAME, rc.SIZES_NAME}:
        findings.append(_f("checksums_set_mismatch"))
    else:
        for name, digest in sums.items():
            if rc.sha256_bytes(entries[name]) != digest:
                findings.append(_f("checksum_disagreement", value_sha256=_vh(name)))

    # Generated external trust anchor.
    if facts["generated_count"] > 0:
        if expected_generated_sha256 is None:
            not_verifiable.append({"code": "generated_anchor_missing", "content_free": True,
                                   "message": "generated payloads present but no external generated anchor supplied"})
        elif not rc.is_hex64(expected_generated_sha256) or expected_generated_sha256.lower() != facts["generated_allowlist_sha256"]:
            findings.append(_f("generated_anchor_mismatch"))

    # Policy anchoring + payload reclassification.
    embedded_policy = None
    if not payload:
        not_verifiable.append({"code": "empty_payload", "content_free": True,
                               "message": "archive has no repository payload to verify"})
    elif POLICY_ARCHIVE_PATH not in entries:
        findings.append(_f("policy_absent"))
    else:
        try:
            embedded_policy = rc.parse_release_policy(entries[POLICY_ARCHIVE_PATH])
        except rc.ReleaseError as exc:
            findings.append(_f("policy_invalid", detail_code=exc.code))
        if embedded_policy is not None:
            if embedded_policy.sha256 != facts["policy_sha256"] or embedded_policy.policy_id != facts["policy_id"]:
                findings.append(_f("policy_identity_mismatch"))
            if trust_mode == "external_file":
                if entries[POLICY_ARCHIVE_PATH] != trusted_bytes:
                    findings.append(_f("policy_bytes_mismatch"))
                if embedded_policy.sha256 != trusted_sha:
                    findings.append(_f("policy_untrusted"))
                classify_policy = trusted_policy
            elif trust_mode == "hash_only":
                if embedded_policy.sha256 != trusted_sha:
                    findings.append(_f("policy_untrusted"))
                classify_policy = embedded_policy
                not_verifiable.append({"code": "policy_hash_only", "content_free": True,
                                       "message": "trusted policy hash only; semantic PASS requires trusted policy file"})
            else:  # unanchored
                classify_policy = embedded_policy
                not_verifiable.append({"code": "policy_unanchored", "content_free": True,
                                       "message": "candidate internally consistent but not externally policy-anchored"})

            if set(by_archive) == payload:
                for name in ordered_payload:
                    rel = name[len(rc.PAYLOAD_PREFIX):]
                    item = by_archive[name]
                    if name.casefold().endswith(".jsonl"):
                        findings.append(_f("jsonl_present", value_sha256=_vh(name)))
                    try:
                        result = rc.classify_path(rel, classify_policy)
                    except rc.ReleaseError as exc:
                        findings.append(_f("payload_reclassification_failed",
                                           detail_code=exc.code, value_sha256=_vh(name)))
                        continue
                    if item["source"] == "generated":
                        if result.classification == rc.CLASS_ALLOWED_ARCHIVE:
                            findings.append(_f("generated_archive", value_sha256=_vh(name)))
                    else:
                        if (item["classification"] != result.classification
                                or item["rule_id"] != result.rule_id
                                or item["rule_form"] != result.rule_form):
                            findings.append(_f("classification_mismatch", entry_index=index_of[name]))
                        if result.classification == rc.CLASS_ALLOWED_ARCHIVE:
                            data = entries[name]
                            try:
                                recomputed = rc.inspect_archive_bytes(
                                    data, classify_policy, rule_id=result.rule_id,
                                    payload_sha=rc.sha256_bytes(data), payload_size=len(data))
                            except rc.ReleaseError as exc:
                                findings.append(_f("archive_inspection_failed",
                                                   detail_code=exc.code, value_sha256=_vh(name)))
                            else:
                                if recomputed != item["archive_inspection"]:
                                    findings.append(_f("archive_scan_mismatch", entry_index=index_of[name]))

    if findings:
        status = "FAIL"
    elif not_verifiable:
        status = "NOT_VERIFIABLE"
    else:
        status = "PASS"
    return _report(status, findings, not_verifiable, repo_head=facts["head"], policy_trust=trust_mode,
                   generated_count=facts["generated_count"], payload_count=len(payload),
                   control_count=len(control), entry_count=len(entries))


def verify_release_candidate(zip_path: Path, *, expected_policy_file=None,
                             expected_policy_sha256: str | None = None,
                             expected_policy_id: str | None = None,
                             expected_head: str | None = None,
                             expected_generated_sha256: str | None = None) -> dict[str, Any]:
    """Top-level entry: never raises for candidate-controlled input. Maps every
    parsing failure to a content-free structured FAIL (or NOT_VERIFIABLE). No
    candidate-controlled value is ever placed in the returned report."""
    try:
        return _verify(zip_path, expected_policy_file, expected_policy_sha256, expected_policy_id,
                       expected_head, expected_generated_sha256)
    except rc.ReleaseError as exc:  # includes VerificationError, JSON/UTF-8/ZIP/duplicate-key/resource
        return _fail(exc.code)
    except (KeyError, TypeError, ValueError):
        return _fail("candidate_schema_invalid")
    except (NotImplementedError, RuntimeError):
        return _fail("candidate_unsupported_feature")
    except OSError:
        return _fail("candidate_io_failure")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--expected-policy-file", type=Path, default=None,
                        help="EXTERNAL trusted policy file. REQUIRED for a PASS result; "
                             "without it the result is NOT_VERIFIABLE, never PASS.")
    parser.add_argument("--expected-policy-sha256", default=None,
                        help="Trusted policy SHA-256 only. Insufficient for PASS (NOT_VERIFIABLE).")
    parser.add_argument("--expected-policy-id", default=None)
    parser.add_argument("--expected-head", default=None)
    parser.add_argument("--expected-generated-sha256", default=None,
                        help="External trusted generated-allowlist SHA-256; required for PASS when "
                             "generated payloads are present.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = verify_release_candidate(
        args.zip, expected_policy_file=args.expected_policy_file,
        expected_policy_sha256=args.expected_policy_sha256, expected_policy_id=args.expected_policy_id,
        expected_head=args.expected_head, expected_generated_sha256=args.expected_generated_sha256)
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
