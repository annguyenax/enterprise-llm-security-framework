"""The provenance-v1 wire schema and caller-supplied evidence contract."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, TypedDict

SCHEMA_VERSION = "provenance-v1"
UNKNOWN = "UNKNOWN"  # Display only; never a wire value.
SUCCESS_SCOPE = "dispatch_to_final_success"
PROVIDERS = frozenset({"mock", "ollama"})
EXECUTION_PATHS = frozenset({"gateway", "rag"})
STORAGE_BACKENDS = frozenset({"none", "memory", "persistent"})
REQUIRED_KEYS = (
    "schema_version", "run_id", "commit_sha", "provider", "model",
    "execution_path", "storage_backend", "acl_enabled", "is_mock",
    "latency_reportable", "llm_verified", "timing",
)
SLOT_KEYS = ("value", "evidence", "reason")
SLOT_PATHS = (
    "commit_sha", "provider.requested", "provider.effective",
    "model.requested", "model.effective", "execution_path", "storage_backend",
    "acl_enabled", "is_mock", "latency_reportable", "llm_verified",
)
BOOLEAN_SLOTS = frozenset({
    "acl_enabled", "is_mock", "latency_reportable", "llm_verified",
})
TIMING_FIELDS = (
    "source_ref", "run_id", "clock_id", "start", "end", "unit", "scope",
)


class ProvenanceSlot(TypedDict):
    value: str | bool | None
    evidence: str | None
    reason: str | None


class TimingRecord(TypedDict):
    source_ref: str
    run_id: str
    clock_id: str
    start: int | float
    end: int | float
    unit: Literal["ms"]
    scope: str


@dataclass(frozen=True)
class EvidenceSource:
    """Attestation obtained by a trusted, explicit source adapter.

    Registry keys / resolver references locate a concrete log, artifact or
    fixture. `claims` maps slot paths to observed values, not requested-value
    defaults. Effective claims require execution evidence for the same run.
    Clock attestations live HERE, resolved via timing.source_ref (NEW-02),
    rather than in extra timing wire fields. No filesystem/network discovery
    is performed by this package. A fixture attestation is only a test double.
    """

    kind: Literal["log", "artifact", "fixture"]
    claims: Mapping[str, object] = field(default_factory=dict)
    run_id: str | None = None
    execution: bool = False
    real_llm_response: bool = False
    clock_id: str | None = None
    monotonic: bool = False
    same_process: bool = False
    scope: str | None = None
    outcome: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "claims", MappingProxyType(dict(self.claims)))


# A callback can select a run-specific record from a shared log source.
EvidenceResolver = (
    Mapping[str, EvidenceSource]
    | Callable[[str, str | None], EvidenceSource | None]
)


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    message: str


@dataclass(frozen=True)
class ValidationResult:
    errors: tuple[ValidationIssue, ...] = ()

    @property
    def valid(self) -> bool:
        return not self.errors

    def __bool__(self) -> bool:
        return self.valid


def nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def resolve_evidence(
    evidence: EvidenceResolver | None, reference: object, run_id: object,
) -> EvidenceSource | None:
    if not nonempty_string(reference) or evidence is None:
        return None
    try:
        source = (
            evidence.get(reference) if isinstance(evidence, Mapping)
            else evidence(reference, run_id if isinstance(run_id, str) else None)
        )
    except Exception:
        # A failed source adapter cannot turn an unverified claim into evidence.
        return None
    if not isinstance(source, EvidenceSource) or source.kind not in (
        "log", "artifact", "fixture",
    ):
        return None
    return source


def slot_at(artifact: Mapping[str, object], path: str) -> object:
    value: object = artifact
    for part in path.split("."):
        if not isinstance(value, Mapping):
            return None
        value = value.get(part)
    return value


def slot_value(artifact: Mapping[str, object], path: str) -> object:
    slot = slot_at(artifact, path)
    return slot.get("value") if isinstance(slot, Mapping) else None
