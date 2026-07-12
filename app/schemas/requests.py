"""Pydantic request models for the gateway API."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class InputGuardRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="Raw user prompt to evaluate.")
    metadata: dict[str, Any] = Field(default_factory=dict)


class OutputGuardRequest(BaseModel):
    output: str = Field(..., min_length=1, description="Candidate assistant output to evaluate.")
    metadata: dict[str, Any] = Field(default_factory=dict)


class RAGContextChunk(BaseModel):
    doc_id: str = Field(..., min_length=1, description="Source document identifier for this chunk.")
    text: str = Field(..., description="Chunk text as it would be handed to the LLM as context.")
    metadata: dict[str, Any] = Field(default_factory=dict)


class RAGGuardRequest(BaseModel):
    query: str = Field(..., min_length=1, description="User query that triggered this retrieval.")
    context_chunks: list[RAGContextChunk] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="User prompt for the full gateway pipeline.")
    context_chunks: list[RAGContextChunk] = Field(
        default_factory=list,
        description="Optional retrieved-context chunks to run through the RAG Guard (Phase 5). "
        "No real retrieval happens in this phase - callers supply chunks directly.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestionDocumentRequest(BaseModel):
    """One document to ingest (Phase 12B). `extra="forbid"` rejects the
    whole request with a clear validation error if a caller attempts to
    send a security-relevant field (e.g. `trust_level`, `classification`,
    `document_id`) that does not exist on this schema -- those are always
    server-assigned, never caller-supplied. See
    `app/core/source_policy.py` and `app/services/ingestion.py`.
    """

    model_config = ConfigDict(extra="forbid")

    external_id: str = Field(..., min_length=1, max_length=200)
    source_key: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=300)
    text: str = Field(..., min_length=1)
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Free-form caller metadata. Reserved security keys "
        "(trust_level, classification, source_type, is_poisoned, "
        "security_decision, document_id, chunk_id) are silently stripped "
        "before storage -- they can never override the server-controlled "
        "source policy.",
    )


class DocumentIngestRequest(BaseModel):
    documents: list[IngestionDocumentRequest] = Field(..., min_length=1)


class RetrieveRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=50)
