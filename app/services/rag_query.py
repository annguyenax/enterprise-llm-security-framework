"""End-to-end RAG security pipeline orchestration (Phase 12C).

    User query
    -> Input Guard
    -> SQLite BM25 Retrieval (server-side, Phase 12B)
    -> Provenance/Trust Guard
    -> RAG Context Guard (per chunk, then a bounded aggregate pass that
       governs exactly what reaches the provider -- see
       `_bound_chunks_for_aggregate`)
    -> Mock LLM Provider (sanitized query only, inspected context only)
    -> Centralized DLP
    -> Output Guard
    -> Structured Audit
    -> Safe API Response

This is a **new, additive** pipeline behind `POST /v1/rag/query`
(`app/api/routes.py`). It does not change `POST /v1/gateway/chat`
(`app/services/gateway.py`) in any way -- that endpoint still uses
caller-supplied `context_chunks` only and never calls this module.

Every stop path below returns a `RagPipelineResult` rather than raising,
except for retrieval-layer exceptions (`EmptySearchQueryError`,
`FTS5UnavailableError`, or any other unexpected retrieval failure), which
are allowed to propagate to the route, exactly like `POST /v1/retrieve`
already does -- see `app/api/routes.py`. **Every such propagating
exception is still audited first** (Phase 12C Code X audit, Major #3):
a safe terminal audit event is emitted before the exception is
re-raised, so a retrieval or provider-factory failure is never silently
un-audited just because it maps to an HTTP error instead of a 200
response. All other unexpected exceptions from any guard stage are
caught **inside** this module and mapped to a fail-closed `Decision.BLOCK`
outcome for that stage, per this phase's "guard exceptions fail closed"
requirement -- a bug in one guard degrades to a safe refusal, not an
unhandled 500 and not an open pipeline.

This module never reads or branches on `is_poisoned`, `expected_decision`,
or any other benchmark-only ground-truth field -- `RetrievalHit` (Phase
12B) has no such fields, so there is nothing here that could accidentally
do so.
"""
from __future__ import annotations

import dataclasses
import hashlib
import time
import uuid

from app.core.config import settings
from app.core.decisions import Decision, most_severe
from app.core.pipeline import ALL_ON, GuardProfile, ProvenanceSummary, RagPipelineResult, StageResult
from app.guards.dlp_guard import DLPResult, scan_and_redact
from app.guards.input_guard import evaluate_input
from app.guards.output_guard import evaluate_output
from app.guards.provenance_guard import ProvenanceDecision, evaluate_provenance
from app.guards.rag_guard import evaluate_rag_context
from app.retrieval.base import Retriever
from app.retrieval.models import RetrievalHit, RetrievalQuery
from app.schemas.requests import RAGContextChunk
from app.services.audit_logger import log_event
from app.services.llm_provider import BaseLLMProvider, LLMProviderRequest, get_llm_provider

_STOPPING_DECISIONS = (Decision.BLOCK, Decision.HUMAN_REVIEW)

# The aggregate stage specifically fails closed on SANITIZE too, unlike
# every other stage -- see _bound_chunks_for_aggregate's docstring and
# the Major #2 fix note below for why a "sanitized aggregate" cannot be
# safely honored.
_AGGREGATE_STOPPING_DECISIONS = (Decision.BLOCK, Decision.HUMAN_REVIEW, Decision.SANITIZE)

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
STOP_RETRIEVAL_FAILED = "retrieval_failed"
# Added per the Code X final re-audit (terminal audit coverage): both of
# these are stop reasons for controlled failures that happen OUTSIDE
# run_rag_query_uncommitted's own return paths -- a configured top_k
# policy rejection (before the pipeline runs at all) and a response-
# construction failure (after the pipeline has already computed an
# outcome, but before that outcome was successfully turned into an API
# response) -- see audit_top_k_rejected and mark_response_construction_failed.
STOP_TOP_K_REJECTED = "top_k_rejected"
STOP_RESPONSE_CONSTRUCTION_FAILED = "response_construction_failed"

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
_AGGREGATE_SEPARATOR = "\n\n"


def _now_ms() -> float:
    return time.perf_counter() * 1000.0


def _with_total(latency_ms: dict[str, float], t_start: float) -> dict[str, float]:
    """Add a `"total"` entry (wall-clock time across every stage that
    actually ran) to a stage-timing dict, without mutating the caller's
    dict in place."""
    return {**latency_ms, "total": _now_ms() - t_start}


