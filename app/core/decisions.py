"""Shared guard-decision taxonomy.

These 5 values intentionally mirror `redteam/expected-behaviors.yaml` exactly
— this is the same taxonomy the synthetic benchmark (Phase 3) was designed
against, not a separate code-only reinterpretation. See
docs/dataset/dataset-methodology.md for the full rationale.
"""
from __future__ import annotations

from enum import Enum


class Decision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    SANITIZE = "sanitize"
    LOG_ONLY = "log_only"
    HUMAN_REVIEW = "human_review"


# Severity ordering used to combine several rule matches (or several guards'
# results) into a single final decision. Higher number = takes priority.
_SEVERITY: dict[Decision, int] = {
    Decision.ALLOW: 0,
    Decision.LOG_ONLY: 1,
    Decision.SANITIZE: 2,
    Decision.HUMAN_REVIEW: 3,
    Decision.BLOCK: 4,
}


def most_severe(decisions: list[Decision]) -> Decision:
    """Return the highest-severity decision in the list (ALLOW if empty)."""
    if not decisions:
        return Decision.ALLOW
    return max(decisions, key=lambda d: _SEVERITY[d])
