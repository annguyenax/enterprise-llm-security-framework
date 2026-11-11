"""Application configuration.

Reads settings from environment variables with safe local-dev defaults.
No `.env` file is required to run the service. This intentionally does not
use `pydantic-settings` to avoid adding an extra dependency for a handful
of simple values (AGENT_RULES.md rule 11 — ask before adding heavy deps).
"""
from __future__ import annotations

import math
import os
import re
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
OLLAMA_PRIMARY_MODEL = "gemma4:e4b-it-qat"
OLLAMA_PRIMARY_DIGEST = "ee665637121887cf3befff38abbb1be4ee117c7db867d97a67e29049ecd7e15f"
OLLAMA_BACKUP_MODEL = "gemma4:e2b-it-q4_K_M"
OLLAMA_BACKUP_DIGEST = "b37049369adfe3d2b653af0ab301a062ca5cbe96ace6aa0d3f2559ee9b563fc2"


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
    # Enterprise ACL retriever (Slice 2). The default is deliberately the
    # existing Phase 12B backend, so nothing about the current demos or the
    # frozen-benchmark evaluations changes unless an operator opts in.
    # Selecting a backend by name goes through the ADR-004 registry
    # (`app/retrieval/registry.py`), which fails closed on an unknown name.
    retriever_name: str = "sqlite_bm25"
    enterprise_kb_db_path: str = "data/enterprise-kb.db"
    # Optional local semantic leg for workspace hybrid retrieval. Empty keeps
    # the existing BM25-only behavior without downloading a model implicitly.
    workspace_embedding_model: str = ""
    ollama_embedding_base_url: str = "http://127.0.0.1:11434"
    # None means resolve the selected, known model's identity. Unknown tags
    # must supply their own identity; they never inherit the primary digest.
    ollama_model_digest: str | None = None
    ollama_model_quantization: str | None = None
    ollama_backup_model_name: str = OLLAMA_BACKUP_MODEL
    ollama_backup_model_digest: str | None = None
    ollama_backup_model_quantization: str | None = None
    ollama_expected_version: str = "0.40.11"
    ollama_temperature: float = 0.0
    ollama_seed: int = 42
    ollama_num_ctx: int = 4096
    ollama_num_predict: int = 512
    llm_repeat_count: int = 1
    ollama_think: bool = False
    ollama_max_retries: int = 2

    def __post_init__(self) -> None:
        """Fail startup/construction on unsafe Phase 12C limits."""
        temperature = self.ollama_temperature
        if type(temperature) not in {int, float} or not math.isfinite(temperature) or temperature < 0:
            raise ValueError("ollama_temperature must be finite and non-negative")
        if type(self.ollama_seed) is not int:
            raise ValueError("ollama_seed must be an integer")
        for name in ("ollama_num_ctx", "ollama_num_predict", "llm_repeat_count"):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if type(self.ollama_think) is not bool:
            raise ValueError("ollama_think must be a boolean")
        if type(self.ollama_max_retries) is not int or self.ollama_max_retries not in {0, 1, 2}:
            raise ValueError("ollama_max_retries must be 0, 1 or 2")
        if self.ollama_backup_model_name == OLLAMA_BACKUP_MODEL:
            if self.ollama_backup_model_digest is None:
                object.__setattr__(self, "ollama_backup_model_digest", OLLAMA_BACKUP_DIGEST)
            if self.ollama_backup_model_quantization is None:
                object.__setattr__(self, "ollama_backup_model_quantization", "Q4_K_M")
        if self.llm_provider == "ollama":
            if not isinstance(self.llm_model_name, str) or not self.llm_model_name.strip() or self.llm_model_name.strip().startswith("mock"):
                raise ValueError("Ollama requires a non-mock model tag")
            for name in ("ollama_backup_model_name", "ollama_backup_model_quantization", "ollama_expected_version"):
                if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                    raise ValueError(f"{name} must be a non-empty string")
            if self.llm_model_name == OLLAMA_PRIMARY_MODEL:
                identity = (OLLAMA_PRIMARY_DIGEST, "Q4_0")
            elif self.llm_model_name == self.ollama_backup_model_name:
                identity = (self.ollama_backup_model_digest, self.ollama_backup_model_quantization)
            else:
                identity = (None, None)
            for name, default in zip(("ollama_model_digest", "ollama_model_quantization"), identity):
                if getattr(self, name) is None:
                    object.__setattr__(self, name, default)
            for name in ("ollama_model_digest", "ollama_backup_model_digest"):
                value = getattr(self, name)
                if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
                    raise ValueError(f"{name} must be a lowercase SHA-256")
            if not isinstance(self.ollama_model_quantization, str) or not self.ollama_model_quantization.strip():
                raise ValueError("ollama_model_quantization must be a non-empty string")
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
        if not isinstance(self.retriever_name, str) or not self.retriever_name.strip():
            raise ValueError("retriever_name must be a non-empty string")
        if (
            not isinstance(self.enterprise_kb_db_path, str)
            or not self.enterprise_kb_db_path.strip()
        ):
            raise ValueError("enterprise_kb_db_path must be a non-empty string")


def load_settings() -> Settings:
    """Read settings fresh from the current environment.

    Exposed separately from the module-level `settings` singleton so tests
    can construct alternate configurations without monkeypatching env vars.
    """
    provider = os.getenv("LLM_PROVIDER", "mock")
    return Settings(
        app_env=os.getenv("APP_ENV", "dev"),
        log_path=os.getenv("LOG_PATH", "logs/audit.jsonl"),
        enable_audit_log=_str_to_bool(os.getenv("ENABLE_AUDIT_LOG", "true")),
        llm_provider=provider,
        llm_model_name=os.getenv("LLM_MODEL_NAME", OLLAMA_PRIMARY_MODEL if provider == "ollama" else "mock-rag-guard-v1"),
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
        retriever_name=os.getenv("RETRIEVER_NAME", "sqlite_bm25"),
        enterprise_kb_db_path=os.getenv("ENTERPRISE_KB_DB_PATH", "data/enterprise-kb.db"),
        workspace_embedding_model=os.getenv("WORKSPACE_EMBEDDING_MODEL", ""),
        ollama_embedding_base_url=os.getenv("OLLAMA_EMBEDDING_BASE_URL", "http://127.0.0.1:11434"),
        ollama_model_digest=os.getenv("OLLAMA_MODEL_DIGEST"),
        ollama_model_quantization=os.getenv("OLLAMA_MODEL_QUANTIZATION"),
        ollama_backup_model_name=os.getenv("OLLAMA_BACKUP_MODEL_NAME", OLLAMA_BACKUP_MODEL),
        ollama_backup_model_digest=os.getenv("OLLAMA_BACKUP_MODEL_DIGEST"),
        ollama_backup_model_quantization=os.getenv("OLLAMA_BACKUP_MODEL_QUANTIZATION"),
        ollama_expected_version=os.getenv("OLLAMA_EXPECTED_VERSION", "0.40.11"),
        ollama_temperature=float(os.getenv("OLLAMA_TEMPERATURE", "0.0")),
        ollama_seed=int(os.getenv("OLLAMA_SEED", "42")),
        ollama_num_ctx=int(os.getenv("OLLAMA_NUM_CTX", "4096")),
        ollama_num_predict=int(os.getenv("OLLAMA_NUM_PREDICT", "512")),
        llm_repeat_count=int(os.getenv("LLM_REPEAT_COUNT", "1")),
        ollama_think=_str_to_bool(os.getenv("OLLAMA_THINK", "false")),
        ollama_max_retries=int(os.getenv("OLLAMA_MAX_RETRIES", "2")),
    )


settings = load_settings()
