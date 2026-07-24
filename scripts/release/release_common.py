"""Shared fail-closed primitives for the Phase 12G release tooling.

No function here parses a benchmark record or ``result.json``, and none prints
file content. Errors are content-free and carry a stable machine-readable code.
"""
from __future__ import annotations

import hashlib
import os
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Iterable

CHUNK = 65536
HEX64 = frozenset("0123456789abcdef")

# Deterministic ZIP entry metadata.
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
ZIP_CREATE_SYSTEM = 3  # unix
ZIP_EXTERNAL_ATTR = (0o100644 & 0xFFFF) << 16

# Prohibited classification (see release/release-allowlist.json).
PROHIBITED_EXTENSIONS = frozenset(
    {".jsonl", ".db", ".sqlite", ".sqlite3", ".pem", ".key", ".p12", ".pfx"}
)
PROHIBITED_EXACT_NAMES = frozenset(
    {"result.json", "credentials.json", "credential.json", "secrets.json",
     "id_rsa", "id_ed25519"}
)
ENV_ALLOW_EXCEPTIONS = frozenset({".env.example", ".env.sample", ".env.template"})
PROHIBITED_PATH_COMPONENTS = frozenset(
    {".git", ".venv", "venv", "env", "__pycache__", ".pytest_cache",
     ".mypy_cache", ".ruff_cache", "node_modules", ".idea", ".vscode",
     ".tmp", ".pytest-tmp"}
)


class ReleaseError(Exception):
    """Fail-closed error with a stable machine-readable ``code``."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> tuple[str, int]:
    """Return (sha256, size) reading in binary chunks. Never parses content."""
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


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


def validate_relative_posix(relpath: str, *, label: str) -> str:
    """Validate a repo-relative POSIX path. Reject unsafe shapes."""
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


def classify_prohibited(relpath: str) -> str | None:
    """Return a prohibited-class name if ``relpath`` is disallowed, else None."""
    pure = PurePosixPath(relpath)
    parts_cf = tuple(part.casefold() for part in pure.parts)
    name = pure.name
    name_cf = name.casefold()
    suffix_cf = pure.suffix.casefold()

    for component in parts_cf:
        if component in PROHIBITED_PATH_COMPONENTS:
            return f"path_component:{component}"
    if suffix_cf in PROHIBITED_EXTENSIONS:
        return f"extension:{suffix_cf}"
    if name_cf in PROHIBITED_EXACT_NAMES:
        return f"name:{name_cf}"
    if name_cf == ".env" or name_cf.startswith(".env."):
        if name_cf not in {e.casefold() for e in ENV_ALLOW_EXCEPTIONS}:
            return "env_file"
    return None


def deterministic_zip_bytes(files: dict[str, bytes]) -> bytes:
    """Build a deterministic ZIP: sorted names, fixed timestamps and attrs."""
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


def read_zip_entries(zip_path: Path) -> dict[str, bytes]:
    """Reopen a ZIP and return entry bytes, rejecting unsafe/duplicate paths."""
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


def is_hex64(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value.lower()) <= HEX64


def is_hex40(value: object) -> bool:
    return isinstance(value, str) and len(value) == 40 and set(value.lower()) <= HEX64


def exclusive_write(path: Path, data: bytes) -> None:
    """Write bytes with exclusive create (atomic no-clobber). Fails if present."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def assert_within(root: Path, candidate: Path, *, label: str) -> None:
    """Confirm ``candidate`` resolves within ``root`` (no escape)."""
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ReleaseError("path_escape", f"{label} escapes the repository root") from exc


def iter_prohibited(relpaths: Iterable[str]) -> list[tuple[str, str]]:
    """Return (relpath, class) for every prohibited path in ``relpaths``."""
    hits: list[tuple[str, str]] = []
    for rel in relpaths:
        klass = classify_prohibited(rel)
        if klass is not None:
            hits.append((rel, klass))
    return hits