def _contain_provider_output(text: str, max_chars: int) -> tuple[str, bool]:
    """Apply the always-on provider-output bound independently of DLP.

    Phase 12C enforced this same cap inside `scan_and_redact`. Phase
    12E.1 must preserve it even when DLP regex inspection is disabled,
    so orchestration now applies the cap first and lets the DLP branch
    inspect only that bounded value. The discarded suffix is never
    returned, inspected, logged, or passed to Output Guard.
    """
    if not isinstance(text, str):
        raise TypeError("provider output must be a string")
    if type(max_chars) is not int or max_chars <= 0:
        raise ValueError("max_chars must be a positive integer")
    return text[:max_chars], len(text) > max_chars


def _bound_chunks_for_aggregate(
    pairs: list[tuple[RetrievalHit, RAGContextChunk]], max_total_chars: int,
) -> tuple[list[tuple[RetrievalHit, RAGContextChunk]], list[RetrievalHit], str]:
    """Deterministically build the exact bounded chunk set that is both
    (a) inspected by the aggregate RAG Context Guard pass and (b) sent to
    the Mock LLM Provider -- the identical representation, so provider
    context can never diverge from what was actually inspected.

    **Fixed per the Phase 12C Code X audit (Major #2):** the previous
    implementation inspected only bounded *excerpts* joined into a
    throwaway string, then separately sent the FULL, untruncated original
    chunk text to the provider regardless of what the aggregate check
    saw -- an attacker could pad content past the excerpt boundary (each
    chunk was excerpted at 400 chars for inspection, but the whole chunk
    still reached the provider) and still have the uninspected material
    reach the provider. Separator length between joined excerpts was also
    excluded from the character budget, letting the true joined length
    exceed the configured maximum.

    Now: each chunk's text is truncated to at most
    `_AGGREGATE_PER_CHUNK_EXCERPT_CHARS`, further bounded by its
    remaining share of `max_total_chars`; the `"\\n\\n"` separator between
    chunks is charged against that same total budget; once the budget is
    exhausted, remaining chunks are excluded entirely (never partially
    included) -- and this exact bounded/excluded outcome is what both the
    aggregate inspector and the provider see, byte for byte.

    Returns `(included, excluded, aggregate_text)`, where `included` is
    the ordered list of (hit, bounded-and-possibly-truncated chunk) pairs
    that fit the budget, `excluded` is the hits that did not (in original
    order), and `aggregate_text` is exactly `included`'s chunk texts
    joined by the separator -- never longer than `max_total_chars`.
    """
    included: list[tuple[RetrievalHit, RAGContextChunk]] = []
    excluded: list[RetrievalHit] = []
    parts: list[str] = []
    budget = max_total_chars
    for hit, chunk in pairs:
        separator_cost = len(_AGGREGATE_SEPARATOR) if parts else 0
        available = budget - separator_cost
        if available <= 0:
            excluded.append(hit)
            continue
        excerpt = chunk.text[:_AGGREGATE_PER_CHUNK_EXCERPT_CHARS][:available]
        if not excerpt:
            excluded.append(hit)
            continue
        included.append((hit, RAGContextChunk(doc_id=chunk.doc_id, text=excerpt, metadata=chunk.metadata)))
        parts.append(excerpt)
        budget -= separator_cost + len(excerpt)
    aggregate_text = _AGGREGATE_SEPARATOR.join(parts)
    return included, excluded, aggregate_text


def _safe_rag_context_decision(chunks: list[RAGContextChunk]):
    """Run the existing RAG Context Guard, failing closed (BLOCK) on any
    unexpected exception instead of letting it escape."""
    try:
        return evaluate_rag_context(chunks), None
    except Exception as exc:  # noqa: BLE001 -- deliberate fail-closed safety net
        return None, str(type(exc).__name__)


