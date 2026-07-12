"""End-to-end RAG security pipeline orchestration (Phase 12C).

    User query
    -> Input Guard
    -> SQLite BM25 Retrieval (server-side, Phase 12B)
    -> Provenance/Trust Guard
    -> RAG Context Guard (per chunk, then a bounded aggregate pass)
    -> Mock LLM Provider
    -> Centralized DLP
    -> Output Guard
    -> Structured Audit
    -> Safe API Response

This is a **new, additive** pipeline behind `POST /v1/rag/query`
(`app/api/routes.py`). It does not change `POST /v1/gateway/chat`
(`app/services/gateway.py`) in any way -- that endpoint still uses
caller-supplied `context_chunks` only and never calls this module.

Every stop path below returns a `RagPipelineResult` rather than raising,
except for the two retrieval-layer exceptions
(`EmptySearchQueryError`, `FTS5UnavailableError`) which are allowed to
propagate to the route, exactly like `POST /v1/retrieve` already does --
see `app/api/routes.py`. All other unexpected exceptions from any guard
stage are caught **inside** this module and mapped to a fail-closed
`Decision.BLOCK` outcome for that stage, per this phase's "guard
exceptions fail closed" requirement -- a bug in one guard degrades to a
safe refusal, not an unhandled 500 and not an open pipeline.

This module never reads or branches on `is_poisoned`, `expected_decision`,
or any other benchmark-only ground-truth field -- `RetrievalHit` (Phase
12B) has no such fields, so there is nothing here that could accidentally
do so.
"""
from __future__ import annotations

import hashlib
import time
import uuid

from app.core.config import settings
from app.core.decisions import Decision, most_severe
from app.core.pipeline import ProvenanceSummary, RagPipelineResult, StageResult
from app.guards.dlp_guard import DLPResult, scan_and_redact
from app.guards.input_guard import evaluate_input
from app.guards.output_guard import evaluate_output
from app.guards.provenance_guard import ProvenanceDecision, evaluate_provenance
from app.guards.rag_guard import evaluate_rag_context
from app.retrieval.base import Retriever
from app.retrieval.models import RetrievalQuery
from app.schemas.requests import RAGContextChunk
from app.services.audit_logger import log_event
from app.services.llm_provider import BaseLLMProvider, LLMProviderRequest, get_llm_provider

_STOPPING_DECISIONS = (Decision.BLOCK, Decision.HUMAN_REVIEW)

# Machine-readable stop-reason codes -- see module docstring's pipeline
# diagram and this phase's "Fail-closed stop paths" requirement. Every
# `RagPipelineResult.stop_reason` is one of these.
STOP_ALLOWED = "allowed"
STOP_INPUT_BLOCKED = "input_blocked"
STOP_NO_HITS = "no_hits"
STOP_ALL_REJECTED_PROVENANCE = "all_rejected_provenance"
STOP_ALL_CONTEXT_BLOCKED = "all_context_blocked"
STOP_AGGREGATE_CONTEXT_BLOCKED = "aggregate_context_blocked"
STOP_PROVIDER_FAILED = "provider_failed"
STOP_DLP_FAILED = "dlp_failed"
STOP_OUTPUT_BLOCKED = "output_blocked"
STOP_INTERNAL_ERROR = "internal_error"

_ANSWER_INPUT_BLOCKED = (
    "Your query was blocked by the Input Guard and was not used for retrieval. "
    "Reason(s): {reasons}"
)
_ANSWER_NO_HITS = "No relevant information was found for this query."
_ANSWER_ALL_REJECTED_PROVENANCE = (
    "Retrieved content could not be verified as coming from an approved source "
    "and was excluded before reaching the language model."
)
_ANSWER_ALL_CONTEXT_BLOCKED = (
    "Retrieved content was blocked by the RAG Context Guard and was not sent to "
    "the language model."
)
_ANSWER_AGGREGATE_BLOCKED = (
    "The combined retrieved context was blocked by the RAG Context Guard "
    "(coordinated-instruction check) and was not sent to the language model."
)
_ANSWER_PROVIDER_FAILED = "The language model provider failed to generate a response."
_ANSWER_DLP_FAILED = "The response could not be safely inspected for sensitive content and was withheld."
_ANSWER_OUTPUT_BLOCKED = "The generated response was blocked by the Output Guard before being returned."
_ANSWER_INTERNAL_ERROR = "An unexpected internal error occurred while processing this query."

