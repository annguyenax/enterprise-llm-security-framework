"""Application configuration.

Reads settings from environment variables with safe local-dev defaults.
No `.env` file is required to run the service. This intentionally does not
use `pydantic-settings` to avoid adding an extra dependency for a handful
of simple values (AGENT_RULES.md rule 11 — ask before adding heavy deps).
"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _str_to_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_env: str
    log_path: str
    enable_audit_log: bool
    llm_provider: str
    llm_model_name: str
    llm_provider_timeout_seconds: int
    # Phase 12B retrieval settings -- see docs/decisions/ADR-002-retrieval-engine.md
    # and docs/modernization-v2-architecture.md §2. Runtime database files are
    # not committed (already covered by .gitignore's existing `data/`/`*.db`
    # entries from before this phase). Defaulted (not required-positional) so
    # existing code that constructs `Settings(...)` directly (e.g.
    # tests/test_gateway_provider.py, written before Phase 12B) keeps working
    # unchanged -- `load_settings()` below still passes every field explicitly.
    retrieval_db_path: str = "data/retrieval.db"
    retrieval_max_batch_size: int = 20
    retrieval_max_document_chars: int = 200_000
    retrieval_max_query_chars: int = 500
    retrieval_max_query_terms: int = 12
    retrieval_max_top_k: int = 50
    retrieval_chunk_max_chars: int = 800
    retrieval_chunk_overlap_chars: int = 100
    retrieval_busy_timeout_ms: int = 5000


def load_settings() -> Settings:
    """Read settings fresh from the current environment.

    Exposed separately from the module-level `settings` singleton so tests
    can construct alternate configurations without monkeypatching env vars.
    """
    return Settings(
        app_env=os.getenv("APP_ENV", "dev"),
        log_path=os.getenv("LOG_PATH", "logs/audit.jsonl"),
        enable_audit_log=_str_to_bool(os.getenv("ENABLE_AUDIT_LOG", "true")),
        llm_provider=os.getenv("LLM_PROVIDER", "mock"),
        llm_model_name=os.getenv("LLM_MODEL_NAME", "mock-rag-guard-v1"),
        llm_provider_timeout_seconds=int(os.getenv("LLM_PROVIDER_TIMEOUT_SECONDS", "30")),
        retrieval_db_path=os.getenv("RETRIEVAL_DB_PATH", "data/retrieval.db"),
        retrieval_max_batch_size=int(os.getenv("RETRIEVAL_MAX_BATCH_SIZE", "20")),
        retrieval_max_document_chars=int(os.getenv("RETRIEVAL_MAX_DOCUMENT_CHARS", "200000")),
        retrieval_max_query_chars=int(os.getenv("RETRIEVAL_MAX_QUERY_CHARS", "500")),
        retrieval_max_query_terms=int(os.getenv("RETRIEVAL_MAX_QUERY_TERMS", "12")),
        retrieval_max_top_k=int(os.getenv("RETRIEVAL_MAX_TOP_K", "50")),
        retrieval_chunk_max_chars=int(os.getenv("RETRIEVAL_CHUNK_MAX_CHARS", "800")),
        retrieval_chunk_overlap_chars=int(os.getenv("RETRIEVAL_CHUNK_OVERLAP_CHARS", "100")),
        retrieval_busy_timeout_ms=int(os.getenv("RETRIEVAL_BUSY_TIMEOUT_MS", "5000")),
    )


settings = load_settings()
