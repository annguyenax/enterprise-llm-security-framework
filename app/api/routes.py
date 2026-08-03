"""API routes for the LLM Security Gateway through Phase 12C.

Phase 12B added POST /v1/documents/ingest and POST /v1/retrieve (lexical
retrieval foundation only -- see docs/modernization-v2-architecture.md §6).
Phase 12C adds POST /v1/rag/query (Input Guard -> retrieval -> Provenance/
Trust Guard -> RAG Context Guard -> Mock Provider -> DLP -> Output Guard,
see app/services/rag_query.py). POST /v1/gateway/chat remains completely
unchanged -- it still uses only caller-supplied context_chunks and never
calls the retriever or the new pipeline.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.guards.input_guard import evaluate_input
from app.guards.output_guard import evaluate_output
from app.guards.rag_guard import evaluate_rag_context
from app.retrieval.base import Retriever
from app.retrieval.models import IngestionDocument, RetrievalQuery
from app.retrieval.sqlite_bm25 import (
    EmptySearchQueryError,
    FTS5UnavailableError,
    IngestionBatchError,
    SqliteBM25Config,
    SqliteBM25Retriever,
)
from app.schemas.requests import (
    ChatRequest,
    DocumentIngestRequest,
    InputGuardRequest,
    OutputGuardRequest,
    RagQueryRequest,
    RAGGuardRequest,
    RetrieveRequest,
)
from app.schemas.responses import (
    ChatResponse,
    DocumentIngestResponse,
    GuardDecisionResponse,
    HealthResponse,
    IngestionItemResponse,
    ProvenanceItemResponse,
    RagQueryResponse,
    RAGGuardResponse,
    RetrievalHitResponse,
    RetrieveResponse,
    StageResultResponse,
)
from app.services.audit_logger import log_event
from app.services.chunking import ChunkingConfig
from app.services.gateway import run_chat
from app.services.ingestion import IngestionService, IngestionServiceConfig, IngestionValidationError
from app.services.rag_query import (
    audit_top_k_rejected,
    commit_rag_query_audit,
    mark_response_construction_failed,
    run_rag_query_uncommitted,
)

router = APIRouter()

# Module-level singletons, matching this codebase's existing convention of
# a global `settings` object (app/core/config.py). See
# docs/modernization-v2-architecture.md §2/§7.
_retriever: Retriever = SqliteBM25Retriever(
    SqliteBM25Config(
        db_path=settings.retrieval_db_path,
        busy_timeout_ms=settings.retrieval_busy_timeout_ms,
        max_query_chars=settings.retrieval_max_query_chars,
        max_query_terms=settings.retrieval_max_query_terms,
        max_top_k=settings.retrieval_max_top_k,
    )
)
# Configured resource limits are wired through explicitly -- fixed per the
# Phase 12B Codex audit (Major #4, "Configured ingestion resource limits
# are not wired to the service"): the original code constructed
# IngestionService with all-default IngestionServiceConfig/ChunkingConfig,
# so RETRIEVAL_MAX_DOCUMENT_CHARS / RETRIEVAL_CHUNK_MAX_CHARS /
# RETRIEVAL_CHUNK_OVERLAP_CHARS had no actual effect on ingestion.
_ingestion_service = IngestionService(
    _retriever,
    IngestionServiceConfig(
        max_batch_size=settings.retrieval_max_batch_size,
        chunking=ChunkingConfig(
            max_chunk_chars=settings.retrieval_chunk_max_chars,
            overlap_chars=settings.retrieval_chunk_overlap_chars,
            max_document_chars=settings.retrieval_max_document_chars,
        ),
    ),
)

# Eager capability/schema initialization at import time -- fixed per the
# Phase 12B Codex audit (Minor #1, "FTS5 capability verification is
# lazy"): the original code left initialization to the first actual
# retrieval-dependent request, so /health could report success even
# though retrieval could never work. This now fails at import time (i.e.
# at application startup, since app.main imports this module) with a
# clear FTS5UnavailableError if the local SQLite build lacks FTS5,
# matching the project's fail-closed convention elsewhere.
_retriever.initialize()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    # Kept unchanged (existing regression test asserts this exact string)
    # -- Phase 12B does not modify the health endpoint's contract.
    return HealthResponse(status="ok", service="llm-security-gateway", phase="phase-6-mock-provider")


@router.post("/v1/guard/input", response_model=GuardDecisionResponse)
def guard_input(request: InputGuardRequest) -> GuardDecisionResponse:
    result = evaluate_input(request.prompt)
    log_event(
        endpoint="/v1/guard/input",
        request_id=str(uuid.uuid4()),
        input_preview=request.prompt,
        input_decision=result,
        output_decision=None,
        final_decision=result.decision,
        reasons=result.reasons,
        metadata=request.metadata,
    )
    return result


@router.post("/v1/guard/output", response_model=GuardDecisionResponse)
def guard_output(request: OutputGuardRequest) -> GuardDecisionResponse:
    result = evaluate_output(request.output)
    log_event(
        endpoint="/v1/guard/output",
        request_id=str(uuid.uuid4()),
        input_preview=request.output,
        input_decision=None,
        output_decision=result,
        final_decision=result.decision,
        reasons=result.reasons,
        metadata=request.metadata,
    )
    return result


@router.post("/v1/guard/rag-context", response_model=RAGGuardResponse)
def guard_rag_context(request: RAGGuardRequest) -> RAGGuardResponse:
    result = evaluate_rag_context(request.context_chunks)
    preview = " || ".join(
        [request.query] + [chunk.text for chunk in request.context_chunks]
    )
    log_event(
        endpoint="/v1/guard/rag-context",
        request_id=str(uuid.uuid4()),
        input_preview=preview,
        rag_decision=result,
        final_decision=result.decision,
        reasons=result.reasons,
        metadata=request.metadata,
    )
    return result


@router.post("/v1/gateway/chat", response_model=ChatResponse)
def gateway_chat(request: ChatRequest) -> ChatResponse:
    return run_chat(request.prompt, request.context_chunks, request.metadata)


@router.post("/v1/documents/ingest", response_model=DocumentIngestResponse)
def documents_ingest(request: DocumentIngestRequest) -> DocumentIngestResponse:
    """Phase 12B: persistent document ingestion. Trust/classification are
    always server-assigned (app/core/source_policy.py) -- see
    app/schemas/requests.py's IngestionDocumentRequest for why a caller
    cannot supply them. Not wired to any guard yet; that is Phase 12C."""
    if len(request.documents) > settings.retrieval_max_batch_size:
        raise HTTPException(
            status_code=400,
            detail=f"Batch size exceeds the configured maximum of {settings.retrieval_max_batch_size}.",
        )

    documents = [
        IngestionDocument(
            external_id=item.external_id,
            source_key=item.source_key,
            title=item.title,
            text=item.text,
            metadata=item.metadata,
        )
        for item in request.documents
    ]
    request_id = str(uuid.uuid4())

    try:
        result = _ingestion_service.ingest_batch(documents, request_id=request_id)
    except FTS5UnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except IngestionValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IngestionBatchError as exc:
        # Fixed per the Phase 12B Codex audit (Minor #2, "Unexpected
        # storage exceptions lack a stable API mapping"): IngestionBatchError
        # embeds the raw underlying database exception message for
        # server-side logs (see app/retrieval/sqlite_bm25.py), which must
        # never reach the HTTP response -- only a fixed, generic message
        # plus the request_id is returned to the caller.
        raise HTTPException(
            status_code=500,
            detail=f"Ingestion failed unexpectedly (request_id={request_id}). See server logs.",
        ) from exc
    except Exception as exc:  # noqa: BLE001 -- deliberate safety net, see Minor #2
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected server error (request_id={request_id}).",
        ) from exc

    return DocumentIngestResponse(
        request_id=request_id,
        indexed=result.indexed,
        updated=result.updated,
        unchanged=result.unchanged,
        rejected=result.rejected,
        items=[
            IngestionItemResponse(
                external_id=item.external_id,
                source_key=item.source_key,
                document_id=item.document_id,
                status=item.status,
                reason=item.reason,
                chunk_count=item.chunk_count,
                metadata_keys_stripped=item.metadata_keys_stripped,
            )
            for item in result.items
        ],
    )


@router.post("/v1/retrieve", response_model=RetrieveResponse)
def retrieve(request: RetrieveRequest) -> RetrieveResponse:
    """Phase 12B: retrieval-only endpoint (no guard pipeline runs here --
    that is Phase 12C's POST /v1/rag/query, not yet implemented). Exists
    for retrieval-quality evaluation and debugging in isolation."""
    # The Pydantic field bound (le=50) is a generous static ceiling;
    # settings.retrieval_max_top_k is the authoritative, configurable
    # bound enforced here.
    if request.top_k > settings.retrieval_max_top_k:
        raise HTTPException(
            status_code=400,
            detail=f"top_k exceeds the configured maximum of {settings.retrieval_max_top_k}.",
        )

    request_id = str(uuid.uuid4())
    try:
        result = _retriever.search(RetrievalQuery(query=request.query, top_k=request.top_k))
    except EmptySearchQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FTS5UnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 -- deliberate safety net, see Minor #2
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected server error (request_id={request_id}).",
        ) from exc

    return RetrieveResponse(
        normalized_query=result.normalized_query,
        term_count=result.term_count,
        total_hits=result.total_hits,
        hits=[
            RetrievalHitResponse(
                chunk_id=hit.chunk_id,
                document_id=hit.document_id,
                title=hit.title,
                text=hit.text,
                rank=hit.rank,
                retrieval_score=hit.retrieval_score,
                source_id=hit.source_id,
                source_type=hit.source_type,
                classification=hit.classification,
                trust_level=hit.trust_level,
                metadata=dict(hit.metadata),
            )
            for hit in result.hits
        ],
    )


@router.post("/v1/rag/query", response_model=RagQueryResponse)
def rag_query(request: RagQueryRequest) -> RagQueryResponse:
    """Phase 12C: the full guarded end-to-end RAG pipeline -- Input Guard
    -> server-side retrieval -> Provenance/Trust Guard -> RAG Context
    Guard -> Mock Provider -> centralized DLP -> Output Guard. See
    `app/services/rag_query.py` module docstring for the exact stage
    order and every fail-closed stop path. This endpoint retrieves
    context itself; the request schema (`RagQueryRequest`,
    `extra="forbid"`) has no field for `context_chunks`, `trust_level`,
    `classification`, `source_type`, `is_poisoned`, `expected_decision`,
    a guard decision, or a canonical document/chunk ID -- a caller cannot
    supply or override any of them.
    """
    request_id = str(uuid.uuid4())
    top_k = request.top_k or settings.rag_default_top_k
    if top_k > settings.rag_max_top_k:
        # Fixed per the Code X final re-audit ("terminal audit coverage
        # is still incomplete"): this configured-policy rejection used to
        # return before run_rag_query (and therefore its internal audit
        # commit) ever ran, producing zero audit trail for a request that
        # did reach this service. audit_top_k_rejected emits exactly one
        # safe terminal event -- query hash/length only, never the raw
        # query -- before the same 400 response as before.
        audit_top_k_rejected(
            request_id=request_id, query=request.query, configured_max_top_k=settings.rag_max_top_k,
        )
        raise HTTPException(
            status_code=400,
            detail=f"top_k exceeds the configured maximum of {settings.rag_max_top_k}.",
        )

    try:
        pipeline_result, audit_ctx = run_rag_query_uncommitted(
            query=request.query, top_k=top_k, retriever=_retriever, request_id=request_id,
        )
    except EmptySearchQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FTS5UnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 -- deliberate safety net, matches Minor #2 convention
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected server error (request_id={request_id}).",
        ) from exc

    # Fixed per the Code X final terminal-audit re-audit ("nested
    # ProvenanceItemResponse construction occurs outside the protected
    # response-construction and terminal-audit block"): EVERY nested
    # response-model construction -- ProvenanceItemResponse,
    # StageResultResponse, and the outer RagQueryResponse itself -- must
    # happen inside this one try block. The previous code built the
    # `provenance` list *before* the try, so a validation failure there
    # (after the pipeline, including the provider, had already run) would
    # propagate as an unprotected exception: no safe request_id-bearing
    # HTTP 500, and zero terminal audit events, since it happened before
    # either the success-commit or the except-block's corrected commit.
    # The audit event is committed AFTER the *entire* response tree is
    # confirmed successfully built, not before -- run_rag_query_
    # uncommitted deliberately does not audit on the caller's behalf (see
    # its docstring), so there is no earlier "success" event to
    # contradict if anything in this block raises. On any failure here,
    # a corrected block/response_construction_failed event is committed
    # instead of the pipeline's own (now-inaccurate) computed outcome.
    try:
        provenance = (
            [
                ProvenanceItemResponse(
                    document_id=item.document_id,
                    chunk_id=item.chunk_id,
                    title=item.title,
                    source_type=item.source_type,
                    classification=item.classification,
                    trust_level=item.trust_level,
                    rank=item.rank,
                    retrieval_score=item.retrieval_score,
                    status=item.status,
                    reason_code=item.reason_code,
                )
                for item in pipeline_result.provenance
            ]
            if settings.rag_return_provenance
            else []
        )
        stage_items = [
            StageResultResponse(
                stage=sr.stage,
                decision=sr.decision,
                reason_code=sr.reason_code,
                detail=sr.detail,
            )
            for sr in pipeline_result.stage_results
        ]
        response = RagQueryResponse(
            request_id=pipeline_result.request_id,
            decision=pipeline_result.final_decision,
            answer=pipeline_result.answer,
            retrieved_count=pipeline_result.retrieved_count,
            accepted_context_count=pipeline_result.accepted_context_count,
            rejected_context_count=pipeline_result.rejected_context_count,
            provenance=provenance,
            stage_results=stage_items,
            redaction_count=pipeline_result.redaction_count,
            latency_ms=pipeline_result.latency_ms.get("total", 0.0),
            provider_called=pipeline_result.provider_called,
            stop_reason=pipeline_result.stop_reason,
            error_category=pipeline_result.error_category,
        )
    except Exception as exc:  # noqa: BLE001 -- safe response-boundary mapping
        commit_rag_query_audit(mark_response_construction_failed(pipeline_result), audit_ctx)
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected server error (request_id={request_id}).",
        ) from exc

    commit_rag_query_audit(pipeline_result, audit_ctx)
    return response