_AGGREGATE_PER_CHUNK_EXCERPT_CHARS = 400


def _now_ms() -> float:
    return time.perf_counter() * 1000.0


def _build_aggregate_text(chunks: list[RAGContextChunk], max_chars: int) -> str:
    """Join bounded, normalized excerpts from the final accepted chunks
    into one aggregate view, for the cross-chunk coordination check below
    (Phase 12A audit resolution, Grok Critical 2 -- Phase 12C must
    explicitly decide whether a lightweight aggregate check is
    implemented; this is that decision, chosen over silently deferring
    it). Bounded by `max_chars` total, not per chunk, so a large accepted
    set cannot make this check unbounded."""
    parts: list[str] = []
    budget = max_chars
    for chunk in chunks:
        if budget <= 0:
            break
        excerpt = chunk.text[:_AGGREGATE_PER_CHUNK_EXCERPT_CHARS][:budget]
        if not excerpt:
            continue
        parts.append(excerpt)
        budget -= len(excerpt)
    return "\n\n".join(parts)


def _safe_rag_context_decision(chunks: list[RAGContextChunk]):
    """Run the existing RAG Context Guard, failing closed (BLOCK) on any
    unexpected exception instead of letting it escape."""
    try:
        return evaluate_rag_context(chunks), None
    except Exception as exc:  # noqa: BLE001 -- deliberate fail-closed safety net
        return None, str(type(exc).__name__)


