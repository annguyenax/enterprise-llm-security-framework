"""Fail-closed repository policy checks with content-free reports.

The checker reasons only about tracked path names, required-file presence,
conflict-marker shape, and optional Git cleanliness. It never reports source
lines or file contents. PASS therefore means only that the mechanically
defined rules in this module passed; it is not a security certification.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable, Mapping, Sequence


SCHEMA_VERSION = 1
TOOL_NAME = "phase12g_repository_policy"

REQUIRED_MANIFESTS = (
    "datasets/v2/manifests/benchmark-v2-manifest.json",
    "redteam/prompts-manifest.json",
)

RELEASE_POLICY_FILES = (
    "docs/phase12f/00_STATUS_AND_SCOPE.md",
    "docs/phase12f/01_RELEASE_ARCHITECTURE.md",
    "docs/phase12f/02_EVALUATION_GOVERNANCE.md",
    "docs/phase12f/03_OPERATIONAL_RUNBOOK.md",
    "docs/phase12f/04_FINAL_REPORT_TEMPLATE.md",
    "docs/phase12f/05_DEMO_AND_DEFENSE_SCRIPT.md",
    "docs/phase12f/06_LIMITATIONS_AND_FUTURE_WORK.md",
    "docs/phase12f/07_RELEASE_CHECKLIST.md",
)

RELEASE_INTEGRATION_PREFIXES = (
    "docs/phase12f/",
    "scripts/phase12f/",
)
RELEASE_INTEGRATION_FILES = frozenset({"scripts/materialize_v2_frozen_artifacts.py"})

PROHIBITED_EVIDENCE_PREFIXES = (
    "reports/evaluation-v2/",
    "reports/phase12e4/",
    "reports/phase-12e4/",
    "evidence/phase12e4/",
    "evidence/phase-12e4/",
)
PROHIBITED_EVIDENCE_BASENAMES = frozenset(
    {
        "holdout-authorization.json",
        "start-receipt.json",
        "authorization-receipt.json",
    }
)

PROHIBITED_DIRECTORY_COMPONENTS = frozenset(
    {
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".nox",
        ".venv",
        "venv",
        "env",
        "node_modules",
        "site-packages",
        ".eggs",
        "dist",
        "build",
        "htmlcov",
    }
)
PROHIBITED_GENERATED_SUFFIXES = frozenset(
    {".pyc", ".pyo", ".aux", ".bbl", ".blg", ".fdb_latexmk", ".fls", ".toc"}
)
PRIVATE_KEY_SUFFIXES = frozenset({".pem", ".key", ".p12", ".pfx", ".jks", ".keystore"})
PRIVATE_CREDENTIAL_BASENAMES = frozenset(
    {
        "id_rsa",
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
        "credentials.json",
        "service-account.json",
        "service_account.json",
        "secrets.json",
        "secret.json",
    }
)
SAFE_ENV_TEMPLATES = frozenset({".env.example", ".env.sample", ".env.template"})
DATABASE_SUFFIXES = frozenset({".db", ".sqlite", ".sqlite3"})
BINARY_SUFFIXES = frozenset(
    {".7z", ".bmp", ".gif", ".ico", ".jpeg", ".jpg", ".pdf", ".png", ".ttf", ".woff", ".woff2", ".zip"}
)

RULE_ORDER = (
    "tracked_paths",
    "tracked_jsonl",
    "tracked_environment",
    "tracked_database",
    "tracked_credentials",
    "tracked_generated_output",
    "phase12e4_evidence",
    "conflict_markers",
    "case_collisions",
    "required_manifests",
    "release_policy_files",
    "clean_worktree",
)

CODE_TO_RULE: Mapping[str, str] = {
    "unsafe_tracked_path": "tracked_paths",
    "tracked_jsonl": "tracked_jsonl",
    "tracked_environment": "tracked_environment",
    "tracked_database": "tracked_database",
    "tracked_credentials": "tracked_credentials",
    "tracked_generated_output": "tracked_generated_output",
    "phase12e4_evidence": "phase12e4_evidence",
    "conflict_marker": "conflict_markers",
    "tracked_file_unreadable": "conflict_markers",
    "case_collision": "case_collisions",
    "required_manifest_missing": "required_manifests",
    "release_policy_missing": "release_policy_files",
    "dirty_worktree": "clean_worktree",
}

_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")
_CONFLICT_START = re.compile(br"^<{7}(?: .*)?$")
_CONFLICT_MIDDLE = re.compile(br"^={7}$")
_CONFLICT_END = re.compile(br"^>{7}(?: .*)?$")


class PolicyToolError(RuntimeError):
    """A deterministic tool error that never includes command output."""


@dataclass(frozen=True, order=True)
class Finding:
    code: str
    path: str
    related_path: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "code": self.code,
            "path": self.path,
            "related_path": self.related_path,
        }


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _canonical_path(path: str) -> str:
    return path.replace("\\", "/")


def _path_shape_is_safe(path: str) -> bool:
    if not isinstance(path, str) or not path or "\\" in path:
        return False
    if path.startswith(("/", "//")) or _DRIVE_PREFIX.match(path):
        return False
    if any(ord(character) < 32 for character in path):
        return False
    pure = PurePosixPath(path)
    return not pure.is_absolute() and all(part not in {"", ".", ".."} for part in pure.parts)


def _is_environment_file(basename: str) -> bool:
    if basename in SAFE_ENV_TEMPLATES:
        return False
    return basename == ".env" or basename.startswith(".env.")


def _is_credential_file(basename: str, suffix: str) -> bool:
    if suffix in PRIVATE_KEY_SUFFIXES or basename in PRIVATE_CREDENTIAL_BASENAMES:
        return True
    return basename.startswith(("credentials.", "secrets."))


def _is_prohibited_evidence_path(path: str) -> bool:
    lowered = path.casefold()
    basename = PurePosixPath(lowered).name
    if any(lowered.startswith(prefix) for prefix in PROHIBITED_EVIDENCE_PREFIXES):
        return True
    if basename in PROHIBITED_EVIDENCE_BASENAMES:
        return True
    return any(
        component.startswith(("phase12e4-attempt", "phase-12e4-attempt"))
        for component in PurePosixPath(lowered).parts
    )


def _path_findings(path: str) -> list[Finding]:
    findings: list[Finding] = []
    normalized = _canonical_path(path)
    lowered = normalized.casefold()
    pure = PurePosixPath(lowered)
    basename = pure.name
    suffix = pure.suffix

    if not _path_shape_is_safe(path):
        findings.append(Finding("unsafe_tracked_path", normalized))
    if suffix == ".jsonl":
        findings.append(Finding("tracked_jsonl", normalized))
    if _is_environment_file(basename):
        findings.append(Finding("tracked_environment", normalized))
    if suffix in DATABASE_SUFFIXES:
        findings.append(Finding("tracked_database", normalized))
    if _is_credential_file(basename, suffix):
        findings.append(Finding("tracked_credentials", normalized))
    if (
        any(component in PROHIBITED_DIRECTORY_COMPONENTS for component in pure.parts)
        or suffix in PROHIBITED_GENERATED_SUFFIXES
        or basename == ".coverage"
    ):
        findings.append(Finding("tracked_generated_output", normalized))
    if _is_prohibited_evidence_path(normalized):
        findings.append(Finding("phase12e4_evidence", normalized))
    return findings


def contains_conflict_marker(data: bytes) -> bool:
    """Return whether text bytes contain an exact Git conflict-marker line."""
    if b"\x00" in data[:8192]:
        return False
    for line in data.splitlines():
        candidate = line.rstrip(b"\r")
        if (
            _CONFLICT_START.fullmatch(candidate)
            or _CONFLICT_MIDDLE.fullmatch(candidate)
            or _CONFLICT_END.fullmatch(candidate)
        ):
            return True
    return False


def evaluate_policy(
    tracked_paths: Iterable[str],
    *,
    read_bytes: Callable[[str], bytes],
    require_clean_tree: bool = False,
    tree_clean: bool | None = None,
) -> dict[str, object]:
    """Evaluate a tracked path set using an injected content reader."""
    tracked = tuple(sorted(set(tracked_paths)))
    tracked_set = set(tracked)
    findings: list[Finding] = []

    for path in tracked:
        findings.extend(_path_findings(path))

    collision_groups: dict[str, list[str]] = {}
    for path in tracked:
        key = unicodedata.normalize("NFC", _canonical_path(path)).casefold()
        collision_groups.setdefault(key, []).append(_canonical_path(path))
    for group in collision_groups.values():
        distinct = sorted(set(group))
        if len(distinct) > 1:
            findings.append(Finding("case_collision", distinct[0], distinct[1]))

    for required in REQUIRED_MANIFESTS:
        if required not in tracked_set:
            findings.append(Finding("required_manifest_missing", required))

    release_integrated = any(
        path in RELEASE_INTEGRATION_FILES
        or any(path.startswith(prefix) for prefix in RELEASE_INTEGRATION_PREFIXES)
        for path in tracked
    )
    if release_integrated:
        for required in RELEASE_POLICY_FILES:
            if required not in tracked_set:
                findings.append(Finding("release_policy_missing", required))

    for path in tracked:
        normalized = _canonical_path(path)
        if PurePosixPath(normalized.casefold()).suffix in BINARY_SUFFIXES:
            continue
        try:
            data = read_bytes(path)
        except (OSError, ValueError):
            findings.append(Finding("tracked_file_unreadable", normalized))
            continue
        if contains_conflict_marker(data):
            findings.append(Finding("conflict_marker", normalized))

    if require_clean_tree and tree_clean is not True:
        findings.append(Finding("dirty_worktree", "."))

    unique_findings = sorted(set(findings))
    counts = {rule: 0 for rule in RULE_ORDER}
    for finding in unique_findings:
        counts[CODE_TO_RULE[finding.code]] += 1

    checks: list[dict[str, object]] = []
    for rule in RULE_ORDER:
        if rule == "clean_worktree" and not require_clean_tree:
            status = "NOT_SELECTED"
        else:
            status = "FAIL" if counts[rule] else "PASS"
        checks.append({"id": rule, "status": status, "finding_count": counts[rule]})

    failed_checks = sum(check["status"] == "FAIL" for check in checks)
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "status": "FAIL" if unique_findings else "PASS",
        "content_free": True,
        "scope": {
            "tracked_file_count": len(tracked),
            "clean_tree_required": require_clean_tree,
            "release_policy_integrated": release_integrated,
        },
        "summary": {
            "check_count": len(checks),
            "failed_check_count": failed_checks,
            "finding_count": len(unique_findings),
        },
        "checks": checks,
        "findings": [finding.as_dict() for finding in unique_findings],
        "claim_boundary": "MECHANICAL_REPOSITORY_POLICY_ONLY",
    }


def render_markdown(report: Mapping[str, object]) -> str:
    lines = [
        "# Phase 12G Repository Policy",
        "",
        f"- Status: **{report['status']}**",
        "- Scope: mechanically verifiable tracked-tree policy only",
        "- Content-free: yes; source lines and file contents are never included",
        "",
        "## Checks",
        "",
        "| Check | Status | Findings |",
        "|---|---:|---:|",
    ]
    for check in report["checks"]:  # type: ignore[index]
        lines.append(
            f"| `{check['id']}` | {check['status']} | {check['finding_count']} |"  # type: ignore[index]
        )
    lines.extend(["", "## Findings", ""])
    findings = report["findings"]  # type: ignore[index]
    if not findings:
        lines.append("None.")
    else:
        lines.extend(["| Code | Path | Related path |", "|---|---|---|"])
        for finding in findings:
            related = finding["related_path"] or ""  # type: ignore[index]
            lines.append(
                f"| `{finding['code']}` | `{finding['path']}` | `{related}` |"  # type: ignore[index]
            )
    lines.extend(
        [
            "",
            "A PASS is not a vulnerability assessment, dependency audit, or release approval.",
            "",
        ]
    )
    return "\n".join(lines)


def _run_git(repo_root: Path, arguments: Sequence[str]) -> bytes:
    command = [
        "git",
        "-c",
        "core.excludesFile=",
        "-c",
        f"safe.directory={repo_root.as_posix()}",
        "-C",
        str(repo_root),
        *arguments,
    ]
    completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if completed.returncode != 0:
        raise PolicyToolError("Git repository inspection failed")
    return completed.stdout


def _tracked_paths(repo_root: Path) -> tuple[str, ...]:
    raw = _run_git(repo_root, ("ls-files", "-z"))
    try:
        return tuple(item.decode("utf-8") for item in raw.split(b"\x00") if item)
    except UnicodeDecodeError as exc:
        raise PolicyToolError("Tracked paths are not valid UTF-8") from exc


def _tree_is_clean(repo_root: Path) -> bool:
    return not _run_git(repo_root, ("status", "--porcelain=v1", "-z", "--untracked-files=all"))


def _repository_reader(repo_root: Path) -> Callable[[str], bytes]:
    resolved_root = repo_root.resolve()

    def read(path: str) -> bytes:
        pure = PurePosixPath(_canonical_path(path))
        candidate = resolved_root.joinpath(*pure.parts)
        if candidate.is_symlink() or not candidate.is_file():
            raise OSError("tracked path is not a regular file")
        resolved = candidate.resolve()
        try:
            resolved.relative_to(resolved_root)
        except ValueError as exc:
            raise OSError("tracked path escapes repository") from exc
        return candidate.read_bytes()

    return read


def _write_bytes_atomically(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    parser.add_argument("--require-clean-tree", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    repo_root = arguments.repo_root.resolve()
    try:
        tracked = _tracked_paths(repo_root)
        tree_clean = _tree_is_clean(repo_root) if arguments.require_clean_tree else None
        report = evaluate_policy(
            tracked,
            read_bytes=_repository_reader(repo_root),
            require_clean_tree=arguments.require_clean_tree,
            tree_clean=tree_clean,
        )
    except PolicyToolError:
        print("FAIL", file=sys.stderr)
        return 2

    json_bytes = canonical_json_bytes(report)
    markdown_bytes = render_markdown(report).encode("utf-8")
    if arguments.json_out:
        _write_bytes_atomically(arguments.json_out, json_bytes)
    else:
        sys.stdout.buffer.write(json_bytes)
    if arguments.markdown_out:
        _write_bytes_atomically(arguments.markdown_out, markdown_bytes)
    print(report["status"], file=sys.stderr)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())