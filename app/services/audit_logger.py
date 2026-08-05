"""JSONL audit logger.

Appends one JSON object per line to `settings.log_path` (default
`logs/audit.jsonl`), creating the parent directory automatically if it does
not exist. Secret-like patterns are redacted before being written,
independent of what the guards themselves decided, as a defense-in-depth
safety net (AGENT_RULES.md rule 5 — never persist real-looking secrets).
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.decisions import Decision
from app.guards.dlp_guard import redact_sensitive_text
from app.schemas.responses import GuardDecisionResponse, RAGGuardResponse

_WRITE_LOCK = threading.Lock()
_FALLBACK_LOGGER = logging.getLogger("app.audit.fallback")

# Metadata keys that carry conversation/document CONTENT rather than facts
# about a request. Secret redaction alone is not the right control for
# these: the content is sensitive as a whole (an entire chat transcript,
# an uploaded document body), not merely because it might contain a
# token-shaped substring, so no pattern-based detector can make persisting
# it safe.
#
# Enforced centrally here rather than only at the call site, for the same
# reason `_redact_secrets` delegates to the one shared detector set (Phase
# 12C Code X audit, Critical #2): a policy applied only at individual call
# sites silently stops holding the moment a new call site is added.
# `app/services/gateway.py` additionally replaces its own `history` value
# with a `history_turns` count *before* calling `log_event`, so the
# well-behaved path keeps a useful auditable signal; this net exists for
# every other path, and never raises -- an unrecognized value shape is
# omitted, not inspected.
NON_AUDITABLE_CONTENT_KEYS = frozenset(
    {"history", "chat_history", "conversation_history", "messages", "transcript"}
)

_OMITTED_CONTENT = "[omitted: conversation content is never written to the audit log]"


def _redact_secrets(text: str) -> str:
    """Delegates to the single centralized, complete detector set.

    **Fixed per the Phase 12C Code X audit (Critical #2):** this
    previously imported five specific pattern constants directly from
    `app/guards/dlp_guard.py` and applied them in a local tuple, which
    silently omitted the bearer-token and secret-assignment detectors
    added later in the same phase -- a caller could place
    `Bearer <token>` or `password=...` in request metadata and have it
    persisted verbatim in `audit.jsonl`. Calling the shared
    `redact_sensitive_text()` function instead of re-listing individual
    pattern constants means this call site can never again silently
    drift out of sync with the centralized detector set -- there is
    exactly one place (`dlp_guard._DETECTORS`) that defines what counts
    as a secret, and this module no longer needs to know its contents.
    """
    return redact_sensitive_text(text)


def _preview(text: str, max_len: int = 200) -> str:
    redacted = _redact_secrets(text)
    if len(redacted) > max_len:
        return redacted[:max_len] + "...[truncated]"
    return redacted


def _is_non_auditable_key(key: Any) -> bool:
    """Type-first membership test: `key` is checked with `isinstance` before
    it is ever used in a set lookup, because a JSON-shaped dict can carry a
    non-string key and `frozenset` membership on an unhashable one would
    raise `TypeError` inside the audit path."""
    return isinstance(key, str) and key.strip().lower() in NON_AUDITABLE_CONTENT_KEYS


def _redact_value(value: Any) -> Any:
    """Redact strings recursively without changing JSON-compatible shape,
    and omit any value stored under a non-auditable content key at any
    nesting depth (see `NON_AUDITABLE_CONTENT_KEYS`)."""
    if isinstance(value, str):
        return _redact_secrets(value)
    if isinstance(value, dict):
        return {
            key: (_OMITTED_CONTENT if _is_non_auditable_key(key) else _redact_value(item))
            for key, item in value.items()
        }
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
) -> bool:
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
        return True

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

    # Audit-sink failure behavior (Phase 12C Code X audit, Major #3): a
    # disk/permissions failure while writing the audit log must never
    # propagate out of log_event and fail the caller's actual request --
    # the response to the caller has either already been computed or is
    # about to be, and losing one audit line is a strictly better outcome
    # than a 500 caused solely by logging infrastructure. Attempted
    # exactly once, not retried (a retry loop against a sink that is
    # actually down would just block/spin), and the exception itself
    # (which could include a filesystem path) is never included in any
    # response or re-raised -- it is deliberately swallowed here, the one
    # place this project intentionally does so.
    try:
        line = json.dumps(event, ensure_ascii=False)
        log_path = Path(settings.log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with _WRITE_LOCK:
            with log_path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        return True
    except (OSError, TypeError, ValueError, RecursionError):
        # One safe fallback signal only. Never include the exception,
        # submitted metadata, query, provider output, or filesystem path.
        _FALLBACK_LOGGER.error(
            "audit_sink_failure endpoint=%s request_id=%s final_decision=%s",
            endpoint,
            request_id,
            final_decision.value,
        )
        return False