def run_rag_query(
    *,
    query: str,
    top_k: int,
    retriever: Retriever,
    request_id: str | None = None,
    provider: BaseLLMProvider | None = None,
) -> RagPipelineResult:
    """Run the full Phase 12C pipeline for one query.

    Raises `app.retrieval.sqlite_bm25.EmptySearchQueryError` or
    `FTS5UnavailableError` directly (not caught here) -- the caller
    (`app/api/routes.py`) maps these to the same HTTP status codes
    `POST /v1/retrieve` already uses for the same exceptions, per this
    phase's "use existing API conventions" instruction. Every other stop
    path returns a `RagPipelineResult` instead of raising.
    """
    request_id = request_id or str(uuid.uuid4())
    t_start = _now_ms()
    latency_ms: dict[str, float] = {}
    stage_results: list[StageResult] = []

    # -- 1. Input Guard ----------------------------------------------
    t0 = _now_ms()
    try:
        input_result = evaluate_input(query)
    except Exception:  # noqa: BLE001 -- fail closed
        stage_results.append(
            StageResult(
                stage="input_guard", decision=Decision.BLOCK,
                reason_code="input_guard_exception",
            )
        )
        return _finalize(
            request_id=request_id, final_decision=Decision.BLOCK,
            answer=_ANSWER_INTERNAL_ERROR, retrieved_count=0,
            accepted_context_count=0, rejected_context_count=0,
            provenance=[], stage_results=stage_results, redaction_count=0,
            latency_ms=_with_total(latency_ms, t_start), stop_reason=STOP_INTERNAL_ERROR,
            provider_called=False, error_category="input_guard_exception",
            input_decision=None, rag_decision=None, output_decision=None,
            provider_metadata=None, query=query,
        )
    latency_ms["input_guard"] = _now_ms() - t0
    stage_results.append(
        StageResult(stage="input_guard", decision=input_result.decision, reason_code="input_guard_decision")
    )

    if input_result.decision in _STOPPING_DECISIONS:
        reasons = "; ".join(input_result.reasons) or "policy violation"
        return _finalize(
            request_id=request_id, final_decision=input_result.decision,
            answer=_ANSWER_INPUT_BLOCKED.format(reasons=reasons), retrieved_count=0,
            accepted_context_count=0, rejected_context_count=0,
            provenance=[], stage_results=stage_results, redaction_count=0,
            latency_ms=_with_total(latency_ms, t_start), stop_reason=STOP_INPUT_BLOCKED,
            provider_called=False, error_category=None,
            input_decision=input_result, rag_decision=None, output_decision=None,
            provider_metadata=None, query=query,
        )

    effective_query = (
        (input_result.sanitized_text or "") if input_result.decision == Decision.SANITIZE else query
    )

    # -- 2. Retrieval (server-side only; may raise, see docstring) -----
    t0 = _now_ms()
    retrieval_result = retriever.search(RetrievalQuery(query=effective_query, top_k=top_k))
    latency_ms["retrieval"] = _now_ms() - t0
    stage_results.append(
        StageResult(
            stage="retrieval", decision=None, reason_code="retrieval_completed",
            detail=f"hits={len(retrieval_result.hits)}",
        )
    )

    if not retrieval_result.hits:
        return _finalize(
            request_id=request_id, final_decision=Decision.ALLOW,
            answer=_ANSWER_NO_HITS, retrieved_count=0,
            accepted_context_count=0, rejected_context_count=0,
            provenance=[], stage_results=stage_results, redaction_count=0,
            latency_ms=_with_total(latency_ms, t_start), stop_reason=STOP_NO_HITS,
            provider_called=False, error_category=None,
            input_decision=input_result, rag_decision=None, output_decision=None,
            provider_metadata=None, query=query,
        )

    # -- 3. Provenance/Trust Guard -------------------------------------
    t0 = _now_ms()
    try:
        provenance_decisions: list[ProvenanceDecision] = evaluate_provenance(list(retrieval_result.hits))
    except Exception:  # noqa: BLE001 -- fail closed: reject every hit
        provenance_decisions = [
            ProvenanceDecision(hit=hit, accepted=False, reason_code="provenance_guard_exception")
            for hit in retrieval_result.hits
        ]
    latency_ms["provenance_guard"] = _now_ms() - t0
    accepted_hits = [d.hit for d in provenance_decisions if d.accepted]
    stage_results.append(
        StageResult(
            stage="provenance_guard", decision=None, reason_code="provenance_evaluated",
            detail=f"accepted={len(accepted_hits)}/{len(provenance_decisions)}",
        )
    )

    if not accepted_hits:
        provenance_summaries = _summaries_from_provenance(provenance_decisions, {}, False)
        return _finalize(
            request_id=request_id, final_decision=Decision.BLOCK,
            answer=_ANSWER_ALL_REJECTED_PROVENANCE, retrieved_count=len(retrieval_result.hits),
            accepted_context_count=0, rejected_context_count=len(retrieval_result.hits),
            provenance=provenance_summaries, stage_results=stage_results, redaction_count=0,
            latency_ms=_with_total(latency_ms, t_start), stop_reason=STOP_ALL_REJECTED_PROVENANCE,
            provider_called=False, error_category=None,
            input_decision=input_result, rag_decision=None, output_decision=None,
            provider_metadata=None, query=query,
        )

    # -- 4. RAG Context Guard, per accepted chunk ----------------------
    # context_outcomes maps chunk_id -> (accepted, reason_code, decision).
    # `decision` is kept as the actual Decision enum member (not
    # re-parsed out of reason_code later) so per-chunk severity can be
    # folded into final_decision without string-splitting a value that
    # can itself contain an underscore (e.g. Decision.LOG_ONLY == "log_only").
    t0 = _now_ms()
    context_outcomes: dict[str, tuple[bool, str, Decision]] = {}
    final_chunks: list[RAGContextChunk] = []
    for hit in accepted_hits:
        candidate = RAGContextChunk(doc_id=hit.document_id, text=hit.text, metadata=dict(hit.metadata))
        result, exc_name = _safe_rag_context_decision([candidate])
        if result is None:
            context_outcomes[hit.chunk_id] = (False, "context_guard_exception", Decision.BLOCK)
            stage_results.append(
                StageResult(
                    stage="rag_context_guard", decision=Decision.BLOCK,
                    reason_code="context_guard_exception", detail=f"chunk_id={hit.chunk_id}",
                )
            )
            continue
        if result.decision in _STOPPING_DECISIONS:
            context_outcomes[hit.chunk_id] = (False, f"context_guard_{result.decision.value}", result.decision)
            stage_results.append(
                StageResult(
                    stage="rag_context_guard", decision=result.decision,
                    reason_code=f"context_guard_{result.decision.value}", detail=f"chunk_id={hit.chunk_id}",
                )
            )
            continue
        effective_chunk = (
            result.sanitized_chunks[0]
            if result.decision == Decision.SANITIZE and result.sanitized_chunks
            else candidate
        )
        context_outcomes[hit.chunk_id] = (True, f"context_guard_{result.decision.value}", result.decision)
        stage_results.append(
            StageResult(
                stage="rag_context_guard", decision=result.decision,
                reason_code=f"context_guard_{result.decision.value}", detail=f"chunk_id={hit.chunk_id}",
            )
        )
        final_chunks.append(effective_chunk)
    latency_ms["rag_context_guard"] = _now_ms() - t0

    if not final_chunks:
        provenance_summaries = _summaries_from_provenance(provenance_decisions, context_outcomes, False)
        return _finalize(
            request_id=request_id, final_decision=Decision.BLOCK,
            answer=_ANSWER_ALL_CONTEXT_BLOCKED, retrieved_count=len(retrieval_result.hits),
            accepted_context_count=0, rejected_context_count=len(retrieval_result.hits),
            provenance=provenance_summaries, stage_results=stage_results, redaction_count=0,
            latency_ms=_with_total(latency_ms, t_start), stop_reason=STOP_ALL_CONTEXT_BLOCKED,
            provider_called=False, error_category=None,
            input_decision=input_result, rag_decision=None, output_decision=None,
            provider_metadata=None, query=query,
        )

    # -- 5. Bounded aggregate cross-chunk inspection --------------------
    t0 = _now_ms()
    aggregate_text = _build_aggregate_text(final_chunks, settings.rag_max_aggregate_context_chars)
    aggregate_result, aggregate_exc = _safe_rag_context_decision(
        [RAGContextChunk(doc_id="__aggregate__", text=aggregate_text, metadata={})]
    )
    latency_ms["aggregate_context_guard"] = _now_ms() - t0
    aggregate_decision = aggregate_result.decision if aggregate_result else Decision.BLOCK
    aggregate_blocked = aggregate_exc is not None or aggregate_decision in _STOPPING_DECISIONS
    stage_results.append(
        StageResult(
            stage="aggregate_context_guard",
            decision=aggregate_decision,
            reason_code=("aggregate_guard_exception" if aggregate_exc else f"aggregate_{aggregate_decision.value}"),
        )
    )

    if aggregate_blocked:
        provenance_summaries = _summaries_from_provenance(provenance_decisions, context_outcomes, True)
        return _finalize(
            request_id=request_id, final_decision=Decision.BLOCK,
            answer=_ANSWER_AGGREGATE_BLOCKED, retrieved_count=len(retrieval_result.hits),
            accepted_context_count=0, rejected_context_count=len(retrieval_result.hits),
            provenance=provenance_summaries, stage_results=stage_results, redaction_count=0,
            latency_ms=_with_total(latency_ms, t_start), stop_reason=STOP_AGGREGATE_CONTEXT_BLOCKED,
            provider_called=False, error_category=None,
            input_decision=input_result, rag_decision=aggregate_result, output_decision=None,
            provider_metadata=None, query=query,
        )

    # -- 6. Mock LLM Provider (approved context only) -------------------
    t0 = _now_ms()
    active_provider = provider or get_llm_provider(settings.llm_provider)
    try:
        provider_result = active_provider.generate(
            LLMProviderRequest(
                prompt=query, sanitized_prompt=effective_query, context_chunks=final_chunks,
                metadata={}, request_id=request_id,
            )
        )
    except Exception:  # noqa: BLE001 -- fail closed
        provenance_summaries = _summaries_from_provenance(provenance_decisions, context_outcomes, False)
        stage_results.append(
            StageResult(stage="provider", decision=Decision.BLOCK, reason_code="provider_exception")
        )
        return _finalize(
            request_id=request_id, final_decision=Decision.BLOCK,
            answer=_ANSWER_PROVIDER_FAILED, retrieved_count=len(retrieval_result.hits),
            accepted_context_count=len(final_chunks),
            rejected_context_count=len(retrieval_result.hits) - len(final_chunks),
            provenance=provenance_summaries, stage_results=stage_results, redaction_count=0,
            latency_ms=_with_total(latency_ms, t_start), stop_reason=STOP_PROVIDER_FAILED,
            provider_called=True, error_category="provider_failed",
            input_decision=input_result, rag_decision=aggregate_result, output_decision=None,
            provider_metadata=None, query=query,
        )
    latency_ms["provider"] = _now_ms() - t0
    stage_results.append(StageResult(stage="provider", decision=None, reason_code="provider_completed"))

    provider_metadata = {
        "provider_name": provider_result.provider_name,
        "model_name": provider_result.model_name,
        "is_mock": provider_result.is_mock,
    }

    # -- 7. Centralized DLP (redact provider output) ---------------------
    t0 = _now_ms()
    try:
        dlp_result: DLPResult = scan_and_redact(provider_result.text, max_chars=settings.dlp_max_inspect_chars)
    except Exception:  # noqa: BLE001 -- fail closed: never return raw provider output
        provenance_summaries = _summaries_from_provenance(provenance_decisions, context_outcomes, False)
        stage_results.append(StageResult(stage="dlp", decision=Decision.BLOCK, reason_code="dlp_exception"))
        return _finalize(
            request_id=request_id, final_decision=Decision.BLOCK,
            answer=_ANSWER_DLP_FAILED, retrieved_count=len(retrieval_result.hits),
            accepted_context_count=len(final_chunks),
            rejected_context_count=len(retrieval_result.hits) - len(final_chunks),
            provenance=provenance_summaries, stage_results=stage_results, redaction_count=0,
            latency_ms=_with_total(latency_ms, t_start), stop_reason=STOP_DLP_FAILED,
            provider_called=True, error_category="dlp_failed",
            input_decision=input_result, rag_decision=aggregate_result, output_decision=None,
            provider_metadata=provider_metadata, query=query,
        )
    latency_ms["dlp"] = _now_ms() - t0
    stage_results.append(
        StageResult(
            stage="dlp", decision=None, reason_code="dlp_completed",
            detail=f"redaction_count={dlp_result.redaction_count}",
        )
    )

    # -- 8. Output Guard (on redacted text) -------------------------------
    t0 = _now_ms()
    try:
        output_result = evaluate_output(dlp_result.redacted_text)
    except Exception:  # noqa: BLE001 -- fail closed
        output_result = None
    latency_ms["output_guard"] = _now_ms() - t0

    if output_result is None or output_result.decision in _STOPPING_DECISIONS:
        decision = output_result.decision if output_result else Decision.BLOCK
        reason = "output_guard_exception" if output_result is None else f"output_guard_{decision.value}"
        stage_results.append(StageResult(stage="output_guard", decision=decision, reason_code=reason))
        provenance_summaries = _summaries_from_provenance(provenance_decisions, context_outcomes, False)
        return _finalize(
            request_id=request_id, final_decision=most_severe([input_result.decision, aggregate_decision, decision]),
            answer=_ANSWER_OUTPUT_BLOCKED, retrieved_count=len(retrieval_result.hits),
            accepted_context_count=len(final_chunks),
            rejected_context_count=len(retrieval_result.hits) - len(final_chunks),
            provenance=provenance_summaries, stage_results=stage_results,
            redaction_count=dlp_result.redaction_count,
            latency_ms=_with_total(latency_ms, t_start), stop_reason=STOP_OUTPUT_BLOCKED,
            provider_called=True, error_category=None,
            input_decision=input_result, rag_decision=aggregate_result, output_decision=output_result,
            provider_metadata=provider_metadata, query=query,
        )

    stage_results.append(
        StageResult(stage="output_guard", decision=output_result.decision, reason_code=f"output_guard_{output_result.decision.value}")
    )
    final_text = (
        output_result.sanitized_text
        if output_result.decision == Decision.SANITIZE and output_result.sanitized_text
        else dlp_result.redacted_text
    )

    # -- 9. Allowed: assemble the final safe result -----------------------
    per_chunk_decisions = [outcome[2] for outcome in context_outcomes.values() if outcome[0]]
    final_decision = most_severe(
        [input_result.decision, aggregate_decision, output_result.decision, *per_chunk_decisions]
    )
    provenance_summaries = _summaries_from_provenance(provenance_decisions, context_outcomes, False)

    return _finalize(
        request_id=request_id, final_decision=final_decision,
        answer=final_text, retrieved_count=len(retrieval_result.hits),
        accepted_context_count=len(final_chunks),
        rejected_context_count=len(retrieval_result.hits) - len(final_chunks),
        provenance=provenance_summaries, stage_results=stage_results,
        redaction_count=dlp_result.redaction_count,
        latency_ms=_with_total(latency_ms, t_start), stop_reason=STOP_ALLOWED,
        provider_called=True, error_category=None,
        input_decision=input_result, rag_decision=aggregate_result, output_decision=output_result,
        provider_metadata=provider_metadata, query=query,
        dlp_findings=dlp_result.findings,
    )


