"""Phase 12C configuration validation regressions."""
from __future__ import annotations

import pytest

from app.core.config import (
    DLP_MAX_INSPECT_CHARS_HARD_LIMIT,
    RAG_MAX_AGGREGATE_CONTEXT_CHARS_HARD_LIMIT,
    RAG_MAX_TOP_K_HARD_LIMIT,
    Settings,
    load_settings,
)


def _settings(**overrides) -> Settings:
    values = {
        "app_env": "test",
        "log_path": "audit.jsonl",
        "enable_audit_log": False,
        "llm_provider": "mock",
        "llm_model_name": "mock",
        "llm_provider_timeout_seconds": 30,
    }
    values.update(overrides)
    return Settings(**values)


def test_old_direct_settings_construction_remains_compatible():
    configured = _settings()
    assert configured.rag_default_top_k == 5
    assert configured.rag_max_top_k == 20


def test_valid_phase12c_boundary_values_are_accepted():
    configured = _settings(
        retrieval_max_top_k=RAG_MAX_TOP_K_HARD_LIMIT,
        rag_default_top_k=1,
        rag_max_top_k=RAG_MAX_TOP_K_HARD_LIMIT,
        rag_max_aggregate_context_chars=1,
        dlp_max_inspect_chars=1,
    )
    assert configured.rag_default_top_k == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"rag_default_top_k": 0},
        {"rag_max_top_k": -1},
        {"rag_max_aggregate_context_chars": 0},
        {"dlp_max_inspect_chars": -1},
        {"rag_default_top_k": 6, "rag_max_top_k": 5},
        {"retrieval_max_top_k": 10, "rag_max_top_k": 11},
        {"rag_max_top_k": RAG_MAX_TOP_K_HARD_LIMIT + 1, "retrieval_max_top_k": 100},
        {
            "rag_max_aggregate_context_chars":
                RAG_MAX_AGGREGATE_CONTEXT_CHARS_HARD_LIMIT + 1
        },
        {"dlp_max_inspect_chars": DLP_MAX_INSPECT_CHARS_HARD_LIMIT + 1},
        {"rag_default_top_k": True},
        {"rag_return_provenance": "yes"},
    ],
)
def test_invalid_phase12c_values_fail_construction(overrides):
    with pytest.raises(ValueError):
        _settings(**overrides)


def test_non_integer_environment_value_fails_clearly(monkeypatch):
    monkeypatch.setenv("RAG_MAX_TOP_K", "not-an-integer")
    with pytest.raises(ValueError):
        load_settings()


def test_contradictory_environment_values_fail_before_service_use(monkeypatch):
    monkeypatch.setenv("RAG_DEFAULT_TOP_K", "9")
    monkeypatch.setenv("RAG_MAX_TOP_K", "8")
    with pytest.raises(ValueError, match="rag_default_top_k"):
        load_settings()


def test_invalid_boolean_environment_value_fails_clearly(monkeypatch):
    monkeypatch.setenv("RAG_RETURN_PROVENANCE", "sometimes")
    with pytest.raises(ValueError, match="boolean"):
        load_settings()

