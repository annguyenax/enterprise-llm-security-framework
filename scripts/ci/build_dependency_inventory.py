"""Build a deterministic offline inventory of declared Python dependencies.

No package index, vulnerability service, installed environment, or lock
resolver is queried. Direct-reference locations are redacted to source type and
host class so credentials or private URLs cannot enter generated reports.
"""
from __future__ import annotations

import argparse
import configparser
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import parse_qs, urlsplit

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.11+ is repository policy.
    tomllib = None  # type: ignore[assignment]


SCHEMA_VERSION = 1
TOOL_NAME = "phase12g_dependency_inventory"
VULNERABILITY_STATUS = "NOT_CHECKED"

ROOT_DEPENDENCY_FILES = (
    "requirements.txt",
    "requirements-dev.txt",
    "requirements-test.txt",
    "constraints.txt",
    "pyproject.toml",
    "setup.cfg",
)

_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*")
_REQUIREMENT_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)"
    r"(?:\[(?P<extras>[A-Za-z0-9._,-]+)\])?"
    r"(?P<constraint>.*)$"
)
_EXACT_PIN_RE = re.compile(r"^==\s*([^,;\s*]+)$")
_SOURCE_PREFIXES = ("git+", "hg+", "svn+", "bzr+")
_INDEX_DIRECTIVES = ("--index-url", "--extra-index-url", "--find-links", "--trusted-host")
_SAFE_PUBLIC_HOSTS = frozenset({"pypi.org", "files.pythonhosted.org", "github.com", "gitlab.com"})


class InventoryError(RuntimeError):
    """Deterministic inventory failure without source content disclosure."""


@dataclass(frozen=True)
class InventoryFinding:
    code: str
    source_file: str
    source_line: int | None
    package: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "package": self.package,
            "source_file": self.source_file,
            "source_line": self.source_line,
        }


@dataclass(frozen=True)
class RequirementRecord:
    name: str | None
    canonical_name: str | None
    extras: tuple[str, ...]
    constraint: str
    classification: str
    source_type: str
    editable: bool
    marker_present: bool
    hash_count: int
    source_scheme: str | None
    source_host_class: str | None
    source_file: str
    source_line: int | None

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "canonical_name": self.canonical_name,
            "extras": list(self.extras),
            "constraint": self.constraint,
            "classification": self.classification,
            "source_type": self.source_type,
            "editable": self.editable,
            "marker_present": self.marker_present,
            "hash_count": self.hash_count,
            "source_scheme": self.source_scheme,
            "source_host_class": self.source_host_class,
            "source_file": self.source_file,
            "source_line": self.source_line,
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


def canonical_package_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _safe_relative_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    pure = PurePosixPath(normalized)
    if (
        not normalized
        or pure.is_absolute()
        or any(part in {"", ".", ".."} for part in pure.parts)
        or re.match(r"^[A-Za-z]:", normalized)
    ):
        raise InventoryError("dependency file path is not a safe repository-relative path")
    return pure.as_posix()


def discover_declared_files(repo_root: Path) -> tuple[str, ...]:
    discovered = {name for name in ROOT_DEPENDENCY_FILES if (repo_root / name).is_file()}
    requirements_directory = repo_root / "requirements"
    if requirements_directory.is_dir():
        for path in requirements_directory.glob("*.txt"):
            if path.is_file() and not path.is_symlink():
                discovered.add(path.relative_to(repo_root).as_posix())
    return tuple(sorted(discovered))


def _strip_comment(line: str) -> str:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return ""
    marker = re.search(r"\s+#", line)
    if marker:
        line = line[: marker.start()]
    return line.strip()


def _classification(constraint: str, source_type: str) -> str:
    if source_type != "registry":
        return "unbounded"
    compact = re.sub(r"\s+", "", constraint)
    if _EXACT_PIN_RE.fullmatch(compact):
        return "pinned"
    operators = re.findall(r"(===|==|~=|>=|<=|>|<|!=)", compact)
    if "~=" in operators:
        return "bounded"
    has_lower = any(operator in {">", ">="} for operator in operators)
    has_upper = any(operator in {"<", "<="} for operator in operators)
    if has_lower and has_upper:
        return "bounded"
    return "unbounded"


