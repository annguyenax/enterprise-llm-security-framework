"""Strict timing records and separated, evidence-checked latency summaries."""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from .schema import (
    SUCCESS_SCOPE, TIMING_FIELDS, EvidenceResolver, TimingRecord, ValidationIssue,
    ValidationResult, nonempty_string, resolve_evidence, slot_at, slot_value,
)


def is_json_number(value: object) -> bool:
    return type(value) is int or (type(value) is float and math.isfinite(value))


def validate_timing(
    timing: object, *, run_id: object, reportable: bool = False,
    evidence: EvidenceResolver | None = None,
) -> ValidationResult:
    """Validate all structural rules even when reportable is false/unknown.

    NEW-02: source_ref resolves clock_id, monotonicity and same-process
    attestations. There is no parallel clock-evidence field in the artifact.
    NEW-03: run mismatch and reversed marks are invalid for EVERY non-null
    record, independently of the reportability flag.
    """
    errors: list[ValidationIssue] = []

    def error(field: str, message: str) -> None:
        errors.append(ValidationIssue(f"timing.{field}" if field else "timing", message))

    if timing is None:
        if reportable:
            error("", "reportable latency requires a timing object")
        return ValidationResult(tuple(errors))
    if not isinstance(timing, Mapping):
        error("", "must be null or an object")
        return ValidationResult(tuple(errors))
    for name in TIMING_FIELDS:
        if name not in timing:
            error(name, "required field is missing")
        elif name in {"start", "end"}:
            if not is_json_number(timing[name]):
                error(name, "must be a finite JSON number, without coercion")
        elif not nonempty_string(timing[name]):
            error(name, "must be a non-empty string")
    if timing.get("unit") != "ms":
        error("unit", "must be exactly ms")
    if timing.get("run_id") != run_id:
        error("run_id", "must equal the artifact run_id")
    start, end = timing.get("start"), timing.get("end")
    if is_json_number(start) and is_json_number(end) and end < start:
        error("end", "must not precede start")

    source = resolve_evidence(evidence, timing.get("source_ref"), run_id)
    if source is None:
        error("source_ref", "must resolve to a locatable timing source")
    if reportable:
        if timing.get("scope") != SUCCESS_SCOPE:
            error("scope", f"reportable timing requires {SUCCESS_SCOPE}")
        if source is not None:
            if source.run_id != run_id:
                error("source_ref", "source must attest the same run_id")
            if source.clock_id != timing.get("clock_id"):
                error("clock_id", "source must attest the clock used for both marks")
            if source.monotonic is not True or source.same_process is not True:
                error("source_ref", "source must attest a monotonic clock in the same process")
            if (
                source.execution is not True or source.scope != SUCCESS_SCOPE
                or source.outcome != "success"
            ):
                error("source_ref", "source must attest dispatch through final success")
    return ValidationResult(tuple(errors))


def make_timing(
    *, source_ref: str, run_id: str, clock_id: str, start: int | float,
    end: int | float, scope: str, evidence: EvidenceResolver,
) -> TimingRecord:
    """Build an ms record from supplied marks; never coerce or invent marks."""
    timing: TimingRecord = {
        "source_ref": source_ref, "run_id": run_id, "clock_id": clock_id,
        "start": start, "end": end, "unit": "ms", "scope": scope,
    }
    result = validate_timing(timing, run_id=run_id, evidence=evidence)
    if not result.valid:
        raise ValueError(result.errors)
    return timing


@dataclass(frozen=True)
class LatencyGroup:
    source_ref: str
    scope: str
    provider_effective: str | None
    model_effective: str | None
    execution_path: str | None
    storage_backend: str | None
    acl_enabled: bool | None
    is_mock: bool | None
    llm_verified: bool | None
    commit_sha: str | None
    evidence_kind: str | None = None

    @property
    def label(self) -> str:
        if self.is_mock is True or self.provider_effective == "mock":
            return "mock"
        if self.is_mock is None or self.llm_verified is not True:
            return "UNKNOWN"
        # Fixture attestations are test doubles and must never be labelled
        # as response-verified (indistinguishable from log-backed realLLM).
        if self.evidence_kind == "fixture":
            return "in-sample"
        return "response-verified"


@dataclass(frozen=True)
class LatencySummary:
    group: LatencyGroup
    count: int
    p50_ms: int | float
    p95_ms: int | float



_KIND_SLOT_PATHS = (
    "llm_verified", "is_mock", "provider.effective", "model.effective",
    "execution_path", "storage_backend", "acl_enabled", "commit_sha",
    "latency_reportable",
)


def _group_evidence_kind(artifact, evidence, timing_source) -> str | None:
    """A fixture anywhere in the attestation chain stays in-sample.

    The timing source kind alone is not enough: a log-backed clock with a
    fixture-backed llm_verified claim must not be labelled response-verified.
    """
    kinds: list[str] = []
    if timing_source is not None:
        kinds.append(timing_source.kind)
    run_id = artifact.get("run_id") if isinstance(artifact, Mapping) else None
    for path in _KIND_SLOT_PATHS:
        slot = slot_at(artifact, path)
        if not isinstance(slot, Mapping):
            continue
        source = resolve_evidence(evidence, slot.get("evidence"), run_id)
        if source is not None:
            kinds.append(source.kind)
    if "fixture" in kinds:
        return "fixture"
    return kinds[0] if kinds else None


def summarize_latency(
    artifacts: Iterable[Mapping[str, object]], *,
    evidence: EvidenceResolver | None = None,
) -> tuple[LatencySummary, ...]:
    """Nearest-rank percentiles, only from valid, explicitly reportable samples.

    Invalid, historical, false and UNKNOWN records publish no percentiles.
    Groups share source/scope and keep effective identities, execution/storage,
    ACL, commit and mock/verification status separate. Original artifacts and
    any historical percentile fields are never changed or used as samples.
    """
    from .validate import validate_artifact

    groups: dict[LatencyGroup, list[int | float]] = {}
    for artifact in artifacts:
        if not validate_artifact(artifact, evidence=evidence).valid:
            continue
        if slot_value(artifact, "latency_reportable") is not True:
            continue
        timing = artifact["timing"]
        source = resolve_evidence(evidence, timing.get("source_ref"), artifact.get("run_id"))
        group = LatencyGroup(
            source_ref=timing["source_ref"], scope=timing["scope"],
            provider_effective=slot_value(artifact, "provider.effective"),
            model_effective=slot_value(artifact, "model.effective"),
            execution_path=slot_value(artifact, "execution_path"),
            storage_backend=slot_value(artifact, "storage_backend"),
            acl_enabled=slot_value(artifact, "acl_enabled"),
            is_mock=slot_value(artifact, "is_mock"),
            llm_verified=slot_value(artifact, "llm_verified"),
            commit_sha=slot_value(artifact, "commit_sha"),
            evidence_kind=_group_evidence_kind(artifact, evidence, source),
        )
        duration = timing["end"] - timing["start"]
        # Finite marks can still overflow during floating-point subtraction.
        if is_json_number(duration):
            groups.setdefault(group, []).append(duration)
    summaries: list[LatencySummary] = []
    for group, values in groups.items():
        values.sort()
        count = len(values)
        summaries.append(LatencySummary(
            group=group, count=count,
            p50_ms=values[math.ceil(count * 0.50) - 1],
            p95_ms=values[math.ceil(count * 0.95) - 1],
        ))
    return tuple(summaries)
