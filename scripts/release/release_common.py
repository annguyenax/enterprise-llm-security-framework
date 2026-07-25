"""Shared fail-closed primitives for the Phase 12G release tooling.

No function here parses a benchmark record or ``result.json``, and none prints
file content. Errors are content-free and carry a stable machine-readable code.

The release policy (``release/release-allowlist.json``, schema 4) is a **true,
mechanically disjoint closed-world allowlist**. Every tracked path is classified
by counting the inclusion rules whose effective match set contains it:

* 0 permitted matches            -> ``unclassified_tracked_path``
* more than 1 permitted match    -> ``ambiguous_policy_classification``
* a permitted AND a prohibited   -> ``prohibited_policy_overlap``
* exactly 1 prohibited (0 perm.) -> ``tracked_path_prohibited``
* exactly 1 permitted match       -> include, recording the class + unique
                                     rule ID + matched rule form.

Overlap is never resolved by precedence, first-match, or most-specific selection.
The policy loader proves structural disjointness (no two rules can match the same
path) so the classifier never has to choose between two matches.

Archives are prohibited by default. An allowed archive's safety is decided from
the exact bound snapshot bytes (``io.BytesIO``) using one shared inspector with
explicit resource limits, applied identically by the builder and the verifier.

Control-file coverage rule (explicit, enforced by builder and verifier):

* ``release-manifest.json.files`` lists exactly the payload entries (``repo/*``).
* ``FILE_SIZES.json.files`` lists payload + manifest.
* ``SHA256SUMS.txt`` lists payload + manifest + FILE_SIZES.json.
"""
from __future__ import annotations

import hashlib
import io
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

# Outer release-ZIP resource bounds.
MAX_ZIP_ENTRIES = 20000
MAX_ZIP_TOTAL_UNCOMPRESSED = 512 * 1024 * 1024
MAX_CANDIDATE_ZIP_BYTES = 256 * 1024 * 1024  # compressed candidate ceiling (before any read)

# Allowed-archive inspection limits (shared by builder and verifier).
ARCHIVE_INSPECTION_VERSION = 1
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 10000
MAX_ENTRY_NAME_BYTES = 1024
MAX_TOTAL_NAME_BYTES = 2 * 1024 * 1024
MAX_ARCHIVE_DEPTH = 32
MAX_ARCHIVE_COMMENT_BYTES = 4096
SUPPORTED_COMPRESSION = frozenset({zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED})

# Deterministic ZIP entry metadata.
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
ZIP_CREATE_SYSTEM = 3  # unix
ZIP_EXTERNAL_ATTR = (0o100644 & 0xFFFF) << 16
# Canonical raw ZIP structure values (as produced by deterministic_zip_bytes).
ZIP_VERSION_NEEDED = 20
ZIP_VERSION_MADE_BY = (ZIP_CREATE_SYSTEM << 8) | 20  # 788
ZIP_FLAGS_CANONICAL = 0
ZIP_INTERNAL_ATTR_CANONICAL = 0
ZIP_DISK_CANONICAL = 0
_EOCD_SIG = b"PK\x05\x06"
_CD_SIG = b"PK\x01\x02"
_LH_SIG = b"PK\x03\x04"
_ZIP64_EOCD_LOCATOR_SIG = b"PK\x06\x07"
_ZIP64_EOCD_SIG = b"PK\x06\x06"
_ARCHIVE_EXTRA_DATA_SIG = b"PK\x06\x08"
_DIGITAL_SIGNATURE_SIG = b"PK\x05\x05"
# Canonical DOS timestamp derived from the deterministic ZIP_TIMESTAMP.
_ZY, _ZMO, _ZD, _ZH, _ZMI, _ZS = ZIP_TIMESTAMP
ZIP_DOS_TIME = (_ZH << 11) | (_ZMI << 5) | (_ZS // 2)
ZIP_DOS_DATE = ((_ZY - 1980) << 9) | (_ZMO << 5) | _ZD

MANIFEST_NAME = "release-manifest.json"
CHECKSUMS_NAME = "SHA256SUMS.txt"
SIZES_NAME = "FILE_SIZES.json"
CONTROL_FILES = (MANIFEST_NAME, CHECKSUMS_NAME, SIZES_NAME)
PAYLOAD_PREFIX = "repo/"
POLICY_RELPATH = "release/release-allowlist.json"
POLICY_SCHEMA_VERSION = 4
MANIFEST_SCHEMA_VERSION = 5
BUILDER_TOOL = "build_release_candidate"

# Closed-world classifications and rule forms.
CLASS_REQUIRED = "REQUIRED"
CLASS_ALLOWED = "ALLOWED"
CLASS_ALLOWED_ARCHIVE = "ALLOWED_ARCHIVE"
CLASS_GENERATED = "GENERATED"
INCLUSION_CLASSES = frozenset({CLASS_REQUIRED, CLASS_ALLOWED, CLASS_ALLOWED_ARCHIVE})
PAYLOAD_CLASSES = frozenset({CLASS_REQUIRED, CLASS_ALLOWED, CLASS_ALLOWED_ARCHIVE, CLASS_GENERATED})
FORM_EXACT_PATH = "exact_path"
FORM_EXTENSION = "extension"
FORM_EXACT_NAME = "exact_name"
FORM_ARCHIVE_PATH = "archive_path"
RULE_FORMS = frozenset({FORM_EXACT_PATH, FORM_EXTENSION, FORM_EXACT_NAME, FORM_ARCHIVE_PATH})
GENERATED_RULE_ID = "generated-allowlist"
SOURCE_VALUES = frozenset({"tracked", "generated"})

# Canonical manifest sub-object values (verifier checks these exactly).
CONTROL_COVERAGE_CANON = {
    "manifest_files": "payload entries only (repo/*)",
    "sizes_covers": "payload + manifest (excludes SHA256SUMS.txt and FILE_SIZES.json)",
    "checksums_covers": "payload + manifest + FILE_SIZES.json (excludes SHA256SUMS.txt)",
}
ZIP_POLICY_CANON = {
    "entry_order": "lexical",
    "timestamp": "1980-01-01T00:00:00",
    "permissions": "0644",
    "compression": "deflate-9",
}

# Exact manifest schema key sets (schema 4).
MANIFEST_TOP_KEYS = frozenset(
    {"schema_version", "builder", "repository", "policy", "generated", "counts",
     "control_coverage", "content_controls", "zip_policy", "files"}
)
GENERATED_MANIFEST_KEYS = frozenset({"count", "allowlist_sha256"})
GENERATED_DECL_TOP_KEYS = frozenset({"schema_version", "generated_files"})
GENERATED_DECL_ROW_KEYS = frozenset({"path", "sha256", "size_bytes"})
GENERATED_DECL_SCHEMA_VERSION = 1
BUILDER_KEYS = frozenset({"tool", "manifest_schema_version", "archive_inspection_version"})
REPO_KEYS = frozenset({"head", "branch", "base_sha"})
POLICY_ID_KEYS = frozenset({"policy_id", "schema_version", "sha256"})
COUNTS_KEYS = frozenset({"file_count", "tracked_count", "generated_count",
                         "payload_count", "control_count", "entry_count"})
COVERAGE_KEYS = frozenset(CONTROL_COVERAGE_CANON)
CONTENT_CONTROL_KEYS = frozenset(
    {"jsonl_included", "result_json_included", "credentials_included",
     "databases_included", "git_metadata_included", "venv_included", "built_from"}
)
ZIP_POLICY_KEYS = frozenset(ZIP_POLICY_CANON)
FILE_ENTRY_KEYS = frozenset(
    {"archive_path", "path", "sha256", "size_bytes", "source",
     "classification", "rule_id", "rule_form", "archive_inspection"}
)
ARCHIVE_INSPECTION_KEYS = frozenset(
    {"format", "entry_count", "total_name_bytes", "max_name_bytes", "max_depth",
     "comment_length", "payload_sha256", "payload_size", "rule_id", "limits_version", "result"}
)
SIZES_TOP_KEYS = frozenset({"schema_version", "files"})

# Policy schema (schema 4) key sets.
_POLICY_TOP_KEYS = frozenset(
    {"schema_version", "policy_id", "fail_closed", "closed_world", "disjoint",
     "source_of_truth", "archive_inspection_version", "inclusion_rules",
     "prohibited", "optional_generated"}
)
_RULE_KEYS = frozenset({"rule_id", "class", "form", "value", "exclude_exact_paths"})
_PROHIBITED_KEYS = frozenset({"extensions", "exact_names", "env", "path_components", "archive_extensions"})
_ENV_KEYS = frozenset({"prohibit_dotenv", "allow_exceptions"})
_OPTIONAL_GENERATED_KEYS = frozenset({"allowed", "note"})

_CONTROL_CHARS = frozenset(chr(c) for c in range(32)) | {chr(127)}
_RESERVED_DEVICE_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)


