"""Pydantic request models for the gateway API."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


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
