#!/usr/bin/env python3
"""Create a deterministic sanitized Gemini packet after a real closure PASS."""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

if __package__ in {None, ""}:
    ROOT = Path(__file__).resolve().parents[2]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

from scripts.phase12f.common import (  # noqa: E402
    PACKET_SCHEMA_VERSION,
    EvidenceToolError,
    canonical_json_bytes,
    classify_packet_exclusion,
    ensure_output_outside_roots,
    load_allowlist,
    normalize_roots,
    parse_root_arguments,
    physical_file_identity,
    publish_directory_atomically,
    read_stable_bytes,
    resolve_artifact,
    scan_root_files,
    sha256_bytes,
    validate_packet_content,
)


TASK_NAME = "phase12f_gemini_packet"
ZIP_FILENAME = "gemini-packet.zip"
MANIFEST_FILENAME = "PACKET_MANIFEST.json"
SIZES_FILENAME = "FILE_SIZES.json"
CHECKSUMS_FILENAME = "SHA256SUMS.txt"
CLOSURE_GATE = "CODEX_PHASE12E4_CLOSURE_AUDIT_PASS"
CLOSURE_FILENAMES = (
    "STATUS.json",
    "CLOSURE_FINDINGS.json",
    "FINAL_CLOSURE_AUDIT.md",
)
_GATE_RE = re.compile(
    r"(?m)^## Closure Gate\s*\r?\n\s*\r?\n"
    r"(CODEX_PHASE12E4_CLOSURE_AUDIT_(?:PASS|FAIL))\s*$"
)


