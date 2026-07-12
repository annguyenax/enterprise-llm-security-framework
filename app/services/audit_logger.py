"""JSONL audit logger.

Appends one JSON object per line to `settings.log_path` (default
`logs/audit.jsonl`), creating the parent directory automatically if it does
not exist. Secret-like patterns are redacted before being written,
independent of what the guards themselves decided, as a defense-in-depth
safety net (AGENT_RULES.md rule 5 — never persist real-looking secrets).
"""
from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.decisions import Decision
from app.guards.dlp_guard import (
    AWS_KEY_PATTERN,
    FAKE_SECRET_PATTERN,
    GITHUB_TOKEN_PATTERN,
    OPENAI_KEY_PATTERN,
    PRIVATE_KEY_BLOCK_PATTERN,
)
from app.schemas.responses import GuardDecisionResponse, RAGGuardResponse

_WRITE_LOCK = threading.Lock()

# Phase 12C centralization: these five patterns are now defined once in
# app/guards/dlp_guard.py (per docs/modernization-v2-architecture.md §5)
# instead of being redefined here. Same regex source and flags as before
# this change -- see tests/test_dlp_guard.py's
# test_audit_logger_redaction_unchanged_after_consolidation.
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    FAKE_SECRET_PATTERN,
    OPENAI_KEY_PATTERN,
    AWS_KEY_PATTERN,
    GITHUB_TOKEN_PATTERN,
    PRIVATE_KEY_BLOCK_PATTERN,
)


def _redact_secrets(text: str) -> str:
    redacted = text
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def _preview(text: str, max_len: int = 200) -> str:
    redacted = _redact_secrets(text)
    if len(redacted) > max_len:
        return redacted[:max_len] + "...[truncated]"
    return redacted


def _redact_value(value: Any) -> Any:
    """Redact strings recursively without changing JSON-compatible shape."""
    if isinstance(value, str):
        return _redact_secrets(value)
    if isinstance(value, dict):
        return {key: _redact_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    return value


def _guard_summary(
    result: GuardDecisionResponse | RAGGuardResponse | None,
) -> dict[str, Any] | None:
    if result is None:
        return None
    return {
        "decision": result.decision.value,
        "matched_rules": result.matched_rules,
        "risk_score": result.risk_score,
    }


def log_event(
    *,
    endpoint: str,
    request_id: str,
    input_preview: str | None = None,
    input_decision: GuardDecisionResponse | None = None,
    rag_decision: RAGGuardResponse | None = None,
    output_decision: GuardDecisionResponse | None = None,
    final_decision: Decision,
    reasons: list[str],
    metadata: dict[str, Any],
    provider_metadata: dict[str, Any] | None = None,
) -> None:
    """Append one JSONL audit event. No-op if ENABLE_AUDIT_LOG is false.

    Per FR7/NFR3 (docs/diagrams/architecture.md), every guard decision made
    by this gateway should be logged with enough detail to reconstruct why a
    request was allowed/flagged/blocked, without ever persisting a real-
    looking secret in plain text. `input_preview` already passes through
    `_redact_secrets` (via `_preview`) as a defense-in-depth safety net
    covering the RAG Guard path too (e.g. FAKE-SECRET-0000-EXAMPLE inside a
    logged context-chunk preview).
    """
    if not settings.enable_audit_log:
        return

    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_id": request_id,
        "endpoint": endpoint,
        "input_preview": _preview(input_preview) if input_preview else None,
        "input_decision": _guard_summary(input_decision),
        "rag_decision": _guard_summary(rag_decision),
        "output_decision": _guard_summary(output_decision),
        "final_decision": final_decision.value,
        "reasons": reasons,
        "metadata": _redact_value(metadata),
        "provider": _redact_value(provider_metadata),
    }

    log_path = Path(settings.log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    line = json.dumps(event, ensure_ascii=False)
    with _WRITE_LOCK:
        with log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
