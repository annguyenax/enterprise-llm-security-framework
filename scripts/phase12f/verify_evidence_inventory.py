#!/usr/bin/env python3
"""Verify a Phase 12F evidence inventory without modifying source evidence."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any, Mapping, Sequence

if __package__ in {None, ""}:
    ROOT = Path(__file__).resolve().parents[2]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

from scripts.phase12f.common import (  # noqa: E402
    ALLOWLIST_SCHEMA_VERSION,
    ARTIFACT_CLASSES,
    INVENTORY_SCHEMA_VERSION,
    METADATA_PROFILES,
    SAFE_PACKET_CLASSES,
    ArtifactRule,
    EvidenceToolError,
    canonical_json_bytes,
    ensure_output_outside_roots,
    extract_safe_metadata,
    fingerprint_file,
    normalize_roots,
    parse_root_arguments,
    physical_file_identity,
    resolve_artifact,
    scan_root_files,
    sha256_bytes,
    write_file_atomically,
)


REPORT_SCHEMA_VERSION = 1
_GIT_SHA_RE = re.compile(r"[0-9a-f]{40}")
_HEX_SHA_RE = re.compile(r"[0-9a-f]{64}")
_ROOT_NAME_RE = re.compile(r"[a-z][a-z0-9_]{0,63}")
_LOGICAL_ID_RE = re.compile(r"[a-z][a-z0-9_.-]{0,127}")
_INVENTORY_KEYS = {
    "schema_version",
    "candidate_sha",
    "allowlist_sha256",
    "root_names",
    "rules",
    "artifact_count",
    "artifacts",
    "absent_optional_artifacts",
    "prohibited_artifacts_verified_absent",
    "identity_observations",
    "artifact_set_sha256",
}
_RECORD_KEYS = {
    "logical_id",
    "root",
    "path",
    "class",
    "metadata_profile",
    "sha256",
    "size_bytes",
    "safe_metadata",
}
_RULE_KEYS = {
    "logical_id",
    "root",
    "path",
    "class",
    "metadata_profile",
    "packet_class",
}


def _path_key(value: str) -> str:
    return value.casefold() if os.name == "nt" else value


def _finding(category: str, message: str, logical_id: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"category": category, "message": message}
    if logical_id is not None:
        result["logical_id"] = logical_id
    return result


def _load_inventory(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise EvidenceToolError("inventory_input", "inventory must be a regular non-link file")
    try:
        payload = json.loads(path.read_bytes().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceToolError("inventory_schema", "inventory is not strict UTF-8 JSON") from exc
    if not isinstance(payload, dict) or set(payload) != _INVENTORY_KEYS:
        raise EvidenceToolError("inventory_schema", "inventory has an unexpected top-level shape")
    if type(payload["schema_version"]) is not int or payload["schema_version"] != INVENTORY_SCHEMA_VERSION:
        raise EvidenceToolError("inventory_schema", "inventory schema_version must be integer 1")
    candidate = payload["candidate_sha"]
    if not isinstance(candidate, str) or not _GIT_SHA_RE.fullmatch(candidate):
        raise EvidenceToolError("inventory_schema", "inventory candidate_sha is malformed")
    for field in ("allowlist_sha256", "artifact_set_sha256"):
        if not isinstance(payload[field], str) or not _HEX_SHA_RE.fullmatch(payload[field]):
            raise EvidenceToolError("inventory_schema", f"inventory {field} is malformed")
    if not isinstance(payload["rules"], list) or not isinstance(payload["artifacts"], list):
        raise EvidenceToolError("inventory_schema", "inventory rules/artifacts must be lists")
    return payload


def _rules_from_inventory(payload: Mapping[str, Any]) -> tuple[ArtifactRule, ...]:
    rules: list[ArtifactRule] = []
    logical_ids: set[str] = set()
    references: set[tuple[str, str]] = set()
    for index, item in enumerate(payload["rules"]):
        if not isinstance(item, dict) or set(item) != _RULE_KEYS:
            raise EvidenceToolError("inventory_schema", f"rules[{index}] has an invalid shape")
        values = (
            item["logical_id"],
            item["root"],
            item["path"],
            item["class"],
            item["metadata_profile"],
        )
        if not all(isinstance(value, str) for value in values):
            raise EvidenceToolError("inventory_schema", f"rules[{index}] has an invalid type")
        logical_id = item["logical_id"]
        root = item["root"]
        relative = item["path"]
        packet_class = item["packet_class"]
        if not _LOGICAL_ID_RE.fullmatch(logical_id) or not _ROOT_NAME_RE.fullmatch(root):
            raise EvidenceToolError("inventory_schema", f"rules[{index}] has an invalid identifier")
        pure = PurePosixPath(relative)
        if (
            not relative
            or "\\" in relative
            or pure.is_absolute()
            or any(part in {"", ".", ".."} for part in pure.parts)
        ):
            raise EvidenceToolError("path_escape", f"rules[{index}] has an unsafe path")
        if item["class"] not in ARTIFACT_CLASSES or item["metadata_profile"] not in METADATA_PROFILES:
            raise EvidenceToolError("inventory_schema", f"rules[{index}] has an invalid class")
        if packet_class is not None and packet_class not in SAFE_PACKET_CLASSES:
            raise EvidenceToolError("inventory_schema", f"rules[{index}] has an invalid packet class")
        if item["class"] == "prohibited" and (
            item["metadata_profile"] != "none" or packet_class is not None
        ):
            raise EvidenceToolError("inventory_schema", "prohibited rule has active processing")
        reference = (item["root"], _path_key(item["path"]))
        if logical_id in logical_ids or reference in references:
            raise EvidenceToolError("duplicate_logical_artifact", "inventory rules contain a duplicate")
        logical_ids.add(logical_id)
        references.add(reference)
        rules.append(
            ArtifactRule(
                logical_id,
                item["root"],
                item["path"],
                item["class"],
                item["metadata_profile"],
                item["packet_class"],
            )
        )
    normalized_allowlist = {
        "schema_version": ALLOWLIST_SCHEMA_VERSION,
        "candidate_sha": payload["candidate_sha"],
        "artifacts": [
            rule.as_dict()
            for rule in sorted(rules, key=lambda value: value.logical_id)
        ],
    }
    if sha256_bytes(canonical_json_bytes(normalized_allowlist)) != payload["allowlist_sha256"]:
        raise EvidenceToolError("allowlist_identity", "embedded allowlist identity is inconsistent")
    return tuple(rules)


def _records_from_inventory(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(payload["artifacts"]):
        if not isinstance(item, dict) or set(item) != _RECORD_KEYS:
            raise EvidenceToolError("inventory_schema", f"artifacts[{index}] has an invalid shape")
        logical_id = item["logical_id"]
        if not isinstance(logical_id, str) or logical_id in records:
            raise EvidenceToolError("duplicate_logical_artifact", "inventory records contain a duplicate")
        if (
            not _LOGICAL_ID_RE.fullmatch(logical_id)
            or not isinstance(item["root"], str)
            or not isinstance(item["path"], str)
            or not isinstance(item["class"], str)
            or not isinstance(item["metadata_profile"], str)
            or not isinstance(item["sha256"], str)
            or not _HEX_SHA_RE.fullmatch(item["sha256"])
            or type(item["size_bytes"]) is not int
            or item["size_bytes"] < 0
            or not isinstance(item["safe_metadata"], dict)
        ):
            raise EvidenceToolError("inventory_schema", f"artifacts[{index}] has invalid integrity fields")
        records[logical_id] = item
    if type(payload["artifact_count"]) is not int or payload["artifact_count"] != len(records):
        raise EvidenceToolError("inventory_schema", "artifact_count is inconsistent")
    projection = [
        {
            "logical_id": record["logical_id"],
            "sha256": record["sha256"],
            "size_bytes": record["size_bytes"],
        }
        for record in sorted(records.values(), key=lambda value: value["logical_id"])
    ]
    if sha256_bytes(canonical_json_bytes(projection)) != payload["artifact_set_sha256"]:
        raise EvidenceToolError("artifact_set_identity", "artifact-set identity is inconsistent")
    return records


def _observations(records: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    metadata = [record["safe_metadata"] for record in records.values()]
    profiles = Counter(item.get("profile", "none") for item in metadata)
    return {
        "candidate_sha_values": sorted(
            {
                item["candidate_sha"]
                for item in metadata
                if isinstance(item.get("candidate_sha"), str)
            }
        ),
        "authorization_id_values": sorted(
            {
                item["authorization_id"]
                for item in metadata
                if isinstance(item.get("authorization_id"), str)
            }
        ),
        "attempt_values": sorted(
            {
                item["attempt"]
                for item in metadata
                if type(item.get("attempt")) is int
            }
        ),
        "metadata_profile_counts": dict(sorted(profiles.items())),
    }


def _report(
    candidate: str | None,
    status: str,
    failures: list[dict[str, Any]],
    not_verifiable: list[dict[str, Any]],
    checked_count: int,
) -> dict[str, Any]:
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "candidate_sha": candidate,
        "status": status,
        "passed": status == "PASS",
        "checked_artifact_count": checked_count,
        "findings": failures,
        "not_verifiable": not_verifiable,
    }


def verify_inventory(
    inventory_path: Path,
    input_roots: Mapping[str, Path],
) -> dict[str, Any]:
    try:
        payload = _load_inventory(inventory_path)
        rules = _rules_from_inventory(payload)
        records = _records_from_inventory(payload)
        if payload["identity_observations"] != _observations(records):
            raise EvidenceToolError(
                "inventory_schema",
                "identity_observations are inconsistent",
            )
        optional_ids = {
            rule.logical_id
            for rule in rules
            if rule.artifact_class == "optional"
        }
        required_ids = {
            rule.logical_id
            for rule in rules
            if rule.artifact_class == "required"
        }
        prohibited_ids = sorted(
            rule.logical_id
            for rule in rules
            if rule.artifact_class == "prohibited"
        )
        absent_optional = sorted(optional_ids - set(records))
        if payload["absent_optional_artifacts"] != absent_optional:
            raise EvidenceToolError(
                "inventory_schema",
                "absent optional artifact list is inconsistent",
            )
        if payload["prohibited_artifacts_verified_absent"] != prohibited_ids:
            raise EvidenceToolError(
                "inventory_schema",
                "prohibited artifact list is inconsistent",
            )
        if not required_ids.issubset(records):
            raise EvidenceToolError(
                "inventory_schema",
                "required allowlist rule has no inventory record",
            )
        root_names = payload["root_names"]
        if (
            not isinstance(root_names, list)
            or not all(isinstance(item, str) for item in root_names)
            or root_names != sorted({rule.root for rule in rules})
        ):
            raise EvidenceToolError("inventory_schema", "root_names are inconsistent")
        roots = normalize_roots(input_roots, root_names)
    except EvidenceToolError as exc:
        return _report(
            None,
            "FAIL",
            [_finding(exc.category, exc.message)],
            [],
            0,
        )

    failures: list[dict[str, Any]] = []
    not_verifiable: list[dict[str, Any]] = []
    rules_by_reference = {
        (rule.root, _path_key(rule.path)): rule
        for rule in rules
    }
    try:
        scanned = {
            name: scan_root_files(path, name)
            for name, path in roots.items()
        }
    except EvidenceToolError as exc:
        return _report(
            payload["candidate_sha"],
            "FAIL",
            [_finding(exc.category, exc.message)],
            [],
            0,
        )

    for root_name, files in scanned.items():
        allowed = {
            path_key
            for rule_root, path_key in rules_by_reference
            if rule_root == root_name
        }
        for unexpected in sorted(set(files) - allowed):
            failures.append(
                _finding(
                    "added_artifact",
                    f"root {root_name} contains an unallowlisted artifact",
                )
            )

    physical: dict[tuple[int, int], str] = {}
    checked = 0
    metadata_now: list[dict[str, Any]] = []
    for rule in sorted(rules, key=lambda value: value.logical_id):
        try:
            path = resolve_artifact(roots[rule.root], rule.path, rule.logical_id)
        except EvidenceToolError as exc:
            failures.append(_finding(exc.category, exc.message, rule.logical_id))
            continue
        present = path.is_file()
        record = records.get(rule.logical_id)
        if rule.artifact_class == "prohibited":
            if present:
                failures.append(
                    _finding(
                        "prohibited_artifact",
                        "prohibited artifact is present",
                        rule.logical_id,
                    )
                )
            if record is not None:
                failures.append(
                    _finding(
                        "inventory_schema",
                        "prohibited artifact has an inventory record",
                        rule.logical_id,
                    )
                )
            continue
        if not present:
            if rule.artifact_class == "required" or record is not None:
                failures.append(
                    _finding("missing_artifact", "artifact is missing", rule.logical_id)
                )
            continue
        if record is None:
            failures.append(
                _finding(
                    "added_artifact",
                    "present artifact has no inventory record",
                    rule.logical_id,
                )
            )
            continue
        checked += 1
        identity = physical_file_identity(path)
        if identity in physical:
            failures.append(
                _finding(
                    "duplicate_logical_artifact",
                    f"artifact aliases {physical[identity]}",
                    rule.logical_id,
                )
            )
        physical[identity] = rule.logical_id
        if (
            record["root"] != rule.root
            or record["path"] != rule.path
            or record["class"] != rule.artifact_class
            or record["metadata_profile"] != rule.metadata_profile
        ):
            failures.append(
                _finding(
                    "inventory_schema",
                    "record classification disagrees with its rule",
                    rule.logical_id,
                )
            )
        try:
            digest, size_bytes = fingerprint_file(path)
        except EvidenceToolError as exc:
            failures.append(_finding(exc.category, exc.message, rule.logical_id))
            continue
        if size_bytes != record["size_bytes"]:
            failures.append(
                _finding("changed_artifact", "artifact byte size changed", rule.logical_id)
            )
        if digest != record["sha256"]:
            failures.append(
                _finding("changed_artifact", "artifact SHA-256 changed", rule.logical_id)
            )
        try:
            safe_metadata = extract_safe_metadata(path, rule.metadata_profile)
        except EvidenceToolError as exc:
            failures.append(_finding(exc.category, exc.message, rule.logical_id))
            continue
        try:
            if fingerprint_file(path) != (digest, size_bytes):
                failures.append(
                    _finding(
                        "source_changed",
                        "artifact changed during metadata projection",
                        rule.logical_id,
                    )
                )
                continue
        except EvidenceToolError as exc:
            failures.append(_finding(exc.category, exc.message, rule.logical_id))
            continue
        metadata_now.append(safe_metadata)
        if safe_metadata != record["safe_metadata"]:
            failures.append(
                _finding("changed_metadata", "safe metadata changed", rule.logical_id)
            )

    unknown_records = sorted(set(records) - {rule.logical_id for rule in rules})
    for logical_id in unknown_records:
        failures.append(
            _finding("duplicate_logical_artifact", "record has no allowlist rule", logical_id)
        )

    candidates = {
        item["candidate_sha"]
        for item in metadata_now
        if isinstance(item.get("candidate_sha"), str)
    }
    authorization_ids = {
        item["authorization_id"]
        for item in metadata_now
        if isinstance(item.get("authorization_id"), str)
    }
    attempts = {
        item["attempt"]
        for item in metadata_now
        if type(item.get("attempt")) is int
    }
    if not candidates:
        not_verifiable.append(
            _finding(
                "candidate_identity",
                "no safe metadata artifact independently exposes candidate identity",
            )
        )
    elif candidates != {payload["candidate_sha"]}:
        failures.append(
            _finding(
                "candidate_identity",
                "safe metadata candidate does not match inventory candidate",
            )
        )
    if len(authorization_ids) > 1:
        failures.append(
            _finding(
                "authorization_identity",
                "safe metadata contains multiple authorization identities",
            )
        )
    if len(attempts) > 1:
        failures.append(
            _finding(
                "attempt_identity",
                "safe metadata contains multiple attempt identities",
            )
        )

    profiles_in_rules = {rule.metadata_profile for rule in rules}
    profiles_present = {
        item.get("profile")
        for item in metadata_now
        if isinstance(item.get("profile"), str)
    }
    for profile in ("authorization", "receipt"):
        if profile in profiles_in_rules and profile not in profiles_present:
            not_verifiable.append(
                _finding(
                    f"{profile}_identity",
                    f"{profile} identity was configured but is unavailable",
                )
            )
    if "receipt" in profiles_present and "authorization" not in profiles_present:
        not_verifiable.append(
            _finding(
                "authorization_identity",
                "receipt is present without an authorization metadata source",
            )
        )

    if failures:
        status = "FAIL"
    elif not_verifiable:
        status = "NOT_VERIFIABLE"
    else:
        status = "PASS"
    return _report(
        payload["candidate_sha"],
        status,
        failures,
        not_verifiable,
        checked,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--root", action="append", default=[], metavar="NAME=PATH")
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    roots: dict[str, Path] = {}
    try:
        roots = parse_root_arguments(args.root)
    except EvidenceToolError as exc:
        report = _report(
            None,
            "FAIL",
            [_finding(exc.category, exc.message)],
            [],
            0,
        )
    else:
        report = verify_inventory(args.inventory, roots)
    encoded = canonical_json_bytes(report)
    if args.output is None:
        sys.stdout.buffer.write(encoded)
    else:
        try:
            normalized_for_output = normalize_roots(
                roots,
                tuple(sorted(roots)),
            )
            ensure_output_outside_roots(args.output, normalized_for_output)
            write_file_atomically(args.output, encoded)
        except EvidenceToolError as exc:
            print(f"FAIL [{exc.category}]: {exc.message}", file=sys.stderr)
            return 1
    if report["status"] == "PASS":
        return 0
    if report["status"] == "NOT_VERIFIABLE":
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
