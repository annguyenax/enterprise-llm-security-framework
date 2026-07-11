"""Offline tests for the Phase 6 LLM provider abstraction."""
import pytest

from app.core.config import load_settings
from app.schemas.requests import RAGContextChunk
from app.services.llm_provider import (
    LLMProviderRequest,
    MockLLMProvider,
    get_llm_provider,
)


def _request() -> LLMProviderRequest:
    return LLMProviderRequest(
        prompt="What is the refund policy?",
        sanitized_prompt="What is the refund policy?",
        context_chunks=[RAGContextChunk(doc_id="DOC-1", text="Refunds require review.", metadata={})],
        metadata={"test": True},
        request_id="request-1",
    )


def test_mock_provider_is_deterministic_and_offline_by_contract():
    provider = MockLLMProvider("mock-rag-guard-v1")
    first = provider.generate(_request())
    second = provider.generate(_request())

    assert first == second
    assert first.provider_name == "mock"
    assert first.model_name == "mock-rag-guard-v1"
    assert first.is_mock is True
    assert "No real LLM call was made" in first.text
    assert "1 guard-approved context chunk(s)" in first.text
    assert "Refunds require review" not in first.text
    assert first.usage == {"input_units": 0, "output_units": 0}


def test_provider_factory_only_allows_mock():
    assert isinstance(get_llm_provider(" MOCK "), MockLLMProvider)
    with pytest.raises(ValueError, match="Only the offline 'mock' provider"):
        get_llm_provider("external-provider")


def test_llm_config_defaults_require_no_env_file(monkeypatch):
    for name in ("LLM_PROVIDER", "LLM_MODEL_NAME", "LLM_PROVIDER_TIMEOUT_SECONDS"):
        monkeypatch.delenv(name, raising=False)
    configured = load_settings()
    assert configured.llm_provider == "mock"
    assert configured.llm_model_name == "mock-rag-guard-v1"
    assert configured.llm_provider_timeout_seconds == 30