def _audit_failure(
    *,
    request_id: str,
    query: str,
    stage_results: list[StageResult],
    latency_ms: dict[str, float],
    stop_reason: str,
    input_decision=None,
) -> None:
    """Emit a safe terminal audit event for a controlled failure that is
    about to propagate as an exception (retrieval or provider-factory
    failures -- see the module docstring) rather than being returned as a
    `RagPipelineResult`.

    **Added per the Phase 12C Code X audit (Major #3):** these failures
    previously propagated before any `_finalize`/`log_event` call ever
    ran, so a retrieval or configuration failure produced no audit trail
    at all, even though the request reached this service. Mirrors
    `_finalize`'s safe-metadata shape without constructing a
    `RagPipelineResult`, since the caller will re-raise, not return one,
    for this path.
    """
    query_hash = hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]
    safe_metadata = {
        "query_hash": query_hash,
        "query_length": len(query),
        "stop_reason": stop_reason,
        "provider_called": False,
        "error_category": stop_reason,
        "stage_reason_codes": [
            {"stage": sr.stage, "reason_code": sr.reason_code} for sr in stage_results
        ],
        "latency_ms": latency_ms,
    }
    log_event(
        endpoint="/v1/rag/query",
        request_id=request_id,
        input_preview=None,
        input_decision=input_decision,
        rag_decision=None,
        output_decision=None,
        final_decision=Decision.BLOCK,
        reasons=[sr.reason_code for sr in stage_results] or [stop_reason],
        metadata=safe_metadata,
        provider_metadata=None,
    )


@dataclasses.dataclass(frozen=True)
class RagQueryAuditContext:
    """The guard-decision objects and raw query needed to finish the
    `/v1/rag/query` terminal audit event, kept OUT of `RagPipelineResult`
    itself -- `RagPipelineResult` is safe to hand to `app/api/routes.py`
    for building the public API response, but the objects here (e.g. the
    full `GuardDecisionResponse`) are audit-log inputs, not response
    fields, and the raw `query` in particular must never reach the API
    response at all.

    Not part of any public HTTP-facing contract. This exists specifically
    so `run_rag_query_uncommitted` can hand back everything needed to
    finish the audit event *later* (after `app/api/routes.py` confirms
    the API response object itself was built successfully), instead of
    committing the audit event immediately and unconditionally the way
    `run_rag_query` (the simpler, direct-service-caller entry point)
    still does. This is the "clear explicit internal contract" the Code
    X final re-audit asked for, in preference to a public flag.
    """

    query: str
    input_decision: object = None
    rag_decision: object = None
    output_decision: object = None
    provider_metadata: dict | None = None


def run_rag_query(
    *,
    query: str,
    top_k: int,
    retriever: Retriever,
    request_id: str | None = None,
    provider: BaseLLMProvider | None = None,
) -> RagPipelineResult:
    """Run the full Phase 12C pipeline for one query and commit its
    terminal audit event immediately.

    This is the simple entry point for direct/service callers (this
    project's own test suite included) that don't need to defer audit
    commitment -- it always audits exactly once before returning,
    matching this function's historical contract. `app/api/routes.py`
    instead calls `run_rag_query_uncommitted` directly, so it can defer
    the commit until the actual API response object has been built
    successfully -- see that function's docstring and
    `commit_rag_query_audit` for why (Code X final re-audit: a
    response-construction failure must never leave behind an earlier,
    now-inaccurate "success" audit event for the same request).
    """
    result, audit_ctx = run_rag_query_uncommitted(
        query=query, top_k=top_k, retriever=retriever, request_id=request_id, provider=provider,
    )
    commit_rag_query_audit(result, audit_ctx)
    return result


def audit_top_k_rejected(*, request_id: str, query: str, configured_max_top_k: int) -> None:
    """Emit exactly one safe terminal audit event for a `top_k` value
    that exceeds the configured Phase 12C policy maximum (distinct from
    Pydantic's static field ceiling, which FastAPI itself rejects with a
    422 before any route code runs). This is rejected by
    `app/api/routes.py` before `run_rag_query`/`run_rag_query_uncommitted`
    is ever called, and therefore before any pipeline stage -- including
    Input Guard -- executes.

    **Fixed per the Code X final re-audit:** this specific HTTP 400 path
    previously produced zero audit trail, since the route returned before
    the pipeline (and its internal audit commit) ever ran. `log_event`
    itself already fails safe (never raises, never exposes an exception)
    on a sink failure -- see its own docstring -- so this function does
    not need its own defensive wrapper around that call.
    """
    query_hash = hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]
    safe_metadata = {
        "query_hash": query_hash,
        "query_length": len(query),
        "stop_reason": STOP_TOP_K_REJECTED,
        "provider_called": False,
        "error_category": STOP_TOP_K_REJECTED,
        "configured_max_top_k": configured_max_top_k,
    }
    log_event(
        endpoint="/v1/rag/query",
        request_id=request_id,
        input_preview=None,
        input_decision=None,
        rag_decision=None,
        output_decision=None,
        final_decision=Decision.BLOCK,
        reasons=[STOP_TOP_K_REJECTED],
        metadata=safe_metadata,
        provider_metadata=None,
    )


