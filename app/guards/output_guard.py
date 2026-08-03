"""Rule-based Output Guard.

Lab-scale regex heuristics for catching obvious leakage patterns in an
assistant response (currently always the mock response from
app/services/gateway.py in this phase — see docs/decisions/ADR-001-mvp-scope.md)
before it would reach the user.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.decisions import Decision, most_severe
from app.guards.dlp_guard import FAKE_SECRET_PATTERN, OUTPUT_GUARD_REALISTIC_SECRET_PATTERN
from app.schemas.responses import GuardDecisionResponse

REDACTED = "[REDACTED]"

# FAKE_SECRET_PATTERN is re-exported (imported above, not redefined) from
# app/guards/dlp_guard.py -- Phase 12C centralization per
# docs/modernization-v2-architecture.md §5. Kept as a module attribute
# here for backward-compatible `from app.guards.output_guard import
# FAKE_SECRET_PATTERN` imports; the regex source and matching behavior
# are unchanged -- see tests/test_dlp_guard.py's consolidation-parity
# tests.


@dataclass(frozen=True)
class Rule:
    rule_id: str
    category: str
    pattern: re.Pattern[str]
    decision: Decision
    weight: float
    reason: str
    redact: bool = False


def _rx(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


RULES: tuple[Rule, ...] = (
    Rule(
        "output-fake-secret", "fake_secret_leak", FAKE_SECRET_PATTERN,
        Decision.SANITIZE, 0.7,
        "Detected this project's synthetic fake-secret marker in the output; redacted before returning.",
        redact=True,
    ),
    Rule(
        "output-realistic-api-key", "sensitive_information_disclosure",
        OUTPUT_GUARD_REALISTIC_SECRET_PATTERN,
        Decision.BLOCK, 0.95,
        "Detected a realistic-looking API key / access token / private-key pattern in the output.",
        redact=True,
    ),
    Rule(
        "output-email-pii", "sensitive_information_disclosure",
        _rx(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        Decision.LOG_ONLY, 0.4,
        "Detected an email-like string in the output; may be a legitimate contact reference - "
        "flagged for review rather than auto-blocked.",
        redact=False,
    ),
    Rule(
        "output-system-prompt-leak", "instruction_leakage",
        _rx(r"\bsystem prompt\b|\bmy (full |complete )?instructions are\b"),
        Decision.BLOCK, 0.85,
        "Detected the output referencing/quoting the system prompt or internal instructions - possible instruction leakage.",
    ),
    Rule(
        "output-disclosure-marker", "unsafe_disclosure_marker",
        _rx(r"\binternal use only\b|\bclassification:\s*(confidential|restricted)\b"),
        Decision.HUMAN_REVIEW, 0.5,
        "Detected a confidentiality/classification marker in the output - ambiguous (could be a "
        "legitimate policy quote); flagged for human review rather than auto-decided.",
    ),
)


def evaluate_output(output: str) -> GuardDecisionResponse:
    """Evaluate a candidate assistant output against the rule set."""
    matched = [rule for rule in RULES if rule.pattern.search(output)]

    if not matched:
        return GuardDecisionResponse(decision=Decision.ALLOW)

    final_decision = most_severe([rule.decision for rule in matched])
    risk_score = max(rule.weight for rule in matched)
    reasons = [rule.reason for rule in matched]
    matched_rules = [rule.rule_id for rule in matched]

    sanitized_text: str | None = None
    if final_decision == Decision.SANITIZE:
        sanitized_text = _redact(output, matched)

    return GuardDecisionResponse(
        decision=final_decision,
        sanitized_text=sanitized_text,
        reasons=reasons,
        matched_rules=matched_rules,
        risk_score=risk_score,
    )


def _redact(output: str, matched: list[Rule]) -> str:
    cleaned = output
    for rule in matched:
        if rule.redact:
            cleaned = rule.pattern.sub(REDACTED, cleaned)
    return cleaned