class ReleaseError(Exception):
    """Fail-closed error with a stable machine-readable ``code``."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class VerificationError(ReleaseError):
    """A controlled verifier failure (subclass so ``except ReleaseError`` covers it)."""


@dataclass(frozen=True)
class InclusionRule:
    rule_id: str
    klass: str
    form: str
    value: str  # normalized (exact_path/archive_path: posix; extension/exact_name: casefolded)
    exclude_exact_paths: frozenset[str]


@dataclass(frozen=True)
class Classification:
    classification: str
    rule_id: str
    rule_form: str


@dataclass(frozen=True)
class TrustedPolicySnapshot:
    """An immutable trusted policy: exact bytes + SHA-256 + parsed semantics, bound
    together once. Consumed by both staged and published verification so no mutable
    pathname is reread between calls."""
    raw_bytes: bytes
    sha256: str
    parsed_policy: "ReleasePolicy"


@dataclass(frozen=True)
class TrustedGeneratedSnapshot:
    """An immutable trusted generated declaration: exact bytes + SHA-256 + parsed
    path->(sha256,size) mapping, bound together once."""
    raw_bytes: bytes
    sha256: str
    mapping: tuple[tuple[str, str, int], ...]  # (path, sha256, size_bytes), sorted

    def as_dict(self) -> dict[str, tuple[str, int]]:
        return {p: (s, z) for p, s, z in self.mapping}


@dataclass(frozen=True)
class ReleasePolicy:
    schema_version: int
    policy_id: str
    inclusion_rules: tuple[InclusionRule, ...]
    required_paths: frozenset[str]
    prohibited_extensions: frozenset[str]
    prohibited_exact_names: frozenset[str]
    prohibited_path_components: frozenset[str]
    prohibited_archive_extensions: frozenset[str]
    env_allow_exceptions: frozenset[str]
    archive_inspection_version: int
    sha256: str


# --------------------------------------------------------------------------- #
# Hash / type primitives
# --------------------------------------------------------------------------- #
def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def value_sha256(value: object) -> str:
    """Content-free digest of a candidate-controlled value for safe reporting.
    Never returns the raw value; used so findings can identify without leaking."""
    return hashlib.sha256(repr(value).encode("utf-8", "replace")).hexdigest()


def is_hex64(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value.lower()) <= HEX64


def is_hex40(value: object) -> bool:
    return isinstance(value, str) and len(value) == 40 and set(value.lower()) <= HEX64


def is_exact_int(value: object) -> bool:
    return type(value) is int  # rejects bool (bool subclasses int)


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
        raise ReleaseError("source_changed", "tracked file changed while being snapshotted")
    return data


# --------------------------------------------------------------------------- #
# Exact-schema validation helpers
# --------------------------------------------------------------------------- #
def require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise VerificationError("schema_type", f"{label} must be an object")
    return value


def require_exact_keys(obj: Any, keys: frozenset[str], label: str) -> dict[str, Any]:
    mapping = require_mapping(obj, label)
    present = set(mapping)
    missing = keys - present
    if missing:
        raise VerificationError("schema_missing_field", f"{label} is missing fields: {sorted(missing)}")
    extra = present - keys
    if extra:
        raise VerificationError("schema_unexpected_field", f"{label} has unexpected fields: {sorted(extra)}")
    return mapping


def require_string(obj: dict[str, Any], key: str, label: str) -> str:
    value = obj[key]
    if type(value) is not str or not value:
        raise VerificationError("schema_type", f"{label}.{key} must be a non-empty string")
    return value


def require_exact_string(obj: dict[str, Any], key: str, expected: str, label: str) -> str:
    value = require_string(obj, key, label)
    if value != expected:
        raise VerificationError("schema_value", f"{label}.{key} has a non-canonical value")
    return value


def require_sha256(obj: dict[str, Any], key: str, label: str) -> str:
    value = obj[key]
    if not is_hex64(value):
        raise VerificationError("schema_type", f"{label}.{key} must be a 64-hex SHA-256")
    return value.lower()


def require_non_negative_integer(obj: dict[str, Any], key: str, label: str) -> int:
    value = obj[key]
    if not is_exact_int(value) or value < 0:
        raise VerificationError("schema_type", f"{label}.{key} must be a non-negative integer (not bool)")
    return value


def require_exact_int_value(obj: dict[str, Any], key: str, expected: int, label: str) -> int:
    value = obj[key]
    if not is_exact_int(value) or value != expected:
        raise VerificationError("schema_value", f"{label}.{key} must be exactly {expected}")
    return value


def require_boolean(obj: dict[str, Any], key: str, label: str) -> bool:
    value = obj[key]
    if type(value) is not bool:
        raise VerificationError("schema_type", f"{label}.{key} must be a boolean")
    return value


def require_list(obj: dict[str, Any], key: str, label: str) -> list[Any]:
    value = obj[key]
    if not isinstance(value, list):
        raise VerificationError("schema_type", f"{label}.{key} must be a list")
    return value


def require_normalized_relative_path(value: Any, label: str) -> str:
    return validate_relative_posix(value, label=label)


# --------------------------------------------------------------------------- #
# JSON parsing (duplicate-key rejecting, controlled UTF-8/JSON errors)
# --------------------------------------------------------------------------- #
def _load_json_no_dupes(raw: str, label: str) -> Any:
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


def load_json_no_dupes(raw: bytes, label: str) -> Any:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ReleaseError("malformed_utf8", f"{label} is not valid UTF-8") from exc
    return _load_json_no_dupes(text, label)


def parse_generated_declaration(raw: bytes) -> tuple[dict[str, tuple[str, int]], str]:
    """Strictly parse an EXTERNAL trusted generated-file declaration. Returns a
    mapping ``path -> (sha256, size_bytes)`` and the SHA-256 of the exact declared
    bytes. Duplicate-key-rejecting; exact schema; safe normalized paths; no
    Boolean sizes; no duplicate/case-colliding/control-name paths. Fail closed."""
    obj = load_json_no_dupes(raw, "generated declaration")  # ReleaseError on UTF-8/JSON/dupes
    if not isinstance(obj, dict) or set(obj) != GENERATED_DECL_TOP_KEYS:
        raise ReleaseError("generated_declaration", "declaration must have exactly schema_version/generated_files")
    if not is_exact_int(obj["schema_version"]) or obj["schema_version"] != GENERATED_DECL_SCHEMA_VERSION:
        raise ReleaseError("generated_declaration", f"declaration schema_version must be {GENERATED_DECL_SCHEMA_VERSION}")
    rows = obj["generated_files"]
    if not isinstance(rows, list):
        raise ReleaseError("generated_declaration", "generated_files must be a list")
    mapping: dict[str, tuple[str, int]] = {}
    folded: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != GENERATED_DECL_ROW_KEYS:
            raise ReleaseError("generated_declaration", "each declaration row needs exactly path/sha256/size_bytes")
        rel = validate_relative_posix(row["path"], label="generated declaration path")
        if rel in (MANIFEST_NAME, CHECKSUMS_NAME, SIZES_NAME):
            raise ReleaseError("generated_declaration", "declaration path collides with a control name")
        sha = row["sha256"]
        if not is_hex64(sha):
            raise ReleaseError("generated_declaration", "declaration sha256 must be 64 hex")
        size = row["size_bytes"]
        if not is_exact_int(size) or size < 0:
            raise ReleaseError("generated_declaration", "declaration size_bytes must be a non-negative integer")
        if rel in mapping:
            raise ReleaseError("generated_declaration", "duplicate declaration path")
        if rel.casefold() in folded:
            raise ReleaseError("generated_declaration", "case-colliding declaration path")
        folded.add(rel.casefold())
        mapping[rel] = (sha.lower(), size)
    return mapping, sha256_bytes(raw)


# --------------------------------------------------------------------------- #
# Immutable trust snapshots (read a trusted file ONCE; bind bytes+sha+semantics)
# --------------------------------------------------------------------------- #
def trusted_policy_snapshot_from_bytes(raw: bytes) -> TrustedPolicySnapshot:
    return TrustedPolicySnapshot(raw_bytes=raw, sha256=sha256_bytes(raw),
                                 parsed_policy=parse_release_policy(raw))


def trusted_generated_snapshot_from_bytes(raw: bytes) -> TrustedGeneratedSnapshot:
    mapping, sha = parse_generated_declaration(raw)
    ordered = tuple((p, s, z) for p, (s, z) in sorted(mapping.items()))
    return TrustedGeneratedSnapshot(raw_bytes=raw, sha256=sha, mapping=ordered)


def _read_trusted_bytes(path: object, code: str) -> bytes:
    p = Path(path).expanduser()
    if is_symlink_or_reparse(p) or not p.is_file():
        raise VerificationError(code, "external trusted file is missing")
    try:
        return p.read_bytes()
    except OSError as exc:
        raise VerificationError(code, "external trusted file unreadable") from exc


def load_trusted_policy_snapshot(path: object) -> TrustedPolicySnapshot:
    return trusted_policy_snapshot_from_bytes(_read_trusted_bytes(path, "trusted_policy_unreadable"))


def load_trusted_generated_snapshot(path: object) -> TrustedGeneratedSnapshot:
    return trusted_generated_snapshot_from_bytes(_read_trusted_bytes(path, "trusted_generated_unreadable"))


# --------------------------------------------------------------------------- #
# Path safety
# --------------------------------------------------------------------------- #
def validate_relative_posix(relpath: str, *, label: str) -> str:
    """THE authoritative cross-platform safe-relative-path validator. Shared by the
    policy parser, generated declaration, manifest, checksum/size parsers, outer
    ZIP entries and nested archive names. Rejects drive/colon/ADS/UNC/backslash,
    control chars, traversal, reserved device names, and whitespace-ambiguous
    components. Never uses only PurePosixPath.is_absolute()."""
    if not isinstance(relpath, str) or not relpath.strip():
        raise ReleaseError("path_shape", f"{label} must be a non-empty string")
    if "\\" in relpath:
        raise ReleaseError("path_backslash", f"{label} must use POSIX separators")
    if ":" in relpath:  # drive (C:) and NTFS alternate data stream (file:stream)
        raise ReleaseError("path_colon", f"{label} must not contain a colon")
    if any(ch in _CONTROL_CHARS for ch in relpath):
        raise ReleaseError("path_control_char", f"{label} contains control characters")
    if relpath.startswith("/"):
        raise ReleaseError("path_absolute", f"{label} must be relative")
    if relpath.endswith("/"):
        raise ReleaseError("path_shape", f"{label} must not be a directory entry")
    # Validate RAW segments directly (PurePosixPath collapses '.', '//' and leading
    # './', so parts alone is insufficient).
    segments = relpath.split("/")
    for seg in segments:
        if seg in ("", ".", ".."):
            raise ReleaseError("path_traversal", f"{label} has an empty/dot component")
        if seg != seg.strip() or seg.endswith(".") or seg.endswith(" "):
            raise ReleaseError("path_whitespace", f"{label} has an ambiguous component")
        base = seg.split(".", 1)[0].upper()
        if base in _RESERVED_DEVICE_NAMES:
            raise ReleaseError("path_reserved_name", f"{label} uses a reserved device name")
    pure = PurePosixPath(relpath)
    if pure.is_absolute() or pure.drive or pure.root:
        raise ReleaseError("path_absolute", f"{label} must be relative")
    if tuple(pure.parts) != tuple(segments):  # normalization would change the logical identity
        raise ReleaseError("path_noncanonical", f"{label} is not in canonical form")
    return pure.as_posix()


def assert_within(root: Path, candidate: Path, *, label: str) -> None:
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ReleaseError("path_escape", f"{label} escapes the repository root") from exc


# --------------------------------------------------------------------------- #
# Policy parsing (schema 4) + structural disjointness proof
# --------------------------------------------------------------------------- #
def _casefold_str_set(value: Any, label: str) -> frozenset[str]:
    if not isinstance(value, list) or not all(isinstance(x, str) and x for x in value):
        raise ReleaseError("policy_schema", f"{label} must be a list of non-empty strings")
    lowered = [x.casefold() for x in value]
    if len(set(lowered)) != len(lowered):
        raise ReleaseError("policy_conflict", f"{label} has case-colliding entries")
    return frozenset(lowered)


def _extension_set(value: Any, label: str) -> frozenset[str]:
    exts = _casefold_str_set(value, label)
    for ext in exts:
        if not ext.startswith(".") or len(ext) < 2 or "*" in ext or "?" in ext or "/" in ext or "\\" in ext:
            raise ReleaseError("policy_pattern", f"unsupported extension pattern in {label}: {ext}")
    return exts


def _component_set(value: Any, label: str) -> frozenset[str]:
    comps = _casefold_str_set(value, label)
    for comp in comps:
        if "*" in comp or "?" in comp or "/" in comp or "\\" in comp:
            raise ReleaseError("policy_pattern", f"unsupported path-component pattern in {label}: {comp}")
    return comps


def _validate_extension_token(value: str, label: str) -> str:
    v = value.casefold()
    if not v.startswith(".") or len(v) < 2 or "*" in v or "?" in v or "/" in v or "\\" in v:
        raise ReleaseError("policy_pattern", f"unsupported extension token in {label}: {value}")
    return v


def _parse_inclusion_rule(raw: Any) -> InclusionRule:
    obj = raw
    if not isinstance(obj, dict):
        raise ReleaseError("policy_schema", "each inclusion rule must be an object")
    unknown = set(obj) - _RULE_KEYS
    if unknown:
        raise ReleaseError("policy_unknown_key", f"inclusion rule has unknown keys: {sorted(unknown)}")
    for key in _RULE_KEYS:
        if key not in obj:
            raise ReleaseError("policy_missing", f"inclusion rule is missing key: {key}")
    rule_id = obj["rule_id"]
    if not isinstance(rule_id, str) or not rule_id.strip():
        raise ReleaseError("policy_schema", "rule_id must be a non-empty string")
    klass = obj["class"]
    if not isinstance(klass, str) or klass not in INCLUSION_CLASSES:
        raise ReleaseError("policy_schema", "invalid rule class")
    form = obj["form"]
    if not isinstance(form, str) or form not in RULE_FORMS:
        raise ReleaseError("policy_schema", "invalid rule form")
    value = obj["value"]
    if not isinstance(value, str) or not value:
        raise ReleaseError("policy_schema", "rule value must be a non-empty string")
    excl_raw = obj["exclude_exact_paths"]
    if not isinstance(excl_raw, list):
        raise ReleaseError("policy_schema", "exclude_exact_paths must be a list")
    exclusions = frozenset(validate_relative_posix(x, label="exclude_exact_paths") for x in excl_raw)

    # Class/form compatibility + value normalization.
    if form in (FORM_EXACT_PATH, FORM_ARCHIVE_PATH):
        value = validate_relative_posix(value, label="rule value")
        if form == FORM_EXACT_PATH and klass not in (CLASS_REQUIRED, CLASS_ALLOWED):
            raise ReleaseError("policy_schema", "exact_path rule must be REQUIRED or ALLOWED")
        if form == FORM_ARCHIVE_PATH and klass != CLASS_ALLOWED_ARCHIVE:
            raise ReleaseError("policy_schema", "archive_path rule must be ALLOWED_ARCHIVE")
        if exclusions:
            raise ReleaseError("policy_schema", "exact/archive path rules cannot have exclusions")
    elif form == FORM_EXTENSION:
        if klass != CLASS_ALLOWED:
            raise ReleaseError("policy_schema", "extension rule must be ALLOWED")
        value = _validate_extension_token(value, "rule value")
    elif form == FORM_EXACT_NAME:
        if klass != CLASS_ALLOWED:
            raise ReleaseError("policy_schema", "exact_name rule must be ALLOWED")
        if ("/" in value or "\\" in value or ":" in value or value in ("", ".", "..")
                or any(ch in _CONTROL_CHARS for ch in value)):
            raise ReleaseError("policy_schema", "exact_name value must be a bare filename")
        value = value.casefold()
    return InclusionRule(rule_id=rule_id, klass=klass, form=form, value=value,
                         exclude_exact_paths=exclusions)


def _rule_effective_matches(rule: InclusionRule, rel: str, name_cf: str, suffix_cf: str) -> bool:
    if rel in rule.exclude_exact_paths:
        return False
    if rule.form in (FORM_EXACT_PATH, FORM_ARCHIVE_PATH):
        return rel == rule.value
    if rule.form == FORM_EXTENSION:
        return suffix_cf == rule.value
    if rule.form == FORM_EXACT_NAME:
        return name_cf == rule.value
    return False


def _would_paths_overlap(a: InclusionRule, b: InclusionRule) -> bool:
    """Return True if there could exist any path matching BOTH rules a and b
    (ignoring exclusions on that path). Proves structural disjointness."""
    forms = {a.form, b.form}

    def _exact_value(r: InclusionRule) -> str:
        return r.value

    # Two exact/archive path rules overlap only if identical value.
    if a.form in (FORM_EXACT_PATH, FORM_ARCHIVE_PATH) and b.form in (FORM_EXACT_PATH, FORM_ARCHIVE_PATH):
        return a.value == b.value
    # Two extension rules overlap iff same extension.
    if a.form == FORM_EXTENSION and b.form == FORM_EXTENSION:
        return a.value == b.value
    # Two exact_name rules overlap iff same name.
    if a.form == FORM_EXACT_NAME and b.form == FORM_EXACT_NAME:
        return a.value == b.value
    # exact/archive path (value V) vs extension: overlap unless V excluded by that ext rule.
    if FORM_EXTENSION in forms and (FORM_EXACT_PATH in forms or FORM_ARCHIVE_PATH in forms):
        ext_rule = a if a.form == FORM_EXTENSION else b
        path_rule = b if a.form == FORM_EXTENSION else a
        v = path_rule.value
        return PurePosixPath(v).suffix.casefold() == ext_rule.value and v not in ext_rule.exclude_exact_paths
    # exact/archive path (value V) vs exact_name: overlap unless V excluded by that name rule.
    if FORM_EXACT_NAME in forms and (FORM_EXACT_PATH in forms or FORM_ARCHIVE_PATH in forms):
        name_rule = a if a.form == FORM_EXACT_NAME else b
        path_rule = b if a.form == FORM_EXACT_NAME else a
        v = path_rule.value
        return PurePosixPath(v).name.casefold() == name_rule.value and v not in name_rule.exclude_exact_paths
    # extension vs exact_name: overlap iff the name's suffix equals the extension.
    if FORM_EXTENSION in forms and FORM_EXACT_NAME in forms:
        ext_rule = a if a.form == FORM_EXTENSION else b
        name_rule = b if a.form == FORM_EXTENSION else a
        return PurePosixPath(name_rule.value).suffix.casefold() == ext_rule.value
    return False


def parse_release_policy(raw: bytes) -> ReleasePolicy:
    """Validate the disjoint closed-world release policy (schema 4). Fail closed."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ReleaseError("malformed_utf8", "release policy is not valid UTF-8") from exc
    policy = _load_json_no_dupes(text, "release policy")
    if not isinstance(policy, dict):
        raise ReleaseError("policy_schema", "release policy must be a JSON object")
    unknown = set(policy) - _POLICY_TOP_KEYS
    if unknown:
        raise ReleaseError("policy_unknown_key", f"release policy has unknown keys: {sorted(unknown)}")
    for key in _POLICY_TOP_KEYS:
        if key not in policy:
            raise ReleaseError("policy_missing", f"release policy is missing required key: {key}")
    if not is_exact_int(policy["schema_version"]) or policy["schema_version"] != POLICY_SCHEMA_VERSION:
        raise ReleaseError("policy_schema", f"policy schema_version must be exactly {POLICY_SCHEMA_VERSION}")
    policy_id = policy["policy_id"]
    if not isinstance(policy_id, str) or not policy_id:
        raise ReleaseError("policy_schema", "policy_id must be a non-empty string")
    if policy["fail_closed"] is not True:
        raise ReleaseError("policy_schema", "policy fail_closed must be true")
    if policy["closed_world"] is not True:
        raise ReleaseError("policy_schema", "policy closed_world must be true")
    if policy["disjoint"] is not True:
        raise ReleaseError("policy_schema", "policy disjoint must be true")
    if not isinstance(policy["source_of_truth"], str) or not policy["source_of_truth"]:
        raise ReleaseError("policy_schema", "policy source_of_truth must be a non-empty string")
    aiv = policy["archive_inspection_version"]
    if not is_exact_int(aiv) or aiv != ARCHIVE_INSPECTION_VERSION:
        raise ReleaseError("policy_schema", f"archive_inspection_version must be exactly {ARCHIVE_INSPECTION_VERSION}")

    rules_raw = policy["inclusion_rules"]
    if not isinstance(rules_raw, list) or not rules_raw:
        raise ReleaseError("policy_schema", "inclusion_rules must be a non-empty list")
    rules = tuple(_parse_inclusion_rule(r) for r in rules_raw)
    ids = [r.rule_id for r in rules]
    if len(ids) != len(set(ids)):
        raise ReleaseError("policy_conflict", "duplicate rule_id")
    if len({i.casefold() for i in ids}) != len(ids):
        raise ReleaseError("policy_conflict", "case-colliding rule_id")
    # Duplicate effective rule (same form+value+class).
    seen_fv: set[tuple[str, str, str]] = set()
    for r in rules:
        key = (r.form, r.value, r.klass)
        if key in seen_fv:
            raise ReleaseError("policy_conflict", "duplicate effective inclusion rule")
        seen_fv.add(key)
    # Structural disjointness: no two rules may match the same possible path.
    for i in range(len(rules)):
        for j in range(i + 1, len(rules)):
            if _would_paths_overlap(rules[i], rules[j]):
                raise ReleaseError("ambiguous_policy_classification",
                                   f"rules {rules[i].rule_id} and {rules[j].rule_id} can match the same path")

    # --- prohibited ---
    prohibited = policy["prohibited"]
    if not isinstance(prohibited, dict):
        raise ReleaseError("policy_schema", "policy.prohibited must be an object")
    unknown_p = set(prohibited) - _PROHIBITED_KEYS
    if unknown_p:
        raise ReleaseError("policy_unknown_key", f"prohibited has unknown keys: {sorted(unknown_p)}")
    for key in _PROHIBITED_KEYS:
        if key not in prohibited:
            raise ReleaseError("policy_missing", f"prohibited is missing required class: {key}")
    prohibited_extensions = _extension_set(prohibited["extensions"], "prohibited.extensions")
    prohibited_exact_names = _casefold_str_set(prohibited["exact_names"], "prohibited.exact_names")
    prohibited_path_components = _component_set(prohibited["path_components"], "prohibited.path_components")
    prohibited_archive_extensions = _extension_set(prohibited["archive_extensions"], "prohibited.archive_extensions")

    env = prohibited["env"]
    if not isinstance(env, dict):
        raise ReleaseError("policy_schema", "prohibited.env must be an object")
    if set(env) != _ENV_KEYS:
        raise ReleaseError("policy_schema", "prohibited.env must have exactly prohibit_dotenv/allow_exceptions")
    if env["prohibit_dotenv"] is not True:
        raise ReleaseError("policy_schema", "prohibited.env.prohibit_dotenv must be true")
    env_allow_exceptions = _casefold_str_set(env["allow_exceptions"], "prohibited.env.allow_exceptions")

    # --- optional_generated (exact keys) ---
    optional = policy["optional_generated"]
    if not isinstance(optional, dict) or set(optional) != _OPTIONAL_GENERATED_KEYS:
        raise ReleaseError("policy_schema", "optional_generated must have exactly allowed/note")
    if optional["allowed"] is not True:
        raise ReleaseError("policy_schema", "optional_generated.allowed must be true")
    if not isinstance(optional["note"], str) or not optional["note"]:
        raise ReleaseError("policy_schema", "optional_generated.note must be a non-empty string")

    # --- cross-class sanity ---
    if prohibited_extensions & prohibited_archive_extensions:
        raise ReleaseError("policy_conflict", "an extension is both a general and an archive prohibition")
    if env_allow_exceptions & prohibited_exact_names:
        raise ReleaseError("policy_conflict", "an env allow-exception is also a prohibited exact name")

    required_paths = frozenset(
        r.value for r in rules if r.form == FORM_EXACT_PATH and r.klass == CLASS_REQUIRED)

    partial = ReleasePolicy(
        schema_version=POLICY_SCHEMA_VERSION, policy_id=policy_id, inclusion_rules=rules,
        required_paths=required_paths, prohibited_extensions=prohibited_extensions,
        prohibited_exact_names=prohibited_exact_names, prohibited_path_components=prohibited_path_components,
        prohibited_archive_extensions=prohibited_archive_extensions,
        env_allow_exceptions=env_allow_exceptions, archive_inspection_version=aiv,
        sha256=sha256_bytes(raw),
    )

    # Every inclusion rule's own value must not be absolutely prohibited, and an
    # ALLOWED extension token must not be a prohibited (archive) extension.
    for r in rules:
        if r.form == FORM_EXTENSION and (r.value in prohibited_extensions or r.value in prohibited_archive_extensions):
            raise ReleaseError("ambiguous_policy_classification",
                               f"allowed extension {r.value} is also prohibited")
        if r.form in (FORM_EXACT_PATH, FORM_ARCHIVE_PATH):
            abs_hit = classify_prohibited_absolute(r.value, partial)
            if r.form == FORM_EXACT_PATH and abs_hit is not None:
                raise ReleaseError("prohibited_policy_overlap",
                                   f"required/allowed path {r.value} matches a prohibited rule")
            if r.form == FORM_ARCHIVE_PATH:
                suffix = PurePosixPath(r.value).suffix.casefold()
                if abs_hit is not None:
                    raise ReleaseError("prohibited_policy_overlap",
                                       f"allowed archive {r.value} matches a prohibited rule")
                if suffix not in prohibited_archive_extensions:
                    raise ReleaseError("policy_conflict",
                                       f"allowed archive lacks a recognised archive extension: {r.value}")
    return partial