def _summaries_from_provenance(
    provenance_decisions: list[ProvenanceDecision],
    context_outcomes: dict[str, tuple[bool, str, Decision]],
    aggregate_blocked: bool,
) -> list[ProvenanceSummary]:
    summaries: list[ProvenanceSummary] = []
    for decision in provenance_decisions:
        hit = decision.hit
        if not decision.accepted:
            status, reason_code = "rejected", decision.reason_code
        else:
            outcome = context_outcomes.get(hit.chunk_id)
            if outcome is None:
                status, reason_code = "rejected", "not_evaluated"
            elif not outcome[0]:
                status, reason_code = "rejected", outcome[1]
            elif aggregate_blocked:
                status, reason_code = "rejected", "aggregate_context_blocked"
            else:
                status, reason_code = "accepted", "allowed_source"
        summaries.append(
            ProvenanceSummary(
                document_id=hit.document_id, chunk_id=hit.chunk_id, title=hit.title,
                source_type=hit.source_type, classification=hit.classification,
                trust_level=hit.trust_level, rank=hit.rank, retrieval_score=hit.retrieval_score,
                status=status, reason_code=reason_code,
            )
        )
    return summaries


def _finalize(
    *,
    request_id: str,
    final_decision: Decision,
    answer: str,
    retrieved_count: int,
    accepted_context_count: int,
    rejected_context_count: int,
    provenance: list[ProvenanceSummary],
    stage_results: list[StageResult],
    redaction_count: int,
    latency_ms: dict[str, float],
    stop_reason: str,
    provider_called: bool,
    error_category: str | None,
    input_decision,
    rag_decision,
    output_decision,
    provider_metadata: dict | None,
    query: str,
    dlp_findings: tuple = (),
) -> RagPipelineResult:
    result = RagPipelineResult(
        request_id=request_id,
        final_decision=final_decision,
        answer=answer,
        retrieved_count=retrieved_count,
        accepted_context_count=accepted_context_count,
        rejected_context_count=rejected_context_count,
        provenance=tuple(provenance),
        stage_results=tuple(stage_results),
        redaction_count=redaction_count,
        latency_ms=latency_ms,
        stop_reason=stop_reason,
        provider_called=provider_called,
        error_category=error_category,
    )

    # Never log the raw query: it may contain sensitive enterprise content
    # pulled in by natural-language phrasing (unlike the other endpoints'
    # redacted-preview convention). Only a non-reversible hash + length.
    query_hash = hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]
    provenance_categories: dict[str, int] = {}
    for item in provenance:
        provenance_categories[item.trust_level] = provenance_categories.get(item.trust_level, 0) + 1
    dlp_categories: dict[str, int] = {}
    for finding in dlp_findings:
        dlp_categories[finding.category] = dlp_categories.get(finding.category, 0) + finding.count

    safe_metadata = {
        "query_hash": query_hash,
        "query_length": len(query),
        "retrieved_count": retrieved_count,
        "accepted_context_count": accepted_context_count,
        "rejected_context_count": rejected_context_count,
        "stop_reason": stop_reason,
        "provider_called": provider_called,
        "redaction_count": redaction_count,
        "dlp_finding_categories": dlp_categories,
        "provenance_trust_categories": provenance_categories,
        "stage_reason_codes": [
            {"stage": sr.stage, "reason_code": sr.reason_code} for sr in stage_results
        ],
        "latency_ms": latency_ms,
        "error_category": error_category,
    }

    log_event(
        endpoint="/v1/rag/query",
        request_id=request_id,
        input_preview=None,
        input_decision=input_decision,
        rag_decision=rag_decision,
        output_decision=output_decision,
        final_decision=final_decision,
        reasons=[sr.reason_code for sr in stage_results] or [stop_reason],
        metadata=safe_metadata,
        provider_metadata=provider_metadata,
    )
    return result


def _with_total(latency_ms: dict[str, float], t_start: float) -> dict[str, float]:
    """Add a `"total"` entry (wall-clock time across every stage that
    actually ran) to a stage-timing dict, without mutating the caller's
    dict in place."""
    return {**latency_ms, "total": _now_ms() - t_start}
