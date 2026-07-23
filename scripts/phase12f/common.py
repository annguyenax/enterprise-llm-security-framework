"""Shared safety primitives for Phase 12F evidence tooling.

The helpers in this module deliberately operate on explicit allowlists and
logical root names. Persisted artifacts never contain source-machine paths.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import shutil
import stat
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping, Sequence


ALLOWLIST_SCHEMA_VERSION = 1
INVENTORY_SCHEMA_VERSION = 1
PACKET_SCHEMA_VERSION = 1
MAX_SAFE_JSON_BYTES = 16 * 1024 * 1024
INCOMPLETE_MARKER = ".phase12f-incomplete.json"

ARTIFACT_CLASSES = frozenset({"required", "optional", "prohibited"})
METADATA_PROFILES = frozenset(
    {
        "none",
        "closure_status",
        "closure_findings",
        "authorization",
        "receipt",
        "result_manifest",
        "analysis_manifest",
    }
)
SAFE_PACKET_CLASSES: Mapping[str, frozenset[str]] = {
    "aggregate_json": frozenset({".json"}),
    "aggregate_csv": frozenset({".csv"}),
    "aggregate_markdown": frozenset({".md"}),
    "safe_manifest_json": frozenset({".json"}),
    "checksum_text": frozenset({".txt"}),
}

_ROOT_NAME_RE = re.compile(r"[a-z][a-z0-9_]{0,63}")
_LOGICAL_ID_RE = re.compile(r"[a-z][a-z0-9_.-]{0,127}")
_GIT_SHA_RE = re.compile(r"[0-9a-f]{40}")
_HEX_SHA_RE = re.compile(r"[0-9a-f]{64}")
_FORBIDDEN_JSON_KEYS = frozenset(
    {
        "query",
        "raw_query",
        "prompt",
        "answer",
        "response",
        "context",
        "context_chunks",
        "retrieved_text",
        "raw_text",
        "secret",
        "secret_value",
        "password",
        "api_key",
        "access_token",
        "token",
        "private_key",
        "credentials",
        "cases",
        "records",
    }
)
_SENSITIVE_TEXT_MARKERS = (
    b"-----BEGIN PRIVATE KEY-----",
    b"-----BEGIN RSA PRIVATE KEY-----",
    b"AWS_SECRET_ACCESS_KEY=",
    b"OPENAI_API_KEY=",
    b"PASSWORD=",
    b"API_KEY=",
    b"SECRET=",
    b"TOKEN=",
)


class EvidenceToolError(Exception):
    """A deterministic, content-free validation error."""

    def __init__(self, category: str, message: str) -> None:
        super().__init__(message)
        self.category = category
        self.message = message

    def __str__(self) -> str:
        return f"{self.category}: {self.message}"


@dataclass(frozen=True)
class ArtifactRule:
    logical_id: str
    root: str
    path: str
    artifact_class: str
    metadata_profile: str
    packet_class: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "logical_id": self.logical_id,
            "root": self.root,
            "path": self.path,
            "class": self.artifact_class,
            "metadata_profile": self.metadata_profile,
            "packet_class": self.packet_class,
        }


@dataclass(frozen=True)
class Allowlist:
    candidate_sha: str
    rules: tuple[ArtifactRule, ...]
    sha256: str

    @property
    def root_names(self) -> tuple[str, ...]:
        return tuple(sorted({rule.root for rule in self.rules}))


def canonical_json_bytes(value: Any) -> bytes:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise EvidenceToolError("noncanonical_value", "value is not canonical JSON") from exc
    return (encoded + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _stable_stat_identity(details: os.stat_result) -> tuple[int, int, int, int]:
    return (
        details.st_dev,
        details.st_ino,
        details.st_size,
        details.st_mtime_ns,
    )


def fingerprint_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
        after = os.fstat(stream.fileno())
    current = path.stat()
    if (
        _stable_stat_identity(before) != _stable_stat_identity(after)
        or _stable_stat_identity(after) != _stable_stat_identity(current)
    ):
        raise EvidenceToolError(
            "source_changed",
            "source artifact changed while it was being fingerprinted",
        )
    return digest.hexdigest(), after.st_size


def sha256_file(path: Path) -> str:
    return fingerprint_file(path)[0]


def read_stable_bytes(path: Path, *, maximum_bytes: int | None = None) -> bytes:
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        if maximum_bytes is not None and before.st_size > maximum_bytes:
            raise EvidenceToolError(
                "resource_limit",
                "source artifact exceeds the configured byte limit",
            )
        data = stream.read()
        after = os.fstat(stream.fileno())
    current = path.stat()
    if (
        len(data) != after.st_size
        or _stable_stat_identity(before) != _stable_stat_identity(after)
        or _stable_stat_identity(after) != _stable_stat_identity(current)
    ):
        raise EvidenceToolError(
            "source_changed",
            "source artifact changed while it was being read",
        )
    return data


def _is_link_or_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        attributes = path.lstat().st_file_attributes
    except (AttributeError, FileNotFoundError, OSError):
        return False
    return bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _assert_no_link_components(path: Path, label: str) -> None:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        if not current.exists() and not current.is_symlink():
            continue
        if _is_link_or_reparse(current):
            raise EvidenceToolError("symlink_input", f"{label} traverses a link or reparse point")


def _validate_relative_path(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise EvidenceToolError("allowlist_schema", f"{location} must be a non-empty POSIX path")
    pure = PurePosixPath(value)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise EvidenceToolError("path_escape", f"{location} is not a contained relative path")
    return pure.as_posix()


def _exact_keys(value: Mapping[str, Any], expected: set[str], location: str) -> None:
    if set(value) != expected:
        raise EvidenceToolError("allowlist_schema", f"{location} has an unexpected key set")


def _read_json_object(path: Path, location: str) -> dict[str, Any]:
    if _is_link_or_reparse(path) or not path.is_file():
        raise EvidenceToolError("unsafe_input", f"{location} must be a regular non-link file")
    try:
        value = json.loads(
            read_stable_bytes(path, maximum_bytes=MAX_SAFE_JSON_BYTES).decode("utf-8")
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceToolError("invalid_json", f"{location} is not strict UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise EvidenceToolError("invalid_json", f"{location} must contain a JSON object")
    return value


def load_allowlist(path: Path) -> Allowlist:
    payload = _read_json_object(path, "allowlist")
    _exact_keys(payload, {"schema_version", "candidate_sha", "artifacts"}, "allowlist")
    if type(payload["schema_version"]) is not int or payload["schema_version"] != ALLOWLIST_SCHEMA_VERSION:
        raise EvidenceToolError("allowlist_schema", "allowlist schema_version must be integer 1")
    candidate = payload["candidate_sha"]
    if not isinstance(candidate, str) or not _GIT_SHA_RE.fullmatch(candidate):
        raise EvidenceToolError("allowlist_schema", "candidate_sha must be a lowercase 40-hex Git SHA")
    artifacts = payload["artifacts"]
    if not isinstance(artifacts, list) or not artifacts:
        raise EvidenceToolError("allowlist_schema", "artifacts must be a non-empty list")

    rules: list[ArtifactRule] = []
    logical_ids: set[str] = set()
    references: set[tuple[str, str]] = set()
    expected_rule_keys = {
        "logical_id",
        "root",
        "path",
        "class",
        "metadata_profile",
        "packet_class",
    }
    for index, item in enumerate(artifacts):
        location = f"artifacts[{index}]"
        if not isinstance(item, dict):
            raise EvidenceToolError("allowlist_schema", f"{location} must be an object")
        _exact_keys(item, expected_rule_keys, location)
        logical_id = item["logical_id"]
        root = item["root"]
        artifact_class = item["class"]
        profile = item["metadata_profile"]
        packet_class = item["packet_class"]
        if not isinstance(logical_id, str) or not _LOGICAL_ID_RE.fullmatch(logical_id):
            raise EvidenceToolError("allowlist_schema", f"{location}.logical_id is invalid")
        if not isinstance(root, str) or not _ROOT_NAME_RE.fullmatch(root):
            raise EvidenceToolError("allowlist_schema", f"{location}.root is invalid")
        relative = _validate_relative_path(item["path"], f"{location}.path")
        if not isinstance(artifact_class, str) or artifact_class not in ARTIFACT_CLASSES:
            raise EvidenceToolError("allowlist_schema", f"{location}.class is invalid")
        if not isinstance(profile, str) or profile not in METADATA_PROFILES:
            raise EvidenceToolError("allowlist_schema", f"{location}.metadata_profile is invalid")
        if packet_class is not None and (
            not isinstance(packet_class, str) or packet_class not in SAFE_PACKET_CLASSES
        ):
            raise EvidenceToolError("allowlist_schema", f"{location}.packet_class is invalid")
        if artifact_class == "prohibited" and (profile != "none" or packet_class is not None):
            raise EvidenceToolError(
                "allowlist_schema",
                "prohibited artifacts cannot carry parse or packet classes",
            )
        if logical_id in logical_ids:
            raise EvidenceToolError("duplicate_logical_artifact", f"duplicate logical_id {logical_id}")
        reference = (root, relative.casefold() if os.name == "nt" else relative)
        if reference in references:
            raise EvidenceToolError(
                "duplicate_logical_artifact",
                "two rules reference the same artifact",
            )
        logical_ids.add(logical_id)
        references.add(reference)
        rules.append(ArtifactRule(logical_id, root, relative, artifact_class, profile, packet_class))
    normalized = {
        "schema_version": ALLOWLIST_SCHEMA_VERSION,
        "candidate_sha": candidate,
        "artifacts": [
            rule.as_dict()
            for rule in sorted(rules, key=lambda item: item.logical_id)
        ],
    }
    return Allowlist(
        candidate,
        tuple(rules),
        sha256_bytes(canonical_json_bytes(normalized)),
    )


def parse_root_arguments(values: Sequence[str]) -> dict[str, Path]:
    roots: dict[str, Path] = {}
    for value in values:
        if not isinstance(value, str) or "=" not in value:
            raise EvidenceToolError("root_argument", "each root must use NAME=PATH")
        name, raw_path = value.split("=", 1)
        if not _ROOT_NAME_RE.fullmatch(name) or not raw_path:
            raise EvidenceToolError("root_argument", "root name or path is invalid")
        if name in roots:
            raise EvidenceToolError("root_argument", f"duplicate root name {name}")
        roots[name] = Path(raw_path)
    return roots


def normalize_roots(roots: Mapping[str, Path], expected_names: Sequence[str]) -> dict[str, Path]:
    if set(roots) != set(expected_names):
        raise EvidenceToolError("root_identity", "provided root names do not match the allowlist")
    normalized: dict[str, Path] = {}
    physical: set[tuple[int, int]] = set()
    for name in sorted(roots):
        path = Path(roots[name]).absolute()
        _assert_no_link_components(path, f"root {name}")
        if not path.is_dir() or _is_link_or_reparse(path):
            raise EvidenceToolError("unsafe_root", f"root {name} must be a regular directory")
        resolved = path.resolve(strict=True)
        details = resolved.stat()
        identity = (details.st_dev, details.st_ino)
        if identity in physical:
            raise EvidenceToolError("duplicate_root", "two logical roots reference the same directory")
        physical.add(identity)
        normalized[name] = resolved
    return normalized


def resolve_artifact(root: Path, relative: str, logical_id: str) -> Path:
    relative = _validate_relative_path(relative, logical_id)
    candidate = root.joinpath(*PurePosixPath(relative).parts)
    _assert_no_link_components(candidate, logical_id)
    nearest_parent = candidate.parent
    while not nearest_parent.exists():
        if nearest_parent == nearest_parent.parent:
            raise EvidenceToolError(
                "path_escape",
                f"{logical_id} has no contained existing parent",
            )
        nearest_parent = nearest_parent.parent
    resolved_parent = nearest_parent.resolve(strict=True)
    try:
        resolved_parent.relative_to(root)
    except ValueError as exc:
        raise EvidenceToolError("path_escape", f"{logical_id} escapes its root") from exc
    if candidate.exists() and _is_link_or_reparse(candidate):
        raise EvidenceToolError("symlink_input", f"{logical_id} is a link or reparse point")
    return candidate


def scan_root_files(root: Path, root_name: str) -> dict[str, Path]:
    files: dict[str, Path] = {}
    stack = [root]
    while stack:
        directory = stack.pop()
        with os.scandir(directory) as entries:
            ordered = sorted(entries, key=lambda item: item.name.casefold())
        for entry in ordered:
            path = Path(entry.path)
            relative = path.relative_to(root).as_posix()
            if _is_link_or_reparse(path):
                raise EvidenceToolError("symlink_input", f"root {root_name} contains a link")
            if entry.is_dir(follow_symlinks=False):
                stack.append(path)
            elif entry.is_file(follow_symlinks=False):
                key = relative.casefold() if os.name == "nt" else relative
                if key in files:
                    raise EvidenceToolError(
                        "duplicate_logical_artifact",
                        f"root {root_name} has duplicate paths",
                    )
                files[key] = path
            else:
                raise EvidenceToolError(
                    "unsafe_input",
                    f"root {root_name} contains a special filesystem entry",
                )
    return files


def physical_file_identity(path: Path) -> tuple[int, int]:
    details = path.stat()
    return details.st_dev, details.st_ino


def extract_safe_metadata(path: Path, profile: str) -> dict[str, Any]:
    if profile == "none":
        return {}
    if path.name.casefold() == "result.json" or path.suffix.casefold() == ".jsonl":
        raise EvidenceToolError(
            "forbidden_parse",
            "record-level artifacts cannot use metadata profiles",
        )
    payload = _read_json_object(path, profile)

    field_maps: Mapping[str, tuple[tuple[str, str, type], ...]] = {
        "closure_status": (
            ("candidate_sha", "candidate_sha", str),
            ("state", "state", str),
        ),
        "closure_findings": (
            ("candidate_sha", "candidate_sha", str),
            ("closure_gate", "closure_gate", str),
        ),
        "authorization": (
            ("execution_commit", "candidate_sha", str),
            ("authorization_id", "authorization_id", str),
            ("attempt", "attempt", int),
            ("provider_id", "provider_id", str),
            ("benchmark_manifest_sha256", "benchmark_manifest_sha256", str),
            ("holdout_authorized", "holdout_authorized", bool),
        ),
        "receipt": (
            ("execution_commit", "candidate_sha", str),
            ("authorization_id", "authorization_id", str),
            ("attempt", "attempt", int),
            ("provider_id", "provider_id", str),
            ("status", "receipt_status", str),
        ),
        "result_manifest": (
            ("git_commit", "candidate_sha", str),
            ("authorization_id", "authorization_id", str),
            ("attempt", "attempt", int),
            ("config_id", "config_id", str),
            ("run_status", "run_status", str),
            ("provider_id", "provider_id", str),
        ),
        "analysis_manifest": (
            ("analyzer_commit", "candidate_sha", str),
            ("authorization_id", "authorization_id", str),
            ("attempt", "attempt", int),
            ("split", "split", str),
        ),
    }
    metadata: dict[str, Any] = {"profile": profile}
    for source, target, expected_type in field_maps[profile]:
        if source not in payload:
            raise EvidenceToolError("metadata_schema", f"{profile} is missing {source}")
        value = payload[source]
        if expected_type is int:
            valid = type(value) is int
        elif expected_type is bool:
            valid = type(value) is bool
        else:
            valid = isinstance(value, expected_type)
        if not valid:
            raise EvidenceToolError(
                "metadata_schema",
                f"{profile}.{source} has the wrong type",
            )
        metadata[target] = value
    if "candidate_sha" in metadata and not _GIT_SHA_RE.fullmatch(metadata["candidate_sha"]):
        raise EvidenceToolError(
            "metadata_schema",
            f"{profile} candidate identity is malformed",
        )
    if "benchmark_manifest_sha256" in metadata and not _HEX_SHA_RE.fullmatch(
        metadata["benchmark_manifest_sha256"]
    ):
        raise EvidenceToolError(
            "metadata_schema",
            "benchmark manifest identity is malformed",
        )
    return metadata


def classify_packet_exclusion(relative: str) -> str | None:
    pure = PurePosixPath(relative)
    parts = tuple(part.casefold() for part in pure.parts)
    name = parts[-1]
    suffix = PurePosixPath(name).suffix.casefold()
    if ".git" in parts:
        return "git_data"
    if name == "result.json":
        return "result_record"
    if suffix == ".jsonl":
        return "benchmark_jsonl"
    if name == ".env" or name.startswith(".env."):
        return "environment_file"
    if suffix in {".db", ".sqlite", ".sqlite3"}:
        return "database"
    if suffix in {".pem", ".key", ".p12", ".pfx"} or name in {
        "credentials.json",
        "credential.json",
        "secrets.json",
        "id_rsa",
        "id_ed25519",
    }:
        return "credential"
    return None


def _walk_json_keys(value: Any) -> list[str]:
    keys: list[str] = []
    stack = [value]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            for key, child in current.items():
                if not isinstance(key, str):
                    raise EvidenceToolError("packet_content", "JSON keys must be strings")
                keys.append(key.casefold().strip().replace("-", "_"))
                stack.append(child)
        elif isinstance(current, list):
            stack.extend(current)
    return keys


def validate_packet_content(path: Path, packet_class: str, logical_id: str) -> bytes:
    if packet_class not in SAFE_PACKET_CLASSES:
        raise EvidenceToolError("packet_class", f"{logical_id} has no safe packet class")
    if classify_packet_exclusion(path.name) is not None:
        raise EvidenceToolError(
            "prohibited_packet_artifact",
            f"{logical_id} is a prohibited artifact class",
        )
    suffix = path.suffix.casefold()
    if suffix not in SAFE_PACKET_CLASSES[packet_class]:
        raise EvidenceToolError(
            "packet_class",
            f"{logical_id} has an incompatible extension",
        )
    data = read_stable_bytes(path)
    lowered_data = data.lower()
    if any(marker.lower() in lowered_data for marker in _SENSITIVE_TEXT_MARKERS):
        raise EvidenceToolError(
            "credential_content",
            f"{logical_id} contains a credential marker",
        )
    if packet_class in {"aggregate_json", "safe_manifest_json"}:
        try:
            value = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise EvidenceToolError(
                "packet_content",
                f"{logical_id} is not strict UTF-8 JSON",
            ) from exc
        forbidden = sorted(set(_walk_json_keys(value)) & _FORBIDDEN_JSON_KEYS)
        if forbidden:
            raise EvidenceToolError(
                "raw_field",
                f"{logical_id} contains a forbidden record field",
            )
    elif packet_class == "aggregate_csv":
        try:
            reader = csv.reader(io.StringIO(data.decode("utf-8-sig")))
            header = next(reader)
        except (UnicodeDecodeError, StopIteration, csv.Error) as exc:
            raise EvidenceToolError(
                "packet_content",
                f"{logical_id} is not a valid UTF-8 CSV",
            ) from exc
        normalized = {item.casefold().strip().replace("-", "_") for item in header}
        if normalized & _FORBIDDEN_JSON_KEYS:
            raise EvidenceToolError(
                "raw_field",
                f"{logical_id} contains a forbidden record column",
            )
    else:
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise EvidenceToolError(
                "packet_content",
                f"{logical_id} is not UTF-8 text",
            ) from exc
    return data


def ensure_output_outside_roots(output: Path, roots: Mapping[str, Path]) -> None:
    output_absolute = output.absolute()
    nearest = output_absolute
    while not nearest.exists():
        nearest = nearest.parent
    _assert_no_link_components(nearest, "output parent")
    resolved_output = output_absolute.resolve(strict=False)
    for root in roots.values():
        try:
            resolved_output.relative_to(root)
        except ValueError:
            continue
        raise EvidenceToolError(
            "output_containment",
            "output directory must be outside all source roots",
        )


def write_incomplete_marker(directory: Path, task: str) -> None:
    directory.mkdir(parents=True, exist_ok=False)
    marker = {"schema_version": 1, "task": task, "state": "INCOMPLETE"}
    (directory / INCOMPLETE_MARKER).write_bytes(canonical_json_bytes(marker))


def publish_directory_atomically(
    output: Path,
    task: str,
    populate: Callable[[Path], None],
    *,
    allow_recognized_incomplete: bool,
    refuse_existing: bool = False,
) -> None:
    output = output.absolute()
    output.parent.mkdir(parents=True, exist_ok=True)
    _assert_no_link_components(output.parent, "output parent")
    if output.exists() or output.is_symlink():
        if _is_link_or_reparse(output) or not output.is_dir():
            raise EvidenceToolError(
                "output_reuse",
                "output path is not a reusable directory",
            )
        entries = list(output.iterdir())
        if refuse_existing:
            raise EvidenceToolError(
                "output_reuse",
                "packet output directory already exists",
            )
        if not entries:
            output.rmdir()
        elif (
            allow_recognized_incomplete
            and [item.name for item in entries] == [INCOMPLETE_MARKER]
        ):
            marker = _read_json_object(entries[0], "incomplete marker")
            expected = {"schema_version": 1, "task": task, "state": "INCOMPLETE"}
            if marker != expected:
                raise EvidenceToolError(
                    "output_reuse",
                    "output contains an unrecognized incomplete marker",
                )
            entries[0].unlink()
            output.rmdir()
        else:
            raise EvidenceToolError(
                "output_reuse",
                "output directory is non-empty",
            )

    staging = output.with_name(
        f".{output.name}.{task}.{uuid.uuid4().hex}.staging"
    )
    staging.mkdir(parents=False, exist_ok=False)
    try:
        populate(staging)
        if output.exists():
            raise EvidenceToolError(
                "output_race",
                "output directory appeared during publication",
            )
        os.replace(staging, output)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        raise


def write_file_atomically(
    path: Path,
    data: bytes,
    *,
    refuse_existing: bool = True,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if refuse_existing and (path.exists() or path.is_symlink()):
        raise EvidenceToolError("output_reuse", "output file already exists")
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