# --------------------------------------------------------------------------- #
# Classification
# --------------------------------------------------------------------------- #
def classify_prohibited_absolute(relpath: str, policy: ReleasePolicy) -> str | None:
    """Absolute (non-archive) prohibitions: path components, extensions, exact
    names, and .env* files. Returns a content-free label or None."""
    pure = PurePosixPath(relpath)
    name_cf = pure.name.casefold()
    suffix_cf = pure.suffix.casefold()
    for component in (part.casefold() for part in pure.parts):
        if component in policy.prohibited_path_components:
            return f"path_component:{component}"
    if suffix_cf in policy.prohibited_extensions:
        return f"extension:{suffix_cf}"
    if name_cf in policy.prohibited_exact_names:
        return f"name:{name_cf}"
    if (name_cf == ".env" or name_cf.startswith(".env.")) and name_cf not in policy.env_allow_exceptions:
        return "env_file"
    return None


def classify_path(relpath: str, policy: ReleasePolicy) -> Classification:
    """Disjoint closed-world classification by COUNTING matches (no precedence).
    Raises a fail-closed ReleaseError with the R3 reason codes."""
    rel = validate_relative_posix(relpath, label="path")
    pure = PurePosixPath(rel)
    name_cf = pure.name.casefold()
    suffix_cf = pure.suffix.casefold()

    permitted = [r for r in policy.inclusion_rules
                 if _rule_effective_matches(r, rel, name_cf, suffix_cf)]
    absolute = classify_prohibited_absolute(rel, policy)
    archive_ext = suffix_cf in policy.prohibited_archive_extensions
    archive_allowlisted = any(r.form == FORM_ARCHIVE_PATH and r.value == rel for r in permitted)
    prohibited_hit = absolute is not None or (archive_ext and not archive_allowlisted)

    if prohibited_hit and permitted:
        raise ReleaseError("prohibited_policy_overlap", f"{rel} matches inclusion and prohibited rules")
    if prohibited_hit:
        raise ReleaseError("tracked_path_prohibited", f"{rel} is prohibited by policy")
    if len(permitted) == 0:
        raise ReleaseError("unclassified_tracked_path", f"{rel} matches no inclusion rule")
    if len(permitted) > 1:
        raise ReleaseError("ambiguous_policy_classification", f"{rel} matches multiple inclusion rules")
    rule = permitted[0]
    return Classification(rule.klass, rule.rule_id, rule.form)


