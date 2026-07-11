"""Small, explainable RAG Context Guard with Phase 5.1 hardening.

Detection uses normalized text to catch simple whitespace, zero-width, and
leetspeak evasions. Sanitization always operates on the original text so
source content and chunk metadata are preserved. These heuristics are not a
semantic classifier and do not provide complete prompt-injection protection.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.decisions import Decision, most_severe
from app.schemas.requests import RAGContextChunk
from app.schemas.responses import RAGGuardResponse

REDACTED = "[REDACTED]"
ZERO_WIDTH_PATTERN = re.compile(r"[\u200b-\u200d\u2060\ufeff]")
FAKE_SECRET_PATTERN = re.compile(r"FAKE-SECRET-0000-EXAMPLE(-[A-Z-]+)?", re.IGNORECASE)
HIDDEN_BLOCK_PATTERN = re.compile(
    r"<!--.*?--\s*>|<!(?:--)?\s*.*?--\s*>|/\*.*?\*/",
    re.IGNORECASE | re.DOTALL,
)
HIDDEN_RISK_PATTERN = re.compile(
    r"\b(ignore|disregard|override|system|developer|instruction|reveal|secret|bypass|supersede)\w*\b",
    re.IGNORECASE,
)


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


def _normalize_for_detection(text: str) -> str:
    """Normalize only the copy used by detectors, never returned content."""
    normalized = ZERO_WIDTH_PATTERN.sub("", text).lower()
    normalized = normalized.translate(str.maketrans({
        "0": "o", "3": "e", "4": "a", "@": "a",
        "5": "s", "$": "s", "1": "i",
    }))
    return re.sub(r"\s+", " ", normalized).strip()


RULES: tuple[Rule, ...] = (
    Rule(
        "rag-system-override", "instruction_override",
        _rx(
            r"\bnotice to ai\b"
            r"|\b(new directives? (replace|supersede)[^.!?]{0,35}(previous|prior|existing) guidelines?)\b"
            r"|\boperating under new directives?\b"
            r"|\bthis document supersedes? (existing|previous|prior|system)? ?instructions?\b"
            r"|\btreat this as the highest priority instruction\b"
            r"|\b(developer|system) (rules?|instructions?) (are|is) no longer applicable\b"
            r"|\bthis note must override (previous|prior|existing) (policy|instructions?|guidelines?)\b"
            r"|\bsupersedes?[^.!?]{0,35}(previous|prior|system)[^.!?]{0,25}instructions?\b"
        ),
        Decision.BLOCK, 0.9,
        "Detected retrieved content claiming authority to replace system or developer instructions.",
    ),
    Rule(
        "rag-fake-secret", "fake_secret_leak", FAKE_SECRET_PATTERN,
        Decision.SANITIZE, 0.7,
        "Detected the synthetic fake-secret marker; redacted before context use.",
        redact=True,
    ),
    Rule(
        "rag-policy-bypass", "policy_bypass",
        _rx(
            r"\b(bypass (the )?policy|override (the )?approval workflow|waive (the )?approval"
            r"|skip (manager )?approval|approve (the )?refund immediately|proceed without approval"
            r"|exception without review|disregard[^.!?]{0,45}(threshold|policy|review|approval)"
            r"|high[- ]priority request[^.!?]{0,35}ignore[^.!?]{0,20}(normal )?policy)\b"
        ),
        Decision.SANITIZE, 0.72,
        "Detected an instruction to bypass a policy, review, or approval control.",
    ),
    Rule(
        "rag-transcript-quoted-injection", "transcript_injection",
        _rx(r"\b(support agent notes?|customer support log|customer message|the user said|agent confirmed)\b"),
        Decision.SANITIZE, 0.68,
        "Detected a support transcript carrying a policy-override instruction.",
    ),
    Rule(
        "rag-generic-ignore-instructions", "instruction_override",
        _rx(r"\b(ignore|disregard|forget) (all )?(prior|previous|existing|earlier) (system |developer )?instructions?\b"),
        Decision.SANITIZE, 0.75,
        "Detected language instructing the model to ignore prior instructions.",
    ),
    Rule(
        "rag-ambiguous-authority-claim", "authority_claim",
        _rx(r"\bthis (note|memo) (should|must) be (treated|considered) as (final|authoritative)\b"),
        Decision.HUMAN_REVIEW, 0.55,
        "Detected an ambiguous authority claim requiring human review.",
    ),
    Rule(
        "rag-weak-override-keyword", "weak_signal", _rx(r"\boverride\b"),
        Decision.LOG_ONLY, 0.3,
        "Detected the word 'override'; logged as a weak signal that may be benign.",
    ),
)

TRANSCRIPT_MARKER_PATTERN = _rx(
    r"\b(support agent notes?|customer support log|customer message|the user said|agent confirmed)\b"
)
TRANSCRIPT_ATTACK_PATTERN = _rx(
    r"\b(ignore|disregard|bypass|override)\b[^.!?]{0,80}\b(policy|approval|instructions?|workflow)\b"
    r"|\bignore\b[^.!?]{0,80}\b(restrictions?|rules?|guidelines?)\b"
    r"|\b(approve|refund|proceed)\b[^.!?]{0,45}\bwithout approval\b"
    r"|\bapprove (the )?refund immediately\b"
)


def evaluate_rag_context(chunks: list[RAGContextChunk]) -> RAGGuardResponse:
    all_matched: list[Rule] = []
    per_chunk_matches: list[tuple[RAGContextChunk, list[Rule], bool]] = []

    for chunk in chunks:
        normalized = _normalize_for_detection(chunk.text)
        matched = [
            rule for rule in RULES
            if rule.category not in {"transcript_injection", "fake_secret_leak"}
            and rule.pattern.search(normalized)
        ]
        if FAKE_SECRET_PATTERN.search(chunk.text):
            matched.append(next(rule for rule in RULES if rule.category == "fake_secret_leak"))
        transcript_attack = bool(
            TRANSCRIPT_MARKER_PATTERN.search(normalized)
            and TRANSCRIPT_ATTACK_PATTERN.search(normalized)
        )
        if transcript_attack:
            matched.append(next(rule for rule in RULES if rule.category == "transcript_injection"))

        hidden_attack = any(
            HIDDEN_RISK_PATTERN.search(_normalize_for_detection(block.group(0)))
            for block in HIDDEN_BLOCK_PATTERN.finditer(chunk.text)
        )
        if hidden_attack:
            matched.append(_hidden_rule())

        matched = _dedupe_rules(matched)
        per_chunk_matches.append((chunk, matched, hidden_attack))
        all_matched.extend(matched)

    if not all_matched:
        return RAGGuardResponse(decision=Decision.ALLOW, sanitized_chunks=list(chunks))

    categories = {rule.category for rule in all_matched}
    decisions = [rule.decision for rule in all_matched]
    # Compound signals are deterministic: paired override+bypass evidence is
    # at least sanitize; explicit system replacement remains block.
    if {"instruction_override", "policy_bypass"} <= categories:
        decisions.append(Decision.SANITIZE)

    final_decision = most_severe(decisions)
    sanitized_chunks: list[RAGContextChunk] | None
    if final_decision == Decision.BLOCK:
        sanitized_chunks = None
    elif final_decision == Decision.SANITIZE:
        sanitized_chunks = [
            RAGContextChunk(
                doc_id=chunk.doc_id,
                text=_sanitize_text(chunk.text, matched, hidden_attack),
                metadata=chunk.metadata,
            )
            for chunk, matched, hidden_attack in per_chunk_matches
        ]
    else:
        sanitized_chunks = list(chunks)

    return RAGGuardResponse(
        decision=final_decision,
        sanitized_chunks=sanitized_chunks,
        reasons=_dedupe([rule.reason for rule in all_matched]),
        matched_rules=_dedupe([rule.rule_id for rule in all_matched]),
        risk_score=max(rule.weight for rule in all_matched),
    )


def _hidden_rule() -> Rule:
    return Rule(
        "rag-hidden-html-comment", "hidden_instruction", HIDDEN_BLOCK_PATTERN,
        Decision.SANITIZE, 0.78,
        "Detected instruction-like content in a hidden HTML, XML, JS, or CSS comment block.",
    )


def _sanitize_text(text: str, matched: list[Rule], hidden_attack: bool) -> str:
    cleaned = text
    if hidden_attack:
        cleaned = HIDDEN_BLOCK_PATTERN.sub(
            lambda match: "" if HIDDEN_RISK_PATTERN.search(
                _normalize_for_detection(match.group(0))
            ) else match.group(0),
            cleaned,
        )
    if any(rule.redact for rule in matched):
        cleaned = FAKE_SECRET_PATTERN.sub(REDACTED, cleaned)

    removable = {
        rule.category for rule in matched
        if rule.decision == Decision.SANITIZE
    } - {"hidden_instruction", "fake_secret_leak"}
    if removable:
        lines = cleaned.splitlines(keepends=True)
        kept = []
        for line in lines:
            normalized_line = _normalize_for_detection(line)
            malicious = any(
                rule.category in removable and rule.pattern.search(normalized_line)
                for rule in matched if rule.category != "transcript_injection"
            )
            if "transcript_injection" in removable:
                malicious = malicious or bool(TRANSCRIPT_ATTACK_PATTERN.search(normalized_line))
            if not malicious:
                kept.append(line)
        cleaned = "".join(kept)
    return re.sub(r"[ \t]+", " ", cleaned).strip()


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _dedupe_rules(rules: list[Rule]) -> list[Rule]:
    return list({rule.rule_id: rule for rule in rules}.values())
