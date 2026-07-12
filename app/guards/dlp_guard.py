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


def _find_non_overlapping_matches(
    inspected: str,
) -> list[tuple[int, int, str, str]]:
    """Collect every detector match against the ORIGINAL (pre-redaction)
    inspected text, then deterministically resolve overlaps, so that
    redacting one detector's match can never create new text that a
    later detector then double-counts.

    Fixed per the Phase 12C Code X audit (Minor #1): the previous
    implementation ran each detector *sequentially over the
    already-redacted text* -- e.g. `api_key=sk-...` was counted once by
    `OPENAI_KEY_PATTERN`, which replaced it with `[REDACTED]`, and then
    `SECRET_ASSIGNMENT_PATTERN` matched `api_key=[REDACTED]` as a
    *second*, spurious finding over the same source span. Collecting all
    matches up front against the untouched text and keeping only
    non-overlapping spans (longest match first at a given start
    position, in `_DETECTORS` order as the tiebreaker) makes each source
    span attributable to exactly one finding.
    """
    matches: list[tuple[int, int, str, str]] = []
    for detector_id, category, pattern in _DETECTORS:
        for m in pattern.finditer(inspected):
            matches.append((m.start(), m.end(), detector_id, category))

    # Longest match wins at a given start position (so a full private-key
    # block is redacted as one unit rather than a narrower pattern
    # claiming a sub-span of it first); `_DETECTORS` order breaks
    # remaining ties deterministically since Python's sort is stable.
    matches.sort(key=lambda item: (item[0], -(item[1] - item[0])))

    accepted: list[tuple[int, int, str, str]] = []
    covered_until = -1
    for start, end, detector_id, category in matches:
        if start < covered_until:
            continue
        accepted.append((start, end, detector_id, category))
        covered_until = end

    accepted.sort(key=lambda item: item[0])
    return accepted


def redact_sensitive_text(text: str) -> str:
    """Redact every centralized detector pattern from `text`, with no
    input-size bound.

    This is the stable, complete redaction entry point for callers that
    must never allow any part of the input to bypass redaction (e.g.
    `app/services/audit_logger.py`'s defense-in-depth safety net) --
    unlike `scan_and_redact`, there is no `max_chars`/tail concept here,
    since a safety-net logger must redact the whole value, not a bounded
    inspection window. Phase 12C fix (Code X Critical #2): the audit
    logger previously imported only 5 of the 7 centralized patterns
    directly, silently omitting the bearer-token and secret-assignment
    detectors added for Phase 12C. Importing this single function instead
    of individual pattern constants means the audit logger can never
    silently drift out of sync with the detector set again.
    """
    accepted = _find_non_overlapping_matches(text)
    pieces: list[str] = []
    cursor = 0
    for start, end, _detector_id, _category in accepted:
        pieces.append(text[cursor:start])
        pieces.append(REDACTED)
        cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces)


def scan_and_redact(text: str, *, max_chars: int) -> DLPResult:
    """Deterministically scan `text` for known secret/leak patterns and
    return a redacted copy plus safe finding counts.

    Bounded input size: only the first `max_chars` characters are ever
    inspected. **Fixed per the Phase 12C Code X audit (Critical #1):**
    the previous implementation appended the uninspected tail back onto
    the returned text verbatim, so a secret placed beyond the inspection
    boundary reached the Output Guard, the API response, and audit
    metadata completely unredacted -- a direct violation of "no
    provider-output character may reach downstream consumers unless it
    was actually inspected." The fix adopts the documented safe model:
    **the uninspected tail is now dropped entirely, never appended** --
    `redacted_text` only ever contains content that was actually passed
    through the detector set. `truncated=True` tells the caller this
    happened (surfaced in `app/services/rag_query.py`'s stage_results),
    so truncation is auditable rather than silent; it is not expected in
    practice against the deterministic Mock LLM Provider's short output,
    but the pipeline must be safe regardless of provider implementation.

    Never logs or returns the raw matched value anywhere other than
    inside `redacted_text` itself (which has already had it replaced).
    """
    if type(max_chars) is not int or max_chars <= 0:
        raise ValueError("max_chars must be a positive integer")

    if len(text) > max_chars:
        inspected = text[:max_chars]
        truncated = True
    else:
        inspected = text
        truncated = False

    accepted = _find_non_overlapping_matches(inspected)

    counts: dict[tuple[str, str], int] = {}
    pieces: list[str] = []
    cursor = 0
    for start, end, detector_id, category in accepted:
        pieces.append(inspected[cursor:start])
        pieces.append(REDACTED)
        cursor = end
        key = (detector_id, category)
        counts[key] = counts.get(key, 0) + 1
    pieces.append(inspected[cursor:])
    redacted = "".join(pieces)

    findings = tuple(
        DLPFinding(detector_id=detector_id, category=category, count=count)
        for (detector_id, category), count in counts.items()
    )
    redaction_count = sum(finding.count for finding in findings)
    return DLPResult(
        redacted_text=redacted,
        findings=findings,
        redaction_count=redaction_count,
        truncated=truncated,
    )