def classification_summary(paths: list[str], policy: ReleasePolicy) -> dict[str, int]:
    """Content-free classification counts over a set of tracked paths."""
    summary = {"tracked": len(paths), "required": 0, "allowed": 0, "allowed_archive": 0,
               "prohibited": 0, "unclassified": 0, "ambiguous": 0, "overlap": 0}
    for rel in paths:
        try:
            result = classify_path(rel, policy)
        except ReleaseError as exc:
            if exc.code == "unclassified_tracked_path":
                summary["unclassified"] += 1
            elif exc.code == "ambiguous_policy_classification":
                summary["ambiguous"] += 1
            elif exc.code == "prohibited_policy_overlap":
                summary["overlap"] += 1
            elif exc.code == "tracked_path_prohibited":
                summary["prohibited"] += 1
            else:
                raise
            continue
        if result.classification == CLASS_REQUIRED:
            summary["required"] += 1
        elif result.classification == CLASS_ALLOWED:
            summary["allowed"] += 1
        elif result.classification == CLASS_ALLOWED_ARCHIVE:
            summary["allowed_archive"] += 1
    return summary


# --------------------------------------------------------------------------- #
# Shared allowed-archive inspection (snapshot-bound; builder + verifier)
# --------------------------------------------------------------------------- #
def _validate_archive_member_name(name: str) -> tuple[str, bool, int]:
    """Validate one nested entry name via THE authoritative cross-platform path
    validator (same contract as outer release paths). A single trailing slash is a
    directory entry; the remaining logical path is validated identically. Returns
    (normalized_logical_path, is_dir, depth). Never reads nested content."""
    if not isinstance(name, str) or not name:
        raise ReleaseError("archive_invalid_name", "archive entry name is empty")
    is_dir = name.endswith("/")
    stripped = name[:-1] if is_dir else name
    if not stripped or stripped.endswith("/"):
        raise ReleaseError("archive_invalid_name", "archive entry name has an empty component")
    try:
        norm = validate_relative_posix(stripped, label="archive entry")
    except ReleaseError as exc:  # map every path_* code to a single content-free archive code
        raise ReleaseError("archive_unsafe_name", "allowed archive has an unsafe nested name") from exc
    depth = len(PurePosixPath(norm).parts)
    if depth > MAX_ARCHIVE_DEPTH:
        raise ReleaseError("archive_depth", "archive entry name is too deep")
    return norm, is_dir, depth


