"""Small, explainable RAG Context Guard with Phase 5.1 hardening.

Detection uses normalized text to catch simple whitespace, zero-width, and
leetspeak evasions. Sanitization always operates on the original text so
source content and chunk metadata are preserved. These heuristics are not a
semantic classifier and do not provide complete prompt-injection protection.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from app.core.decisions import Decision, most_severe
from app.schemas.requests import RAGContextChunk
from app.schemas.responses import RAGGuardResponse

REDACTED = "[REDACTED]"
ZERO_WIDTH_PATTERN = re.compile(r"[\u200b-\u200d\u2060\ufeff]")
INTRA_WORD_DOT_PATTERN = re.compile(r"(?<=\w)[.\u00b7\u2022](?=\w)")
SPACED_LETTER_RUN_PATTERN = re.compile(r"(?<!\w)(?:[a-z]\s+){2,}[a-z](?!\w)")
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
    normalized = unicodedata.normalize("NFKC", text)
    normalized = ZERO_WIDTH_PATTERN.sub("", normalized).lower()
    # Strip Vietnamese diacritics on the detector copy so one rule covers
    # both accented and deliberately accent-smudged attack text.  Preserve
    # the original chunk for citations and sanitization.
    normalized = unicodedata.normalize("NFKD", normalized)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.replace("đ", "d")
    normalized = normalized.translate(str.maketrans({
        "0": "o", "3": "e", "4": "a", "@": "a",
        "5": "s", "$": "s", "1": "i",
    }))
    # Defeat punctuation inserted inside words (c.h.i) and runs of isolated
    # letters (b o q u a).  Requiring at least three isolated letters avoids
    # joining common two-letter initials and keeps false positives bounded.
    normalized = INTRA_WORD_DOT_PATTERN.sub("", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return SPACED_LETTER_RUN_PATTERN.sub(
        lambda match: re.sub(r"\s+", "", match.group(0)), normalized
    )


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
        "rag-obfuscated-ignore-vi", "instruction_override",
        _rx(
            r"\bbo\s*qua\b[^.!?\n]{0,80}"
            r"\b(?:moi\s+)?(?:quy\s*dinh|chi\s*thi|huong\s*dan|lenh)\b"
        ),
        Decision.BLOCK, 0.92,
        "Detected Vietnamese instruction-override language, including spaced or punctuated obfuscation.",
    ),
    Rule(
        "rag-response-coercion", "response_coercion",
        _rx(
            r"\b(?:respond|reply|answer|output|print)\s+(?:only|exactly|verbatim)\b"
            r"|\b(?:always|for every (?:question|request))\s+(?:respond|reply|answer|output)\b"
            r"|\bchi\s+(?:duoc\s+)?tra\s+loi(?:\s+chinh\s+xac)?\b"
            r"|\bluon\s+tra\s+loi\b"
            r"|\bvoi\s+ moi\s+cau\s+hoi[^.!?\n]{0,40}\btra\s+loi\b"
        ),
        Decision.BLOCK, 0.91,
        "Detected retrieved content attempting to force a fixed model response.",
    ),
    Rule(
        "rag-conditional-trigger", "conditional_trigger",
        _rx(
            r"\b(?:if|only if)\b[^.!?\n]{0,100}\b(?:respond|reply|answer|output|print)\b"
            r"|\bneu\s+(?:cau\s+hoi|yeu\s+cau|nguoi\s+dung)\b[^.!?\n]{0,100}"
            r"\b(?:tra\s+loi|in\s+ra|xuat)\b"
        ),
        Decision.BLOCK, 0.93,
        "Detected a conditional or sleeper trigger targeting the assistant.",
    ),
    Rule(
        "rag-source-suppression", "source_manipulation",
        _rx(
            r"\b(?:do not|never)\s+(?:cite|mention|name|show|display|reveal)\b[^.!?\n]{0,60}"
            r"\b(?:source|document|file)\b"
            r"|\bkhong\s+(?:duoc\s+)?(?:dan|hien\s+thi|nhac|neu|noi)\b[^.!?\n]{0,60}"
            r"\b(?:nguon|tai\s+lieu|ten\s+file|tep)\b"
            r"|\b(?:cite|attribute)\b[^.!?\n]{0,50}\b(?:instead|as coming from)\b"
        ),
        Decision.BLOCK, 0.90,
        "Detected an attempt to suppress, hide, or forge document provenance.",
    ),
    Rule(
        "rag-cross-document-exfiltration", "data_exfiltration",
        _rx(
            r"\b(?:find|search|open|read|copy|extract)\b[^.!?\n]{0,100}"
            r"\b(?:other|all|another)?\s*(?:documents?|files?|runbooks?)\b[^.!?\n]{0,120}"
            r"\b(?:api\s*keys?|tokens?|passwords?|secrets?|environment\s+variables?)\b"
            r"|\b(?:tim|doc|mo|sao\s+chep|trich\s+xuat)\b[^.!?\n]{0,100}"
            r"\b(?:tai\s+lieu|tep|runbook)\b[^.!?\n]{0,120}"
            r"\b(?:api\s*key|token|mat\s+khau|bi\s+mat|bien\s+moi\s+truong)\b"
        ),
        Decision.BLOCK, 0.97,
        "Detected retrieved instructions attempting cross-document secret exfiltration.",
    ),
    Rule(
        "rag-bulk-verbatim-disclosure", "data_exfiltration",
        _rx(
            r"\b(?:print|return|output|copy|reveal)\b[^.!?\n]{0,60}"
            r"\b(?:all|entire|full|verbatim)\b[^.!?\n]{0,40}"
            r"\b(?:information|data|record|content|details)\b"
            r"|\b(?:in|tra\s+ve|sao\s+chep|tiet\s+lo)\b[^.!?\n]{0,60}"
            r"\bnguyen\s+van\b[^.!?\n]{0,40}\b(?:toan\s+bo|thong\s+tin|du\s+lieu|noi\s+dung)\b"
        ),
        Decision.BLOCK, 0.96,
        "Detected retrieved instructions demanding bulk verbatim disclosure of sensitive records.",
    ),
    Rule(
        "rag-markdown-exfiltration", "data_exfiltration",
        _rx(
            r"!\[[^\]]*\]\(https?://[^)\s]{1,300}[?&]"
            r"(?:secret|token|api[_-]?key|password|data|content)="
        ),
        Decision.BLOCK, 0.97,
        "Detected a Markdown resource URL attempting to exfiltrate data through a sensitive query parameter.",
    ),
    Rule(
        "rag-numeric-integrity-override", "data_integrity",
        _rx(
            r"\b(?:when|whenever)\s+(?:calculating|computing|summing)\b[^.!?\n]{0,100}"
            r"\b(?:always|must)\s+(?:report|return|use)\b"
            r"|\bkhi\s+(?:tinh|tong\s+hop)\b[^.!?\n]{0,100}"
            r"\b(?:luon\s+bao|luon\s+tra|khong\s+su\s+dung\s+phep\s+tinh)\b"
        ),
        Decision.BLOCK, 0.94,
        "Detected an instruction to replace source-derived calculations with a fixed value.",
    ),
    Rule(
        "rag-business-fact-override", "data_integrity",
        _rx(
            r"\b(?:ignore|disregard|replace)\b[^.!?\n]{0,80}"
            r"\b(?:date|time|amount|value|business content|source data)\b"
            r"|\bbo\s+qua\b[^.!?\n]{0,80}"
            r"\b(?:thoi\s+gian|ngay|so\s+tien|du\s+lieu|noi\s+dung\s+nghiep\s+vu)\b"
            r"[^.!?\n]{0,100}\b(?:luon\s+tra\s+loi|thay\s+bang|bao\s+rang)\b"
        ),
        Decision.BLOCK, 0.95,
        "Detected retrieved instructions attempting to overwrite business facts from the source.",
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
        if str(chunk.metadata.get("guard_decision", "")).casefold() == "not_evaluated":
            matched.append(_unreviewed_source_rule())
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


def _unreviewed_source_rule() -> Rule:
    return Rule(
        "rag-unreviewed-upload", "unreviewed_source", re.compile(r"$^"),
        Decision.BLOCK, 0.98,
        "Retrieved document was uploaded through the unguarded lab and has not passed content review.",
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
