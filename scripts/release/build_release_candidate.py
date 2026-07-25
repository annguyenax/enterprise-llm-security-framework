"""Deterministic Phase 12G release-candidate builder (verify-before-publish).

Builds a release ZIP from tracked Git files plus an explicit operator-supplied
generated-file allowlist. Classification is driven by the tracked, mechanically
disjoint closed-world release policy ``release/release-allowlist.json`` (schema
4): EVERY tracked path is classified by COUNTING matching inclusion rules (no
precedence); exactly one permitted match includes the path and records its
class + unique rule ID + matched rule form. Zero matches -> unclassified;
more than one -> ambiguous; permitted+prohibited -> overlap.

The policy file is read ONCE; the same bytes are parsed, hashed and packaged.
Each tracked file is read exactly once into a single bound snapshot that is both
hashed and written to the ZIP. An allowed archive's safety is decided from THOSE
SAME snapshot bytes (io.BytesIO) via the shared inspector — never a second read.

Publication order: build + verify a ZIP in a same-volume staging directory,
require verifier PASS (anchored to the tracked policy identity), then publish the
exact verified bytes with an atomic no-clobber hard link, recheck hash/size, and
verify the published ZIP again. A pre-publication failure leaves no final
directory or ZIP.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from release_common import (  # type: ignore
        BUILDER_TOOL, CHECKSUMS_NAME, CLASS_ALLOWED_ARCHIVE, CLASS_GENERATED,
        CONTROL_COVERAGE_CANON, GENERATED_RULE_ID, MANIFEST_NAME, MANIFEST_SCHEMA_VERSION,
        PAYLOAD_PREFIX, POLICY_RELPATH, SIZES_NAME, ZIP_POLICY_CANON, ReleaseError, ReleasePolicy,
        assert_within, checksum_text, classify_path, classification_summary, deterministic_zip_bytes,
        exclusive_write, hardlink_no_clobber, inspect_archive_bytes, is_hex40, is_symlink_or_reparse,
        parse_release_policy, read_snapshot_bytes, read_zip_entries, sha256_bytes, validate_relative_posix,
    )
    import verify_release_candidate as _verifier  # type: ignore
else:
    from .release_common import (  # noqa: F401
        BUILDER_TOOL, CHECKSUMS_NAME, CLASS_ALLOWED_ARCHIVE, CLASS_GENERATED,
        CONTROL_COVERAGE_CANON, GENERATED_RULE_ID, MANIFEST_NAME, MANIFEST_SCHEMA_VERSION,
        PAYLOAD_PREFIX, POLICY_RELPATH, SIZES_NAME, ZIP_POLICY_CANON, ReleaseError, ReleasePolicy,
        assert_within, checksum_text, classify_path, classification_summary, deterministic_zip_bytes,
        exclusive_write, hardlink_no_clobber, inspect_archive_bytes, is_hex40, is_symlink_or_reparse,
        parse_release_policy, read_snapshot_bytes, read_zip_entries, sha256_bytes, validate_relative_posix,
    )
    from . import verify_release_candidate as _verifier  # noqa: F401

ZIP_NAME = "release-candidate.zip"


def _git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo_root), *args],
                            capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise ReleaseError("git_error", f"git {' '.join(args)} failed")
    return result.stdout


def _clean_tree_state(repo_root: Path) -> str:
    return _git(repo_root, "status", "--porcelain", "--untracked-files=no").strip()


def _tracked_files(repo_root: Path) -> list[str]:
    raw = _git(repo_root, "ls-files", "-z")
    return sorted(item for item in raw.split("\0") if item)


def _load_generated_allowlist(path: Path) -> tuple[list[dict[str, Any]], str]:
    """Load the EXTERNAL operator-supplied generated allowlist. Returns the
    validated entries and the SHA-256 of the exact allowlist bytes (the external
    trusted generated-allowlist anchor)."""
    if is_symlink_or_reparse(path):
        raise ReleaseError("generated_allowlist", "generated allowlist is a symlink/reparse point")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ReleaseError("generated_allowlist", "generated allowlist could not be read") from exc
    allowlist_sha = sha256_bytes(raw)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
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
    return entries, allowlist_sha


def _reject_symlink_chain(repo_root: Path, rel: str) -> None:
    partial = repo_root
    for part in Path(rel).parts:
        partial = partial / part
        if partial.exists() and is_symlink_or_reparse(partial):
            raise ReleaseError("symlink_rejected", f"{rel} passes through a symlink/reparse point")


def _snapshot_tracked(repo_root: Path, rel: str, policy: ReleasePolicy,
                      policy_bytes: bytes) -> dict[str, Any]:
    rel = validate_relative_posix(rel, label="path")
    result = classify_path(rel, policy)  # fails closed on unclassified/ambiguous/overlap/prohibited
    absolute = repo_root / Path(rel)
    assert_within(repo_root, absolute, label=rel)
    _reject_symlink_chain(repo_root, rel)
    if not absolute.is_file():
        raise ReleaseError("missing_source", f"declared file is absent: {rel}")
    # SINGLE bound snapshot (reuse the exact policy bytes already read for the policy file).
    data = policy_bytes if rel == POLICY_RELPATH else read_snapshot_bytes(absolute)
    archive_inspection = None
    if result.classification == CLASS_ALLOWED_ARCHIVE:
        # Safety decided from the SAME bound bytes, not a second filesystem read.
        archive_inspection = inspect_archive_bytes(
            data, policy, rule_id=result.rule_id,
            payload_sha=sha256_bytes(data), payload_size=len(data))
    return {"path": rel, "sha256": sha256_bytes(data), "size_bytes": len(data),
            "source": "tracked", "classification": result.classification,
            "rule_id": result.rule_id, "rule_form": result.rule_form,
            "archive_inspection": archive_inspection, "_bytes": data}


def _snapshot_generated(repo_root: Path, declared: dict[str, Any],
                        policy: ReleasePolicy) -> dict[str, Any]:
    rel = validate_relative_posix(declared["path"], label="generated path")
    result = classify_path(rel, policy)  # must be an includable, non-archive path
    if result.classification == CLASS_ALLOWED_ARCHIVE:
        raise ReleaseError("generated_archive", f"generated archives are not supported: {rel}")
    absolute = repo_root / Path(rel)
    assert_within(repo_root, absolute, label=rel)
    _reject_symlink_chain(repo_root, rel)
    if not absolute.is_file():
        raise ReleaseError("missing_source", f"declared generated file is absent: {rel}")
    data = read_snapshot_bytes(absolute)
    if sha256_bytes(data) != declared["sha256"] or len(data) != declared["size_bytes"]:
        raise ReleaseError("generated_mismatch", f"generated file does not match its pin: {rel}")
    return {"path": rel, "sha256": sha256_bytes(data), "size_bytes": len(data),
            "source": "generated", "classification": CLASS_GENERATED,
            "rule_id": GENERATED_RULE_ID, "rule_form": "generated",
            "archive_inspection": None, "_bytes": data}


def _build_payload(*, repo_root: Path, expected_head: str | None, expected_branch: str | None,
                   base_sha: str | None, generated_allowlist: Path | None) -> dict[str, Any]:
    head_before = _git(repo_root, "rev-parse", "HEAD").strip()
    if _clean_tree_state(repo_root) != "":
        raise ReleaseError("dirty_tree", "repository working tree has tracked modifications")
    branch = _git(repo_root, "rev-parse", "--abbrev-ref", "HEAD").strip()
    if expected_head is not None and head_before != expected_head:
        raise ReleaseError("identity_mismatch", "HEAD does not match --expected-head")
    if expected_branch is not None and branch != expected_branch:
        raise ReleaseError("identity_mismatch", "branch does not match --expected-branch")
    if base_sha is not None and not is_hex40(base_sha):
        raise ReleaseError("identity_format", "--base-sha is not a 40-hex commit id")

    policy_path = repo_root / POLICY_RELPATH
    if not policy_path.is_file() or is_symlink_or_reparse(policy_path):
        raise ReleaseError("policy_missing", "tracked release policy is missing or not a regular file")
    policy_bytes = read_snapshot_bytes(policy_path)
    policy = parse_release_policy(policy_bytes)
    assert sha256_bytes(policy_bytes) == policy.sha256

    tracked = _tracked_files(repo_root)
    tracked_set = set(tracked)
    if POLICY_RELPATH not in tracked_set:
        raise ReleaseError("policy_untracked", "release policy path is not tracked by git")
    for required in policy.required_paths:
        if required not in tracked_set:
            raise ReleaseError("policy_required_missing", f"required policy path not tracked: {required}")
    tracked_jsonl = [rel for rel in tracked if rel.casefold().endswith(".jsonl")]
    if tracked_jsonl:
        raise ReleaseError("tracked_jsonl", f"tracked JSONL is prohibited: {tracked_jsonl[:3]}")

    # Mechanical disjointness proof over the current tracked set.
    summary = classification_summary(tracked, policy)
    for bad in ("unclassified", "ambiguous", "overlap", "prohibited"):
        if summary[bad] != 0:
            raise ReleaseError(f"tracked_{bad}", f"tracked set has {summary[bad]} {bad} path(s)")

    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rel in tracked:
        entry = _snapshot_tracked(repo_root, rel, policy, policy_bytes)
        key = entry["path"].casefold()
        if key in seen:
            raise ReleaseError("duplicate_logical_path", f"duplicate logical path: {entry['path']}")
        seen.add(key)
        entries.append(entry)

    generated_entries: list[dict[str, Any]] = []
    generated_allowlist_sha: str | None = None
    if generated_allowlist is not None:
        declared_entries, generated_allowlist_sha = _load_generated_allowlist(
            generated_allowlist.expanduser().resolve())
        for declared in declared_entries:
            entry = _snapshot_generated(repo_root, declared, policy)
            key = entry["path"].casefold()
            if key in seen:
                raise ReleaseError("duplicate_logical_path", f"generated path duplicates a tracked path: {entry['path']}")
            seen.add(key)
            generated_entries.append(entry)

    if _git(repo_root, "rev-parse", "HEAD").strip() != head_before:
        raise ReleaseError("source_changed", "repository HEAD changed during snapshot preparation")
    if _git(repo_root, "rev-parse", "--abbrev-ref", "HEAD").strip() != branch:
        raise ReleaseError("source_changed", "repository branch changed during snapshot preparation")
    if _clean_tree_state(repo_root) != "":
        raise ReleaseError("source_changed", "repository changed during snapshot preparation")

    all_entries = sorted(entries + generated_entries, key=lambda item: item["path"])
    payload: dict[str, bytes] = {f"{PAYLOAD_PREFIX}{e['path']}": e["_bytes"] for e in all_entries}
    file_count = len(all_entries)

    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "builder": {"tool": BUILDER_TOOL, "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
                    "archive_inspection_version": policy.archive_inspection_version},
        "repository": {"head": head_before, "branch": branch, "base_sha": base_sha},
        "policy": {"policy_id": policy.policy_id, "schema_version": policy.schema_version,
                   "sha256": policy.sha256},
        "generated": {"count": len(generated_entries), "allowlist_sha256": generated_allowlist_sha},
        "counts": {"file_count": file_count, "tracked_count": len(entries),
                   "generated_count": len(generated_entries), "payload_count": file_count,
                   "control_count": 3, "entry_count": file_count + 3},
        "control_coverage": dict(CONTROL_COVERAGE_CANON),
        "content_controls": {
            "jsonl_included": False, "result_json_included": False,
            "credentials_included": False, "databases_included": False,
            "git_metadata_included": False, "venv_included": False,
            "built_from": "git ls-files + explicit generated allowlist; disjoint closed-world policy-enforced",
        },
        "zip_policy": dict(ZIP_POLICY_CANON),
        "files": [
            {"archive_path": f"{PAYLOAD_PREFIX}{e['path']}", "path": e["path"],
             "sha256": e["sha256"], "size_bytes": e["size_bytes"], "source": e["source"],
             "classification": e["classification"], "rule_id": e["rule_id"],
             "rule_form": e["rule_form"], "archive_inspection": e["archive_inspection"]}
            for e in all_entries
        ],
    }
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    payload[MANIFEST_NAME] = manifest_bytes

    sizes_payload = {name: len(data) for name, data in payload.items()}
    sizes = {"schema_version": 1, "files": dict(sorted(sizes_payload.items()))}
    sizes_bytes = (json.dumps(sizes, indent=2, sort_keys=True) + "\n").encode("utf-8")
    payload[SIZES_NAME] = sizes_bytes

    payload[CHECKSUMS_NAME] = checksum_text(payload)

    zip_bytes = deterministic_zip_bytes(payload)
    return {
        "zip_bytes": zip_bytes, "manifest_bytes": manifest_bytes,
        "sizes_bytes": sizes_bytes, "checksums_bytes": payload[CHECKSUMS_NAME],
        "payload": payload, "policy": policy, "summary": summary,
        "head": head_before, "branch": branch,
        "payload_count": file_count, "control_count": 3,
        "generated_count": len(generated_entries), "generated_allowlist_sha256": generated_allowlist_sha,
    }


def _verify_zip_pass(zip_path: Path, policy_path: Path, policy: ReleasePolicy, *,
                     generated_allowlist_sha: str | None, stage: str) -> str:
    """Verify with the EXTERNAL trusted policy FILE bytes and, when generated
    files are present, the EXTERNAL trusted generated-allowlist SHA (from the
    operator-supplied allowlist file). Never candidate self-anchoring. Requires PASS."""
    report = _verifier.verify_release_candidate(
        zip_path, expected_policy_file=policy_path, expected_policy_id=policy.policy_id,
        expected_generated_sha256=generated_allowlist_sha)
    if report.get("status") != "PASS":
        raise ReleaseError("verify_before_publish", f"{stage} verification did not PASS")
    return report.get("policy_trust", "")


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

    zip_path = output_dir / ZIP_NAME
    policy_path = repo_root / POLICY_RELPATH
    if output_dir.exists():
        raise ReleaseError("output_reuse", "output directory already exists")
    if zip_path.exists():
        raise ReleaseError("output_reuse", "release ZIP already exists")

    built = _build_payload(
        repo_root=repo_root, expected_head=expected_head, expected_branch=expected_branch,
        base_sha=base_sha, generated_allowlist=generated_allowlist,
    )
    policy = built["policy"]
    zip_bytes = built["zip_bytes"]
    verified_sha = sha256_bytes(zip_bytes)
    verified_size = len(zip_bytes)

    staging_dir: Path | None = None
    created_output = False
    try:
        staging_dir = Path(tempfile.mkdtemp(prefix=".rc-stage-", dir=str(output_dir.parent)))
        staging_zip = staging_dir / ZIP_NAME
        exclusive_write(staging_zip, zip_bytes)
        exclusive_write(staging_dir / MANIFEST_NAME, built["manifest_bytes"])
        exclusive_write(staging_dir / SIZES_NAME, built["sizes_bytes"])
        exclusive_write(staging_dir / CHECKSUMS_NAME, checksum_text({
            ZIP_NAME: zip_bytes, MANIFEST_NAME: built["manifest_bytes"], SIZES_NAME: built["sizes_bytes"],
        }))

        if sha256_bytes(staging_zip.read_bytes()) != verified_sha:
            raise ReleaseError("staging_mismatch", "staged ZIP bytes differ from the in-memory build")
        prepub_trust = _verify_zip_pass(staging_zip, policy_path, policy,
                                        generated_allowlist_sha=built["generated_allowlist_sha256"], stage="staging")

        output_dir.mkdir(parents=True, exist_ok=False)
        created_output = True
        hardlink_no_clobber(staging_zip, zip_path)
        exclusive_write(output_dir / MANIFEST_NAME, built["manifest_bytes"])
        exclusive_write(output_dir / SIZES_NAME, built["sizes_bytes"])
        exclusive_write(output_dir / CHECKSUMS_NAME, checksum_text({
            ZIP_NAME: zip_bytes, MANIFEST_NAME: built["manifest_bytes"], SIZES_NAME: built["sizes_bytes"],
        }))

        final_bytes = zip_path.read_bytes()
        if sha256_bytes(final_bytes) != verified_sha or len(final_bytes) != verified_size:
            raise ReleaseError("publication_mismatch", "published ZIP bytes differ from the verified ZIP")
        postpub_trust = _verify_zip_pass(zip_path, policy_path, policy,
                                         generated_allowlist_sha=built["generated_allowlist_sha256"], stage="published")

        reopened = read_zip_entries(zip_path)
        if set(reopened) != set(built["payload"]):
            raise ReleaseError("zip_verification", "published ZIP entry set is inconsistent after reopen")
        for name, data in built["payload"].items():
            if sha256_bytes(reopened[name]) != sha256_bytes(data):
                raise ReleaseError("zip_verification", "published ZIP entry bytes changed after reopen")
    except BaseException:
        if created_output and output_dir.exists():
            shutil.rmtree(output_dir, ignore_errors=True)
        raise
    finally:
        if staging_dir is not None and staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)

    return {
        "schema_version": 1, "tool": BUILDER_TOOL, "ok": True,
        "repo_head": built["head"], "repo_branch": built["branch"],
        "policy_id": policy.policy_id, "policy_schema_version": policy.schema_version,
        "policy_sha256": policy.sha256, "classification_summary": built["summary"],
        "trust_anchor_source": "external_tracked_policy",
        "trusted_policy_path": POLICY_RELPATH, "trusted_policy_sha256": policy.sha256,
        "verifier_trust_mode": postpub_trust,
        "prepublication_verifier_result": "PASS", "postpublication_verifier_result": "PASS",
        "prepublication_verifier_trust_mode": prepub_trust,
        "generated_count": built["generated_count"], "generated_allowlist_sha256": built["generated_allowlist_sha256"],
        "output_dir": str(output_dir), "zip_path": str(zip_path),
        "zip_sha256": verified_sha, "zip_size_bytes": verified_size,
        "zip_entry_count": len(built["payload"]), "payload_count": built["payload_count"],
        "control_count": 3, "verified_before_publish": True, "published_atomically": True,
        "clean_tree_before": True, "clean_tree_after": True,
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
        payload = {"schema_version": 1, "tool": BUILDER_TOOL,
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
