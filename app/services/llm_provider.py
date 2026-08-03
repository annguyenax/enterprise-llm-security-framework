"""Offline-first LLM provider abstraction for the Phase 6 gateway.

Collaboration seam (ADR-004): additional offline/approved providers are added by
calling ``register_provider(name, factory)`` from their own module under
``app/services/providers/`` — the ``get_llm_provider`` factory below is NOT
edited, minimizing merge conflicts between the gateway and LLM workstreams. The
built-in ``mock`` provider is registered here and remains the default; behavior
for existing callers is unchanged.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable

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


# --- Provider registry (ADR-004 collaboration seam) -------------------------
# Maps a normalized provider name to a zero-argument factory. New providers
# register here from their own module; `get_llm_provider` is not edited.
_PROVIDER_REGISTRY: dict[str, Callable[[], BaseLLMProvider]] = {}


def register_provider(name: str, factory: Callable[[], BaseLLMProvider]) -> None:
    """Register an offline/approved provider factory under a normalized name.

    Fail-closed on an empty or duplicate name so two workstreams cannot silently
    collide. Called by provider modules under ``app/services/providers/``.
    """
    key = name.strip().lower()
    if not key:
        raise ValueError("provider name must be non-empty")
    if key in _PROVIDER_REGISTRY:
        raise ValueError(f"provider {key!r} is already registered")
    _PROVIDER_REGISTRY[key] = factory


def get_llm_provider(provider_name: str) -> BaseLLMProvider:
    """Return a configured local provider, rejecting unsupported names."""
    normalized = provider_name.strip().lower()
    factory = _PROVIDER_REGISTRY.get(normalized)
    if factory is None:
        raise ValueError(
            f"Unsupported LLM provider {provider_name!r}. Only the offline 'mock' provider is available."
        )
    return factory()


# Built-in offline provider. Remains the default and preserves prior behavior.
register_provider("mock", MockLLMProvider)
