"""Typed, defensively-immutable models for the Phase 12B retrieval
foundation.

Security invariants enforced by construction (see
docs/modernization-v2-architecture.md §3-4 and required decision C in
docs/modernization-final-plan.md):

- These models never carry a benchmark-only ground-truth field such as
  `is_poisoned`. Nothing here can accidentally leak it into a runtime
  decision.
- `metadata` on every record is copied into a `MappingProxyType` at
  construction time, so callers cannot mutate a record's metadata through
  a shared dict reference after the fact.
- `DocumentRecord`/`ChunkRecord`'s security-relevant fields
  (`trust_level`, `classification`, `source_type`) are always populated by
  server-side code (`app/core/source_policy.py`, `app/services/ingestion.py`)
  -- `IngestionDocument`, the one model that represents raw caller input,
  deliberately has no such fields at all, so there is nothing for a caller
  to override.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, Mapping

_EMPTY_METADATA: Mapping[str, str] = MappingProxyType({})


def _freeze_metadata(metadata: Mapping[str, object] | None) -> Mapping[str, object]:
    if not metadata:
        return _EMPTY_METADATA
    return MappingProxyType(dict(metadata))


@dataclass(frozen=True)
class DocumentRecord:
    """A persisted document's metadata (not its chunks)."""

    document_id: str
    external_id: str
    source_key: str
    source_id: str
    source_type: str
    classification: str
    trust_level: str
    title: str
    content_hash: str
    created_at: str
    updated_at: str
    metadata: Mapping[str, object] = field(default_factory=lambda: _EMPTY_METADATA)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))


@dataclass(frozen=True)
class ChunkRecord:
    """One deterministic, paragraph-aware chunk of a document's text."""

    chunk_id: str
    document_id: str
    chunk_index: int
    text: str
    content_hash: str
    metadata: Mapping[str, object] = field(default_factory=lambda: _EMPTY_METADATA)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))


@dataclass(frozen=True)
class RetrievalQuery:
    query: str
    top_k: int


@dataclass(frozen=True)
class RetrievalHit:
    chunk_id: str
    document_id: str
    title: str
    text: str
    rank: int
    retrieval_score: float
    source_id: str
    source_type: str
    classification: str
    trust_level: str
    metadata: Mapping[str, object] = field(default_factory=lambda: _EMPTY_METADATA)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))


@dataclass(frozen=True)
class RetrievalResult:
    normalized_query: str
    term_count: int
    total_hits: int
    hits: tuple[RetrievalHit, ...]


@dataclass(frozen=True)
class IngestionDocument:
    """Caller-supplied ingestion input, already validated by Pydantic at
    the API boundary and stripped of any field that could carry a
    security decision -- there is deliberately no `trust_level`,
    `classification`, `source_type`, `document_id`, or `chunk_id` field
    on this type. Those are always assigned by
    `app/core/source_policy.py` and `app/services/ingestion.py`."""

    external_id: str
    source_key: str
    title: str
    text: str
    metadata: Mapping[str, object] = field(default_factory=lambda: _EMPTY_METADATA)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))


@dataclass(frozen=True)
class SourcePolicyDecision:
    """Server-controlled provenance/trust assignment for one source_key.
    Never constructed from caller-supplied request data."""

    source_key: str
    source_type: str
    classification: str
    trust_level: str
    policy_id: str


IngestionStatus = Literal["indexed", "updated", "unchanged", "rejected"]


@dataclass(frozen=True)
class IngestionItemResult:
    external_id: str
    source_key: str
    document_id: str | None
    status: IngestionStatus
    reason: str | None = None
    chunk_count: int | None = None
    # Number of reserved security-relevant metadata keys (trust_level,
    # classification, is_poisoned, etc., at any nesting depth/case
    # variant) that were silently stripped from caller-supplied metadata
    # before storage. Zero means no spoofing attempt was detected; a
    # positive count is an auditable signal that one was, without ever
    # persisting or logging the stripped value itself. Added per the
    # Phase 12B Codex audit (Major #2).
    metadata_keys_stripped: int = 0


@dataclass(frozen=True)
class IngestionBatchResult:
    indexed: int
    updated: int
    unchanged: int
    rejected: int
    items: tuple[IngestionItemResult, ...]
