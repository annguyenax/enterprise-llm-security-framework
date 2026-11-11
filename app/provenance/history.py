"""Explicit new/history reading that keeps original bytes and numbers."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import Literal

from .schema import (
    SCHEMA_VERSION, SLOT_PATHS, UNKNOWN, EvidenceResolver, ValidationIssue,
    ValidationResult, nonempty_string, slot_at, slot_value,
)
from .validate import _slot_errors, validate_artifact


def _freeze(value: object) -> object:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")


@dataclass(frozen=True)
class HistoryField:
    value: object
    evidence: str | None
    reason: str | None

    @property
    def display(self) -> object:
        return UNKNOWN if self.value is None else self.value


@dataclass(frozen=True)
class HistoryView:
    original_bytes: bytes
    document: object
    mode: Literal["new", "history"]
    status: Literal["valid", "invalid", "versionless", "unsupported"]
    fields: Mapping[str, HistoryField]
    validation: ValidationResult
    latency_reportable: bool = False

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.original_bytes).hexdigest()

    @property
    def valid_new_artifact(self) -> bool:
        return self.status == "valid" and self.validation.valid


def read_artifact(
    original: bytes, *, mode: Literal["new", "history"],
    evidence: EvidenceResolver | None = None,
) -> HistoryView:
    """Read bytes in an explicitly selected mode; never normalize or rewrite.

    Historical fractional numbers use Decimal to avoid rounding original
    digits. Original bytes remain authoritative, including whitespace. No old
    metrics are recomputed, published or promoted to verified percentiles.
    New/supported documents are validated separately using JSON number types.
    A null/missing version is versionless only in history mode.
    """
    if mode not in {"new", "history"}:
        raise ValueError("mode must be explicitly new or history")
    if not isinstance(original, bytes):
        raise TypeError("original must be bytes")
    try:
        parsed = json.loads(original, parse_float=Decimal, parse_constant=_reject_constant)
        validation_document = json.loads(original, parse_constant=_reject_constant)
    except (UnicodeError, ValueError) as exc:
        validation = ValidationResult((ValidationIssue("$", f"invalid JSON: {exc}"),))
        return HistoryView(original, None, mode, "invalid", MappingProxyType({}), validation)

    version = parsed.get("schema_version") if isinstance(parsed, dict) else None
    if not isinstance(parsed, dict):
        status = "invalid"
        validation = validate_artifact(validation_document, evidence=None)
    elif version is None:
        status = "versionless" if mode == "history" else "invalid"
        # Do not interpret or resolve evidence for versionless / non-v1 docs.
        validation = validate_artifact(validation_document, evidence=None)
    elif version != SCHEMA_VERSION:
        status = "unsupported"
        validation = validate_artifact(validation_document, evidence=None)
    else:
        validation = validate_artifact(validation_document, evidence=evidence)
        status = "valid" if validation.valid else "invalid"

    fields: dict[str, HistoryField] = {}
    if status != "valid":
        # Versionless, unsupported, and invalid documents are never interpreted
        # with provenance-v1 rules: no run_id promotion, no resolver calls.
        if status == "unsupported":
            reason = "Unsupported schema_version; metadata is not interpreted"
        elif status == "versionless":
            reason = "Versionless historical artifact; metadata is not interpreted under provenance-v1"
        else:
            reason = "Invalid artifact; metadata is not interpreted as verified facts"
        for path in ("run_id", *SLOT_PATHS):
            fields[path] = HistoryField(None, None, reason)
    else:
        for path in ("run_id", *SLOT_PATHS):
            reason = f"Missing or unverified historical {path}"
            run_id = validation_document.get("run_id")
            if path == "run_id" and nonempty_string(run_id):
                fields[path] = HistoryField(run_id, None, None)
                continue
            if path != "run_id":
                slot = slot_at(validation_document, path)
                if not _slot_errors(path, slot, run_id, evidence):
                    fields[path] = HistoryField(slot["value"], slot["evidence"], slot["reason"])
                    continue
            fields[path] = HistoryField(None, None, reason)

    return HistoryView(
        original_bytes=original, document=_freeze(parsed), mode=mode, status=status,
        fields=MappingProxyType(fields), validation=validation,
        latency_reportable=(
            status == "valid" and slot_value(validation_document, "latency_reportable") is True
        ),
    )


def read_history(original: bytes, *, evidence: EvidenceResolver | None = None) -> HistoryView:
    """Convenience entry for read-only history mode; not an upgrade path."""
    return read_artifact(original, mode="history", evidence=evidence)
