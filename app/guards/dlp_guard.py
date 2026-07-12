"""Centralized deterministic DLP (data-leak-prevention) detector/redactor
(Phase 12C).

Primary responsibility for this phase: inspect and redact **provider
output** in the new `POST /v1/rag/query` pipeline, before the Output
Guard and the final API response -- see `app/services/rag_query.py`.

This module is also the canonical source for the secret-pattern regexes
previously duplicated across `app/guards/output_guard.py` and
`app/services/audit_logger.py` (per
`docs/modernization-v2-architecture.md` §5's consolidation target). Both
of those modules now import their pattern constants from here instead of
maintaining separate copies; their matching/decision *behavior* is
unchanged -- see the regression tests in `tests/test_dlp_guard.py`
(`test_output_guard_redaction_unchanged_after_consolidation` and
`test_audit_logger_redaction_unchanged_after_consolidation`) that assert
byte-identical output on the existing fixture set before this
consolidation is considered safe. `app/guards/rag_guard.py` is
deliberately left untouched -- its own `FAKE_SECRET_PATTERN` copy serves
a different purpose (pre-provider content filtering as one signal among
many RAG Context Guard rules) and touching it is not necessary for this
phase's integration, per the "only modify when necessary" scope rule.

Deterministic and offline: no external service, no new dependency, no
ML model -- plain regex detectors, same category of implementation as
every other guard in this project.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# -- Canonical secret patterns (single source of truth) ---------------------

# This project's one synthetic canary-secret format, used throughout
# datasets/redteam fixtures. Never a real vendor format.
FAKE_SECRET_PATTERN = re.compile(r"FAKE-SECRET-0000-EXAMPLE(-[A-Z-]+)?", re.IGNORECASE)

# Individual, narrowly-scoped patterns for common cloud/API credential
# shapes -- kept separate (rather than one combined alternation) so each
# can report its own finding category and count.
OPENAI_KEY_PATTERN = re.compile(r"\bsk-[A-Za-z0-9]{16,}\b")
AWS_KEY_PATTERN = re.compile(r"\bAKIA[A-Z0-9]{12,}\b")
GITHUB_TOKEN_PATTERN = re.compile(r"\bghp_[A-Za-z0-9]{20,}\b")

# Full PEM-style private-key block, including the END marker -- DOTALL so
# the multi-line key body is captured and redacted as one unit rather than
# leaving the key material between BEGIN/END exposed.
PRIVATE_KEY_BLOCK_PATTERN = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL
)

# `app/guards/output_guard.py`'s original combined pattern, preserved
# verbatim (same source text, same lack of DOTALL/END-capture) so that
# module's existing BLOCK decision on a bare "-----BEGIN ... PRIVATE
# KEY-----" marker is byte-identical after delegating to this module --
# see the module docstring above.
OUTPUT_GUARD_REALISTIC_SECRET_PATTERN = re.compile(
    r"\bsk-[A-Za-z0-9]{16,}\b|\bAKIA[A-Z0-9]{12,}\b|\bghp_[A-Za-z0-9]{20,}\b|-----BEGIN [A-Z ]*PRIVATE KEY-----",
    re.IGNORECASE,
)

# New for Phase 12C: an HTTP Authorization-header-style bearer token
# appearing directly in text (e.g. echoed by a provider or pasted into a
# document).
BEARER_TOKEN_PATTERN = re.compile(r"\bBearer\s+[A-Za-z0-9\-_.=]{10,}\b")

# New for Phase 12C: an explicit password/secret/API-key *assignment*
# (`key: value` or `key=value`), not a bare mention of the word. Requiring
# the assignment operator and a following non-whitespace value is what
# keeps this from over-redacting ordinary sentences like "please update
# your password" or "the api key field is required".
SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"\b(?:password|passwd|secret|api[_-]?key)\s*[:=]\s*\S+", re.IGNORECASE
)

REDACTED = "[REDACTED]"

# Applied in this fixed order so a private-key block is fully redacted as
# one unit before any narrower pattern could match a fragment inside it.
_DETECTORS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    ("dlp-canary-secret", "canary_secret", FAKE_SECRET_PATTERN),
    ("dlp-private-key", "private_key", PRIVATE_KEY_BLOCK_PATTERN),
    ("dlp-openai-key", "api_key", OPENAI_KEY_PATTERN),
    ("dlp-aws-key", "api_key", AWS_KEY_PATTERN),
    ("dlp-github-token", "api_key", GITHUB_TOKEN_PATTERN),
    ("dlp-bearer-token", "bearer_token", BEARER_TOKEN_PATTERN),
    ("dlp-secret-assignment", "secret_assignment", SECRET_ASSIGNMENT_PATTERN),
)


@dataclass(frozen=True)
class DLPFinding:
    """A safe, count-only finding -- never the detected value itself."""

    detector_id: str
    category: str
    count: int


@dataclass(frozen=True)
class DLPResult:
    redacted_text: str
    findings: tuple[DLPFinding, ...]
    redaction_count: int
    truncated: bool


def scan_and_redact(text: str, *, max_chars: int) -> DLPResult:
    """Deterministically scan `text` for known secret/leak patterns and
    return a redacted copy plus safe finding counts.

    Bounded input size: only the first `max_chars` characters are
    inspected/redacted (a deliberate, documented limitation -- see
    `app/README.md` -- not a DoS-hardening claim). Content beyond that
    bound is passed through unredacted, appended after the inspected
    portion; `truncated=True` signals this happened so a caller can
    decide how to treat it (the Phase 12C pipeline only ever feeds this
    the mock provider's own short, deterministic text, so truncation is
    not expected in practice).

    Never logs or returns the raw matched value anywhere other than
    inside `redacted_text` itself (which has already had it replaced).
    """
    if len(text) > max_chars:
        inspected, tail = text[:max_chars], text[max_chars:]
        truncated = True
    else:
        inspected, tail = text, ""
        truncated = False

    findings: list[DLPFinding] = []
    redacted = inspected
    for detector_id, category, pattern in _DETECTORS:
        count = sum(1 for _ in pattern.finditer(redacted))
        if count:
            findings.append(DLPFinding(detector_id=detector_id, category=category, count=count))
            redacted = pattern.sub(REDACTED, redacted)

    redaction_count = sum(finding.count for finding in findings)
    return DLPResult(
        redacted_text=redacted + tail,
        findings=tuple(findings),
        redaction_count=redaction_count,
        truncated=truncated,
    )