def inspect_archive_bytes(data: bytes, policy: ReleasePolicy, *, rule_id: str,
                          payload_sha: str, payload_size: int) -> dict[str, Any]:
    """Inspect an allowed archive from its EXACT bound bytes (names/metadata only,
    never extracts, never reads nested content). Shared by builder and verifier;
    identical limits and reason codes. Returns content-free inspection metadata."""
    if len(data) > MAX_ARCHIVE_BYTES:
        raise ReleaseError("archive_too_large", "allowed archive exceeds the size limit")
    if len(data) != payload_size or sha256_bytes(data) != payload_sha:
        raise ReleaseError("archive_binding_mismatch", "archive bytes are not the bound payload bytes")
    try:
        with zipfile.ZipFile(io.BytesIO(data), "r") as archive:
            comment = archive.comment or b""
            if len(comment) > MAX_ARCHIVE_COMMENT_BYTES:
                raise ReleaseError("archive_comment_too_long", "allowed archive comment is too long")
            infos = archive.infolist()
            if len(infos) > MAX_ARCHIVE_ENTRIES:
                raise ReleaseError("archive_too_many_entries", "allowed archive has too many entries")
            names = [i.filename for i in infos]
            if len(names) != len(set(names)):
                raise ReleaseError("archive_duplicate_name", "allowed archive has duplicate nested names")
            if len({n.casefold() for n in names}) != len(names):
                raise ReleaseError("archive_case_collision", "allowed archive has case-colliding nested names")
            total_name = 0
            max_name = 0
            max_depth = 0
            file_logical: set[str] = set()
            dir_logical: set[str] = set()
            for info in infos:
                if info.flag_bits & 0x1:
                    raise ReleaseError("archive_encrypted", "allowed archive has an encrypted entry")
                if info.compress_type not in SUPPORTED_COMPRESSION:
                    raise ReleaseError("archive_unsupported_compression", "unsupported nested compression")
                name = info.filename
                nb = len(name.encode("utf-8"))
                if nb > MAX_ENTRY_NAME_BYTES:
                    raise ReleaseError("archive_name_too_long", "nested entry name is too long")
                total_name += nb
                if total_name > MAX_TOTAL_NAME_BYTES:
                    raise ReleaseError("archive_total_names_too_long", "nested entry names exceed the total limit")
                norm, is_dir, depth = _validate_archive_member_name(name)  # shared authoritative validator
                (dir_logical if is_dir else file_logical).add(norm.casefold())
                max_depth = max(max_depth, depth)
                max_name = max(max_name, nb)
                if not is_dir:
                    if classify_prohibited_absolute(norm, policy) is not None:
                        raise ReleaseError("archive_prohibited_nested", "allowed archive has a prohibited nested name")
                    if PurePosixPath(norm).suffix.casefold() in policy.prohibited_archive_extensions:
                        raise ReleaseError("archive_nested_archive", "allowed archive contains a nested archive")
            if file_logical & dir_logical:
                raise ReleaseError("archive_file_dir_collision", "a nested name is both a file and a directory")
    except zipfile.BadZipFile as exc:
        raise ReleaseError("archive_malformed", "allowed archive is not a readable ZIP") from exc
    except (NotImplementedError, RuntimeError) as exc:
        raise ReleaseError("archive_unsupported", "allowed archive uses an unsupported feature") from exc
    return {
        "format": "zip", "entry_count": len(names), "total_name_bytes": total_name,
        "max_name_bytes": max_name, "max_depth": max_depth, "comment_length": len(comment),
        "payload_sha256": payload_sha, "payload_size": payload_size,
        "rule_id": rule_id, "limits_version": ARCHIVE_INSPECTION_VERSION, "result": "SAFE",
    }


