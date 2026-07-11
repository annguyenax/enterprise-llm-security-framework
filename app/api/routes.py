"""API routes for the LLM Security Gateway skeleton (Phase 4)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.guards.input_guard import evaluate_input
from app.guards.output_guard import evaluate_output
from app.schemas.requests import ChatRequest, InputGuardRequest, OutputGuardRequest
from app.schemas.responses import ChatResponse, GuardDecisionResponse, HealthResponse
from app.services.audit_logger import log_event
from app.services.gateway import run_chat

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="llm-security-gateway", phase="phase-4-skeleton")


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


@router.post("/v1/gateway/chat", response_model=ChatResponse)
def gateway_chat(request: ChatRequest) -> ChatResponse:
    return run_chat(request.prompt, request.metadata)
