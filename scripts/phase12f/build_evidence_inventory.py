#!/usr/bin/env python3
"""Build a deterministic, content-free evidence inventory."""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

if __package__ in {None, ""}:
    ROOT = Path(__file__).resolve().parents[2]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

from scripts.phase12f.common import (  # noqa: E402
    INVENTORY_SCHEMA_VERSION,
    Allowlist,
    ArtifactRule,
    EvidenceToolError,
    canonical_json_bytes,
    ensure_output_outside_roots,
    extract_safe_metadata,
    fingerprint_file,
    load_allowlist,
    normalize_roots,
    parse_root_arguments,
    physical_file_identity,
    publish_directory_atomically,
    resolve_artifact,
    scan_root_files,
    sha256_bytes,
)


INVENTORY_FILENAME = "evidence-inventory.json"
MARKDOWN_FILENAME = "evidence-inventory.md"
TASK_NAME = "phase12f_evidence_inventory"


def _path_key(value: str) -> str:
    return value.casefold() if os.name == "nt" else value


def _rule_map(rules: Sequence[ArtifactRule]) -> dict[tuple[str, str], ArtifactRule]:
    return {(rule.root, _path_key(rule.path)): rule for rule in rules}


def _identity_observations(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    metadata = [record["safe_metadata"] for record in records]
    profiles = Counter(item.get("profile", "none") for item in metadata)
    candidates = sorted(
        {
            item["candidate_sha"]
            for item in metadata
            if isinstance(item.get("candidate_sha"), str)
        }
    )
    authorizations = sorted(
        {
            item["authorization_id"]
            for item in metadata
            if isinstance(item.get("authorization_id"), str)
        }
    )
    attempts = sorted(
        {
            item["attempt"]
            for item in metadata
            if type(item.get("attempt")) is int
        }
    )
    return {
        "candidate_sha_values": candidates,
        "authorization_id_values": authorizations,
        "attempt_values": attempts,
        "metadata_profile_counts": dict(sorted(profiles.items())),
    }


def build_inventory(
    allowlist_path: Path,
    input_roots: Mapping[str, Path],
) -> tuple[dict[str, Any], str]:
    allowlist = load_allowlist(allowlist_path)
    roots = normalize_roots(input_roots, allowlist.root_names)
    rules_by_reference = _rule_map(allowlist.rules)
    scanned = {
        name: scan_root_files(path, name)
        for name, path in roots.items()
    }

    for name, files in scanned.items():
        allowed_paths = {
            key_path
            for key_root, key_path in rules_by_reference
            if key_root == name
        }
        unexpected = sorted(set(files) - allowed_paths)
        if unexpected:
            raise EvidenceToolError(
                "unexpected_artifact",
                f"root {name} contains {len(unexpected)} unallowlisted file(s)",
            )

    records: list[dict[str, Any]] = []
    absent_optional: list[str] = []
    prohibited_absent: list[str] = []
    physical_files: dict[tuple[int, int], str] = {}
    for rule in sorted(allowlist.rules, key=lambda item: item.logical_id):
        path = resolve_artifact(roots[rule.root], rule.path, rule.logical_id)
        present = path.is_file()
        if rule.artifact_class == "required" and not present:
            raise EvidenceToolError(
                "missing_artifact",
                f"required artifact {rule.logical_id} is missing",
            )
        if rule.artifact_class == "prohibited":
            if present:
                raise EvidenceToolError(
                    "prohibited_artifact",
                    f"prohibited artifact {rule.logical_id} is present",
                )
            prohibited_absent.append(rule.logical_id)
            continue
        if not present:
            absent_optional.append(rule.logical_id)
            continue

        identity = physical_file_identity(path)
        if identity in physical_files:
            raise EvidenceToolError(
                "duplicate_logical_artifact",
                f"{rule.logical_id} aliases {physical_files[identity]}",
            )
        physical_files[identity] = rule.logical_id
        digest, size_bytes = fingerprint_file(path)
        safe_metadata = extract_safe_metadata(path, rule.metadata_profile)
        if fingerprint_file(path) != (digest, size_bytes):
            raise EvidenceToolError(
                "source_changed",
                f"{rule.logical_id} changed during metadata projection",
            )
        records.append(
            {
                "logical_id": rule.logical_id,
                "root": rule.root,
                "path": rule.path,
                "class": rule.artifact_class,
                "metadata_profile": rule.metadata_profile,
                "sha256": digest,
                "size_bytes": size_bytes,
                "safe_metadata": safe_metadata,
            }
        )

    observations = _identity_observations(records)
    observed_candidates = observations["candidate_sha_values"]
    if observed_candidates and observed_candidates != [allowlist.candidate_sha]:
        raise EvidenceToolError(
            "candidate_identity",
            "safe metadata does not match the allowlist candidate",
        )
    if len(observations["authorization_id_values"]) > 1:
        raise EvidenceToolError(
            "authorization_identity",
            "safe metadata contains multiple authorization identities",
        )
    if len(observations["attempt_values"]) > 1:
        raise EvidenceToolError(
            "attempt_identity",
            "safe metadata contains multiple attempt identities",
        )

    artifact_projection = [
        {
            "logical_id": record["logical_id"],
            "sha256": record["sha256"],
            "size_bytes": record["size_bytes"],
        }
        for record in records
    ]
    inventory: dict[str, Any] = {
        "schema_version": INVENTORY_SCHEMA_VERSION,
        "candidate_sha": allowlist.candidate_sha,
        "allowlist_sha256": allowlist.sha256,
        "root_names": list(allowlist.root_names),
        "rules": [rule.as_dict() for rule in sorted(allowlist.rules, key=lambda item: item.logical_id)],
        "artifact_count": len(records),
        "artifacts": records,
        "absent_optional_artifacts": sorted(absent_optional),
        "prohibited_artifacts_verified_absent": sorted(prohibited_absent),
        "identity_observations": observations,
        "artifact_set_sha256": sha256_bytes(canonical_json_bytes(artifact_projection)),
    }
    return inventory, render_markdown(inventory)


def render_markdown(inventory: Mapping[str, Any]) -> str:
    lines = [
        "# Phase 12F Evidence Inventory",
        "",
        f"- Candidate: `{inventory['candidate_sha']}`",
        f"- Allowlist SHA-256: `{inventory['allowlist_sha256']}`",
        f"- Artifact count: `{inventory['artifact_count']}`",
        f"- Artifact-set SHA-256: `{inventory['artifact_set_sha256']}`",
        "",
        "| Logical artifact | Root | Relative path | Class | SHA-256 | Bytes |",
        "|---|---|---|---|---|---:|",
    ]
    for record in inventory["artifacts"]:
        lines.append(
            f"| `{record['logical_id']}` | `{record['root']}` | "
            f"`{record['path']}` | `{record['class']}` | "
            f"`{record['sha256']}` | {record['size_bytes']} |"
        )
    lines.extend(
        [
            "",
            "## Classification",
            "",
            "Optional artifacts absent: "
            + (
                ", ".join(f"`{item}`" for item in inventory["absent_optional_artifacts"])
                or "None"
            ),
            "",
            "Prohibited artifacts verified absent: "
            + (
                ", ".join(
                    f"`{item}`"
                    for item in inventory["prohibited_artifacts_verified_absent"]
                )
                or "None"
            ),
            "",
            "Only safe metadata profiles were parsed. Record-level result and JSONL "
            "content was not parsed.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_inventory(
    allowlist_path: Path,
    roots: Mapping[str, Path],
    output_directory: Path,
) -> dict[str, Any]:
    allowlist = load_allowlist(allowlist_path)
    normalized = normalize_roots(roots, allowlist.root_names)
    ensure_output_outside_roots(output_directory, normalized)
    inventory, markdown = build_inventory(allowlist_path, normalized)

    def populate(staging: Path) -> None:
        (staging / INVENTORY_FILENAME).write_bytes(canonical_json_bytes(inventory))
        (staging / MARKDOWN_FILENAME).write_text(
            markdown,
            encoding="utf-8",
            newline="\n",
        )

    publish_directory_atomically(
        output_directory,
        TASK_NAME,
        populate,
        allow_recognized_incomplete=True,
    )
    return inventory


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allowlist", required=True, type=Path)
    parser.add_argument(
        "--root",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help="Explicit logical input root; repeat for every allowlist root.",
    )
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        roots = parse_root_arguments(args.root)
        inventory = write_inventory(args.allowlist, roots, args.output_dir)
    except EvidenceToolError as exc:
        print(f"FAIL [{exc.category}]: {exc.message}", file=sys.stderr)
        return 1
    print(
        f"OK: inventoried {inventory['artifact_count']} allowlisted artifact(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