# --------------------------------------------------------------------------- #
# Deterministic ZIP + checksum text + bounded reopen
# --------------------------------------------------------------------------- #
def deterministic_zip_bytes(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9, strict_timestamps=True) as archive:
        archive.comment = b""  # canonical: no outer archive comment
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = ZIP_CREATE_SYSTEM
            info.external_attr = ZIP_EXTERNAL_ATTR
            info.comment = b""      # canonical: no per-entry comment
            info.extra = b""        # canonical: no extra field
            archive.writestr(info, files[name], compress_type=zipfile.ZIP_DEFLATED,
                             compresslevel=9)
    return buffer.getvalue()


def checksum_text(files: dict[str, bytes]) -> bytes:
    return "".join(f"{sha256_bytes(files[name])}  {name}\n"
                   for name in sorted(files)).encode("ascii")


def parse_checksum_text(data: bytes) -> dict[str, str]:
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


def validate_zip_structure(data: bytes) -> None:
    """Read-only raw-structure validation of the outer release ZIP: one canonical
    single-disk EOCD with no trailing bytes/ZIP64/multi-disk, and per-entry
    central+local headers with the exact canonical flags/versions/attributes and
    local/central agreement. Names-only path safety. Fails closed with content-free
    reason codes. Never extracts."""
    import struct
    n = len(data)
    if n < 22:
        raise ReleaseError("zip_structure", "release ZIP is too small to be canonical")
    eocd = data.rfind(_EOCD_SIG)
    if eocd < 0 or eocd + 22 > n:
        raise ReleaseError("zip_structure", "no End-Of-Central-Directory record")
    disk, cddisk, ethis, etot, cdsize, cdoff, clen = struct.unpack("<HHHHIIH", data[eocd + 4:eocd + 22])
    if clen != 0:
        raise ReleaseError("zip_comment_nonempty", "EOCD records a non-empty archive comment")
    if eocd + 22 != n:
        raise ReleaseError("zip_trailing_bytes", "trailing bytes after EOCD")
    if eocd >= 20 and data[eocd - 20:eocd - 16] == _ZIP64_EOCD_LOCATOR_SIG:
        raise ReleaseError("zip_zip64", "ZIP64 EOCD locator present")
    if disk != 0 or cddisk != 0 or ethis != etot:
        raise ReleaseError("zip_multidisk", "EOCD is not single-disk canonical")
    if etot == 0xFFFF or cdsize == 0xFFFFFFFF or cdoff == 0xFFFFFFFF:
        raise ReleaseError("zip_zip64", "ZIP64 sentinel values present")
    if etot > MAX_ZIP_ENTRIES:
        raise ReleaseError("zip_too_many_entries", "release ZIP has too many entries")
    if not (0 <= cdoff <= cdoff + cdsize <= eocd):
        raise ReleaseError("zip_structure", "central-directory bounds are invalid")
    if cdoff + cdsize != eocd:
        raise ReleaseError("zip_structure", "central directory does not end exactly at EOCD")
    off = cdoff
    names: list[str] = []
    local_records: list[tuple[int, int]] = []  # (start, end) of each local record
    for _ in range(etot):
        if off + 46 > eocd or data[off:off + 4] != _CD_SIG:
            raise ReleaseError("zip_structure", "malformed central-directory header")
        (vmb, vn, flags, comp, cmt, cmd, crc, csz, usz, nl, el, cl,
         dstart, iattr, eattr, loff) = struct.unpack("<HHHHHHIIIHHHHHII", data[off + 4:off + 46])
        end = off + 46 + nl + el + cl
        if end > eocd:
            raise ReleaseError("zip_structure", "central-directory header overruns EOCD")
        raw_name = data[off + 46:off + 46 + nl]
        if vmb != ZIP_VERSION_MADE_BY:
            raise ReleaseError("zip_version", "non-canonical version-made-by")
        if vn != ZIP_VERSION_NEEDED:
            raise ReleaseError("zip_version", "non-canonical version-needed")
        if flags != ZIP_FLAGS_CANONICAL:
            raise ReleaseError("zip_flags", "non-canonical general-purpose flags")
        if comp not in SUPPORTED_COMPRESSION:
            raise ReleaseError("zip_unsupported_compression", "non-canonical compression method")
        if cmt != ZIP_DOS_TIME or cmd != ZIP_DOS_DATE:
            raise ReleaseError("zip_central_timestamp", "non-canonical central DOS timestamp")
        if el != 0 or cl != 0:
            raise ReleaseError("zip_noncanonical_metadata", "central header has extra/comment bytes")
        if dstart != ZIP_DISK_CANONICAL:
            raise ReleaseError("zip_disk_start", "non-canonical entry disk-start")
        if iattr != ZIP_INTERNAL_ATTR_CANONICAL:
            raise ReleaseError("zip_internal_attr", "non-canonical internal attributes")
        if eattr != ZIP_EXTERNAL_ATTR:
            raise ReleaseError("zip_external_attr", "non-canonical external attributes")
        try:
            name = raw_name.decode("ascii")
        except UnicodeDecodeError as exc:
            raise ReleaseError("zip_nonascii_name", "non-ASCII entry name with canonical flags") from exc
        validate_relative_posix(name, label="zip entry")
        # Local header agreement (including DOS timestamp parsed from raw local bytes).
        if not (0 <= loff <= loff + 30 <= cdoff) or data[loff:loff + 4] != _LH_SIG:
            raise ReleaseError("zip_structure", "malformed local header")
        (lvn, lflags, lcomp, lmt, lmd, lcrc, lcsz, lusz, lnl, lel) = struct.unpack(
            "<HHHHHIIIHH", data[loff + 4:loff + 30])
        lname = data[loff + 30:loff + 30 + lnl]
        if (lvn != vn or lflags != flags or lcomp != comp or lcrc != crc
                or lcsz != csz or lusz != usz or lname != raw_name or lel != 0):
            raise ReleaseError("zip_local_central_mismatch", "local header disagrees with central directory")
        if lmt != ZIP_DOS_TIME or lmd != ZIP_DOS_DATE:
            raise ReleaseError("zip_local_timestamp", "non-canonical local DOS timestamp")
        if lmt != cmt or lmd != cmd:
            raise ReleaseError("zip_local_central_timestamp_mismatch", "local/central DOS timestamp disagree")
        local_end = loff + 30 + lnl + lel + csz
        if local_end > cdoff:
            raise ReleaseError("zip_structure", "local record overruns the central directory")
        local_records.append((loff, local_end))
        names.append(name)
        off = end
    if off != eocd:
        raise ReleaseError("zip_structure", "unexpected trailing central-directory records")
    if len(names) != len(set(names)):
        raise ReleaseError("zip_duplicate", "duplicate entry names")
    if len({x.casefold() for x in names}) != len(names):
        raise ReleaseError("zip_case_collision", "case-colliding entry names")
    # Prove complete, gap-free byte coverage of the local-record region [0, cdoff):
    # ordered, contiguous, non-overlapping, starting at 0 and ending exactly at cdoff.
    # Any gap is an archive-extra-data / digital-signature / unaccounted-bytes record.
    cursor = 0
    for start, rec_end in sorted(local_records):
        if start != cursor:
            sig = data[cursor:cursor + 4]
            if sig == _ARCHIVE_EXTRA_DATA_SIG:
                raise ReleaseError("zip_archive_extra_data", "archive-extra-data record present")
            if sig == _DIGITAL_SIGNATURE_SIG or sig == _ZIP64_EOCD_SIG or sig == _ZIP64_EOCD_LOCATOR_SIG:
                raise ReleaseError("zip_digital_signature", "unsupported structural record present")
            raise ReleaseError("zip_record_gap" if start > cursor else "zip_unaccounted_bytes",
                               "unaccounted bytes between local records")
        cursor = rec_end
    if cursor != cdoff:
        sig = data[cursor:cursor + 4]
        if sig == _ARCHIVE_EXTRA_DATA_SIG:
            raise ReleaseError("zip_archive_extra_data", "archive-extra-data record before central directory")
        if sig in (_DIGITAL_SIGNATURE_SIG, _ZIP64_EOCD_SIG, _ZIP64_EOCD_LOCATOR_SIG):
            raise ReleaseError("zip_digital_signature", "unsupported structural record before central directory")
        raise ReleaseError("zip_unaccounted_bytes", "unaccounted bytes before the central directory")


