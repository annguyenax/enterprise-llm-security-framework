"""Validate datasets/enterprise-kb/ against its declared schema.

Checks the corpus is well-formed, that every document's access-control
metadata parses through `app.retrieval.acl.EnterpriseDocMetadata`, that the
file is byte-canonical (so its hash is reproducible), and that the manifest
still describes the bytes on disk.

Run:
    .venv\\Scripts\\python.exe scripts/validate_enterprise_kb.py

Exit code 0 = every check passed; 1 = at least one failure.

Conventions this file follows deliberately:

- **Type-first validation.** Every value is checked with `isinstance` before
  it is used in a membership test, hashed, or compared. `list`/`dict` are
  unhashable, so `value in SOME_SET` raises `TypeError` on them; and `bool`
  is a subclass of `int`, so integer checks use `type(x) is int` rather than
  `isinstance(x, int)`.
- **Error messages carry relative paths only**, never an absolute path and
  never raw artifact content -- a validator's own output should not become a
  second copy of the data it is validating.
- **No new dependency.** The corpus is JSONL and the manifest is JSON, both
  stdlib-parseable. PyYAML is deliberately absent from `requirements.txt`
  (AGENT_RULES.md rule 11), which is also why the corpus is not YAML.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.retrieval.acl import (  # noqa: E402  -- after sys.path setup
    ENTERPRISE_KB_SOURCE_KEY,
    EnterpriseDocMetadata,
)

KB_ROOT = Path("datasets/enterprise-kb")
CORPUS_RELATIVE = "corpus/documents.jsonl"
MANIFEST_RELATIVE = "manifests/enterprise-kb-manifest.json"

SCHEMA_VERSION = "enterprise-kb-1"

# Keys every corpus row must carry, exactly -- no more, no less. A row with
# an unexpected key is rejected rather than ignored: an unread key in a
# security-relevant artifact is a silent assumption mismatch.
REQUIRED_ROW_KEYS = frozenset(
    {
        "access_departments",
        "access_roles",
        "content",
        "document_id",
        "external_id",
        "language",
        "owner_department",
        "sensitivity",
        "source_key",
        "title",
        "valid_from",
        "valid_to",
    }
)

# Fields that are server-assigned everywhere else in this project and must
# therefore never appear in a hand-authored dataset row. Listed explicitly
# so a reviewer can see what is being excluded and why.
FORBIDDEN_ROW_KEYS = frozenset(
    {
        "chunk_id",
        "classification",
        "expected_decision",
        "is_poisoned",
        "security_decision",
        "source_type",
        "trust_level",
    }
)

MAX_CONTENT_CHARS = 20_000
MAX_TITLE_CHARS = 300


class Report:
    """Collects failures without stopping at the first one, so a single run
    reports every problem rather than making the operator iterate."""

    def __init__(self) -> None:
        self.errors: list[str] = []

    def fail(self, message: str) -> None:
        self.errors.append(message)

    @property
    def ok(self) -> bool:
        return not self.errors


def _read_text(path: Path, relative: str, report: Report) -> str | None:
    if not path.is_file():
        report.fail(f"{relative}: file khong ton tai")
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        report.fail(f"{relative}: khong doc duoc ({type(exc).__name__})")
        return None


def _check_row_shape(row: Any, line_number: int, report: Report) -> dict | None:
    """Structural checks that must pass before the row is worth parsing."""
    if not isinstance(row, dict):
        report.fail(f"{CORPUS_RELATIVE}:{line_number}: dong khong phai JSON object")
        return None

    keys = set(row.keys())
    if any(not isinstance(key, str) for key in keys):
        report.fail(f"{CORPUS_RELATIVE}:{line_number}: co key khong phai chuoi")
        return None

    forbidden = sorted(keys & FORBIDDEN_ROW_KEYS)
    if forbidden:
        report.fail(
            f"{CORPUS_RELATIVE}:{line_number}: chua truong do server gan: {forbidden}"
        )
        return None

    missing = sorted(REQUIRED_ROW_KEYS - keys)
    if missing:
        report.fail(f"{CORPUS_RELATIVE}:{line_number}: thieu truong {missing}")
        return None

    unexpected = sorted(keys - REQUIRED_ROW_KEYS)
    if unexpected:
        report.fail(f"{CORPUS_RELATIVE}:{line_number}: truong khong mong doi {unexpected}")
        return None

    for field in ("document_id", "external_id", "title", "content", "language"):
        value = row[field]
        if not isinstance(value, str) or not value.strip():
            report.fail(
                f"{CORPUS_RELATIVE}:{line_number}: '{field}' phai la chuoi khong rong"
            )
            return None

    if len(row["title"]) > MAX_TITLE_CHARS:
        report.fail(f"{CORPUS_RELATIVE}:{line_number}: 'title' vuot qua {MAX_TITLE_CHARS} ky tu")
        return None
    if len(row["content"]) > MAX_CONTENT_CHARS:
        report.fail(
            f"{CORPUS_RELATIVE}:{line_number}: 'content' vuot qua {MAX_CONTENT_CHARS} ky tu"
        )
        return None

    if row["source_key"] != ENTERPRISE_KB_SOURCE_KEY:
        report.fail(
            f"{CORPUS_RELATIVE}:{line_number}: 'source_key' phai la "
            f"{ENTERPRISE_KB_SOURCE_KEY!r}"
        )
        return None

    for field in ("access_roles", "access_departments"):
        value = row[field]
        if not isinstance(value, list) or not value:
            report.fail(f"{CORPUS_RELATIVE}:{line_number}: '{field}' phai la mang khong rong")
            return None
        if any(not isinstance(item, str) for item in value):
            report.fail(f"{CORPUS_RELATIVE}:{line_number}: '{field}' chi duoc chua chuoi")
            return None
        if value != sorted(value):
            report.fail(
                f"{CORPUS_RELATIVE}:{line_number}: '{field}' phai duoc sap xep tang dan"
            )
            return None
        if len(set(value)) != len(value):
            report.fail(f"{CORPUS_RELATIVE}:{line_number}: '{field}' co phan tu trung lap")
            return None

    for field in ("valid_from", "valid_to"):
        value = row[field]
        if value is not None and not isinstance(value, str):
            report.fail(f"{CORPUS_RELATIVE}:{line_number}: '{field}' phai la chuoi hoac null")
            return None

    return row


def _check_canonical_serialization(row: dict, raw_line: str, line_number: int, report: Report) -> None:
    """The corpus must be byte-canonical so its hash is reproducible.

    `datasets/v2/corpus/documents.jsonl` follows the same convention (sorted
    keys, no ASCII escaping); this makes the manifest hash meaningful as a
    drift check rather than an artifact of whichever tool wrote the file.
    """
    canonical = json.dumps(row, ensure_ascii=False, sort_keys=True)
    if raw_line != canonical:
        report.fail(
            f"{CORPUS_RELATIVE}:{line_number}: dong khong o dang canonical "
            "(can sort_keys=True, ensure_ascii=False, khong khoang trang thua)"
        )


def validate_corpus(kb_root: Path, report: Report) -> tuple[list[dict], str]:
    """Validate every corpus row. Returns `(rows, sha256_of_file)`."""
    corpus_path = kb_root / CORPUS_RELATIVE
    text = _read_text(corpus_path, CORPUS_RELATIVE, report)
    if text is None:
        return [], ""

    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()

    if text and not text.endswith("\n"):
        report.fail(f"{CORPUS_RELATIVE}: thieu ky tu xuong dong o cuoi file")
    if "\r" in text:
        report.fail(f"{CORPUS_RELATIVE}: chua ky tu CR; can dung xuong dong LF")

    rows: list[dict] = []
    seen_ids: set[str] = set()

    for index, raw_line in enumerate(text.splitlines(), start=1):
        if not raw_line.strip():
            report.fail(f"{CORPUS_RELATIVE}:{index}: dong trong khong duoc phep")
            continue
        try:
            parsed = json.loads(raw_line)
        except json.JSONDecodeError:
            report.fail(f"{CORPUS_RELATIVE}:{index}: JSON khong hop le")
            continue

        row = _check_row_shape(parsed, index, report)
        if row is None:
            continue

        _check_canonical_serialization(row, raw_line, index, report)

        document_id = row["document_id"]
        if document_id in seen_ids:
            report.fail(f"{CORPUS_RELATIVE}:{index}: 'document_id' bi trung lap")
        seen_ids.add(document_id)

        if row["external_id"] != document_id:
            report.fail(
                f"{CORPUS_RELATIVE}:{index}: 'external_id' phai trung 'document_id'"
            )

        # The authoritative check: the same model ingestion will use.
        try:
            EnterpriseDocMetadata(
                source_key=row["source_key"],
                sensitivity=row["sensitivity"],
                access_roles=frozenset(row["access_roles"]),
                access_departments=frozenset(row["access_departments"]),
                owner_department=row["owner_department"],
                valid_from=row["valid_from"],
                valid_to=row["valid_to"],
            )
        except Exception as exc:  # noqa: BLE001 -- surfaced as a report line
            report.fail(
                f"{CORPUS_RELATIVE}:{index}: metadata khong hop le "
                f"({type(exc).__name__})"
            )
            continue

        rows.append(row)

    if not rows and report.ok:
        report.fail(f"{CORPUS_RELATIVE}: khong co tai lieu nao")

    return rows, digest


def validate_manifest(kb_root: Path, rows: list[dict], digest: str, report: Report) -> None:
    manifest_path = kb_root / MANIFEST_RELATIVE
    text = _read_text(manifest_path, MANIFEST_RELATIVE, report)
    if text is None:
        return

    try:
        manifest = json.loads(text)
    except json.JSONDecodeError:
        report.fail(f"{MANIFEST_RELATIVE}: JSON khong hop le")
        return

    if not isinstance(manifest, dict):
        report.fail(f"{MANIFEST_RELATIVE}: phai la JSON object")
        return

    if manifest.get("schema_version") != SCHEMA_VERSION:
        report.fail(f"{MANIFEST_RELATIVE}: 'schema_version' phai la {SCHEMA_VERSION!r}")

    status = manifest.get("manifest_status")
    if not isinstance(status, str) or status not in {"draft", "final"}:
        report.fail(f"{MANIFEST_RELATIVE}: 'manifest_status' phai la 'draft' hoac 'final'")

    document_count = manifest.get("document_count")
    if type(document_count) is not int or document_count != len(rows):
        report.fail(
            f"{MANIFEST_RELATIVE}: 'document_count' khong khop so tai lieu thuc te "
            f"({len(rows)})"
        )

    if manifest.get("corpus_sha256") != digest:
        report.fail(
            f"{MANIFEST_RELATIVE}: 'corpus_sha256' khong khop noi dung "
            f"{CORPUS_RELATIVE} hien tai"
        )

    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        report.fail(f"{MANIFEST_RELATIVE}: 'files' phai la mang khong rong")
        return

    for entry in files:
        if not isinstance(entry, dict):
            report.fail(f"{MANIFEST_RELATIVE}: moi phan tu 'files' phai la object")
            continue
        relative = entry.get("path")
        if not isinstance(relative, str) or not relative:
            report.fail(f"{MANIFEST_RELATIVE}: 'files[].path' phai la chuoi khong rong")
            continue
        target = kb_root / relative
        if not target.is_file():
            report.fail(f"{MANIFEST_RELATIVE}: 'files[].path' tro toi file khong ton tai: {relative}")
            continue
        content = target.read_bytes()
        if entry.get("sha256") != hashlib.sha256(content).hexdigest():
            report.fail(f"{MANIFEST_RELATIVE}: sha256 khong khop cho {relative}")
        size = entry.get("size_bytes")
        if type(size) is not int or size != len(content):
            report.fail(f"{MANIFEST_RELATIVE}: size_bytes khong khop cho {relative}")

    counts = manifest.get("sensitivity_counts")
    if not isinstance(counts, dict):
        report.fail(f"{MANIFEST_RELATIVE}: 'sensitivity_counts' phai la object")
        return
    actual: dict[str, int] = {}
    for row in rows:
        key = row["sensitivity"]
        actual[key] = actual.get(key, 0) + 1
    if counts != actual:
        report.fail(
            f"{MANIFEST_RELATIVE}: 'sensitivity_counts' khong khop phan bo thuc te"
        )


def validate(kb_root: Path | str = KB_ROOT) -> Report:
    """Validate the knowledge base rooted at `kb_root`. Returns a `Report`;
    the caller decides what to do with a failure (the CLI exits non-zero,
    the test suite asserts on `report.errors`)."""
    report = Report()
    root = Path(kb_root)
    if not root.is_dir():
        report.fail(f"{root.as_posix()}: thu muc khong ton tai")
        return report
    rows, digest = validate_corpus(root, report)
    validate_manifest(root, rows, digest, report)
    return report


def main() -> int:
    report = validate()
    if report.ok:
        print("OK: enterprise-kb hop le (corpus canonical, metadata parse, manifest khop).")
        return 0
    print(f"FAIL: {len(report.errors)} van de:")
    for error in report.errors:
        print(f"  - {error}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
