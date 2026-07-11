"""API routes for the LLM Security Gateway through Phase 6."""
from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.guards.input_guard import evaluate_input
from app.guards.output_guard import evaluate_output
from app.guards.rag_guard import evaluate_rag_context
from app.schemas.requests import ChatRequest, InputGuardRequest, OutputGuardRequest, RAGGuardRequest
from app.schemas.responses import ChatResponse, GuardDecisionResponse, HealthResponse, RAGGuardResponse
from app.services.audit_logger import log_event
from app.services.gateway import run_chat

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
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
