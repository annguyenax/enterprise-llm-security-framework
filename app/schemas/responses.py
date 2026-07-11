"""Pydantic response models for the gateway API."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.decisions import Decision
from app.schemas.requests import RAGContextChunk


class HealthResponse(BaseModel):
    status: str
    service: str
    phase: str


class GuardDecisionResponse(BaseModel):
    decision: Decision
    sanitized_text: str | None = None
    reasons: list[str] = Field(default_factory=list)
    matched_rules: list[str] = Field(default_factory=list)
    risk_score: float = Field(0.0, ge=0.0, le=1.0)


class RAGGuardResponse(BaseModel):
    decision: Decision
    sanitized_chunks: list[RAGContextChunk] | None = None
    reasons: list[str] = Field(default_factory=list)
    matched_rules: list[str] = Field(default_factory=list)
    risk_score: float = Field(0.0, ge=0.0, le=1.0)


class ChatResponse(BaseModel):
    request_id: str
    input_guard: GuardDecisionResponse
    rag_guard: RAGGuardResponse | None = None
    output_guard: GuardDecisionResponse | None = None
    final_decision: Decision
    response: str
