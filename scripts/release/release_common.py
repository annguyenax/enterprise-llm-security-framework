"""Shared fail-closed primitives for the Phase 12G release tooling.

No function here parses a benchmark record or ``result.json``, and none prints
file content. Errors are content-free and carry a stable machine-readable code.

Control-file coverage rule (explicit, enforced by builder and verifier):

* ``release-manifest.json.files`` lists exactly the payload entries (``repo/*``).
* ``FILE_SIZES.json.files`` lists every archive entry EXCEPT ``FILE_SIZES.json``
  and ``SHA256SUMS.txt`` (i.e. payload + manifest).
* ``SHA256SUMS.txt`` lists every archive entry EXCEPT ``SHA256SUMS.txt`` itself
  (i.e. payload + manifest + FILE_SIZES.json).
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

CHUNK = 65536
HEX64 = frozenset("0123456789abcdef")
MAX_FILE_BYTES = 64 * 1024 * 1024  # per-file snapshot ceiling

# Deterministic ZIP entry metadata.
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
ZIP_CREATE_SYSTEM = 3  # unix
ZIP_EXTERNAL_ATTR = (0o100644 & 0xFFFF) << 16

MANIFEST_NAME = "release-manifest.json"
CHECKSUMS_NAME = "SHA256SUMS.txt"
SIZES_NAME = "FILE_SIZES.json"
CONTROL_FILES = (MANIFEST_NAME, CHECKSUMS_NAME, SIZES_NAME)
PAYLOAD_PREFIX = "repo/"
POLICY_RELPATH = "release/release-allowlist.json"
POLICY_SCHEMA_VERSION = 2

_ALLOWED_POLICY_KEYS = frozenset(
    {"schema_version", "policy_id", "fail_closed", "source_of_truth",
     "prohibited", "required_present", "optional_generated"}
)
_ALLOWED_PROHIBITED_KEYS = frozenset({"extensions", "exact_names", "env", "path_components"})
_ALLOWED_ENV_KEYS = frozenset({"prohibit_dotenv", "allow_exceptions"})


class ReleaseError(Exception):
    """Fail-closed error with a stable machine-readable ``code``."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ReleasePolicy:
    schema_version: int
    policy_id: str
    prohibited_extensions: frozenset[str]
    prohibited_exact_names: frozenset[str]
    env_allow_exceptions: frozenset[str]
    prohibited_path_components: frozenset[str]
    required_present: tuple[str, ...]
    sha256: str


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_hex64(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value.lower()) <= HEX64


def is_hex40(value: object) -> bool:
    return isinstance(value, str) and len(value) == 40 and set(value.lower()) <= HEX64