def read_zip_entries(zip_path: Path) -> dict[str, bytes]:
    """Reopen a ZIP and return entry bytes, applying outer resource bounds, the
    canonical raw-structure contract and safe-path validation. Never extracts.
    Maps unsupported/encrypted/malformed archives to controlled ReleaseError."""
    p = Path(zip_path)
    try:
        size = p.stat().st_size
    except OSError as exc:
        raise ReleaseError("candidate_io_failure", "release ZIP could not be stat'd") from exc
    if size > MAX_CANDIDATE_ZIP_BYTES:  # ceiling BEFORE any allocation/read
        raise ReleaseError("zip_too_large", "candidate ZIP exceeds the size ceiling")
    try:
        with open(p, "rb") as handle:
            raw = handle.read(MAX_CANDIDATE_ZIP_BYTES + 1)
    except OSError as exc:
        raise ReleaseError("candidate_io_failure", "release ZIP could not be read") from exc
    if len(raw) > MAX_CANDIDATE_ZIP_BYTES:
        raise ReleaseError("zip_too_large", "candidate ZIP exceeds the size ceiling")
    validate_zip_structure(raw)  # canonical EOCD/central/local metadata, single-disk, safe names
    try:
        with zipfile.ZipFile(io.BytesIO(raw), "r") as archive:
            if archive.comment != b"":
                raise ReleaseError("zip_comment_nonempty", "release ZIP has a non-empty archive comment")
            infos = archive.infolist()
            if len(infos) > MAX_ZIP_ENTRIES:
                raise ReleaseError("zip_too_many_entries", "release ZIP has too many entries")
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                raise ReleaseError("zip_duplicate", "ZIP contains duplicate entries")
            if len({n.casefold() for n in names}) != len(names):
                raise ReleaseError("zip_case_collision", "ZIP contains case-colliding entries")
            total = 0
            for info in infos:
                name = info.filename
                validate_relative_posix(name, label="zip entry")
                if info.flag_bits & 0x1:
                    raise ReleaseError("zip_encrypted", "ZIP contains an encrypted entry")
                if info.compress_type not in SUPPORTED_COMPRESSION:
                    raise ReleaseError("zip_unsupported_compression", "ZIP uses unsupported compression")
                if info.comment != b"":
                    raise ReleaseError("zip_entry_comment", "ZIP entry carries a non-empty comment")
                if info.extra != b"":
                    raise ReleaseError("zip_entry_extra", "ZIP entry carries an extra field")
                if info.file_size > MAX_FILE_BYTES:
                    raise ReleaseError("zip_entry_too_large", "a ZIP entry exceeds the size limit")
                total += info.file_size
                if total > MAX_ZIP_TOTAL_UNCOMPRESSED:
                    raise ReleaseError("zip_total_too_large", "ZIP total uncompressed size exceeds the limit")
            result: dict[str, bytes] = {}
            for info in infos:
                try:
                    result[info.filename] = archive.read(info.filename)
                except (NotImplementedError, RuntimeError) as exc:
                    raise ReleaseError("zip_unsupported", "a ZIP entry could not be read safely") from exc
            return result
    except zipfile.BadZipFile as exc:
        raise ReleaseError("zip_malformed", "release ZIP is not a readable archive") from exc


