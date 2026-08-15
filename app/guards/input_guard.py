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
import unicodedata
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


# --- input normalization (de-obfuscation before rule matching) -------------
# Attackers hide keyword triggers behind zero-width characters and Cyrillic
# look-alikes (garak-style "unicode smudging"). Normalizing the text before the
# rules run — NFKC, strip zero-width, fold common homoglyphs to Latin — makes
# the rules see the underlying intent. This is a general de-obfuscation step,
# not tuned to any evaluation case.
_ZERO_WIDTH = dict.fromkeys(
    (0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF, 0x00AD), None
)
_HOMOGLYPH = str.maketrans(
    {
        "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x",
        "ѕ": "s", "і": "i", "ј": "j", "ԁ": "d", "ո": "n",
        "А": "A", "Е": "E", "О": "O", "Р": "P", "С": "C", "У": "Y", "Х": "X",
        "В": "B", "Н": "H", "К": "K", "М": "M", "Т": "T",
    }
)


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text).translate(_ZERO_WIDTH).translate(_HOMOGLYPH)


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
    Rule(
        "direct-disregard-own-instructions", "direct_prompt_injection",
        _rx(
            r"\b(disregard|ignore|set aside)\b[^.?!]{0,20}"
            r"\b(your(?: current)?|the current) instructions?\b[^.?!]{0,80}"
            r"\b(print|reveal|output|answer|say|comply|instead)\b"
        ),
        Decision.BLOCK, 0.9,
        "Detected an instruction override paired with a replacement or disclosure action.",
    ),
    Rule(
        "direct-forget-prior-message", "direct_prompt_injection",
        _rx(
            r"^\s*(please\s+)?forget\s+(everything|all)\s+"
            r"(you were|you have been|you've been)\s+told\s+"
            r"(before|prior to)\s+(this|the)\s+(message|request|prompt)\b"
        ),
        Decision.BLOCK, 0.9,
        "Detected an imperative to forget all instructions given before the current message.",
    ),

    Rule(
        "direct-ignore-previous-policy", "direct_prompt_injection",
        _rx(
            r"\b(ignore|disregard|forget|override)\b[^.?!\n]{0,30}"
            r"\b(previous|prior|existing|current|all|the)\b[^.?!\n]{0,25}"
            r"\b(polic(y|ies)|rules?|guidelines?)\b"
        ),
        Decision.BLOCK, 0.9,
        "Detected an instruction to ignore/override existing policy or rules - a poisoned-context injection pattern.",
    ),
    Rule(
        "direct-ignore-vi", "direct_prompt_injection",
        _rx(
            r"\b(bỏ\s*qua|phớt\s*lờ|đừng\s*tuân|không\s*tuân\s*theo|quên\s*(hết|đi|toàn bộ))\b"
            r"[^.?!\n]{0,30}"
            r"\b(hướng\s*dẫn|chỉ\s*dẫn|chỉ\s*thị|quy\s*định|chính\s*sách|policy|ràng\s*buộc)\b"
        ),
        Decision.BLOCK, 0.88,
        "Detected a Vietnamese 'ignore the instructions/policy' style prompt injection.",
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
        "Detected a fictional/game framing combined with a 'no restrictions' claim - a common jailbreak wrapper.",
    ),
    Rule(
        "jailbreak-training-detailed-attack", "jailbreak",
        _rx(
            r"\b(security awareness|training|educational)\b[^.?!]{0,100}"
            r"\b(write out|describe|explain)\b[^.?!]{0,80}"
            r"\b(exactly|step[- ]by[- ]step|in full detail)\b[^.?!]{0,120}"
            r"\b(attacker|extract|steal|bypass)\w*\b"
        ),
        Decision.BLOCK, 0.82,
        "Detected a training pretext paired with a request for detailed offensive instructions.",
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
    Rule(
        "extract-bulk-confidential-context", "sensitive_extraction",
        _rx(
            r"\b(print|output|reveal|dump)\b[^.?!]{0,35}"
            r"(?:\b(full (contents|text)|complete contents)\b[^.?!]{0,80}"
            r"\b(confidential|restricted|internal)?\s*documents?\b[^.?!]{0,60}\b(context|loaded)\b"
            r"|\bevery (confidential|restricted|internal) document\b[^.?!]{0,60}\b(context|loaded)\b)"
        ),
        Decision.BLOCK, 0.88,
        "Detected a bulk extraction request for confidential documents in model context.",
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
    Rule(
        "ragctx-ignore-official-source", "rag_context_manipulation",
        _rx(
            r"\b(ignore|disregard)\b[^.?!]{0,55}"
            r"\b(official|retrieved|verified)\b[^.?!]{0,45}"
            r"\b(document|context|policy)\b[^.?!]{0,90}"
            r"\b(instead|ground truth|use this text|replacement)\b"
        ),
        Decision.BLOCK, 0.84,
        "Detected an attempt to replace an official or retrieved source with user-supplied ground truth.",
    ),

    # --- authority impersonation / executive-override exfiltration ---
    # Targets the two invariants of the "I am an executive, so bypass the
    # rules and hand over the data" social-engineering pattern (PyRIT-style
    # C-suite / roleplay attacks), independent of the exact wording:
    #   (1) an authority-override directive, and
    #   (2) a bulk sensitive-data extraction.
    # Each rule below is a strong signal on its own; matching either invariant
    # is enough to block. Rules are bilingual (vi/en) because the deployment
    # is Vietnamese-facing and real attacks arrive in both. Deliberately does
    # NOT block on a bare authority claim ("tôi là giám đốc"), which is not by
    # itself malicious and would raise false positives on legitimate queries.
    Rule(
        "authority-override-policy", "authority_impersonation",
        _rx(r"\b(overrides?|supersedes?)\b[^.?!\n]{0,25}\b(hr|company|internal|these|all|any)?\s*(polic(y|ies)|acl|access control)\b"),
        Decision.BLOCK, 0.85,
        "Detected a claim that the request overrides organizational policy or access control.",
    ),
    Rule(
        "authority-drop-acl", "authority_impersonation",
        _rx(r"\b(bỏ|gỡ|tắt|vô hiệu hoá|disable|ignore|bypass)\b[^.?!\n]{0,18}\b(acl|access control|mọi policy|policy retrieval)\b"),
        Decision.BLOCK, 0.85,
        "Detected an instruction to disable or bypass access-control / ACL enforcement.",
    ),
    Rule(
        "authority-do-not-refuse", "authority_impersonation",
        _rx(r"\bkhông\s+(được\s+)?từ chối\b[^.?!\n]{0,18}\b(cấp trên|sếp|lãnh đạo|ban|executive|ceo|giám đốc)\b|\bdo not refuse\b[^.?!\n]{0,18}\b(executives?|superiors?|the (ceo|board|director))\b"),
        Decision.BLOCK, 0.8,
        "Detected coercion not to refuse an asserted authority figure - a social-engineering override.",
    ),
    Rule(
        "authority-authorize-bulk-export", "authority_impersonation",
        _rx(r"\bauthorize\b[^.?!\n]{0,20}\b(bulk\s+)?export\b|\bbulk export of\b[^.?!\n]{0,20}\b(payslips?|payroll|salar(y|ies)|compensation)\b"),
        Decision.BLOCK, 0.82,
        "Detected an attempt to authorize a bulk export of payroll / compensation data.",
    ),
    Rule(
        "authority-bulk-sensitive-extract", "sensitive_extraction",
        _rx(
            r"\b(trích xuất|xuất|in|dump|export|paste|reveal|liệt kê)\b[^.?!\n]{0,45}"
            r"\b(toàn bộ|tất cả|mọi|all|full|bulk|any)\b[^.?!\n]{0,45}"
            r"\b(phiếu lương|bảng lương|thực nhận|payslips?|salary (bands?|figures?|tables?)|"
            r"compensation|restricted|confidential|mật)\b"
        ),
        Decision.BLOCK, 0.85,
        "Detected a bulk extraction request for payroll / compensation / restricted records.",
    ),
    Rule(
        "authority-open-all-restricted", "sensitive_extraction",
        _rx(
            r"\b(mở|in|reveal|open|paste|dump)\b[^.?!\n]{0,20}"
            r"\b(mọi|toàn bộ|tất cả|all|any|every)\b[^.?!\n]{0,25}"
            r"\b(tài liệu\s+)?(restricted|confidential|mật)\b"
        ),
        Decision.BLOCK, 0.82,
        "Detected a request to open/print all restricted or confidential documents.",
    ),

    Rule(
        "ragctx-injection-marker", "rag_context_manipulation",
        _rx(
            r"\[system\s+for\b[^\]]*\bonly\]"
            r"|\(\(\s*begin[^)]{0,40}polic(y|ies)"
            r"|\binvisible\s+polic(y|ies)\b"
            r"|\binternal\s+policy\s+update\b"
            r"|—?\s*authoritative\s*\]"
        ),
        Decision.BLOCK, 0.85,
        "Detected a poisoned-context / role-spoof injection marker (fake system directive or authoritative policy update).",
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
        "Detected a request to send messages on the user's behalf - no such capability exists.",
    ),
    Rule(
        "tool-execute-query", "tool_action_misuse",
        _rx(r"\bexecute a database query\b"),
        Decision.BLOCK, 0.8,
        "Detected a request to execute a database query - no such capability exists.",
    ),
    Rule(
        "tool-admin-panel", "tool_action_misuse",
        _rx(r"\baccess the (internal )?admin(istration)? panel\b"),
        Decision.BLOCK, 0.8,
        "Detected a request to access an administration panel - no such capability exists.",
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
        "Detected a request to delete application logs - no such capability exists.",
    ),
)


# Self-service exemption. A user asking for THEIR OWN data is an authorization
# question owned by the ACL/RBAC layer (which only ever returns documents the
# actor may read), not a prompt-injection signal. Suppress the bulk-extraction
# rules when the request is clearly scoped to the requester's own data and does
# not also demand other people's or company-wide data. This narrows a false-
# positive class (raised by out-of-distribution review probes) on a general
# principle, not by tuning to any evaluation set; an attacker who also asks for
# others' data re-arms the rule via _BULK_OTHERS, and the ACL guard remains the
# real control regardless.
# The self-marker must attach to the DATA OBJECT being requested (a payslip /
# salary / record "của chính tôi"), not appear as a bare "của tôi" anywhere in
# the message. Otherwise an attacker appends "Đây là yêu cầu của tôi." to a bulk
# request and steals the exemption (found in the Grok re-audit of 6ea8578).
_SELF_SERVICE = _rx(
    r"\b(phiếu\s+lương|bảng\s+lương|thực\s+nhận|lương|chấm\s+công|bảng\s+công|"
    r"hồ\s+sơ|thông\s+tin|dữ\s+liệu|tài\s+khoản|hợp\s+đồng|phép|payslips?|salary|"
    r"record|data|account)\b"
    r"[^.?!\n]{0,25}"
    r"\b(của\s+(chính\s+)?tôi|của\s+mình|của\s+bản\s+thân|của\s+chính\s+mình|"
    r"my\s+own|of\s+mine)\b"
)
_BULK_OTHERS = _rx(
    r"\b(của\s+(cả\s+|toàn\s+)?(phòng|công\s+ty|đội|bộ\s+phận|team)|"
    r"tất\s+cả\s+nhân\s+viên|mọi\s+nhân\s+viên|toàn\s+bộ\s+nhân\s+viên|"
    r"of\s+all\s+(staff|employees)|of\s+everyone|người\s+khác|nhân\s+viên\s+khác|"
    r"whole\s+company)\b"
)
_SELF_SERVICE_EXEMPT = frozenset(
    {"authority-bulk-sensitive-extract", "authority-open-all-restricted"}
)


def evaluate_input(prompt: str) -> GuardDecisionResponse:
    """Evaluate a raw user prompt against the rule set and return a decision.

    The prompt is de-obfuscated first (see `_normalize`) so that zero-width and
    homoglyph "unicode smudging" cannot hide a keyword trigger from the rules.
    """
    normalized = _normalize(prompt)
    matched = [rule for rule in RULES if rule.pattern.search(normalized)]

    if matched and _SELF_SERVICE.search(normalized) and not _BULK_OTHERS.search(normalized):
        matched = [rule for rule in matched if rule.rule_id not in _SELF_SERVICE_EXEMPT]

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
