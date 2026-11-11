"""Validate emitted artifacts without filling missing fields or metadata."""
from __future__ import annotations

import re
from collections.abc import Mapping

from .schema import (
    BOOLEAN_SLOTS, EXECUTION_PATHS, PROVIDERS, REQUIRED_KEYS, SCHEMA_VERSION,
    SLOT_KEYS, SLOT_PATHS, STORAGE_BACKENDS, EvidenceResolver, EvidenceSource,
    ValidationIssue, ValidationResult, nonempty_string, resolve_evidence,
    slot_at, slot_value,
)
from .timing import validate_timing


def _value_valid(path: str, value: object) -> bool:
    if value is None:
        return True
    if path in BOOLEAN_SLOTS:
        return type(value) is bool
    if not nonempty_string(value):
        return False
    if path == "commit_sha":
        return re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", value) is not None
    if path.startswith("provider."):
        return value in PROVIDERS
    if path == "execution_path":
        return value in EXECUTION_PATHS
    if path == "storage_backend":
        return value in STORAGE_BACKENDS
    return path.startswith("model.")


def _claims(source: EvidenceSource, path: str, value: object) -> bool:
    observed = source.claims.get(path)
    # Python bool == int is not evidence of the same JSON type/value.
    return type(observed) is type(value) and observed == value


def _same_run(source: EvidenceSource, run_id: object) -> bool:
    """A missing or null run_id never matches; None == None is not evidence."""
    return nonempty_string(run_id) and source.run_id == run_id


def _supports(source: EvidenceSource, path: str, value: object, run_id: object) -> bool:
    if not _same_run(source, run_id):
        return False
    mock_evidence = (
        _claims(source, "is_mock", True)
        or (source.execution is True and _claims(source, "provider.effective", "mock"))
    )
    if path == "llm_verified" and value is False and mock_evidence:
        return True
    if not _claims(source, path, value):
        return False
    if path.endswith(".effective"):
        return source.execution is True
    if path == "llm_verified" and value is True:
        return source.execution is True and source.real_llm_response is True
    return True


def _slot_errors(
    path: str, slot: object, run_id: object, evidence: EvidenceResolver | None,
) -> list[ValidationIssue]:
    def error(message: str) -> list[ValidationIssue]:
        return [ValidationIssue(path, message)]

    if not isinstance(slot, Mapping) or set(slot) != set(SLOT_KEYS):
        return error("slot must have exactly value, evidence, reason")
    value, reference, reason = (slot[key] for key in SLOT_KEYS)
    if not _value_valid(path, value):
        return error("unsupported value or wrong type")
    if reason is not None and not nonempty_string(reason):
        return error("reason must be null or a non-empty string")
    if value is None:
        if reference is not None or not nonempty_string(reason):
            return error("UNKNOWN requires null evidence and a non-empty reason")
        return []
    source = resolve_evidence(evidence, reference, run_id)
    if source is None or not _supports(source, path, value, run_id):
        return error("claimed value requires locatable, corresponding evidence")
    if path == "latency_reportable" and value is False and not nonempty_string(reason):
        return error("false reportability requires a non-empty reason")
    return []


def validate_artifact(
    artifact: object, *, evidence: EvidenceResolver | None = None,
) -> ValidationResult:
    """Check a NEW artifact, without repair, inference or version guessing.

    NEW-01: is_mock=true together with llm_verified=true is explicitly
    invalid, even when both slots point at evidence. Effective mock execution
    likewise requires evidence-backed llm_verified=false.
    NEW-04: llm_verified=true requires same-run response verification, not
    merely is_mock=false, an HTTP response, or a reference-shaped string.
    """
    if not isinstance(artifact, Mapping):
        return ValidationResult((ValidationIssue("$", "artifact must be an object"),))
    if artifact.get("schema_version") != SCHEMA_VERSION:
        # Unsupported/versionless documents are not interpreted using v1,
        # including their timing or historical percentile fields.
        return ValidationResult((
            ValidationIssue("schema_version", f"must be exactly {SCHEMA_VERSION}"),
        ))
    errors = [
        ValidationIssue(key, "required key is missing")
        for key in REQUIRED_KEYS if key not in artifact
    ]
    run_id = artifact.get("run_id")
    if not nonempty_string(run_id):
        errors.append(ValidationIssue("run_id", "must be a non-empty, non-null string"))
    for name in ("provider", "model"):
        if not isinstance(artifact.get(name), Mapping):
            errors.append(ValidationIssue(name, "must be an object with requested and effective slots"))
    for path in SLOT_PATHS:
        errors.extend(_slot_errors(path, slot_at(artifact, path), run_id, evidence))

    mock = slot_value(artifact, "is_mock") is True
    effective_mock = slot_value(artifact, "provider.effective") == "mock"
    verified = slot_value(artifact, "llm_verified")
    if mock and verified is True:
        errors.append(ValidationIssue("llm_verified", "NEW-01: mock and verified=true are contradictory"))
    if (mock or effective_mock) and verified is not False:
        errors.append(ValidationIssue("llm_verified", "mock execution requires evidence-backed false"))
    if "timing" in artifact:
        errors.extend(validate_timing(
            artifact["timing"], run_id=run_id,
            reportable=slot_value(artifact, "latency_reportable") is True,
            evidence=evidence,
        ).errors)
    return ValidationResult(tuple(errors))
