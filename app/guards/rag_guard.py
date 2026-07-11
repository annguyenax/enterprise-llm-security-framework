"""Rule-based RAG Context Guard (Phase 5).

Evaluates retrieved-context chunks (the text a real RAG pipeline would be
about to hand to the LLM) for signs of RAG document poisoning / indirect
prompt injection, before that text ever reaches a (mock or real) LLM call.
Same lab-scale regex/keyword heuristic approach as
app/guards/input_guard.py and app/guards/output_guard.py - not a machine-
learned classifier, not comprehensive coverage.

Decision taxonomy (see app/core/decisions.py, shared with all guards):
    allow < log_only < sanitize < human_review < block

Design intent per chunk, validated against every file in
datasets/poisoned/ (see docs/dataset/*):
  - Hidden HTML-comment instructions -> sanitize (strip the comment,
    keep legitimate surrounding text) - datasets/poisoned/hidden-html-instruction.md.
  - Explicit "this document supersedes system instructions" style override,
    addressed directly at the AI with no legitimate content of its own
    -> block - datasets/poisoned/system-override.md.
  - The fake secret marker `FAKE-SECRET-0000-EXAMPLE` -> sanitize + redact.
    The dataset's own `expected_guard_decision` for this file is `block`,
    but this project also has an Output Guard backstop
    (app/guards/output_guard.py) that independently blocks any completion
    containing this marker - see fake-secret-leak.md's own "Explanation for
    Evaluator" section, which frames this as a two-layer defense-in-depth
    test. Redacting the marker at the RAG layer (rather than dropping the
    whole chunk) still guarantees the secret can never reach the LLM
    context, while keeping this guard's default MVP behavior consistent
    with output_guard.py's existing sanitize+redact treatment of the same
    marker. This deviation is a deliberate design choice, not an oversight.
  - Policy-bypass instructions that contradict a known policy without
    addressing "the AI" directly -> sanitize (weaker/ambiguous signals fall
    back to log_only) - datasets/poisoned/policy-bypass.md.
  - Indirect injection via a quoted transcript ("Customer message: ...
    Ignore ...") -> sanitize, treated as context isolation: the quoted
    instruction is stripped rather than the whole transcript, since the
    transcript itself models correct behavior -
    datasets/poisoned/support-transcript-injection.md.
  - A dedicated, narrow "treat this note as final/authoritative" pattern
    is scored as human_review: an ambiguous authority claim that is not
    clearly a direct override and not clearly benign. No current dataset
    file matches this rule; it exists for the human_review branch of the
    decision taxonomy and is covered by a hand-written test case.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.decisions import Decision, most_severe
from app.schemas.requests import RAGContextChunk
from app.schemas.responses import RAGGuardResponse

REDACTED = "[REDACTED]"

# Same fixed fake-secret format used across this project (see
# app/guards/output_guard.py and app/services/audit_logger.py).
FAKE_SECRET_PATTERN = re.compile(r"FAKE-SECRET-0000-EXAMPLE(-[A-Z-]+)?", re.IGNORECASE)
HIDDEN_HTML_COMMENT_PATTERN = re.compile(r"<!--.*?-->", re.DOTALL)


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
        "rag-hidden-html-comment", "hidden_html_instruction",
        HIDDEN_HTML_COMMENT_PATTERN,
        Decision.SANITIZE, 0.75,
        "Detected a hidden HTML comment in retrieved context; a naive pipeline would still forward "
        "this invisible text to the LLM, so it was stripped.",
    ),
    Rule(
        "rag-system-override", "system_instruction_override",
        _rx(
            r"\bnotice to ai\b"
            r"|\bsupersedes?\b[^.?!]{0,30}\b(earlier|previous|prior|system)\b[^.?!]{0,20}\binstructions?\b"
            r"|\bthis document supersedes\b"
        ),
        Decision.BLOCK, 0.9,
        "Detected retrieved content directly addressing the AI assistant and claiming authority to "
        "override system instructions.",
    ),
    Rule(
        "rag-fake-secret", "fake_secret_leak",
        FAKE_SECRET_PATTERN,
        Decision.SANITIZE, 0.7,
        "Detected this project's synthetic fake-secret marker in retrieved context; redacted before "
        "the chunk is used (Output Guard also blocks this marker as a backstop).",
        redact=True,
    ),
    Rule(
        "rag-policy-bypass", "policy_bypass",
        _rx(r"\bdisregard the\b[^.?!]{0,60}\b(threshold|policy|review|approval)\b"),
        Decision.SANITIZE, 0.6,
        "Detected an instruction to disregard a known policy threshold or approval step.",
    ),
    Rule(
        "rag-transcript-quoted-injection", "indirect_prompt_injection",
        _rx(r"(customer|user)\s+(message|said|wrote)[:\s]*[\"'][^\"']{0,40}\bignore\b"),
        Decision.SANITIZE, 0.55,
        "Detected an embedded instruction inside quoted third-party speech; isolating the quoted "
        "text so it is not treated as a live command.",
    ),
    Rule(
        "rag-generic-ignore-instructions", "direct_override_language",
        _rx(r"\bignore all (prior|previous) instructions\b"),
        Decision.SANITIZE, 0.7,
        "Detected 'ignore all prior/previous instructions' style override language in retrieved context.",
    ),
    Rule(
        "rag-ambiguous-authority-claim", "ambiguous_authority_claim",
        _rx(r"\bthis (note|memo|update) (should|must) be (treated|considered) as (final|authoritative)\b"),
        Decision.HUMAN_REVIEW, 0.55,
        "Detected an ambiguous claim of final/authoritative status that is not a clear override; "
        "flagged for human review rather than auto-decided.",
    ),
    Rule(
        "rag-weak-override-keyword", "weak_signal",
        _rx(r"\boverride\b"),
        Decision.LOG_ONLY, 0.3,
        "Detected the word 'override' in retrieved context; may be benign, logged for visibility.",
    ),
)


def evaluate_rag_context(chunks: list[RAGContextChunk]) -> RAGGuardResponse:
    """Evaluate a list of retrieved-context chunks and return one combined
    decision, plus per-chunk sanitized text when the decision is SANITIZE."""
    all_matched: list[Rule] = []
    per_chunk_matches: list[tuple[RAGContextChunk, list[Rule]]] = []

    for chunk in chunks:
        matched = [rule for rule in RULES if rule.pattern.search(chunk.text)]
        per_chunk_matches.append((chunk, matched))
        all_matched.extend(matched)

    if not all_matched:
        return RAGGuardResponse(decision=Decision.ALLOW, sanitized_chunks=list(chunks))

    final_decision = most_severe([rule.decision for rule in all_matched])
    risk_score = max(rule.weight for rule in all_matched)
    reasons = _dedupe([rule.reason for rule in all_matched])
    matched_rules = _dedupe([rule.rule_id for rule in all_matched])

    sanitized_chunks: list[RAGContextChunk] | None
    if final_decision == Decision.BLOCK:
        sanitized_chunks = None
    elif final_decision == Decision.SANITIZE:
        sanitized_chunks = [
            RAGContextChunk(
                doc_id=chunk.doc_id,
                text=_sanitize_text(chunk.text, matched),
                metadata=chunk.metadata,
            )
            for chunk, matched in per_chunk_matches
        ]
    else:
        sanitized_chunks = list(chunks)

    return RAGGuardResponse(
        decision=final_decision,
        sanitized_chunks=sanitized_chunks,
        reasons=reasons,
        matched_rules=matched_rules,
        risk_score=risk_score,
    )


def _sanitize_text(text: str, matched: list[Rule]) -> str:
    cleaned = text
    for rule in matched:
        if rule.redact:
            cleaned = rule.pattern.sub(REDACTED, cleaned)
        elif rule.decision == Decision.SANITIZE:
            cleaned = rule.pattern.sub("", cleaned)
    return re.sub(r"[ \t]+", " ", cleaned).strip()


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