def _source_metadata(target: str) -> tuple[str, str | None, str | None, str | None]:
    value = target.strip()
    lowered = value.casefold()
    if lowered.startswith(_SOURCE_PREFIXES):
        source_type = "vcs"
    elif re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", value):
        source_type = "url"
    else:
        return "local", None, None, None

    parsed = urlsplit(value)
    scheme = parsed.scheme.casefold() or None
    try:
        hostname = parsed.hostname.casefold() if parsed.hostname else None
    except ValueError:
        hostname = None
    if hostname in _SAFE_PUBLIC_HOSTS:
        host_class = "known_public"
    elif hostname:
        host_class = "other"
    else:
        host_class = "missing"
    package = None
    fragment = parse_qs(parsed.fragment)
    if fragment.get("egg"):
        candidate = fragment["egg"][0]
        if _NAME_RE.fullmatch(candidate):
            package = candidate
    return source_type, scheme, host_class, package


def _source_findings(
    record: RequirementRecord,
    *,
    has_embedded_credentials: bool = False,
) -> list[InventoryFinding]:
    findings: list[InventoryFinding] = []
    details = (record.source_file, record.source_line, record.canonical_name)
    if record.editable:
        findings.append(InventoryFinding("editable_dependency", *details))
    if record.source_type == "vcs":
        findings.append(InventoryFinding("vcs_dependency", *details))
    elif record.source_type == "url":
        findings.append(InventoryFinding("direct_url_dependency", *details))
    elif record.source_type == "local":
        findings.append(InventoryFinding("local_path_dependency", *details))
    if record.source_scheme in {"http", "git+http", "hg+http", "svn+http", "bzr+http", "file"}:
        findings.append(InventoryFinding("prohibited_dependency_source", *details))
    elif record.source_host_class == "other":
        findings.append(InventoryFinding("suspicious_dependency_source", *details))
    if has_embedded_credentials:
        findings.append(InventoryFinding("credential_in_dependency_source", *details))
    return findings


def _parse_requirement_value(
    value: str,
    *,
    source_file: str,
    source_line: int | None,
    editable: bool = False,
) -> tuple[RequirementRecord | None, list[InventoryFinding]]:
    raw = value.strip()
    hash_count = len(re.findall(r"(?:^|\s)--hash(?:=|\s)", raw))
    raw = re.sub(r"\s+--hash(?:=|\s+)\S+", "", raw).strip()
    requirement_part, separator, _marker = raw.partition(";")
    marker_present = bool(separator)
    requirement_part = requirement_part.strip()

    direct_name: str | None = None
    target = requirement_part
    if " @ " in requirement_part:
        left, target = requirement_part.split(" @ ", 1)
        match = _REQUIREMENT_RE.fullmatch(left.strip())
        if not match or match.group("constraint").strip():
            finding = InventoryFinding("malformed_requirement", source_file, source_line)
            return None, [finding]
        direct_name = match.group("name")

    source_type, scheme, host_class, inferred_name = _source_metadata(target)
    has_credentials = False
    if source_type in {"vcs", "url"}:
        parsed = urlsplit(target)
        has_credentials = parsed.username is not None or parsed.password is not None
        name = direct_name or inferred_name
        record = RequirementRecord(
            name=name,
            canonical_name=canonical_package_name(name) if name else None,
            extras=(),
            constraint="<direct-reference>",
            classification="unbounded",
            source_type=source_type,
            editable=editable,
            marker_present=marker_present,
            hash_count=hash_count,
            source_scheme=scheme,
            source_host_class=host_class,
            source_file=source_file,
            source_line=source_line,
        )
        return record, _source_findings(record, has_embedded_credentials=has_credentials)

    if editable and direct_name is None:
        name = None
        record = RequirementRecord(
            name=None,
            canonical_name=None,
            extras=(),
            constraint="<local-reference>",
            classification="unbounded",
            source_type="local",
            editable=True,
            marker_present=marker_present,
            hash_count=hash_count,
            source_scheme=None,
            source_host_class=None,
            source_file=source_file,
            source_line=source_line,
        )
        return record, _source_findings(record)

    match = _REQUIREMENT_RE.fullmatch(requirement_part)
    if not match:
        return None, [InventoryFinding("malformed_requirement", source_file, source_line)]
    name = match.group("name")
    extras = tuple(sorted(filter(None, (match.group("extras") or "").split(","))))
    constraint = re.sub(r"\s+", "", match.group("constraint"))
    if constraint and not re.match(r"^(===|==|~=|>=|<=|>|<|!=)", constraint):
        return None, [
            InventoryFinding("malformed_requirement", source_file, source_line, canonical_package_name(name))
        ]
    record = RequirementRecord(
        name=name,
        canonical_name=canonical_package_name(name),
        extras=extras,
        constraint=constraint,
        classification=_classification(constraint, "registry"),
        source_type="registry",
        editable=editable,
        marker_present=marker_present,
        hash_count=hash_count,
        source_scheme=None,
        source_host_class=None,
        source_file=source_file,
        source_line=source_line,
    )
    return record, []


