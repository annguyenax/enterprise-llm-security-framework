"""Typed result contracts for the Phase 12C end-to-end RAG pipeline
(`app/services/rag_query.py`).

These types exist so `POST /v1/rag/query` can return a safe, structured
summary of what happened at every stage -- retrieval counts, provenance
decisions, guard-stage outcomes, DLP redaction counts, timing -- without
ever exposing raw internals (database paths, SQL errors, stack traces,
full retrieved chunk text by default, or detected secret values). See
`docs/modernization-v2-architecture.md` §1/§6 for the target pipeline
shape this implements.

Phase 12E.1 adds the internal-only `GuardProfile` value used to ablate
individual guard layers through `run_rag_query_uncommitted`. It contains
no retrieval, provider, bounds, audit, exception, Settings, environment,
or HTTP controls; those remain always-on infrastructure.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from app.core.decisions import Decision


@dataclass(frozen=True)
class GuardProfile:
    """Immutable internal guard-stage selection for Phase 12E ablation.

    Public request handling never constructs or selects this value. The
    six booleans control only whether their corresponding guard function
    is invoked; retrieval, provider execution, resource bounds, typed
    construction, exception handling, and audit safety are deliberately
    outside this contract.
    """

    input_guard: bool = True
    provenance_guard: bool = True
    rag_context_guard: bool = True
    aggregate_context_guard: bool = True
    dlp: bool = True
    output_guard: bool = True

    def __post_init__(self) -> None:
        for name in (
            "input_guard",
            "provenance_guard",
            "rag_context_guard",
            "aggregate_context_guard",
            "dlp",
            "output_guard",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be a boolean")

    @property
    def profile_id(self) -> str:
        """Return a deterministic identity derived only from all controls."""
        canonical = json.dumps(
            {
                "aggregate_context_guard": self.aggregate_context_guard,
                "dlp": self.dlp,
                "input_guard": self.input_guard,
                "output_guard": self.output_guard,
                "provenance_guard": self.provenance_guard,
                "rag_context_guard": self.rag_context_guard,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


ALL_ON = GuardProfile()


@dataclass(frozen=True)
class StageResult:
    """One pipeline stage's outcome, safe to serialize directly in an API
    response or audit log -- never carries raw prompt/context/output text."""

    stage: str
    decision: Decision | None
    reason_code: str
    detail: str | None = None


@dataclass(frozen=True)
class ProvenanceSummary:
    """A safe, per-hit summary of a retrieved chunk's provenance and
    whether it was accepted into the LLM context. Deliberately excludes
    the chunk's full text and raw metadata -- see
    `docs/modernization-v2-architecture.md` §6, "Do not return full
    retrieved context by default"."""

    document_id: str
    chunk_id: str
    title: str
    source_type: str
    classification: str
    trust_level: str
    rank: int
    retrieval_score: float
    status: str  # "accepted" | "rejected"
    reason_code: str


@dataclass(frozen=True)
class RagPipelineResult:
    """The complete, typed outcome of one `run_rag_query(...)` call.

    `error_category` is populated only for infrastructure-style failures
    (retrieval/provider/DLP failure, unexpected internal error) -- pure
    guard decisions (blocked input, rejected provenance, blocked context)
    leave it `None` since they are not errors, they are the pipeline
    working as designed.
    """

    request_id: str
    final_decision: Decision
    answer: str
    retrieved_count: int
    accepted_context_count: int
    rejected_context_count: int
    provenance: tuple[ProvenanceSummary, ...] = field(default_factory=tuple)
    stage_results: tuple[StageResult, ...] = field(default_factory=tuple)
    redaction_count: int = 0
    dlp_finding_categories: dict[str, int] = field(default_factory=dict)
    latency_ms: dict[str, float] = field(default_factory=dict)
    stop_reason: str = "allowed"
    provider_called: bool = False
    error_category: str | None = None