def _strict_json_object(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceToolError("closure_schema", f"{label} is not strict UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise EvidenceToolError("closure_schema", f"{label} must contain a JSON object")
    return value


def _locate_unique_closure_files(closure_directory: Path) -> dict[str, Path]:
    roots = normalize_roots({"closure": closure_directory}, ("closure",))
    closure = roots["closure"]
    files = scan_root_files(closure, "closure")
    located: dict[str, Path] = {}
    for filename in CLOSURE_FILENAMES:
        matches = [
            path
            for relative, path in files.items()
            if PurePosixPath(relative).name.casefold() == filename.casefold()
        ]
        if not matches:
            raise EvidenceToolError("closure_missing", f"{filename} is missing")
        if len(matches) != 1:
            raise EvidenceToolError("closure_ambiguous", f"{filename} is ambiguous")
        located[filename] = matches[0]
    return located


def validate_closure(
    closure_directory: Path,
    candidate_sha: str,
) -> tuple[dict[str, bytes], dict[str, Any]]:
    paths = _locate_unique_closure_files(closure_directory)
    raw = {name: read_stable_bytes(path) for name, path in paths.items()}
    status = _strict_json_object(raw["STATUS.json"], "closure STATUS")
    findings = _strict_json_object(
        raw["CLOSURE_FINDINGS.json"],
        "closure findings",
    )
    try:
        report_text = raw["FINAL_CLOSURE_AUDIT.md"].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise EvidenceToolError("closure_schema", "closure report is not UTF-8") from exc

    if status.get("candidate_sha") != candidate_sha:
        raise EvidenceToolError("closure_identity", "closure STATUS candidate does not match")
    state = status.get("state")
    if state != "COMPLETE":
        if state == "RUNNING":
            raise EvidenceToolError("closure_running", "closure audit is still RUNNING")
        raise EvidenceToolError("closure_failed", "closure STATUS is not COMPLETE")
    if findings.get("candidate_sha") != candidate_sha:
        raise EvidenceToolError("closure_identity", "closure findings candidate does not match")
    if findings.get("closure_gate") != CLOSURE_GATE:
        raise EvidenceToolError("closure_failed", "closure findings do not contain PASS")
    for severity in ("critical", "major"):
        value = findings.get(severity)
        if not isinstance(value, list) or value:
            raise EvidenceToolError(
                "closure_failed",
                f"closure {severity} findings are not empty",
            )
    gates = _GATE_RE.findall(report_text)
    if gates != [CLOSURE_GATE]:
        if not gates:
            raise EvidenceToolError("closure_missing", "closure report has no unambiguous gate")
        raise EvidenceToolError("closure_ambiguous", "closure report gate is ambiguous")

    safe_files = {
        "closure/STATUS.json": validate_packet_content(
            paths["STATUS.json"],
            "aggregate_json",
            "closure_status",
        ),
        "closure/CLOSURE_FINDINGS.json": validate_packet_content(
            paths["CLOSURE_FINDINGS.json"],
            "aggregate_json",
            "closure_findings",
        ),
        "closure/FINAL_CLOSURE_AUDIT.md": validate_packet_content(
            paths["FINAL_CLOSURE_AUDIT.md"],
            "aggregate_markdown",
            "closure_report",
        ),
    }
    identity = {
        "candidate_sha": candidate_sha,
        "status_state": state,
        "closure_gate": CLOSURE_GATE,
        "files": [
            {
                "archive_path": archive_path,
                "sha256": sha256_bytes(data),
                "size_bytes": len(data),
            }
            for archive_path, data in sorted(safe_files.items())
        ],
    }
    return safe_files, identity


def _archive_path(logical_id: str, relative: str) -> str:
    basename = PurePosixPath(relative).name
    return f"artifacts/{logical_id}/{basename}"


def _zip_bytes(files: Mapping[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(
        buffer,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        strict_timestamps=True,
    ) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (0o100644 & 0xFFFF) << 16
            archive.writestr(
                info,
                files[name],
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )
    return buffer.getvalue()


def _checksum_bytes(files: Mapping[str, bytes]) -> bytes:
    return "".join(
        f"{sha256_bytes(files[name])}  {name}\n"
        for name in sorted(files)
    ).encode("ascii")


def _verify_zip(path: Path, expected: Mapping[str, bytes]) -> None:
    with zipfile.ZipFile(path, "r") as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or names != sorted(expected):
            raise EvidenceToolError("zip_verification", "ZIP entry allowlist is inconsistent")
        for name in names:
            pure = PurePosixPath(name)
            if pure.is_absolute() or ".." in pure.parts or "\\" in name:
                raise EvidenceToolError("zip_verification", "ZIP contains an unsafe path")
            if archive.read(name) != expected[name]:
                raise EvidenceToolError("zip_verification", "ZIP entry bytes changed")
        checksum_text = archive.read(CHECKSUMS_FILENAME).decode("ascii")
        for line in checksum_text.splitlines():
            parts = line.split("  ", 1)
            if len(parts) != 2:
                raise EvidenceToolError("zip_verification", "checksum format is invalid")
            digest, name = parts
            if name == CHECKSUMS_FILENAME or name not in expected:
                raise EvidenceToolError("zip_verification", "checksum references an invalid entry")
            if digest != sha256_bytes(expected[name]):
                raise EvidenceToolError("zip_verification", "checksum verification failed")


def _verify_checksum_text(data: bytes, expected: Mapping[str, bytes]) -> None:
    try:
        lines = data.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise EvidenceToolError("checksum_verification", "checksum file is not ASCII") from exc
    if len(lines) != len(expected):
        raise EvidenceToolError("checksum_verification", "checksum entry count is inconsistent")
    seen: set[str] = set()
    for line in lines:
        parts = line.split("  ", 1)
        if len(parts) != 2:
            raise EvidenceToolError("checksum_verification", "checksum format is invalid")
        digest, name = parts
        if name in seen or name not in expected:
            raise EvidenceToolError("checksum_verification", "checksum target is invalid")
        seen.add(name)
        if digest != sha256_bytes(expected[name]):
            raise EvidenceToolError("checksum_verification", "checksum digest is invalid")


def build_packet_payload(
    closure_directory: Path,
    allowlist_path: Path,
    input_roots: Mapping[str, Path],
) -> tuple[dict[str, bytes], dict[str, Any]]:
    allowlist = load_allowlist(allowlist_path)
    roots = normalize_roots(input_roots, allowlist.root_names)
    closure_files, closure_identity = validate_closure(
        closure_directory,
        allowlist.candidate_sha,
    )
    scanned = {
        name: scan_root_files(path, name)
        for name, path in roots.items()
    }
    rules_by_reference = {
        (
            rule.root,
            rule.path.casefold() if os.name == "nt" else rule.path,
        ): rule
        for rule in allowlist.rules
    }
    copied_references: set[tuple[str, str]] = set()
    physical: dict[tuple[int, int], str] = {}
    archive_files: dict[str, bytes] = dict(closure_files)
    artifact_entries: list[dict[str, Any]] = []

    for rule in sorted(allowlist.rules, key=lambda value: value.logical_id):
        path = resolve_artifact(roots[rule.root], rule.path, rule.logical_id)
        present = path.is_file()
        if rule.artifact_class == "prohibited":
            continue
        if not present:
            if rule.artifact_class == "required":
                raise EvidenceToolError(
                    "missing_artifact",
                    f"required packet artifact {rule.logical_id} is missing",
                )
            continue
        if rule.packet_class is None:
            raise EvidenceToolError(
                "packet_class",
                f"{rule.logical_id} is not explicitly approved for packet copying",
            )
        excluded_class = classify_packet_exclusion(rule.path)
        if excluded_class is not None:
            raise EvidenceToolError(
                "prohibited_packet_artifact",
                f"{rule.logical_id} belongs to excluded class {excluded_class}",
            )
        identity = physical_file_identity(path)
        if identity in physical:
            raise EvidenceToolError(
                "duplicate_logical_artifact",
                f"{rule.logical_id} aliases {physical[identity]}",
            )
        physical[identity] = rule.logical_id
        data = validate_packet_content(path, rule.packet_class, rule.logical_id)
        archive_path = _archive_path(rule.logical_id, rule.path)
        if archive_path in archive_files:
            raise EvidenceToolError("duplicate_logical_artifact", "packet archive path is duplicated")
        archive_files[archive_path] = data
        artifact_entries.append(
            {
                "logical_id": rule.logical_id,
                "root": rule.root,
                "path": rule.path,
                "packet_class": rule.packet_class,
                "archive_path": archive_path,
                "sha256": sha256_bytes(data),
                "size_bytes": len(data),
            }
        )
        copied_references.add(
            (
                rule.root,
                rule.path.casefold() if os.name == "nt" else rule.path,
            )
        )

    excluded = Counter()
    for root_name, files in scanned.items():
        for relative in files:
            reference = (root_name, relative)
            if reference in copied_references:
                continue
            rule = rules_by_reference.get(reference)
            category = classify_packet_exclusion(relative)
            if category is None and rule is not None and rule.artifact_class == "prohibited":
                category = "explicit_prohibited"
            excluded[category or "not_allowlisted"] += 1

    manifest: dict[str, Any] = {
        "schema_version": PACKET_SCHEMA_VERSION,
        "candidate_sha": allowlist.candidate_sha,
        "allowlist_sha256": allowlist.sha256,
        "closure": closure_identity,
        "artifact_count": len(artifact_entries),
        "artifacts": artifact_entries,
        "excluded_artifact_classes": [
            {"class": name, "count": count}
            for name, count in sorted(excluded.items())
        ],
        "content_controls": {
            "result_json_included": False,
            "jsonl_included": False,
            "credentials_included": False,
            "databases_included": False,
            "git_data_included": False,
            "source_paths_are_logical": True,
        },
        "zip_policy": {
            "entry_order": "lexical",
            "timestamp": "1980-01-01T00:00:00",
            "permissions": "0644",
            "compression": "deflate-9",
        },
    }
    archive_files[MANIFEST_FILENAME] = canonical_json_bytes(manifest)
    sizes = {
        "schema_version": 1,
        "files": {
            name: len(data)
            for name, data in sorted(archive_files.items())
        },
    }
    archive_files[SIZES_FILENAME] = canonical_json_bytes(sizes)
    archive_files[CHECKSUMS_FILENAME] = _checksum_bytes(archive_files)
    return archive_files, manifest


def prepare_packet(
    closure_directory: Path,
    allowlist_path: Path,
    input_roots: Mapping[str, Path],
    output_directory: Path,
) -> dict[str, Any]:
    allowlist = load_allowlist(allowlist_path)
    roots = normalize_roots(input_roots, allowlist.root_names)
    closure_root = normalize_roots({"closure": closure_directory}, ("closure",))["closure"]
    containment_roots = dict(roots)
    containment_roots["closure"] = closure_root
    ensure_output_outside_roots(output_directory, containment_roots)
    archive_files, manifest = build_packet_payload(
        closure_root,
        allowlist_path,
        roots,
    )
    zip_data = _zip_bytes(archive_files)

    def populate(staging: Path) -> None:
        manifest_bytes = archive_files[MANIFEST_FILENAME]
        sizes_bytes = archive_files[SIZES_FILENAME]
        (staging / MANIFEST_FILENAME).write_bytes(manifest_bytes)
        (staging / SIZES_FILENAME).write_bytes(sizes_bytes)
        zip_path = staging / ZIP_FILENAME
        zip_path.write_bytes(zip_data)
        _verify_zip(zip_path, archive_files)
        external_files = {
            MANIFEST_FILENAME: manifest_bytes,
            SIZES_FILENAME: sizes_bytes,
            ZIP_FILENAME: zip_data,
        }
        external_checksums = _checksum_bytes(external_files)
        _verify_checksum_text(external_checksums, external_files)
        (staging / CHECKSUMS_FILENAME).write_bytes(external_checksums)

    publish_directory_atomically(
        output_directory,
        TASK_NAME,
        populate,
        allow_recognized_incomplete=False,
        refuse_existing=True,
    )
    return {
        "candidate_sha": manifest["candidate_sha"],
        "artifact_count": manifest["artifact_count"],
        "zip_sha256": sha256_bytes(zip_data),
        "zip_size_bytes": len(zip_data),
        "zip_entry_count": len(archive_files),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--closure-dir", required=True, type=Path)
    parser.add_argument("--allowlist", required=True, type=Path)
    parser.add_argument("--root", action="append", default=[], metavar="NAME=PATH")
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        roots = parse_root_arguments(args.root)
        result = prepare_packet(
            args.closure_dir,
            args.allowlist,
            roots,
            args.output_dir,
        )
    except EvidenceToolError as exc:
        print(f"FAIL [{exc.category}]: {exc.message}", file=sys.stderr)
        return 1
    print(
        f"OK: created deterministic packet with {result['zip_entry_count']} ZIP entries."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
