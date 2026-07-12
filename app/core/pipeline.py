"""Typed result contracts for the Phase 12C end-to-end RAG pipeline
(`app/services/rag_query.py`).

These types exist so `POST /v1/rag/query` can return a safe, structured
summary of what happened at every stage -- retrieval counts, provenance
decisions, guard-stage outcomes, DLP redaction counts, timing -- without
ever exposing raw internals (database paths, SQL errors, stack traces,
full retrieved chunk text by default, or detected secret values). See
`docs/modernization-v2-architecture.md` §1/§6 for the target pipeline
shape this implements.

**Scope note:** `docs/modernization-v2-architecture.md` §2 also names this
module as the future home of `GuardProfile` (an ablation on/off
configuration for guard layers). That is explicitly a **Phase 12E**
concern ("target phase 12C (definition), 12E (used)") and is deliberately
**not** implemented in this pass -- the current Phase 12C task scope asks
only for a typed pipeline result, not the ablation harness. Recorded here
so the omission is visible, not silent, per `AGENT_RULES.md` rule 12.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.core.decisions import Decision


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