# --------------------------------------------------------------------------- #
# Atomic no-clobber publication
# --------------------------------------------------------------------------- #
def exclusive_write(path: Path, data: bytes) -> None:
    with open(path, "xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def hardlink_no_clobber(src: Path, dst: Path) -> None:
    """Publish exact verified bytes by hard-linking src -> dst. No-clobber and
    fail-closed. Never uses os.replace."""
    if dst.exists():
        raise ReleaseError("destination_exists", "final destination already exists")
    try:
        os.link(src, dst)
    except FileExistsError as exc:
        raise ReleaseError("destination_exists", "final destination already exists") from exc
    except OSError as exc:
        raise ReleaseError("hardlink_unsupported", "atomic hard-link publication is not supported here") from exc


# --------------------------------------------------------------------------- #
# Infallible content-free public emission
# --------------------------------------------------------------------------- #
# Precomputed fixed ASCII fallback — no dynamic interpolation of any value.
PUBLIC_OUTPUT_FAILURE_BYTES = (
    b'{\n  "content_free": true,\n  "error_code": "public_output_failure",\n'
    b'  "schema_version": 1,\n  "status": "FAIL",\n  "tool": "release"\n}\n'
)


def _write_stream_bytes(stream, data: bytes) -> bool:
    """Write bytes to a text/binary stream, flushing. Returns True on success,
    False on ANY ordinary failure (never raises for ordinary errors).
    KeyboardInterrupt/SystemExit (BaseException) still propagate."""
    try:
        buffer = getattr(stream, "buffer", None)
        if buffer is not None:
            buffer.write(data)
            buffer.flush()
        else:
            stream.write(data.decode("ascii", "replace"))
            stream.flush()
        return True
    except Exception:
        return False


def emit_public_result(payload: dict, *, output_path, primary_stream, fallback_stream,
                       exit_code: int) -> int:
    """THE single content-free public emitter. Serializes to immutable bytes first,
    then writes the optional output file and the primary stream; on ANY write/flush
    failure it emits a fixed content-free fallback on the alternate stream (never
    reusing candidate/exception text) and returns a nonzero exit code. When both
    streams fail it returns nonzero WITHOUT raising and WITHOUT producing output. An
    output-write failure never yields PASS exit semantics."""
    try:
        data = (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")
    except Exception:
        if not _write_stream_bytes(primary_stream, PUBLIC_OUTPUT_FAILURE_BYTES):
            _write_stream_bytes(fallback_stream, PUBLIC_OUTPUT_FAILURE_BYTES)
        return max(exit_code, 1)
    if output_path is not None:
        try:
            with open(output_path, "wb") as handle:
                handle.write(data)
                handle.flush()
        except Exception:
            if not _write_stream_bytes(primary_stream, PUBLIC_OUTPUT_FAILURE_BYTES):
                _write_stream_bytes(fallback_stream, PUBLIC_OUTPUT_FAILURE_BYTES)
            return max(exit_code, 1)
    if _write_stream_bytes(primary_stream, data):
        return exit_code
    # Primary stream failed: fixed content-free fallback on the alternate stream.
    _write_stream_bytes(fallback_stream, PUBLIC_OUTPUT_FAILURE_BYTES)
    return max(exit_code, 1)