def _resolve_include(repo_root: Path, current_file: str, value: str) -> str:
    candidate = (PurePosixPath(current_file).parent / value.replace("\\", "/")).as_posix()
    safe = _safe_relative_path(candidate)
    resolved = (repo_root / safe).resolve()
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise InventoryError("included dependency file escapes repository") from exc
    return safe


def _parse_requirements_file(
    repo_root: Path,
    relative: str,
    *,
    visited: set[str],
) -> tuple[list[RequirementRecord], list[InventoryFinding], set[str]]:
    safe = _safe_relative_path(relative)
    if safe in visited:
        return [], [InventoryFinding("dependency_include_cycle", safe, None)], {safe}
    visited.add(safe)
    path = repo_root / safe
    if path.is_symlink() or not path.is_file():
        return [], [InventoryFinding("dependency_file_missing", safe, None)], {safe}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise InventoryError("declared dependency file is not readable UTF-8 text") from exc

    records: list[RequirementRecord] = []
    findings: list[InventoryFinding] = []
    files = {safe}
    for line_number, source_line in enumerate(lines, start=1):
        line = _strip_comment(source_line)
        if not line:
            continue
        include_match = re.match(r"^(?:-r|--requirement)\s+(.+)$", line)
        constraint_match = re.match(r"^(?:-c|--constraint)\s+(.+)$", line)
        if include_match or constraint_match:
            value = (include_match or constraint_match).group(1).strip()  # type: ignore[union-attr]
            try:
                included = _resolve_include(repo_root, safe, value)
            except InventoryError:
                findings.append(InventoryFinding("unsafe_dependency_include", safe, line_number))
                continue
            child_records, child_findings, child_files = _parse_requirements_file(
                repo_root, included, visited=visited
            )
            records.extend(child_records)
            findings.extend(child_findings)
            files.update(child_files)
            continue
        if line.startswith(_INDEX_DIRECTIVES):
            directive = line.split(maxsplit=1)[0].split("=", 1)[0]
            code = "prohibited_source_directive" if directive == "--trusted-host" else "dependency_source_directive"
            findings.append(InventoryFinding(code, safe, line_number))
            continue
        if line.startswith("--"):
            findings.append(InventoryFinding("unsupported_dependency_directive", safe, line_number))
            continue
        editable = False
        value = line
        editable_match = re.match(r"^(?:-e|--editable)(?:\s+|=)(.+)$", line)
        if editable_match:
            editable = True
            value = editable_match.group(1)
        record, record_findings = _parse_requirement_value(
            value,
            source_file=safe,
            source_line=line_number,
            editable=editable,
        )
        if record:
            records.append(record)
        findings.extend(record_findings)
    return records, findings, files