def mark_response_construction_failed(result: RagPipelineResult) -> RagPipelineResult:
    """Build a corrected copy of `result` for the one case where the
    guard/retrieval pipeline computed successfully but the API response
    object (`RagQueryResponse`) then failed to construct from it.

    **Added per the Code X final re-audit:** `result`'s own
    `final_decision`/`stop_reason` (e.g. "allowed") describe what the
    *pipeline* computed, not what the *caller actually received* -- once
    response construction has failed, the caller gets a generic 500, so
    the terminal audit event must say so too, not the pipeline's original
    (now inaccurate) outcome. `provider_called` is preserved from `result`
    since it reflects what actually executed, not what the API layer
    later did with it; `answer` is replaced with a fixed safe string so
    the original provider text is never a factor in this corrected
    record (it already wasn't logged either way -- see
    `commit_rag_query_audit` -- but this keeps the whole object honest).
    """
    return dataclasses.replace(
        result,
        final_decision=Decision.BLOCK,
        answer=_ANSWER_INTERNAL_ERROR,
        stop_reason=STOP_RESPONSE_CONSTRUCTION_FAILED,
        error_category=STOP_RESPONSE_CONSTRUCTION_FAILED,
    )


def run_rag_query_uncommitted(
    *,
    query: str,
    top_k: int,
    retriever: Retriever,
    request_id: str | None = None,
    provider: BaseLLMProvider | None = None,
    guard_profile: GuardProfile = ALL_ON,
) -> tuple[RagPipelineResult, RagQueryAuditContext]:
    """Run the full Phase 12C pipeline for one query and return
    `(result, audit_ctx)` WITHOUT committing the terminal audit event --
    the caller must call `commit_rag_query_audit(result, audit_ctx)`
    itself once it knows what the caller-visible outcome actually is (see
    `run_rag_query` for the simple immediate-commit alternative, and
    `app/api/routes.py::rag_query` for the deferred-commit usage this was
    added for).

    May raise `app.retrieval.sqlite_bm25.EmptySearchQueryError`,
    `FTS5UnavailableError`, or another unexpected retrieval exception --
    the caller (`app/api/routes.py`) maps the first two to the same HTTP
    status codes `POST /v1/retrieve` already uses for the identical
    exceptions, per this phase's "use existing API conventions"
    instruction, and any other exception to a generic safe 500. Every
    such exception is audited (see `_audit_failure`) before it
    propagates -- there is no response-construction step for these paths
    to defer past (the route builds a plain `HTTPException` directly from
    a fixed string, not from a `RagPipelineResult`), so committing
    immediately here is already safe. Every other stop path returns a
    `RagPipelineResult` instead of raising. `guard_profile` is the sole
    internal ablation seam. Public routes omit it and therefore receive
    immutable `ALL_ON`; it is never selected from HTTP, Settings, or the
    environment.
    """
    request_id = request_id or str(uuid.uuid4())
    t_start = _now_ms()
    latency_ms: dict[str, float] = {}
    stage_results: list[StageResult] = []

    # -- 1. Input Guard ----------------------------------------------
    input_result = None
    if guard_profile.input_guard:
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
            StageResult(
                stage="input_guard", decision=input_result.decision,
                reason_code="input_guard_decision",
            )
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

        input_severity = input_result.decision
        # Effective (post-Input-Guard) query used for retrieval AND as the
        # only prompt-shaped value ever handed to the provider (see step 6
        # below and the Major #A fix note there) -- once SANITIZE has run,
        # nothing derived from the raw `query` may reach the provider.
        effective_query = (
            (input_result.sanitized_text or "")
            if input_result.decision == Decision.SANITIZE
            else query
        )
    else:
        stage_results.append(
            StageResult(
                stage="input_guard", decision=None,
                reason_code="input_guard_disabled_ablation",
            )
        )
        input_severity = Decision.ALLOW
        effective_query = query

    # -- 2. Retrieval (server-side only; may raise, see docstring) -----
    t0 = _now_ms()
    try:
        retrieval_result = retriever.search(RetrievalQuery(query=effective_query, top_k=top_k))
    except Exception as exc:
        stage_results.append(
            StageResult(
                stage="retrieval", decision=Decision.BLOCK, reason_code="retrieval_failed",
                detail=type(exc).__name__,
            )
        )
        _audit_failure(
            request_id=request_id, query=query, stage_results=stage_results,
            latency_ms=_with_total(latency_ms, t_start), stop_reason=STOP_RETRIEVAL_FAILED,
            input_decision=input_result,
        )
        raise
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
    if guard_profile.provenance_guard:
        t0 = _now_ms()
        provenance_exception = False
        try:
            provenance_decisions: list[ProvenanceDecision] = evaluate_provenance(
                list(retrieval_result.hits)
            )
        except Exception:  # noqa: BLE001 -- fail closed: reject every hit
            provenance_exception = True
            provenance_decisions = [
                ProvenanceDecision(
                    hit=hit, accepted=False, reason_code="provenance_guard_exception"
                )
                for hit in retrieval_result.hits
            ]
        latency_ms["provenance_guard"] = _now_ms() - t0
        accepted_hits = [d.hit for d in provenance_decisions if d.accepted]
        # Fixed per the Phase 12C Code X audit (Major #3): the stage-level
        # reason_code previously said "provenance_evaluated" unconditionally,
        # even when evaluate_provenance() had actually raised -- obscuring
        # the real failure reason in the audit trail's own stage summary.
        stage_results.append(
            StageResult(
                stage="provenance_guard",
                decision=(Decision.BLOCK if provenance_exception else None),
                reason_code=(
                    "provenance_guard_exception"
                    if provenance_exception
                    else "provenance_evaluated"
                ),
                detail=f"accepted={len(accepted_hits)}/{len(provenance_decisions)}",
            )
        )
    else:
        provenance_decisions = [
            ProvenanceDecision(
                hit=hit,
                accepted=True,
                reason_code="provenance_guard_disabled_ablation",
            )
            for hit in retrieval_result.hits
        ]
        accepted_hits = [decision.hit for decision in provenance_decisions]
        stage_results.append(
            StageResult(
                stage="provenance_guard", decision=None,
                reason_code="provenance_guard_disabled_ablation",
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
    context_outcomes: dict[str, tuple[bool, str, Decision]] = {}
    passed_pairs: list[tuple[RetrievalHit, RAGContextChunk]] = []
    if guard_profile.rag_context_guard:
        t0 = _now_ms()
        for hit in accepted_hits:
            candidate = RAGContextChunk(
                doc_id=hit.document_id, text=hit.text, metadata=dict(hit.metadata)
            )
            result, exc_name = _safe_rag_context_decision([candidate])
            if result is None:
                context_outcomes[hit.chunk_id] = (
                    False, "context_guard_exception", Decision.BLOCK,
                )
                stage_results.append(
                    StageResult(
                        stage="rag_context_guard", decision=Decision.BLOCK,
                        reason_code="context_guard_exception", detail=f"chunk_id={hit.chunk_id}",
                    )
                )
                continue
            if result.decision in _STOPPING_DECISIONS:
                context_outcomes[hit.chunk_id] = (
                    False, f"context_guard_{result.decision.value}", result.decision,
                )
                stage_results.append(
                    StageResult(
                        stage="rag_context_guard", decision=result.decision,
                        reason_code=f"context_guard_{result.decision.value}",
                        detail=f"chunk_id={hit.chunk_id}",
                    )
                )
                continue
            effective_chunk = (
                result.sanitized_chunks[0]
                if result.decision == Decision.SANITIZE and result.sanitized_chunks
                else candidate
            )
            context_outcomes[hit.chunk_id] = (
                True, f"context_guard_{result.decision.value}", result.decision,
            )
            stage_results.append(
                StageResult(
                    stage="rag_context_guard", decision=result.decision,
                    reason_code=f"context_guard_{result.decision.value}",
                    detail=f"chunk_id={hit.chunk_id}",
                )
            )
            passed_pairs.append((hit, effective_chunk))
        latency_ms["rag_context_guard"] = _now_ms() - t0
    else:
        stage_results.append(
            StageResult(
                stage="rag_context_guard", decision=None,
                reason_code="rag_context_guard_disabled_ablation",
            )
        )
        for hit in accepted_hits:
            candidate = RAGContextChunk(
                doc_id=hit.document_id, text=hit.text, metadata=dict(hit.metadata)
            )
            context_outcomes[hit.chunk_id] = (
                True, "rag_context_guard_disabled_ablation", Decision.ALLOW,
            )
            passed_pairs.append((hit, candidate))

    if not passed_pairs:
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

    # -- 5. Bounded aggregate inspection -- governs the EXACT provider ---
    # -- context (see _bound_chunks_for_aggregate's docstring, Major #2) -
    aggregate_t0 = _now_ms() if guard_profile.aggregate_context_guard else None
    bounded_pairs, excluded_by_budget, aggregate_text = _bound_chunks_for_aggregate(
        passed_pairs, settings.rag_max_aggregate_context_chars,
    )
    original_text_by_chunk_id = {hit.chunk_id: chunk.text for hit, chunk in passed_pairs}
    for included_hit, bounded_chunk in bounded_pairs:
        if bounded_chunk.text != original_text_by_chunk_id[included_hit.chunk_id]:
            context_outcomes[included_hit.chunk_id] = (
                True,
                "aggregate_budget_truncated",
                Decision.SANITIZE,
            )
    for excluded_hit in excluded_by_budget:
        context_outcomes[excluded_hit.chunk_id] = (False, "aggregate_budget_exceeded", Decision.SANITIZE)

    if not guard_profile.aggregate_context_guard:
        stage_results.append(
            StageResult(
                stage="aggregate_context_guard", decision=None,
                reason_code="aggregate_context_guard_disabled_ablation",
            )
        )

    if not bounded_pairs:
        # The entire per-chunk-accepted set was excluded by the aggregate
        # character budget -- functionally identical to all_context_blocked
        # (nothing reaches the provider), so it is reported the same way.
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

    aggregate_result = None
    if guard_profile.aggregate_context_guard:
        aggregate_result, aggregate_exc = _safe_rag_context_decision(
            [RAGContextChunk(doc_id="__aggregate__", text=aggregate_text, metadata={})]
        )
        latency_ms["aggregate_context_guard"] = _now_ms() - aggregate_t0
        aggregate_decision = aggregate_result.decision if aggregate_result else Decision.BLOCK
        # Fail closed on SANITIZE too, unlike every other stage: a sanitized
        # *joined-and-truncated* blob has no safe, deterministic mapping back
        # onto the individual RAGContextChunk objects the provider expects.
        aggregate_blocked = (
            aggregate_exc is not None
            or aggregate_decision in _AGGREGATE_STOPPING_DECISIONS
        )
        stage_results.append(
            StageResult(
                stage="aggregate_context_guard",
                decision=aggregate_decision,
                reason_code=(
                    "aggregate_guard_exception"
                    if aggregate_exc
                    else f"aggregate_{aggregate_decision.value}"
                ),
                detail=f"aggregate_chars={len(aggregate_text)}",
            )
        )
    else:
        aggregate_decision = Decision.ALLOW
        aggregate_blocked = False

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

    # The provider receives exactly the bounded/truncated chunks that
    # were just inspected as `aggregate_text` -- never the original,
    # untruncated chunk text (Major #2 fix).
    final_chunks = [chunk for _hit, chunk in bounded_pairs]

    # -- 6. Mock LLM Provider (sanitized query + inspected context only) -
    t0 = _now_ms()
    provider_called = False
    try:
        resolved_provider = provider or get_llm_provider(settings.llm_provider)
        provider_called = True
        provider_result = resolved_provider.generate(
            LLMProviderRequest(
                # Fixed per the Phase 12C Code X audit (Major #A): both
                # `prompt` and `sanitized_prompt` are now the SAME
                # post-Input-Guard `effective_query` for this pipeline --
                # the raw, pre-sanitization `query` is never placed in any
                # provider-visible field. A provider implementation that
                # reads `request.prompt` instead of `request.sanitized_prompt`
                # can therefore never see text the Input Guard removed.
                # This changes only this call site, not the shared
                # `LLMProviderRequest` contract or app/services/gateway.py's
                # own call (`/v1/gateway/chat` keeps its Phase 4-6
                # behavior unchanged, per this phase's backward-
                # compatibility requirement).
                prompt=effective_query, sanitized_prompt=effective_query,
                context_chunks=final_chunks, metadata={}, request_id=request_id,
            )
        )
    except Exception:  # noqa: BLE001 -- fail closed
        provider_reason = (
            "provider_exception" if provider_called else "provider_factory_exception"
        )
        provider_error_category = (
            STOP_PROVIDER_FAILED if provider_called else "provider_factory_failed"
        )
        provenance_summaries = _summaries_from_provenance(provenance_decisions, context_outcomes, False)
        stage_results.append(
            StageResult(stage="provider", decision=Decision.BLOCK, reason_code=provider_reason)
        )
        return _finalize(
            request_id=request_id, final_decision=Decision.BLOCK,
            answer=_ANSWER_PROVIDER_FAILED, retrieved_count=len(retrieval_result.hits),
            accepted_context_count=len(final_chunks),
            rejected_context_count=len(retrieval_result.hits) - len(final_chunks),
            provenance=provenance_summaries, stage_results=stage_results, redaction_count=0,
            latency_ms=_with_total(latency_ms, t_start), stop_reason=STOP_PROVIDER_FAILED,
            provider_called=provider_called, error_category=provider_error_category,
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

    # -- 7. Always-on output containment, then optional centralized DLP -
    if not guard_profile.dlp:
        stage_results.append(
            StageResult(
                stage="dlp", decision=None,
                reason_code="dlp_disabled_ablation",
            )
        )

    try:
        contained_output, output_truncated = _contain_provider_output(
            provider_result.text, settings.dlp_max_inspect_chars,
        )
    except Exception:  # noqa: BLE001 -- fail closed on malformed provider output/config
        provenance_summaries = _summaries_from_provenance(provenance_decisions, context_outcomes, False)
        stage_results.append(
            StageResult(
                stage="output_containment", decision=Decision.BLOCK,
                reason_code="output_containment_exception",
            )
        )
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

    if guard_profile.dlp:
        t0 = _now_ms()
        try:
            dlp_result: DLPResult = scan_and_redact(
                contained_output, max_chars=settings.dlp_max_inspect_chars,
            )
        except Exception:  # noqa: BLE001 -- fail closed: never return raw provider output
            provenance_summaries = _summaries_from_provenance(
                provenance_decisions, context_outcomes, False,
            )
            stage_results.append(
                StageResult(stage="dlp", decision=Decision.BLOCK, reason_code="dlp_exception")
            )
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
        if output_truncated and not dlp_result.truncated:
            dlp_result = dataclasses.replace(dlp_result, truncated=True)
        latency_ms["dlp"] = _now_ms() - t0
        # A DLP redaction is a security-relevant SANITIZE decision and
        # participates in final-decision severity.
        dlp_decision = (
            Decision.SANITIZE if dlp_result.redaction_count > 0 else Decision.ALLOW
        )
        stage_results.append(
            StageResult(
                stage="dlp", decision=dlp_decision,
                reason_code=(
                    "dlp_redacted" if dlp_result.redaction_count > 0 else "dlp_completed"
                ),
                detail=(
                    f"redaction_count={dlp_result.redaction_count} "
                    f"truncated={dlp_result.truncated}"
                ),
            )
        )
    else:
        dlp_result = DLPResult(
            redacted_text=contained_output,
            findings=(),
            redaction_count=0,
            truncated=output_truncated,
        )
        dlp_decision = Decision.ALLOW

    # -- 8. Output Guard (on redacted text) -------------------------------
    output_result = None
    if guard_profile.output_guard:
        t0 = _now_ms()
        try:
            output_result = evaluate_output(dlp_result.redacted_text)
        except Exception:  # noqa: BLE001 -- fail closed
            output_result = None
        latency_ms["output_guard"] = _now_ms() - t0

        if output_result is None or output_result.decision in _STOPPING_DECISIONS:
            decision = output_result.decision if output_result else Decision.BLOCK
            reason = (
                "output_guard_exception"
                if output_result is None
                else f"output_guard_{decision.value}"
            )
            stage_results.append(
                StageResult(stage="output_guard", decision=decision, reason_code=reason)
            )
            provenance_summaries = _summaries_from_provenance(
                provenance_decisions, context_outcomes, False,
            )
            return _finalize(
                request_id=request_id,
                final_decision=most_severe(
                    [input_severity, aggregate_decision, dlp_decision, decision]
                ),
                answer=_ANSWER_OUTPUT_BLOCKED, retrieved_count=len(retrieval_result.hits),
                accepted_context_count=len(final_chunks),
                rejected_context_count=len(retrieval_result.hits) - len(final_chunks),
                provenance=provenance_summaries, stage_results=stage_results,
                redaction_count=dlp_result.redaction_count,
                latency_ms=_with_total(latency_ms, t_start), stop_reason=STOP_OUTPUT_BLOCKED,
                provider_called=True, error_category=None,
                input_decision=input_result, rag_decision=aggregate_result,
                output_decision=output_result,
                provider_metadata=provider_metadata, query=query,
                dlp_findings=dlp_result.findings,
            )

        output_decision = output_result.decision
        stage_results.append(
            StageResult(
                stage="output_guard", decision=output_decision,
                reason_code=f"output_guard_{output_decision.value}",
            )
        )
        final_text = (
            output_result.sanitized_text
            if output_result.decision == Decision.SANITIZE and output_result.sanitized_text
            else dlp_result.redacted_text
        )
    else:
        output_decision = Decision.ALLOW
        final_text = dlp_result.redacted_text
        stage_results.append(
            StageResult(
                stage="output_guard", decision=None,
                reason_code="output_guard_disabled_ablation",
            )
        )

    # -- 9. Allowed: assemble the final safe result -----------------------
    per_chunk_decisions = [outcome[2] for outcome in context_outcomes.values() if outcome[0]]
    final_decision = most_severe(
        [input_severity, aggregate_decision, dlp_decision, output_decision, *per_chunk_decisions]
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
                status, reason_code = "accepted", outcome[1]
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
) -> tuple[RagPipelineResult, RagQueryAuditContext]:
    """Build the typed `RagPipelineResult` plus the audit inputs needed
    to describe it later, WITHOUT committing any audit event itself.

    **Changed per the Code X final re-audit:** this used to call
    `log_event(...)` directly and return only the `RagPipelineResult`,
    which is exactly what let a response-construction failure in
    `app/api/routes.py` leave behind an already-committed "success" audit
    event for a request the caller actually received as a 500. Building
    the result and committing the audit are now two separate steps --
    see `run_rag_query` (commits immediately, for direct/service callers)
    and `commit_rag_query_audit` (the extracted commit step,
    called explicitly once the true caller-visible outcome is known).
    """
    dlp_categories: dict[str, int] = {}
    for finding in dlp_findings:
        dlp_categories[finding.category] = (
            dlp_categories.get(finding.category, 0) + finding.count
        )

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
        dlp_finding_categories=dlp_categories,
        latency_ms=latency_ms,
        stop_reason=stop_reason,
        provider_called=provider_called,
        error_category=error_category,
    )
    audit_ctx = RagQueryAuditContext(
        query=query,
        input_decision=input_decision,
        rag_decision=rag_decision,
        output_decision=output_decision,
        provider_metadata=provider_metadata,
    )
    return result, audit_ctx


def commit_rag_query_audit(result: RagPipelineResult, audit_ctx: RagQueryAuditContext) -> None:
    """Emit exactly the one terminal `/v1/rag/query` audit event that
    describes `result` -- the extracted, previously-inline logging body
    of what `_finalize` used to do directly (see that function's
    docstring for why it was split out).

    Callers are responsible for calling this **exactly once** per
    request, for whichever outcome is actually visible to the caller --
    `run_rag_query` does so immediately; `app/api/routes.py` calls it
    only after confirming the API response object was built successfully
    (or with `mark_response_construction_failed(result)` if it was not).
    """
    # Never log the raw query: it may contain sensitive enterprise content
    # pulled in by natural-language phrasing (unlike the other endpoints'
    # redacted-preview convention). Only a non-reversible hash + length.
    query_hash = hashlib.sha256(audit_ctx.query.encode("utf-8")).hexdigest()[:16]
    provenance_categories: dict[str, int] = {}
    for item in result.provenance:
        provenance_categories[item.trust_level] = provenance_categories.get(item.trust_level, 0) + 1
    safe_metadata = {
        "query_hash": query_hash,
        "query_length": len(audit_ctx.query),
        "retrieved_count": result.retrieved_count,
        "accepted_context_count": result.accepted_context_count,
        "rejected_context_count": result.rejected_context_count,
        "stop_reason": result.stop_reason,
        "provider_called": result.provider_called,
        "redaction_count": result.redaction_count,
        "dlp_finding_categories": result.dlp_finding_categories,
        "provenance_trust_categories": provenance_categories,
        "stage_reason_codes": [
            {"stage": sr.stage, "reason_code": sr.reason_code} for sr in result.stage_results
        ],
        "latency_ms": result.latency_ms,
        "error_category": result.error_category,
    }

    log_event(
        endpoint="/v1/rag/query",
        request_id=result.request_id,
        input_preview=None,
        input_decision=audit_ctx.input_decision,
        rag_decision=audit_ctx.rag_decision,
        output_decision=audit_ctx.output_decision,
        final_decision=result.final_decision,
        reasons=[sr.reason_code for sr in result.stage_results] or [result.stop_reason],
        metadata=safe_metadata,
        provider_metadata=audit_ctx.provider_metadata,
    )
