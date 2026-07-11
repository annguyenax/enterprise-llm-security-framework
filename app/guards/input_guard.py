"""Rule-based Input Guard.

Lab-scale regex/keyword heuristics only — this is explicitly NOT a machine-
learned classifier and NOT a claim of comprehensive prompt-injection
coverage. Rule categories follow the taxonomy designed in
docs/evaluation/red-team-test-design.md and validated in
docs/dataset/source-mapping.md. See docs/dataset/dataset-methodology.md
§6-7 for what this kind of heuristic can and cannot prove.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.decisions import Decision, most_severe
from app.schemas.responses import GuardDecisionResponse


@dataclass(frozen=True)
class Rule:
    rule_id: str
    category: str
    pattern: re.Pattern[str]
    decision: Decision
    weight: float
    reason: str


def _rx(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


# Each rule maps to one of the 7 required categories from the task spec:
# direct prompt injection, role override, jailbreak wording, sensitive
# extraction, hidden/system prompt reveal, malicious retrieved context,
# tool/action misuse — plus instruction-hierarchy attacks from the Phase 3
# benchmark design.
RULES: tuple[Rule, ...] = (
    # --- direct prompt injection / ignore-instructions ---
    Rule(
        "direct-ignore-instructions", "direct_prompt_injection",
        _rx(r"\b(ignore|disregard|forget)\b[^.?!]{0,40}\b(previous|prior|above|earlier|all)\b[^.?!]{0,20}\binstructions?\b"),
        Decision.BLOCK, 0.95,
        "Detected an 'ignore/disregard previous instructions' style direct prompt injection pattern.",
    ),
    Rule(
        "direct-system-override", "direct_prompt_injection",
        _rx(r"\bsystem prompt override\b|\bsupersedes?\b[^.?!]{0,30}\b(earlier|previous|system)\b[^.?!]{0,20}\binstructions?\b"),
        Decision.BLOCK, 0.9,
        "Detected an explicit claim to override the system prompt/instructions.",
    ),

    # --- role override ---
    Rule(
        "role-you-are-now", "role_override",
        _rx(r"\byou are now\b[^.?!]{0,60}\b(unbound|unrestricted|dan|freegpt|devmode|no rules?)\b"),
        Decision.BLOCK, 0.85,
        "Detected an attempt to reassign the assistant's identity to an unrestricted alter-ego.",
    ),
    Rule(
        "role-act-as-admin", "role_override",
        _rx(r"\bact as( the)?( system)? administrator\b|\broleplay as\b|\bpretend (you are|to be)\b"),
        Decision.BLOCK, 0.8,
        "Detected a request to roleplay as an administrator or adopt a different persona.",
    ),
    Rule(
        "role-no-longer-assistant", "role_override",
        _rx(r"\byou are no longer\b[^.?!]{0,40}\bassistant\b"),
        Decision.BLOCK, 0.8,
        "Detected an attempt to strip the assistant of its configured identity.",
    ),

    # --- instruction hierarchy attack ---
    Rule(
        "hierarchy-priority-claim", "instruction_hierarchy_attack",
        _rx(r"\bhigher priority than\b|\bhighest[- ]priority instruction\b|\bpriority level:?\s*critical\b"),
        Decision.BLOCK, 0.85,
        "Detected a false claim that this message outranks the system prompt in priority.",
    ),
    Rule(
        "hierarchy-fake-sender-role", "instruction_hierarchy_attack",
        _rx(r"\btreat this (message|instruction) as coming from the developer\b"),
        Decision.BLOCK, 0.8,
        "Detected an attempt to spoof a higher-trust sender role from within user input.",
    ),

    # --- jailbreak ---
    Rule(
        "jailbreak-keyword", "jailbreak",
        _rx(r"\bjailbreak\b|\bdo anything now\b|\bDAN\b|\bno content restrictions?\b|\bno content polic(y|ies)\b"),
        Decision.BLOCK, 0.9,
        "Detected a known jailbreak keyword or template reference.",
    ),
    Rule(
        "jailbreak-fictional-frame", "jailbreak",
        _rx(r"\b(roleplay|game|story|dialogue)\b[^.?!]{0,80}\bno (content )?restrictions?\b"),
        Decision.BLOCK, 0.75,
        "Detected a fictional/game framing combined with a 'no restrictions' claim — a common jailbreak wrapper.",
    ),

    # --- sensitive extraction / reveal hidden or system prompt ---
    Rule(
        "extract-system-prompt", "sensitive_extraction",
        _rx(r"\bsystem prompt\b|\binternal configuration\b|\bhidden instructions?\b"),
        Decision.BLOCK, 0.85,
        "Detected a request referencing the system prompt, hidden instructions, or internal configuration.",
    ),
    Rule(
        "extract-reveal-instructions", "sensitive_extraction",
        _rx(r"\b(reveal|print|output|repeat|disclose)\b[^.?!]{0,30}\b(your )?instructions\b"),
        Decision.BLOCK, 0.85,
        "Detected a request to reveal/print/repeat the assistant's instructions verbatim.",
    ),
    Rule(
        "extract-other-person-data", "sensitive_extraction",
        _rx(r"\banother (employee|user)'?s\b"),
        Decision.BLOCK, 0.7,
        "Detected a request for another individual's private/HR data.",
    ),

    # --- RAG context manipulation / malicious retrieved context ---
    Rule(
        "ragctx-replace-document", "rag_context_manipulation",
        _rx(r"\bthe retrieved document is wrong\b|\breplace it with this instead\b"),
        Decision.SANITIZE, 0.6,
        "Detected an attempt to supply replacement text for a retrieved document; offending fragment stripped.",
    ),
    Rule(
        "ragctx-ignore-retrieved", "rag_context_manipulation",
        _rx(r"\bignore (anything|everything) else you retrieved\b|\bdisregard the retrieved\b"),
        Decision.BLOCK, 0.8,
        "Detected an attempt to make the assistant discard legitimately retrieved context.",
    ),
    Rule(
        "ragctx-fake-authority", "rag_context_manipulation",
        _rx(r"\bonly trust the following text\b|\btreat the following as (an )?authoritative\b"),
        Decision.BLOCK, 0.8,
        "Detected an attempt to inject fake authoritative context directly into the prompt.",
    ),

    # --- tool / action misuse ---
    Rule(
        "tool-file-or-api-access", "tool_action_misuse",
        _rx(r"\buse your (file system|api|database) access\b"),
        Decision.BLOCK, 0.8,
        "Detected a request to exercise a tool/system-access capability this MVP does not have.",
    ),
    Rule(
        "tool-send-email", "tool_action_misuse",
        _rx(r"\bsend an email on my behalf\b"),
        Decision.BLOCK, 0.75,
        "Detected a request to send messages on the user's behalf — no such capability exists.",
    ),
    Rule(
        "tool-execute-query", "tool_action_misuse",
        _rx(r"\bexecute a database query\b"),
        Decision.BLOCK, 0.8,
        "Detected a request to execute a database query — no such capability exists.",
    ),
    Rule(
        "tool-admin-panel", "tool_action_misuse",
        _rx(r"\baccess the (internal )?admin(istration)? panel\b"),
        Decision.BLOCK, 0.8,
        "Detected a request to access an administration panel — no such capability exists.",
    ),
    Rule(
        "tool-reset-password", "tool_action_misuse",
        _rx(r"\breset (another|a) user'?s? password\b"),
        Decision.BLOCK, 0.8,
        "Detected a request to reset another user's password without verification.",
    ),
    Rule(
        "tool-delete-logs", "tool_action_misuse",
        _rx(r"\bdelete the (application )?logs\b"),
        Decision.BLOCK, 0.8,
        "Detected a request to delete application logs — no such capability exists.",
    ),
)


def evaluate_input(prompt: str) -> GuardDecisionResponse:
    """Evaluate a raw user prompt against the rule set and return a decision."""
    matched = [rule for rule in RULES if rule.pattern.search(prompt)]

    if not matched:
        return GuardDecisionResponse(decision=Decision.ALLOW)

    final_decision = most_severe([rule.decision for rule in matched])
    risk_score = max(rule.weight for rule in matched)
    reasons = [rule.reason for rule in matched]
    matched_rules = [rule.rule_id for rule in matched]

    sanitized_text: str | None = None
    if final_decision == Decision.SANITIZE:
        sanitized_text = _sanitize_prompt(prompt, matched)

    return GuardDecisionResponse(
        decision=final_decision,
        sanitized_text=sanitized_text,
        reasons=reasons,
        matched_rules=matched_rules,
        risk_score=risk_score,
    )


def _sanitize_prompt(prompt: str, matched: list[Rule]) -> str:
    """Best-effort truncation at the first SANITIZE-triggering match.

    Kept deliberately simple: SANITIZE-tier rules target replacement-style
    injection attempts, where everything from the trigger phrase onward is
    untrusted, so truncating there is a reasonable first pass. A real
    implementation would likely do more targeted span removal.
    """
    cleaned = prompt
    for rule in matched:
        if rule.decision == Decision.SANITIZE:
            match = rule.pattern.search(cleaned)
            if match:
                cleaned = cleaned[: match.start()].strip()
    return cleaned or "[prompt content removed by Input Guard sanitization]"
