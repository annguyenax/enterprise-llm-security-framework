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


class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="User prompt for the full gateway pipeline.")
    metadata: dict[str, Any] = Field(default_factory=dict)