def _parse_pyproject(repo_root: Path, relative: str) -> tuple[list[RequirementRecord], list[InventoryFinding]]:
    if tomllib is None:
        return [], [InventoryFinding("unsupported_dependency_file", relative, None)]
    try:
        payload = tomllib.loads((repo_root / relative).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise InventoryError("pyproject.toml is not readable TOML") from exc
    values: list[str] = []
    project = payload.get("project", {})
    if isinstance(project, dict):
        dependencies = project.get("dependencies", [])
        if isinstance(dependencies, list):
            values.extend(value for value in dependencies if isinstance(value, str))
        optional = project.get("optional-dependencies", {})
        if isinstance(optional, dict):
            for group in sorted(optional):
                group_values = optional[group]
                if isinstance(group_values, list):
                    values.extend(value for value in group_values if isinstance(value, str))
    records: list[RequirementRecord] = []
    findings: list[InventoryFinding] = []
    for index, value in enumerate(values, start=1):
        record, item_findings = _parse_requirement_value(
            value, source_file=relative, source_line=index
        )
        if record:
            records.append(record)
        findings.extend(item_findings)
    return records, findings


def _parse_setup_cfg(repo_root: Path, relative: str) -> tuple[list[RequirementRecord], list[InventoryFinding]]:
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read(repo_root / relative, encoding="utf-8")
    except (OSError, configparser.Error) as exc:
        raise InventoryError("setup.cfg is not readable configuration") from exc
    values: list[str] = []
    if parser.has_option("options", "install_requires"):
        values.extend(parser.get("options", "install_requires").splitlines())
    for section in sorted(section for section in parser.sections() if section == "options.extras_require"):
        for key in sorted(parser[section]):
            values.extend(parser[section][key].splitlines())
    records: list[RequirementRecord] = []
    findings: list[InventoryFinding] = []
    for index, value in enumerate(values, start=1):
        if not value.strip():
            continue
        record, item_findings = _parse_requirement_value(
            value, source_file=relative, source_line=index
        )
        if record:
            records.append(record)
        findings.extend(item_findings)
    return records, findings


def _exact_pin(record: RequirementRecord) -> str | None:
    match = _EXACT_PIN_RE.fullmatch(record.constraint)
    return match.group(1) if match else None


def build_inventory(
    repo_root: Path,
    *,
    declared_files: Iterable[str] | None = None,
) -> dict[str, object]:
    root = repo_root.resolve()
    initial_files = tuple(sorted(set(declared_files or discover_declared_files(root))))
    records: list[RequirementRecord] = []
    findings: list[InventoryFinding] = []
    inspected_files: set[str] = set()
    visited: set[str] = set()

    for relative in initial_files:
        safe = _safe_relative_path(relative)
        if safe in inspected_files:
            continue
        if safe.endswith((".txt", ".in")):
            parsed, item_findings, child_files = _parse_requirements_file(
                root, safe, visited=visited
            )
            inspected_files.update(child_files)
        elif safe == "pyproject.toml":
            parsed, item_findings = _parse_pyproject(root, safe)
            inspected_files.add(safe)
        elif safe == "setup.cfg":
            parsed, item_findings = _parse_setup_cfg(root, safe)
            inspected_files.add(safe)
        else:
            parsed = []
            item_findings = [InventoryFinding("unsupported_dependency_file", safe, None)]
            inspected_files.add(safe)
        records.extend(parsed)
        findings.extend(item_findings)

    records.sort(
        key=lambda item: (
            item.canonical_name or "",
            item.source_file,
            item.source_line or 0,
            item.constraint,
        )
    )
    groups: dict[str, list[RequirementRecord]] = {}
    for record in records:
        if record.canonical_name:
            groups.setdefault(record.canonical_name, []).append(record)

    duplicates: list[dict[str, object]] = []
    conflicts: list[dict[str, object]] = []
    for package, group in sorted(groups.items()):
        if len(group) < 2:
            continue
        locations = [
            {"source_file": item.source_file, "source_line": item.source_line}
            for item in group
        ]
        duplicates.append(
            {"package": package, "declaration_count": len(group), "locations": locations}
        )
        pins = sorted({pin for item in group if (pin := _exact_pin(item)) is not None})
        constraints = sorted({item.constraint for item in group})
        if len(pins) > 1:
            conflicts.append(
                {"package": package, "kind": "incompatible_exact_pins", "locations": locations}
            )
        elif len(constraints) > 1:
            conflicts.append(
                {"package": package, "kind": "non_identical_constraints", "locations": locations}
            )

    unique_findings = sorted(
        {finding for finding in findings},
        key=lambda item: (item.code, item.source_file, item.source_line or 0, item.package or ""),
    )
    counts = {
        classification: sum(record.classification == classification for record in records)
        for classification in ("pinned", "bounded", "unbounded")
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "status": "REVIEW_REQUIRED" if unique_findings or conflicts or duplicates else "CLEAR",
        "content_free": True,
        "network_used": False,
        "installed_environment_inspected": False,
        "vulnerability_status": VULNERABILITY_STATUS,
        "declared_files": sorted(inspected_files),
        "summary": {
            "declaration_count": len(records),
            "package_count": len(groups),
            "pinned_count": counts["pinned"],
            "bounded_count": counts["bounded"],
            "unbounded_count": counts["unbounded"],
            "duplicate_group_count": len(duplicates),
            "conflict_group_count": len(conflicts),
            "finding_count": len(unique_findings),
        },
        "requirements": [record.as_dict() for record in records],
        "duplicates": duplicates,
        "conflicts": conflicts,
        "findings": [finding.as_dict() for finding in unique_findings],
        "conflict_detection_scope": "EXACT_PINS_AND_NON_IDENTICAL_DUPLICATE_DECLARATIONS",
        "claim_boundary": "DECLARED_DEPENDENCIES_ONLY_NO_VULNERABILITY_CHECK",
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Phase 12G Dependency Inventory",
        "",
        f"- Status: **{report['status']}**",
        f"- Vulnerability status: **{report['vulnerability_status']}**",
        "- Network used: no",
        "- Installed environment inspected: no",
        "- Scope: declared dependency files only",
        "",
        "This offline inventory does not claim that dependencies are vulnerability-free.",
        "",
        "## Summary",
        "",
        f"- Declarations: {summary['declaration_count']}",
        f"- Packages: {summary['package_count']}",
        f"- Pinned / bounded / unbounded: {summary['pinned_count']} / {summary['bounded_count']} / {summary['unbounded_count']}",
        f"- Duplicate groups: {summary['duplicate_group_count']}",
        f"- Conflict groups: {summary['conflict_group_count']}",
        "",
        "## Declared Requirements",
        "",
        "| Package | Constraint | Class | Source type | Declared at |",
        "|---|---|---|---|---|",
    ]
    for item in report["requirements"]:
        package = item["canonical_name"] or "<unnamed>"
        line = item["source_line"] if item["source_line"] is not None else "-"
        lines.append(
            f"| `{package}` | `{item['constraint']}` | {item['classification']} | {item['source_type']} | `{item['source_file']}:{line}` |"
        )
    lines.extend(["", "## Findings", ""])
    if not report["findings"] and not report["conflicts"]:
        lines.append("None from the mechanically implemented source and duplication checks.")
    else:
        for finding in report["findings"]:
            line = finding["source_line"] if finding["source_line"] is not None else "-"
            lines.append(
                f"- `{finding['code']}` at `{finding['source_file']}:{line}` (package: `{finding['package'] or '<unnamed>'}`)"
            )
        for conflict in report["conflicts"]:
            lines.append(f"- `{conflict['kind']}` for `{conflict['package']}`")
    lines.append("")
    return "\n".join(lines)


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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        report = build_inventory(arguments.repo_root)
    except InventoryError:
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())