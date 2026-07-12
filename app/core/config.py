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
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean setting value: {value!r}")


RAG_MAX_TOP_K_HARD_LIMIT = 50
RAG_MAX_AGGREGATE_CONTEXT_CHARS_HARD_LIMIT = 100_000
DLP_MAX_INSPECT_CHARS_HARD_LIMIT = 1_000_000


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
    # Phase 12C RAG query pipeline settings -- see
    # docs/modernization-v2-architecture.md §6/§7 Phase 12C and
    # app/services/rag_query.py. Deliberately separate from the Phase 12B
    # retrieval_* settings above: POST /v1/rag/query feeds retrieved
    # content through guards and the provider, so its own top_k bound is
    # intentionally tighter by default than the retrieval-only debugging
    # endpoint's.
    rag_default_top_k: int = 5
    rag_max_top_k: int = 20
    rag_max_aggregate_context_chars: int = 4000
    dlp_max_inspect_chars: int = 20_000
    rag_return_provenance: bool = True

    def __post_init__(self) -> None:
        """Fail startup/construction on unsafe Phase 12C limits."""
        integer_fields = {
            "rag_default_top_k": self.rag_default_top_k,
            "rag_max_top_k": self.rag_max_top_k,
            "rag_max_aggregate_context_chars": self.rag_max_aggregate_context_chars,
            "dlp_max_inspect_chars": self.dlp_max_inspect_chars,
        }
        for name, value in integer_fields.items():
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")

        if self.rag_default_top_k > self.rag_max_top_k:
            raise ValueError("rag_default_top_k must not exceed rag_max_top_k")
        if self.rag_max_top_k > self.retrieval_max_top_k:
            raise ValueError("rag_max_top_k must not exceed retrieval_max_top_k")
        if self.rag_max_top_k > RAG_MAX_TOP_K_HARD_LIMIT:
            raise ValueError(
                f"rag_max_top_k must not exceed {RAG_MAX_TOP_K_HARD_LIMIT}"
            )
        if (
            self.rag_max_aggregate_context_chars
            > RAG_MAX_AGGREGATE_CONTEXT_CHARS_HARD_LIMIT
        ):
            raise ValueError(
                "rag_max_aggregate_context_chars must not exceed "
                f"{RAG_MAX_AGGREGATE_CONTEXT_CHARS_HARD_LIMIT}"
            )
        if self.dlp_max_inspect_chars > DLP_MAX_INSPECT_CHARS_HARD_LIMIT:
            raise ValueError(
                f"dlp_max_inspect_chars must not exceed {DLP_MAX_INSPECT_CHARS_HARD_LIMIT}"
            )
        if not isinstance(self.rag_return_provenance, bool):
            raise ValueError("rag_return_provenance must be a boolean")


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
        rag_default_top_k=int(os.getenv("RAG_DEFAULT_TOP_K", "5")),
        rag_max_top_k=int(os.getenv("RAG_MAX_TOP_K", "20")),
        rag_max_aggregate_context_chars=int(os.getenv("RAG_MAX_AGGREGATE_CONTEXT_CHARS", "4000")),
        dlp_max_inspect_chars=int(os.getenv("DLP_MAX_INSPECT_CHARS", "20000")),
        rag_return_provenance=_str_to_bool(os.getenv("RAG_RETURN_PROVENANCE", "true")),
    )


settings = load_settings()
