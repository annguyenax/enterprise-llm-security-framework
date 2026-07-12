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
    provider_name: str | None = None
    model_name: str | None = None
    is_mock: bool | None = None


class IngestionItemResponse(BaseModel):
    external_id: str
    source_key: str
    document_id: str | None = None
    status: str
    reason: str | None = None
    chunk_count: int | None = None
    metadata_keys_stripped: int = 0


class DocumentIngestResponse(BaseModel):
    request_id: str
    indexed: int
    updated: int
    unchanged: int
    rejected: int
    items: list[IngestionItemResponse] = Field(default_factory=list)


class RetrievalHitResponse(BaseModel):
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
    metadata: dict[str, object] = Field(default_factory=dict)


class RetrieveResponse(BaseModel):
    normalized_query: str
    term_count: int
    total_hits: int
    hits: list[RetrievalHitResponse] = Field(default_factory=list)