def is_symlink_or_reparse(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
    except OSError:
        return True
    try:
        attrs = os.lstat(path).st_file_attributes  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        return False
    return bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def read_snapshot_bytes(path: Path) -> bytes:
    """Read a file ONCE into memory (with a size ceiling). The returned bytes are
    the single snapshot that must be both hashed and written to the ZIP."""
    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        raise ReleaseError("file_too_large", f"tracked file exceeds the snapshot ceiling: {path.name}")
    data = path.read_bytes()
    if len(data) != size:
        # Size changed between stat and read -> concurrent mutation, fail closed.
        raise ReleaseError("source_changed", "tracked file changed while being snapshotted")
    return data


def _load_json_no_dupes(raw: str, label: str) -> Any:
    """Parse JSON rejecting duplicate object keys."""
    def _hook(pairs):
        seen: set[str] = set()
        for key, _ in pairs:
            if key in seen:
                raise ReleaseError("duplicate_json_key", f"{label} has a duplicate key: {key}")
            seen.add(key)
        return dict(pairs)
    try:
        return json.loads(raw, object_pairs_hook=_hook)
    except json.JSONDecodeError as exc:
        raise ReleaseError("malformed_json", f"{label} is not valid JSON") from exc


def _str_set(value: Any, label: str) -> frozenset[str]:
    if not isinstance(value, list) or not all(isinstance(x, str) and x for x in value):
        raise ReleaseError("policy_schema", f"{label} must be a list of non-empty strings")
    lowered = [x.casefold() for x in value]
    if len(set(lowered)) != len(lowered):
        raise ReleaseError("policy_conflict", f"{label} has duplicate entries")
    return frozenset(lowered)


def parse_release_policy(raw: bytes) -> ReleasePolicy:
    """Validate the machine-consumable release policy. Fail closed on any defect."""
    policy = _load_json_no_dupes(raw.decode("utf-8"), "release policy")
    if not isinstance(policy, dict):
        raise ReleaseError("policy_schema", "release policy must be a JSON object")
    unknown = set(policy) - _ALLOWED_POLICY_KEYS
    if unknown:
        raise ReleaseError("policy_unknown_key", f"release policy has unknown keys: {sorted(unknown)}")
    if policy.get("schema_version") != POLICY_SCHEMA_VERSION:
        raise ReleaseError("policy_schema", f"policy schema_version must be {POLICY_SCHEMA_VERSION}")
    policy_id = policy.get("policy_id")
    if not isinstance(policy_id, str) or not policy_id:
        raise ReleaseError("policy_schema", "policy_id must be a non-empty string")
    if policy.get("fail_closed") is not True:
        raise ReleaseError("policy_schema", "policy fail_closed must be true")

    prohibited = policy.get("prohibited")
    if not isinstance(prohibited, dict):
        raise ReleaseError("policy_schema", "policy.prohibited must be an object")
    unknown_p = set(prohibited) - _ALLOWED_PROHIBITED_KEYS
    if unknown_p:
        raise ReleaseError("policy_unknown_key", f"prohibited has unknown keys: {sorted(unknown_p)}")
    for key in ("extensions", "exact_names", "path_components"):
        if key not in prohibited:
            raise ReleaseError("policy_missing", f"policy.prohibited is missing required class: {key}")
    extensions = _str_set(prohibited["extensions"], "prohibited.extensions")
    for ext in extensions:
        if not ext.startswith(".") or "*" in ext or "?" in ext or "/" in ext:
            raise ReleaseError("policy_pattern", f"unsupported extension pattern: {ext}")
    exact_names = _str_set(prohibited["exact_names"], "prohibited.exact_names")
    path_components = _str_set(prohibited["path_components"], "prohibited.path_components")
    for comp in path_components:
        if "*" in comp or "?" in comp or "/" in comp:
            raise ReleaseError("policy_pattern", f"unsupported path component pattern: {comp}")

    env = prohibited.get("env")
    if not isinstance(env, dict):
        raise ReleaseError("policy_schema", "policy.prohibited.env must be an object")
    if set(env) - _ALLOWED_ENV_KEYS:
        raise ReleaseError("policy_unknown_key", "prohibited.env has unknown keys")
    if env.get("prohibit_dotenv") is not True:
        raise ReleaseError("policy_schema", "prohibited.env.prohibit_dotenv must be true")
    env_allow = _str_set(env.get("allow_exceptions", []), "prohibited.env.allow_exceptions")

    # Conflict: an env allow-exception must not also be a prohibited exact name.
    if env_allow & exact_names:
        raise ReleaseError("policy_conflict", "an env allow-exception is also a prohibited exact name")

    required = policy.get("required_present")
    if not isinstance(required, list) or not all(isinstance(x, str) and x for x in required):
        raise ReleaseError("policy_schema", "required_present must be a list of non-empty strings")
    if len(set(required)) != len(required):
        raise ReleaseError("policy_conflict", "required_present has duplicate entries")

    optional = policy.get("optional_generated")
    if not isinstance(optional, dict) or optional.get("allowed") is not True:
        raise ReleaseError("policy_schema", "optional_generated.allowed must be true")

    return ReleasePolicy(
        schema_version=POLICY_SCHEMA_VERSION,
        policy_id=policy_id,
        prohibited_extensions=extensions,
        prohibited_exact_names=exact_names,
        env_allow_exceptions=env_allow,
        prohibited_path_components=path_components,
        required_present=tuple(required),
        sha256=sha256_bytes(raw),
    )


def classify_prohibited(relpath: str, policy: ReleasePolicy) -> str | None:
    """Return a prohibited-class name if ``relpath`` is disallowed by ``policy``."""
    pure = PurePosixPath(relpath)
    parts_cf = tuple(part.casefold() for part in pure.parts)
    name_cf = pure.name.casefold()
    suffix_cf = pure.suffix.casefold()
    for component in parts_cf:
        if component in policy.prohibited_path_components:
            return f"path_component:{component}"
    if suffix_cf in policy.prohibited_extensions:
        return f"extension:{suffix_cf}"
    if name_cf in policy.prohibited_exact_names:
        return f"name:{name_cf}"
    if name_cf == ".env" or name_cf.startswith(".env."):
        if name_cf not in policy.env_allow_exceptions:
            return "env_file"
    return None


def validate_relative_posix(relpath: str, *, label: str) -> str:
    if not isinstance(relpath, str) or not relpath.strip():
        raise ReleaseError("path_shape", f"{label} must be a non-empty string")
    if "\\" in relpath:
        raise ReleaseError("path_shape", f"{label} must use POSIX separators: {relpath!r}")
    pure = PurePosixPath(relpath)
    if pure.is_absolute() or pure.drive or pure.root:
        raise ReleaseError("path_absolute", f"{label} must be relative: {relpath!r}")
    if any(part in ("", ".", "..") for part in pure.parts):
        raise ReleaseError("path_traversal", f"{label} has an unsafe component: {relpath!r}")
    return pure.as_posix()


def assert_within(root: Path, candidate: Path, *, label: str) -> None:
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ReleaseError("path_escape", f"{label} escapes the repository root") from exc


def deterministic_zip_bytes(files: dict[str, bytes]) -> bytes:
    import io
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9, strict_timestamps=True) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = ZIP_CREATE_SYSTEM
            info.external_attr = ZIP_EXTERNAL_ATTR
            archive.writestr(info, files[name], compress_type=zipfile.ZIP_DEFLATED,
                             compresslevel=9)
    return buffer.getvalue()


