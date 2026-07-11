"""API routes for the LLM Security Gateway through Phase 12B.

Phase 12B adds POST /v1/documents/ingest and POST /v1/retrieve (lexical
retrieval foundation only -- see docs/modernization-v2-architecture.md §6).
These are NOT wired into the guarded gateway pipeline yet: POST
/v1/rag/query does not exist until Phase 12C, and POST /v1/gateway/chat's
behavior is unchanged from Phase 6.
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
    SqliteBM25Config,
    SqliteBM25Retriever,
)
from app.schemas.requests import (
    ChatRequest,
    DocumentIngestRequest,
    InputGuardRequest,
    OutputGuardRequest,
    RAGGuardRequest,
    RetrieveRequest,
)
from app.schemas.responses import (
    ChatResponse,
    DocumentIngestResponse,
    GuardDecisionResponse,
    HealthResponse,
    IngestionItemResponse,
    RAGGuardResponse,
    RetrievalHitResponse,
    RetrieveResponse,
)
from app.services.audit_logger import log_event
from app.services.gateway import run_chat
from app.services.ingestion import IngestionService, IngestionValidationError

router = APIRouter()

# Module-level singletons, matching this codebase's existing convention of
# a global `settings` object (app/core/config.py). Construction here is
# cheap (no I/O) -- schema creation and the FTS5 capability check are lazy
# and happen on first actual use, inside SqliteBM25Retriever itself, not
# at import time. A future dependency-injection refactor is not needed
# for Phase 12B's scope. See docs/modernization-v2-architecture.md §2/§7.
_retriever: Retriever = SqliteBM25Retriever(
    SqliteBM25Config(
        db_path=settings.retrieval_db_path,
        busy_timeout_ms=settings.retrieval_busy_timeout_ms,
        max_query_chars=settings.retrieval_max_query_chars,
        max_query_terms=settings.retrieval_max_query_terms,
        max_top_k=settings.retrieval_max_top_k,
    )
)
_ingestion_service = IngestionService(_retriever)


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

    try:
        result = _retriever.search(RetrievalQuery(query=request.query, top_k=request.top_k))
    except EmptySearchQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FTS5UnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

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
