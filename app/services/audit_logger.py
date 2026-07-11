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
from app.schemas.responses import GuardDecisionResponse

_WRITE_LOCK = threading.Lock()

_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"FAKE-SECRET-0000-EXAMPLE(-[A-Z-]+)?", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9]{16,}\b"),
    re.compile(r"\bAKIA[A-Z0-9]{12,}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL),
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


def _guard_summary(result: GuardDecisionResponse | None) -> dict[str, Any] | None:
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
    output_decision: GuardDecisionResponse | None = None,
    final_decision: Decision,
    reasons: list[str],
    metadata: dict[str, Any],
) -> None:
    """Append one JSONL audit event. No-op if ENABLE_AUDIT_LOG is false.

    Per FR7/NFR3 (docs/diagrams/architecture.md), every guard decision made
    by this gateway should be logged with enough detail to reconstruct why a
    request was allowed/flagged/blocked, without ever persisting a real-
    looking secret in plain text.
    """
    if not settings.enable_audit_log:
        return

    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_id": request_id,
        "endpoint": endpoint,
        "input_preview": _preview(input_preview) if input_preview else None,
        "input_decision": _guard_summary(input_decision),
        "output_decision": _guard_summary(output_decision),
        "final_decision": final_decision.value,
        "reasons": reasons,
        "metadata": metadata,
    }

    log_path = Path(settings.log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    line = json.dumps(event, ensure_ascii=False)
    with _WRITE_LOCK:
        with log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