def checksum_text(files: dict[str, bytes]) -> bytes:
    """Standard ``<sha256><two spaces><name>`` lines, sorted, LF-terminated."""
    return "".join(f"{sha256_bytes(files[name])}  {name}\n"
                   for name in sorted(files)).encode("ascii")


def parse_checksum_text(data: bytes) -> dict[str, str]:
    """Parse a standard SHA256SUMS body, enforcing exact two-space format."""
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ReleaseError("checksums_schema", "SHA256SUMS.txt is not ASCII") from exc
    result: dict[str, str] = {}
    for raw_line in text.splitlines():
        if raw_line == "":
            raise ReleaseError("checksums_format", "SHA256SUMS.txt has a blank line")
        if len(raw_line) < 67 or raw_line[64:66] != "  ":
            raise ReleaseError("checksums_format", "checksum line has non-standard spacing")
        digest, name = raw_line[:64], raw_line[66:]
        if not is_hex64(digest):
            raise ReleaseError("checksums_format", "checksum digest is not valid SHA-256")
        if not name or name.startswith(" "):
            raise ReleaseError("checksums_format", "checksum entry name is malformed")
        if name in result:
            raise ReleaseError("checksums_duplicate", f"duplicate checksum entry: {name}")
        result[name] = digest
    return result


def read_zip_entries(zip_path: Path) -> dict[str, bytes]:
    """Reopen a ZIP and return entry bytes, rejecting unsafe/duplicate paths.
    Does not extract to the filesystem."""
    with zipfile.ZipFile(zip_path, "r") as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise ReleaseError("zip_duplicate", "ZIP contains duplicate entries")
        result: dict[str, bytes] = {}
        for info in infos:
            name = info.filename
            pure = PurePosixPath(name)
            if name.startswith("/") or "\\" in name or pure.is_absolute() or ".." in pure.parts:
                raise ReleaseError("zip_unsafe_path", "ZIP contains an unsafe path")
            result[name] = archive.read(name)
        return result


def load_json_no_dupes(raw: bytes, label: str) -> Any:
    """Public wrapper: parse JSON bytes rejecting duplicate keys."""
    return _load_json_no_dupes(raw.decode("utf-8"), label)


def exclusive_write(path: Path, data: bytes) -> None:
    """Write bytes with exclusive create (atomic no-clobber). Fails if present."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
