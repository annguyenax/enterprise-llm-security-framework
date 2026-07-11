"""Offline-first LLM provider abstraction for the Phase 6 gateway."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings
from app.schemas.requests import RAGContextChunk


@dataclass(frozen=True)
class LLMProviderRequest:
    prompt: str
    sanitized_prompt: str
    context_chunks: list[RAGContextChunk]
    metadata: dict[str, Any]
    request_id: str


@dataclass(frozen=True)
class LLMProviderResponse:
    text: str
    provider_name: str
    model_name: str
    is_mock: bool
    usage: dict[str, int] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseLLMProvider(ABC):
    """Minimal synchronous provider contract used by the gateway."""

    @abstractmethod
    def generate(self, request: LLMProviderRequest) -> LLMProviderResponse:
        """Generate one candidate response for Output Guard evaluation."""


class MockLLMProvider(BaseLLMProvider):
    """Deterministic local provider that never performs network or API calls."""

    provider_name = "mock"

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or settings.llm_model_name

    def generate(self, request: LLMProviderRequest) -> LLMProviderResponse:
        context_note = (
            f" {len(request.context_chunks)} guard-approved context chunk(s) were considered."
            if request.context_chunks
            else " No context chunks were supplied."
        )
        text = (
            "Mock provider response: guard evaluation completed. "
            "No real LLM call was made in this phase."
            + context_note
        )
        return LLMProviderResponse(
            text=text,
            provider_name=self.provider_name,
            model_name=self.model_name,
            is_mock=True,
            usage={"input_units": 0, "output_units": 0},
            metadata={"context_chunks_considered": len(request.context_chunks)},
        )


def get_llm_provider(provider_name: str) -> BaseLLMProvider:
    """Return a configured local provider, rejecting unsupported names."""
    normalized = provider_name.strip().lower()
    if normalized == "mock":
        return MockLLMProvider()
    raise ValueError(
        f"Unsupported LLM provider {provider_name!r}. Only the offline 'mock' provider is available."
    )
