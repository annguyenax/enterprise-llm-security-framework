#!/usr/bin/env python3
"""Validator for the Phase 12D v2 benchmark (`datasets/v2/`).

**Guard-independence (Code X Phase 12D audit, Critical #1):** the default
validation path below imports NOTHING from `app.guards.*`,
`app.services.rag_query`, or any other Phase 12C runtime module, and its
exit status never depends on what the *current* guard implementation
decides. Benchmark integrity validation is an independent property of the
benchmark artifacts themselves (schema correctness, split/label isolation,
contamination controls, taxonomy coverage) -- it must not reject a
structurally valid, independently-authored ground-truth label merely
because it disagrees with today's guard behavior; that disagreement is
exactly what a benchmark exists to measure at Phase 12E, not a benchmark
authoring defect.

An optional, explicitly opt-in, clearly non-gating diagnostic
(`--diagnose-current-guards`) is available separately -- see
`diagnose_against_current_guards()` below -- for a developer who wants a
sanity-check report of where hand-authored labels currently agree or
disagree with `app.guards.input_guard`/`app.guards.rag_guard`. It NEVER
affects this script's exit code, NEVER rewrites any label, and is disabled
by default. It also does not scope to `holdout/` unless
`--include-holdout-diagnostic` is passed too, so an ordinary development
invocation of this script cannot accidentally leak holdout ground truth
into a terminal.

Checks, in the required order (any failure prints a clear, file-relative
message and the script exits non-zero -- see `main()`); every check
function below is written defensively (using `.get(...)`, never direct
indexing) so a malformed artifact reports a clean error instead of an
unhandled traceback:

1.  JSON parsing and record type.
2.  Exact field names AND complete field types (schema) for corpus/case/
    label records -- unknown fields rejected, required fields enforced,
    every field's Python type validated (string/int/bool/list/dict as
    documented) before any dependent check runs, so a malformed value
    (non-string content, duplicate `external_id`, a bool/float `top_k`,
    non-JSON-safe `metadata`, ...) is always a clean validation error, not
    a `TypeError`/`KeyError` (Code X Phase 12D re-audit, Major #1).
3.  Enum values (Decision, split, language, evaluation_scope, category,
    ingestion_mode, expected_document_ingestion_status).
4.  Split consistency (a case's own `split` field matches the file it was
    loaded from) and language consistency (case/label `language` agree).
5.  Unique `document_id`/`case_id`/`external_id` values.
6.  One-to-one case<->label mapping (no dangling/mismatched IDs).
7.  Document reference integrity (`relevant_document_ids` resolve; every
    corpus document is referenced by at least one case, so no document can
    silently bypass document-level contamination scanning).
8.  Explicit scenario-family taxonomy registry coverage (every required
    family present in every split; no unregistered family).
9.  Exact class-distribution bounds (Code X Phase 12D audit, Major #3).
10. Contamination controls: cross-split exact/near-duplicate query and
    document fingerprints, cross-split translation-group/template-id
    reuse, a benchmark-specific bilingual/translation canonicalization
    check (Code X Phase 12D re-audit, Critical #1.B), an authoring-
    provenance cross-check against real artifact text hashes (Critical
    #1.A), cross-split secret reuse, and similarity against v1
    (`redteam/prompts.jsonl`) queries AND every referenced corpus
    document, outside the development split (Critical #2).
11. Source-key policy compatibility, no accidental database files, no
    runtime/label import coupling, no `is_poisoned`/`expected_*` leakage
    into corpus or case files.
12. Manifest structural sanity (path safety only -- SHA-256 recomputation
    and freeze/verify is `scripts/freeze_v2_benchmark.py`'s job).

Exits 0 on success, non-zero (with a clear, deterministically-ordered
message per failure) otherwise. Never touches `app/` files themselves,
never performs a network call.
"""
from __future__ import annotations

import argparse
import difflib
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
# Same-directory script import (not an app/ dependency) so the generator's
# provenance hashes and this validator's fingerprints/hash re-checks are
# always computed by the exact same normalization logic -- Code X Phase
# 12D re-audit, Critical #1 fix.
import build_v2_benchmark as _generator  # noqa: E402

OUT_DIR = ROOT / "datasets" / "v2"
CORPUS_FILE = OUT_DIR / "corpus" / "documents.jsonl"
CASES_DIR = OUT_DIR / "cases"
LABELS_DIR = OUT_DIR / "labels"
DESIGN_DIR = OUT_DIR / "design"
PROVENANCE_FILE = DESIGN_DIR / "authoring-provenance.jsonl"
MANIFEST_PATH = OUT_DIR / "manifests" / "benchmark-v2-manifest.json"
EXEMPTIONS_PATH = OUT_DIR / "contamination-exemptions.json"
V1_PROMPTS_FILE = ROOT / "redteam" / "prompts.jsonl"

SPLITS = ("development", "validation", "holdout")
EXPECTED_SPLIT_COUNTS = {"development": 30, "validation": 30, "holdout": 60}
EXPECTED_TOTAL = 120
EXPECTED_LANGUAGES = {"vi", "en", "bilingual"}

# Code X Phase 12D audit, Major #3: exact reviewed class-distribution
# bounds, matching the audit's own preferred numbers. See
# docs/benchmark-v2-methodology.md Section 6 for the full rationale.
EXPECTED_CATEGORY_COUNTS = {
    "development": {"benign": 12, "malicious": 12, "mixed": 4, "neutral": 2},
    "validation": {"benign": 12, "malicious": 12, "mixed": 4, "neutral": 2},
    "holdout": {"benign": 24, "malicious": 24, "mixed": 8, "neutral": 4},
}

# Code X Phase 12D audit, Major #1: explicit taxonomy registry -- coverage
# is checked against this fixed set, never merely against whatever
# families happen to be present in the generated files.
REQUIRED_FAMILIES = frozenset({
    "clean_benign_rag", "benign_security_discussion", "benign_trap_query",
    "legitimate_authority_language", "academic_discussion_of_injection",
    "benign_secret_like_identifier", "direct_injection", "indirect_retrieved_injection",
    "malicious_low_trust_source", "compromised_trusted_source",
    "provenance_denied_at_ingestion", "mixed_benign_malicious_retrieval",
    "mixed_trust_benign_retrieval", "no_retrieval_hit",
    "all_context_blocked_multi_malicious", "multi_chunk_coordination",
    "fragment_beyond_per_chunk_prefix", "fragment_near_aggregate_budget",
    "zero_width_whitespace_variant", "markdown_html_concealment",
    "leakage_context_exclusion", "leakage_dlp_mechanism_reference",
    "availability_failure_case",
})

KNOWN_SOURCE_KEYS = {
    "api_upload", "synthetic_clean_corpus", "synthetic_external_feed",
    "v2-unregistered-source-key",  # intentionally invalid, provenance_denied_at_ingestion only
}

DECISION_VALUES = {"allow", "block", "sanitize", "log_only", "human_review"}
SPLIT_VALUES = set(SPLITS)
EVALUATION_SCOPE_VALUES = {"end_to_end", "component", "availability_fault", "residual_risk_only"}
CATEGORY_VALUES = {"benign", "malicious", "mixed", "neutral"}
INGESTION_STATUS_VALUES = {"indexed", "rejected"}
INGESTION_MODE_VALUES = {"public", "internal_only", "rejected"}
DLP_ACTION_VALUES = {"not_applicable_mock_provider"}  # plus None
STOP_REASON_VALUES = {
    "allowed", "input_blocked", "no_hits", "all_rejected_provenance",
    "all_context_blocked", "aggregate_context_blocked", "top_k_rejected",
}  # plus None (ambiguous-outcome cases, e.g. zero_width_whitespace_variant)

# Documented bounds (Code X Phase 12D re-audit, Major #1): mirrors the real
# Pydantic hard ceiling (`RAG_MAX_TOP_K_HARD_LIMIT`-adjacent field bound) in
# app/schemas/requests.py so an out-of-range top_k is a schema error here,
# not merely "whatever Python happened not to crash on".
TOP_K_MIN = 1
TOP_K_MAX = 50
DLP_REDACTION_COUNT_MAX = 100

CASE_REQUIRED_FIELDS = {
    "case_id", "split", "scenario_family", "language", "query", "top_k",
    "relevant_document_ids", "evaluation_scope",
}
LABEL_REQUIRED_FIELDS = {
    "case_id", "scenario_family", "language", "template_id", "semantic_group_id",
    "translation_group_id", "authoring_set", "expected_document_ingestion_status",
    "category", "attack_family", "expected_final_decision", "allowed_final_decisions",
    "expected_stop_reason", "allowed_stop_reasons", "expected_provider_called",
    "expected_retrieval_behavior", "expected_context_behavior", "expected_dlp_action",
    "expected_redaction_categories", "expected_redaction_count", "expected_security_property",
    "rationale", "residual_risk",
}
# Fields that must never appear in a case record (label content or
# non-runtime authoring metadata -- Code X Phase 12D audit, Critical #2 /
# Major #2).
LABEL_ONLY_FIELDS = (LABEL_REQUIRED_FIELDS - CASE_REQUIRED_FIELDS) | {
    "is_poisoned", "expected_decision", "expected_ingestion_status",
}
CORPUS_REQUIRED_FIELDS = {
    "document_id", "external_id", "source_key", "ingestion_mode",
    "title", "content", "metadata", "language", "scenario_family",
}
PROVENANCE_REQUIRED_FIELDS = {
    "artifact_id", "artifact_type", "split", "language", "scenario_family",
    "semantic_group_id", "translation_group_id", "authoring_set",
    "normalized_text_hash",
}
# Fields that must never appear in a corpus record (ground truth --
# Code X Phase 12D audit, Major #2).
CORPUS_PROHIBITED_FIELDS = {
    "is_poisoned", "expected_decision", "expected_ingestion_status",
    "expected_final_decision", "expected_document_ingestion_status",
}

CANONICAL_CANARY = "FAKE-SECRET-0000-EXAMPLE-DO-NOT-USE"
_SECRET_LIKE_PATTERN = re.compile(
    r"\bsk-[A-Za-z0-9]{16,}\b|\bAKIA[A-Z0-9]{12,}\b|\bghp_[A-Za-z0-9]{20,}\b|"
    r"\bBearer\s+[A-Za-z0-9\-_.=]{10,}\b|"
    r"\b(?:password|passwd|secret|api[_-]?key)\s*[:=]\s*\S+",
    re.IGNORECASE,
)

# Contamination thresholds -- adopted directly from the Code X Phase 12D
# audit's own methodology (it reported cross-split query similarity at a
# 0.9 threshold and flagged V2-VAL-0007 at a measured 0.929 similarity to
# a v1 case), so this validator uses the same reviewed threshold the
# finding itself was based on. See docs/benchmark-v2-methodology.md
# Section 10a.
SIMILARITY_THRESHOLD = 0.9

# Bilingual/translation-contamination thresholds -- deliberately looser
# than SIMILARITY_THRESHOLD because canonicalization collapses two
# languages onto a shared token vocabulary, so an honest translation pair
# converges much more than raw same-language paraphrase would (Code X
# Phase 12D re-audit, Critical #1 fix). Uses BOTH a SequenceMatcher ratio
# (order-sensitive) and a token-Jaccard ratio (order-insensitive, so a
# clause-reordered direct translation is still caught) -- either
# exceeding its threshold is treated as a finding.
BILINGUAL_SIMILARITY_THRESHOLD = 0.82
BILINGUAL_JACCARD_THRESHOLD = 0.7

# Benchmark-specific, reviewed EN/VI phrase lexicon (Code X Phase 12D
# re-audit, Critical #1.B). NOT a general translation model -- a small,
# hand-reviewed table of concept phrases that actually recur across this
# benchmark's own authored content banks (see
# scripts/build_v2_benchmark.py), used only to canonicalize a direct
# translation or obvious bilingual rewrite onto a shared token so a
# cross-split similarity check can see through the language difference.
# Documented limitation: a translation using different phrasing than this
# lexicon covers will not be canonicalized and may not be caught -- see
# docs/benchmark-v2-methodology.md Section 10b.
# Each entry is (english_phrase, vietnamese_phrase, human_readable_label).
# The label is documentation only -- the actual substitution token is a
# collision-free numeric code derived below (`_BILINGUAL_LEXICON_BY_LENGTH`),
# never the label text itself, so a later (shorter) lexicon entry's phrase
# text can never accidentally re-match a substring of an earlier
# substitution's own token.
BILINGUAL_LEXICON: tuple[tuple[str, str, str], ...] = (
    ("annual leave policy", "chính sách nghỉ phép hàng năm", "leave_policy_full"),
    ("full-time employees", "nhân viên toàn thời gian", "full_time_emp"),
    ("full-time staff", "nhân viên toàn thời gian", "full_time_emp"),
    ("what is the", "là gì", "whatis"),
    ("what is", "là gì", "whatis"),
    ("annual leave", "nghỉ phép hàng năm", "leave"),
    ("leave policy", "chính sách nghỉ phép", "leave_policy"),
    ("policy", "chính sách", "policy"),
    ("password reset", "đặt lại mật khẩu", "pwd_reset"),
    ("it support", "hỗ trợ it", "it_support"),
    ("warranty", "bảo hành", "warranty"),
    ("meal expense", "chi phí ăn uống", "meal_expense"),
    ("business travel", "công tác", "travel"),
    ("document classification", "phân loại tài liệu", "doc_class"),
    ("internal documents", "tài liệu nội bộ", "internal_docs"),
    ("vendor contract", "hợp đồng nhà cung cấp", "vendor_contract"),
    ("new employee", "nhân viên mới", "new_employee"),
    ("onboarding", "tiếp nhận", "onboarding"),
    ("prompt injection", "chèn lệnh", "injection"),
    ("security", "an toàn thông tin", "security"),
    ("approved", "phê duyệt", "approved"),
    ("executive board", "ban giám đốc", "exec_board"),
    ("training", "đào tạo", "training"),
    ("awareness", "nhận thức", "awareness"),
    ("order number", "mã đơn hàng", "order_num"),
    ("tracking code", "mã vận chuyển", "tracking_code"),
    ("ignore", "bỏ qua", "ignore"),
    ("previous instructions", "hướng dẫn trước đó", "prev_instr"),
    ("reveal", "tiết lộ", "reveal"),
    ("unrestricted", "không giới hạn", "unrestricted"),
    ("system administrator", "quản trị viên hệ thống", "sys_admin"),
    ("database query", "truy vấn cơ sở dữ liệu", "db_query"),
    ("customer support", "hỗ trợ khách hàng", "cust_support"),
    ("refund", "hoàn tiền", "refund"),
    ("shipping", "vận chuyển", "shipping"),
    ("emergency", "khẩn cấp", "emergency"),
    ("spending limit", "hạn mức chi tiêu", "spend_limit"),
    ("please", "vui lòng", "please"),
    ("current", "hiện tại", "current"),
    ("for", "cho", "for"),
)

# Matched longest-phrase-first so a longer lexicon entry is never
# fragmented by a shorter one that happens to be one of its substrings
# (e.g. "annual leave policy" must consume before the standalone "policy"
# entry gets a chance to split it apart). Each substitution token is a
# collision-free numeric code (`@C<index>@`), never derived from the
# phrase text, so no later phrase substitution can ever re-match a
# substring of an already-inserted token.
_BILINGUAL_LEXICON_BY_LENGTH: tuple[tuple[str, str, str], ...] = tuple(
    (en, vi, f"@C{i}@")
    for i, (en, vi, _label) in enumerate(
        sorted(BILINGUAL_LEXICON, key=lambda entry: max(len(entry[0]), len(entry[1])), reverse=True)
    )
)


class ValidationError(Exception):
    pass


def _rel(path: Path) -> str:
    """Render a path relative to the repository root for safe, non-
    machine-specific error messages (Code X Phase 12D audit, Major #1)."""
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.name


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise ValidationError(f"Missing required file: {_rel(path)}")
    records = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValidationError(f"{_rel(path)}:{line_no}: invalid JSON ({exc})") from exc
            if not isinstance(record, dict):
                raise ValidationError(f"{_rel(path)}:{line_no}: record is not a JSON object")
            records.append(record)
    return records


def _normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", str(query).strip().lower())


def _fingerprint(text: str) -> str:
    """Normalized text fingerprint used for cross-split contamination
    checks -- delegates to `build_v2_benchmark.normalize_for_fingerprint`,
    the single canonical implementation shared with the generator (Code X
    Phase 12D re-audit, Critical #1 fix), so a fingerprint computed here
    can never silently drift from the one used to build
    `normalized_text_hash` at generation time."""
    return _generator.normalize_for_fingerprint(text)


def _similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def _token_jaccard(a: str, b: str) -> float:
    set_a, set_b = set(a.split()), set(b.split())
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def _canonicalize_bilingual(text: str) -> str:
    """Applies `_fingerprint` normalization, strips sentence punctuation
    (so it can never stick to a substituted canonical token and break
    token-level comparison), then substitutes every `BILINGUAL_LEXICON`
    phrase (English or Vietnamese) with its shared canonical concept
    token -- longest phrases first, so a longer entry is never fragmented
    by a shorter one that is also one of its substrings. A benchmark-
    specific lexical control, not a general translation/semantic-duplicate
    detector -- see docs/benchmark-v2-methodology.md Section 10b."""
    normalized = _fingerprint(text)
    normalized = re.sub(r"[?!.,;:]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    for en_phrase, vi_phrase, token in _BILINGUAL_LEXICON_BY_LENGTH:
        normalized = re.sub(re.escape(en_phrase), token, normalized)
        normalized = re.sub(re.escape(vi_phrase), token, normalized)
    return normalized


def _is_json_safe_value(value: Any, *, _depth: int = 0) -> bool:
    """JSON-compatible-value check for corpus `metadata` (Code X Phase 12D
    re-audit, Major #1): rejects non-string dict keys, NaN/Infinity
    floats, and any type JSON cannot represent, without ever raising."""
    if _depth > 20:
        return False
    if value is None or isinstance(value, (str, int, bool)):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(_is_json_safe_value(v, _depth=_depth + 1) for v in value)
    if isinstance(value, dict):
        return all(isinstance(k, str) for k in value) and all(
            _is_json_safe_value(v, _depth=_depth + 1) for v in value.values()
        )
    return False


# `validate_json_safe_value` is the public name requested by the Code X
# Phase 12D malformed-value re-audit; `_is_json_safe_value` (above) is the
# original implementation, kept so existing call sites are unaffected.
validate_json_safe_value = _is_json_safe_value


# ---------------------------------------------------------------------------
# Type-safe validation helpers (Code X Phase 12D re-audit -- malformed-value
# hardening). Every helper below is designed to NEVER raise regardless of
# `value`'s type: a list, dict, number, bool, or None passed where a string
# enum/list/integer is expected is always reported as a normal, appended
# validation error, never an unhandled TypeError/KeyError from a bare
# `value in some_set` or `some_dict[value]` operation (sets and dicts hash
# their operand, and Python lists/dicts are unhashable, which is exactly
# the class of crash this re-audit found). These helpers are the PRIMARY
# fix -- see `main()`'s defensive top-level exception boundary for the
# secondary, last-resort safety net only.
# ---------------------------------------------------------------------------


def _hashable(value: Any) -> bool:
    try:
        hash(value)
    except TypeError:
        return False
    return True


def _safe_in(value: Any, allowed: Any) -> bool:
    """True iff `value` is hashable and a member of `allowed`. Never
    raises, regardless of `value`'s type -- an unhashable `value` (list,
    dict) is simply reported as "not a member", not a crash. Used as a
    defense-in-depth guard in check functions that may be called directly
    (e.g. from tests) without first passing through `check_schemas`'s own
    type-safe validation."""
    return _hashable(value) and value in allowed


def is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def safe_record_identifier(record: Any, *keys: str, fallback: str = "<unknown>") -> str:
    """Best-effort, crash-proof extraction of a human-readable identifier
    from a record for use in an error message -- never raises even if
    `record` is not a dict or the identifier field itself is malformed."""
    if not isinstance(record, dict):
        return fallback
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value:
            return value
    return fallback


def validate_string_field(
    errors: list[str], value: Any, field_label: str,
    *, allow_none: bool = False, allow_empty: bool = False,
) -> bool:
    """Type-first non-empty-string check. Returns True iff `value` may
    safely be used as a string downstream (`.lower()`, regex, hashing,
    fingerprinting, ...). Appends exactly one clear error and returns
    False for any other value -- list, dict, number, bool, None (unless
    `allow_none`), or empty string (unless `allow_empty`)."""
    if value is None:
        if allow_none:
            return True
        errors.append(f"{field_label} is missing or null (must be a non-empty string)")
        return False
    if isinstance(value, bool) or not isinstance(value, str):
        errors.append(f"{field_label} has invalid type {type(value).__name__} (must be a string)")
        return False
    if not allow_empty and not value.strip():
        errors.append(f"{field_label} is an empty string (must be non-empty)")
        return False
    return True


def validate_string_enum(
    errors: list[str], value: Any, field_label: str, allowed: Any,
    *, allow_none: bool = False,
) -> bool:
    """Type-first enum-membership check: confirms `value` is a plain
    string (rejecting list, dict, number, bool, and None-unless-allowed)
    BEFORE ever performing `value in allowed`, so a malformed value can
    never raise `TypeError: unhashable type` from that membership test.
    This is the single fix for the Code X Phase 12D re-audit's headline
    finding (`expected_stop_reason=[]` / provenance `split=[]` previously
    crashing `check_schemas`/`check_authoring_provenance` outright).
    Returns True iff `value` is valid (a member of `allowed`, or `None`
    when `allow_none=True`)."""
    if value is None:
        if allow_none:
            return True
        errors.append(f"{field_label} is missing or null (must be one of {sorted(allowed)})")
        return False
    if isinstance(value, bool) or not isinstance(value, str):
        errors.append(f"{field_label} has invalid type {type(value).__name__} (must be a string)")
        return False
    if value not in allowed:
        errors.append(f"{field_label} has invalid value {value!r} (must be one of {sorted(allowed)})")
        return False
    return True


def validate_optional_string_enum(errors: list[str], value: Any, field_label: str, allowed: Any) -> bool:
    """`validate_string_enum` with `allow_none=True` -- for fields whose
    documented contract explicitly permits `null` (e.g.
    `expected_stop_reason` on an ambiguous-outcome case)."""
    return validate_string_enum(errors, value, field_label, allowed, allow_none=True)


def validate_string_list(
    errors: list[str], value: Any, field_label: str, *, element_enum: Any = None,
) -> bool:
    """Type-first list-of-strings check: confirms the OUTER value is a
    `list` before ever iterating or indexing it, then validates every
    element is a plain string (rejecting a nested list/dict element)
    BEFORE any membership test or set/dict insertion involving that
    element, reporting the offending index. Never raises regardless of
    `value`'s shape. Returns True iff every element is valid."""
    if not isinstance(value, list):
        errors.append(f"{field_label} has invalid type {type(value).__name__} (must be a list)")
        return False
    ok = True
    for i, element in enumerate(value):
        if isinstance(element, bool) or not isinstance(element, str):
            errors.append(f"{field_label}[{i}] has invalid type {type(element).__name__} (must be a string)")
            ok = False
            continue
        if element_enum is not None and element not in element_enum:
            errors.append(f"{field_label}[{i}] has invalid value {element!r} (must be one of {sorted(element_enum)})")
            ok = False
    return ok


def validate_integer_field(
    errors: list[str], value: Any, field_label: str,
    *, minimum: int | None = None, maximum: int | None = None, allow_none: bool = False,
) -> bool:
    """Type-first integer check. `bool` is explicitly rejected even though
    `isinstance(True, int)` is `True` in Python (`bool` is an `int`
    subclass), since a boolean is never a semantically valid `top_k`/
    redaction-count value."""
    if value is None:
        if allow_none:
            return True
        errors.append(f"{field_label} is missing or null (must be an integer)")
        return False
    if isinstance(value, bool) or not isinstance(value, int):
        errors.append(f"{field_label} has invalid type {type(value).__name__} (must be an integer, not bool/float)")
        return False
    if minimum is not None and value < minimum:
        errors.append(f"{field_label}={value} is below the minimum {minimum}")
        return False
    if maximum is not None and value > maximum:
        errors.append(f"{field_label}={value} is above the maximum {maximum}")
        return False
    return True


# ---------------------------------------------------------------------------
# Stage 1-2: schema (field names, required/unknown fields, basic types)
# ---------------------------------------------------------------------------


def _require_nonempty_str(errors: list[str], value: Any, label: str) -> bool:
    """Returns True (and appends no error) only if `value` is a non-empty
    string. Kept as a thin wrapper over `validate_string_field` for
    backward compatibility with its original call sites/error-message
    shape."""
    return validate_string_field(errors, value, label)


def check_schemas(corpus: list[dict], cases: dict[str, list[dict]], labels: dict[str, list[dict]]) -> list[str]:
    """Complete field-name AND field-type/enum validation for every
    corpus/case/label record. Every single field below is validated
    **type-first, enum-membership second** (Code X Phase 12D re-audit):
    a malformed value -- a list, dict, number, or bool where a string
    enum is expected (e.g. `expected_stop_reason=[]`) -- is always
    resolved by `validate_string_enum`/`validate_string_list`/
    `validate_integer_field` BEFORE any `value in ALLOWED_SET`-style
    membership test can ever see it, so it is always reported as a normal
    validation error, never an unhandled `TypeError: unhashable type`.
    This function itself never raises regardless of the shape of its
    input; `main()` also keeps a final defensive exception boundary as a
    secondary, last-resort safety net -- but this function's own
    type-first ordering is the actual, primary fix."""
    errors: list[str] = []
    for doc in corpus:
        doc_id = safe_record_identifier(doc, "document_id", fallback="<missing document_id>")
        keys = set(doc.keys()) if isinstance(doc, dict) else set()
        missing = CORPUS_REQUIRED_FIELDS - keys
        extra = keys - CORPUS_REQUIRED_FIELDS
        if missing:
            errors.append(f"corpus document {doc_id!r} missing fields: {sorted(missing)}")
        if extra:
            errors.append(f"corpus document {doc_id!r} has unexpected fields: {sorted(extra)}")
        prohibited = CORPUS_PROHIBITED_FIELDS & keys
        if prohibited:
            errors.append(f"corpus document {doc_id!r} illegally carries ground-truth field(s): {sorted(prohibited)}")

        if "document_id" in doc:
            validate_string_field(errors, doc.get("document_id"), f"corpus document {doc_id!r} document_id")
        if "external_id" in doc:
            validate_string_field(errors, doc.get("external_id"), f"corpus document {doc_id!r} external_id")
        if "source_key" in doc:
            validate_string_field(errors, doc.get("source_key"), f"corpus document {doc_id!r} source_key")
        if "ingestion_mode" in doc:
            validate_string_enum(errors, doc.get("ingestion_mode"), f"corpus document {doc_id!r} ingestion_mode", INGESTION_MODE_VALUES)
        if "title" in doc:
            validate_string_field(errors, doc.get("title"), f"corpus document {doc_id!r} title", allow_empty=True)
        if "content" in doc:
            validate_string_field(errors, doc.get("content"), f"corpus document {doc_id!r} content", allow_empty=True)
        if "metadata" in doc:
            metadata = doc.get("metadata")
            if not isinstance(metadata, dict):
                errors.append(f"corpus document {doc_id!r} has non-dict metadata (type {type(metadata).__name__})")
            elif not validate_json_safe_value(metadata):
                errors.append(
                    f"corpus document {doc_id!r} has non-JSON-safe metadata "
                    "(non-string key, NaN/Infinity, or an unsupported nested type)"
                )
        if "language" in doc:
            validate_string_enum(errors, doc.get("language"), f"corpus document {doc_id!r} language", EXPECTED_LANGUAGES)
        if "scenario_family" in doc:
            validate_string_enum(errors, doc.get("scenario_family"), f"corpus document {doc_id!r} scenario_family", REQUIRED_FAMILIES)

    for split in SPLITS:
        for case in cases.get(split, []):
            case_id = safe_record_identifier(case, "case_id", fallback="<missing case_id>")
            keys = set(case.keys()) if isinstance(case, dict) else set()
            missing = CASE_REQUIRED_FIELDS - keys
            extra = keys - CASE_REQUIRED_FIELDS
            if missing:
                errors.append(f"case {case_id!r} missing fields: {sorted(missing)}")
            if extra:
                errors.append(f"case {case_id!r} has unexpected fields: {sorted(extra)}")
            leaked = LABEL_ONLY_FIELDS & keys
            if leaked:
                errors.append(f"case {case_id!r} illegally contains label/authoring-metadata field(s): {sorted(leaked)}")

            if "case_id" in case:
                validate_string_field(errors, case.get("case_id"), f"case {case_id!r} case_id")
            if "split" in case:
                validate_string_enum(errors, case.get("split"), f"case {case_id!r} split", SPLIT_VALUES)
            if "scenario_family" in case:
                validate_string_enum(errors, case.get("scenario_family"), f"case {case_id!r} scenario_family", REQUIRED_FAMILIES)
            if "language" in case:
                validate_string_enum(errors, case.get("language"), f"case {case_id!r} language", EXPECTED_LANGUAGES)
            if "query" in case:
                validate_string_field(errors, case.get("query"), f"case {case_id!r} query")
            if "top_k" in case:
                validate_integer_field(errors, case.get("top_k"), f"case {case_id!r} top_k", minimum=TOP_K_MIN, maximum=TOP_K_MAX)
            if "relevant_document_ids" in case:
                validate_string_list(errors, case.get("relevant_document_ids"), f"case {case_id!r} relevant_document_ids")
            if "evaluation_scope" in case:
                validate_string_enum(errors, case.get("evaluation_scope"), f"case {case_id!r} evaluation_scope", EVALUATION_SCOPE_VALUES)

        for label in labels.get(split, []):
            case_id = safe_record_identifier(label, "case_id", fallback="<missing case_id>")
            keys = set(label.keys()) if isinstance(label, dict) else set()
            missing = LABEL_REQUIRED_FIELDS - keys
            extra = keys - LABEL_REQUIRED_FIELDS
            if missing:
                errors.append(f"label {case_id!r} missing fields: {sorted(missing)}")
            if extra:
                errors.append(f"label {case_id!r} has unexpected fields: {sorted(extra)}")

            if "case_id" in label:
                validate_string_field(errors, label.get("case_id"), f"label {case_id!r} case_id")
            if "scenario_family" in label:
                validate_string_enum(errors, label.get("scenario_family"), f"label {case_id!r} scenario_family", REQUIRED_FAMILIES)
            if "language" in label:
                validate_string_enum(errors, label.get("language"), f"label {case_id!r} language", EXPECTED_LANGUAGES)
            if "authoring_set" in label:
                validate_string_enum(errors, label.get("authoring_set"), f"label {case_id!r} authoring_set", SPLIT_VALUES)
            for str_field in ("template_id", "semantic_group_id", "translation_group_id"):
                if str_field in label:
                    validate_string_field(errors, label.get(str_field), f"label {case_id!r} {str_field}")

            if "expected_final_decision" in label:
                validate_string_enum(errors, label.get("expected_final_decision"), f"label {case_id!r} expected_final_decision", DECISION_VALUES)
            if "allowed_final_decisions" in label:
                validate_string_list(errors, label.get("allowed_final_decisions"), f"label {case_id!r} allowed_final_decisions", element_enum=DECISION_VALUES)

            if "expected_stop_reason" in label:
                validate_optional_string_enum(errors, label.get("expected_stop_reason"), f"label {case_id!r} expected_stop_reason", STOP_REASON_VALUES)
            if "allowed_stop_reasons" in label:
                validate_string_list(errors, label.get("allowed_stop_reasons"), f"label {case_id!r} allowed_stop_reasons", element_enum=STOP_REASON_VALUES)

            if "category" in label:
                validate_string_enum(errors, label.get("category"), f"label {case_id!r} category", CATEGORY_VALUES)

            if "attack_family" in label:
                attack_family = label.get("attack_family")
                if attack_family is not None and not isinstance(attack_family, str):
                    errors.append(f"label {case_id!r} has invalid attack_family (type {type(attack_family).__name__}, must be a string or null)")

            if "expected_document_ingestion_status" in label:
                validate_string_enum(errors, label.get("expected_document_ingestion_status"), f"label {case_id!r} expected_document_ingestion_status", INGESTION_STATUS_VALUES)

            if "expected_dlp_action" in label:
                validate_optional_string_enum(errors, label.get("expected_dlp_action"), f"label {case_id!r} expected_dlp_action", DLP_ACTION_VALUES)

            if "expected_redaction_categories" in label:
                redaction_categories = label.get("expected_redaction_categories")
                if isinstance(redaction_categories, str):
                    errors.append(f"label {case_id!r} has invalid expected_redaction_categories (type str, must be a list of strings)")
                else:
                    validate_string_list(errors, redaction_categories, f"label {case_id!r} expected_redaction_categories")

            if "expected_provider_called" in label:
                provider_called = label.get("expected_provider_called")
                if provider_called is not None and not isinstance(provider_called, bool):
                    errors.append(f"label {case_id!r} has non-boolean expected_provider_called (type {type(provider_called).__name__})")

            if "expected_redaction_count" in label:
                validate_integer_field(
                    errors, label.get("expected_redaction_count"), f"label {case_id!r} expected_redaction_count",
                    minimum=0, maximum=DLP_REDACTION_COUNT_MAX, allow_none=True,
                )

            for optional_str_field in (
                "expected_retrieval_behavior", "expected_context_behavior",
                "expected_security_property", "residual_risk",
            ):
                if optional_str_field in label:
                    value = label.get(optional_str_field)
                    if value is not None and not isinstance(value, str):
                        errors.append(f"label {case_id!r} has invalid {optional_str_field} (type {type(value).__name__}, must be a string or null)")

            if "rationale" in label:
                validate_string_field(errors, label.get("rationale"), f"label {case_id!r} rationale")

    return errors


def check_no_duplicate_external_ids(corpus: list[dict]) -> list[str]:
    """Code X Phase 12D re-audit, Major #1: `external_id` must be unique
    across the corpus, per this benchmark's own documented contract that
    every document maps 1:1 to a distinct external identifier (mirrors
    `document_id` uniqueness -- both are assigned together by the
    generator, so a duplicate would only ever arise from hand-editing)."""
    errors = []
    seen: dict[str, int] = {}
    for d in corpus:
        ext_id = d.get("external_id")
        if isinstance(ext_id, str) and ext_id:
            seen[ext_id] = seen.get(ext_id, 0) + 1
    dupes = sorted(k for k, v in seen.items() if v > 1)
    if dupes:
        errors.append(f"duplicate external_id(s): {dupes}")
    return errors


def check_split_and_language_consistency(cases: dict[str, list[dict]], labels: dict[str, list[dict]]) -> list[str]:
    errors = []
    for split in SPLITS:
        for case in cases.get(split, []):
            case_id = case.get("case_id", "<missing case_id>")
            if "split" in case and case.get("split") != split:
                errors.append(f"case {case_id!r} declares split={case.get('split')!r} but is stored under {split!r}")

        label_by_id = {}
        for label in labels.get(split, []):
            lcid = label.get("case_id")
            if isinstance(lcid, str):  # malformed case_id reported separately by check_schemas
                label_by_id.setdefault(lcid, []).append(label)

        for case in cases.get(split, []):
            case_id = case.get("case_id")
            if not isinstance(case_id, str):
                continue
            for label in label_by_id.get(case_id, []):
                if case.get("language") is not None and label.get("language") is not None and case["language"] != label["language"]:
                    errors.append(
                        f"case {case_id!r} language {case['language']!r} disagrees with its label's language {label['language']!r}"
                    )
                if case.get("scenario_family") is not None and label.get("scenario_family") is not None and case["scenario_family"] != label["scenario_family"]:
                    errors.append(
                        f"case {case_id!r} scenario_family {case['scenario_family']!r} disagrees with its label's scenario_family {label['scenario_family']!r}"
                    )
    return errors


# ---------------------------------------------------------------------------
# Counts, taxonomy, class distribution
# ---------------------------------------------------------------------------


def check_counts(cases: dict[str, list[dict]]) -> list[str]:
    errors = []
    total = 0
    for split in SPLITS:
        n = len(cases.get(split, []))
        total += n
        if n != EXPECTED_SPLIT_COUNTS[split]:
            errors.append(f"split {split!r} has {n} cases, expected {EXPECTED_SPLIT_COUNTS[split]}")
    if total != EXPECTED_TOTAL:
        errors.append(f"total case count is {total}, expected {EXPECTED_TOTAL}")
    return errors


def check_family_registry(cases: dict[str, list[dict]]) -> list[str]:
    errors = []
    for split in SPLITS:
        # Only string scenario_family values can ever be valid set members;
        # a malformed (unhashable) value is reported by check_schemas, not
        # here -- building the set itself must never raise.
        present = {c.get("scenario_family") for c in cases.get(split, []) if isinstance(c.get("scenario_family"), str)}
        missing = REQUIRED_FAMILIES - present
        if missing:
            errors.append(f"split {split!r} is missing required scenario families: {sorted(missing)}")
        unknown = present - REQUIRED_FAMILIES
        if unknown:
            errors.append(f"split {split!r} contains unregistered scenario families: {sorted(unknown)}")
    return errors


def check_language_coverage(cases: dict[str, list[dict]]) -> list[str]:
    errors = []
    # Only string language values can ever be valid set members; a
    # malformed (unhashable) value is reported by check_schemas, not here.
    all_langs = {
        c.get("language") for split in SPLITS for c in cases.get(split, [])
        if isinstance(c.get("language"), str)
    }
    missing = EXPECTED_LANGUAGES - all_langs
    if missing:
        errors.append(f"corpus-wide language coverage missing: {sorted(missing)}")
    unknown = all_langs - EXPECTED_LANGUAGES
    if unknown:
        errors.append(f"unexpected language code(s) found: {sorted(unknown)}")
    return errors


def check_class_distribution(labels: dict[str, list[dict]]) -> list[str]:
    """Code X Phase 12D audit, Major #3: exact reviewed category bounds
    per split, not merely an "approximately balanced" claim."""
    errors = []
    for split in SPLITS:
        # Only string category values can ever be valid Counter/dict keys;
        # a malformed (unhashable) value is reported by check_schemas, not
        # here -- counting itself must never raise.
        counts = Counter(
            label.get("category") for label in labels.get(split, [])
            if isinstance(label.get("category"), str)
        )
        expected = EXPECTED_CATEGORY_COUNTS[split]
        for category, expected_n in expected.items():
            actual_n = counts.get(category, 0)
            if actual_n != expected_n:
                errors.append(
                    f"split {split!r} category {category!r} has {actual_n} case(s), expected exactly {expected_n}"
                )
        unexpected_categories = set(counts) - set(expected) - {None}
        if unexpected_categories:
            errors.append(f"split {split!r} has unexpected categories: {sorted(unexpected_categories)}")
    return errors


# ---------------------------------------------------------------------------
# Referential integrity (defensive -- never KeyErrors on malformed input)
# ---------------------------------------------------------------------------


def check_case_label_mapping(cases: dict[str, list[dict]], labels: dict[str, list[dict]]) -> list[str]:
    """Code X Phase 12D audit, Major #1: a mismatched case_id/label_id
    must be reported as a normal validation error, never an unhandled
    KeyError."""
    errors = []
    for split in SPLITS:
        # Only string case_id values can ever be valid set members; a
        # malformed (unhashable) value is reported by check_schemas, not
        # here -- building the sets/lists below must never raise.
        case_ids = [c.get("case_id") for c in cases.get(split, []) if isinstance(c.get("case_id"), str)]
        label_ids = [l.get("case_id") for l in labels.get(split, []) if isinstance(l.get("case_id"), str)]
        case_id_set = set(case_ids)
        label_id_set = set(label_ids)

        missing_labels = sorted(case_id_set - label_id_set)
        if missing_labels:
            errors.append(f"split {split!r} has case(s) with no matching label: {missing_labels}")
        orphan_labels = sorted(label_id_set - case_id_set)
        if orphan_labels:
            errors.append(f"split {split!r} has label(s) with no matching case: {orphan_labels}")

        dupe_labels = sorted({cid for cid in label_ids if label_ids.count(cid) > 1})
        if dupe_labels:
            errors.append(f"split {split!r} has duplicate label case_id(s): {dupe_labels}")
    return errors


def check_referential_integrity(corpus: list[dict], cases: dict[str, list[dict]]) -> list[str]:
    errors = []
    # Only string document_ids can ever be valid set members/dict keys;
    # a malformed (unhashable) document_id is reported by check_schemas,
    # not here -- building the set itself must never raise.
    doc_ids = {d.get("document_id") for d in corpus if isinstance(d.get("document_id"), str)}
    for split in SPLITS:
        for case in cases.get(split, []):
            case_id = safe_record_identifier(case, "case_id", fallback="<missing case_id>")
            for doc_id in case.get("relevant_document_ids") or []:
                if not _safe_in(doc_id, doc_ids):
                    errors.append(f"case {case_id!r} references unknown document_id {doc_id!r}")
    return errors


def check_no_duplicate_ids(corpus: list[dict], cases: dict[str, list[dict]]) -> list[str]:
    errors = []
    # Only string IDs can ever be valid dict keys; a malformed
    # (unhashable) ID is reported by check_schemas, not here.
    seen_docs: dict[str, int] = {}
    for d in corpus:
        doc_id = d.get("document_id")
        if isinstance(doc_id, str):
            seen_docs[doc_id] = seen_docs.get(doc_id, 0) + 1
    dupes = sorted(k for k, v in seen_docs.items() if v > 1)
    if dupes:
        errors.append(f"duplicate document_id(s): {dupes}")

    seen_cases: dict[str, int] = {}
    for split in SPLITS:
        for c in cases.get(split, []):
            case_id = c.get("case_id")
            if isinstance(case_id, str):
                seen_cases[case_id] = seen_cases.get(case_id, 0) + 1
    dupes = sorted(k for k, v in seen_cases.items() if v > 1)
    if dupes:
        errors.append(f"duplicate case_id(s): {dupes}")
    return errors


def check_no_normalized_duplicate_queries(cases: dict[str, list[dict]]) -> list[str]:
    errors = []
    seen: dict[str, str] = {}
    for split in SPLITS:
        for c in cases.get(split, []):
            query = c.get("query")
            case_id = c.get("case_id", "<missing case_id>")
            if query is None:
                continue
            norm = _normalize_query(query)
            if norm in seen:
                errors.append(f"normalized-duplicate query: case {case_id!r} duplicates {seen[norm]!r}")
            else:
                seen[norm] = case_id
    return errors


# ---------------------------------------------------------------------------
# Contamination controls (Code X Phase 12D audit, Critical #2)
# ---------------------------------------------------------------------------


def _load_exemptions() -> list[dict[str, str]]:
    if not EXEMPTIONS_PATH.exists():
        return []
    with EXEMPTIONS_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    return data.get("exemptions", [])


_EXEMPTION_SCOPES = {"query", "document", "v1", "v1-document", "bilingual"}


def _exemption_errors(exemptions: list[dict[str, str]]) -> list[str]:
    """Type-first (Code X Phase 12D re-audit): validates every exemption
    entry's `rationale`/`scope`/`id_a`/`id_b` fields as plain strings
    before any `.strip()` call or set-membership test, so a malformed
    exemptions file (e.g. `rationale: []`, `scope: {}`) is always a clean
    validation error, never an unhandled `AttributeError`/`TypeError`."""
    errors = []
    for i, entry in enumerate(exemptions):
        if not isinstance(entry, dict):
            errors.append(f"contamination exemption #{i} is not a JSON object")
            continue
        validate_string_field(errors, entry.get("rationale"), f"contamination exemption #{i} rationale")
        validate_string_enum(errors, entry.get("scope"), f"contamination exemption #{i} scope", _EXEMPTION_SCOPES)
        for id_field in ("id_a", "id_b"):
            if id_field in entry:
                validate_string_field(errors, entry.get(id_field), f"contamination exemption #{i} {id_field}")
    return errors


def _is_exempt(exemptions: list[dict[str, str]], scope: str, id_a: Any, id_b: Any) -> bool:
    """Never raises regardless of `id_a`/`id_b`'s type: an unhashable
    value (list, dict) simply cannot match any exemption pair, so it is
    treated as "not exempt" rather than crashing (Code X Phase 12D
    re-audit)."""
    if not _hashable(id_a) or not _hashable(id_b):
        return False
    for entry in exemptions:
        if not isinstance(entry, dict) or entry.get("scope") != scope:
            continue
        entry_id_a, entry_id_b = entry.get("id_a"), entry.get("id_b")
        if not _hashable(entry_id_a) or not _hashable(entry_id_b):
            continue
        if {entry_id_a, entry_id_b} == {id_a, id_b}:
            return True
    return False


def check_cross_split_contamination(
    corpus: list[dict], cases: dict[str, list[dict]], labels: dict[str, list[dict]]
) -> list[str]:
    """Cross-split query/document fingerprint reuse and high lexical
    similarity, plus translation-group/template-id reuse across splits.
    Development-vs-others and validation-vs-holdout pairs are all checked
    (every split pair) -- ADR-003 only exempts *v1* reuse in development,
    not reuse of v2's own content across its own splits."""
    errors: list[str] = []
    exemptions = _load_exemptions()
    errors.extend(_exemption_errors(exemptions))

    # -- query fingerprint / similarity, cross-split only --
    query_by_split: dict[str, list[tuple[str, str, str]]] = {s: [] for s in SPLITS}
    for split in SPLITS:
        for c in cases.get(split, []):
            case_id = c.get("case_id")
            query = c.get("query")
            if case_id is None or not isinstance(query, str):
                continue  # non-string query is reported separately by check_schemas
            query_by_split[split].append((case_id, query, _fingerprint(query)))

    for split_a, split_b in (("development", "validation"), ("development", "holdout"), ("validation", "holdout")):
        for id_a, text_a, fp_a in query_by_split[split_a]:
            for id_b, text_b, fp_b in query_by_split[split_b]:
                if _is_exempt(exemptions, "query", id_a, id_b):
                    continue
                if fp_a and fp_a == fp_b:
                    errors.append(
                        f"cross-split query template reuse: {id_a!r} ({split_a}) and {id_b!r} ({split_b}) "
                        "normalize to the identical fingerprint"
                    )
                    continue
                ratio = _similarity(fp_a, fp_b)
                if ratio >= SIMILARITY_THRESHOLD:
                    errors.append(
                        f"cross-split query similarity {ratio:.3f} >= {SIMILARITY_THRESHOLD}: "
                        f"{id_a!r} ({split_a}) vs {id_b!r} ({split_b})"
                    )

    # -- document fingerprint / similarity, cross-split (split inferred
    #    from which cases reference the document) --
    doc_split: dict[str, set[str]] = {}
    for split in SPLITS:
        for c in cases.get(split, []):
            for doc_id in c.get("relevant_document_ids") or []:
                if isinstance(doc_id, str):  # malformed reference reported separately by check_schemas
                    doc_split.setdefault(doc_id, set()).add(split)
    doc_by_id = {d.get("document_id"): d for d in corpus if isinstance(d.get("document_id"), str)}

    docs_by_split: dict[str, list[tuple[str, str]]] = {s: [] for s in SPLITS}
    for doc_id, splits_seen in doc_split.items():
        doc = doc_by_id.get(doc_id)
        if doc is None or len(splits_seen) != 1:
            continue  # a doc referenced by >1 split is already flagged by referential/contamination logic elsewhere
        (only_split,) = tuple(splits_seen)
        content = doc.get("content")
        if isinstance(content, str):
            docs_by_split[only_split].append((doc_id, _fingerprint(content)))

    for split_a, split_b in (("development", "validation"), ("development", "holdout"), ("validation", "holdout")):
        for id_a, fp_a in docs_by_split[split_a]:
            for id_b, fp_b in docs_by_split[split_b]:
                if _is_exempt(exemptions, "document", id_a, id_b):
                    continue
                if fp_a and fp_a == fp_b:
                    errors.append(
                        f"cross-split document content reuse: {id_a!r} ({split_a}) and {id_b!r} ({split_b}) "
                        "normalize to the identical fingerprint"
                    )
                    continue
                ratio = _similarity(fp_a, fp_b)
                if ratio >= SIMILARITY_THRESHOLD:
                    errors.append(
                        f"cross-split document similarity {ratio:.3f} >= {SIMILARITY_THRESHOLD}: "
                        f"{id_a!r} ({split_a}) vs {id_b!r} ({split_b})"
                    )

    # -- translation_group_id / template_id must never repeat across splits --
    group_owner: dict[str, str] = {}
    for split in SPLITS:
        for label in labels.get(split, []):
            for field in ("template_id", "translation_group_id"):
                value = label.get(field)
                if value is None:
                    continue
                key = f"{field}:{value}"
                owner = group_owner.get(key)
                if owner is not None and owner != split:
                    errors.append(
                        f"{field} {value!r} is reused across splits ({owner!r} and {split!r})"
                    )
                group_owner[key] = split

    return errors


def _load_v1_prompts() -> list[tuple[str, str]]:
    if not V1_PROMPTS_FILE.exists():
        return []
    v1_prompts: list[tuple[str, str]] = []
    with V1_PROMPTS_FILE.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            prompt = record.get("prompt")
            v1_id = record.get("id", "<unknown v1 id>")
            if isinstance(prompt, str) and prompt:
                v1_prompts.append((v1_id, _fingerprint(prompt)))
    return v1_prompts


def find_v1_contamination_matches(
    cases: dict[str, list[dict]], corpus: list[dict]
) -> list[tuple[str, str, str, str, float]]:
    """Returns `(kind, artifact_id, split, v1_case_id, ratio)` tuples for
    every validation/holdout query or referenced-corpus-document match
    against v1 at or above `SIMILARITY_THRESHOLD`. `kind` is `"query"` or
    `"document"`. Code X Phase 12D re-audit, Critical #2 fix: the previous
    `check_v1_contamination` scanned only queries, so a v1 prompt copied
    verbatim into a corpus document would have passed silently. Every
    referenced document is scanned (not just queries); `check_no_orphan_
    documents` independently verifies every corpus document is referenced
    by at least one case, so this referenced-document scan is never a
    partial scan of the corpus. Development is correctly excluded per
    ADR-003. Split out from `check_v1_contamination` so the regeneration
    report can print separate query/document contamination statistics."""
    v1_prompts = _load_v1_prompts()
    if not v1_prompts:
        return []
    exemptions = _load_exemptions()
    doc_by_id = {d.get("document_id"): d for d in corpus if isinstance(d.get("document_id"), str)}

    matches: list[tuple[str, str, str, str, float]] = []
    for split in ("validation", "holdout"):
        for c in cases.get(split, []):
            case_id = c.get("case_id")
            if not isinstance(case_id, str):
                continue  # malformed case_id is reported separately by check_schemas
            query = c.get("query")
            if isinstance(query, str):
                fp = _fingerprint(query)
                for v1_id, v1_fp in v1_prompts:
                    if _is_exempt(exemptions, "v1", case_id, v1_id):
                        continue
                    ratio = _similarity(fp, v1_fp)
                    if ratio >= SIMILARITY_THRESHOLD:
                        matches.append(("query", case_id, split, v1_id, ratio))

            for doc_id in c.get("relevant_document_ids") or []:
                if not isinstance(doc_id, str):
                    continue  # malformed reference is reported separately by check_schemas
                doc = doc_by_id.get(doc_id)
                if doc is None:
                    continue
                content = doc.get("content")
                if not isinstance(content, str):
                    continue
                fp = _fingerprint(content)
                for v1_id, v1_fp in v1_prompts:
                    if _is_exempt(exemptions, "v1-document", doc_id, v1_id):
                        continue
                    ratio = _similarity(fp, v1_fp)
                    if ratio >= SIMILARITY_THRESHOLD:
                        matches.append(("document", doc_id, split, v1_id, ratio))
    return matches


def check_v1_contamination(cases: dict[str, list[dict]], corpus: list[dict]) -> list[str]:
    """ADR-003 prohibits v1 reuse in v2's validation/holdout splits (v1
    reuse is only ever legitimate in development). Error messages identify
    only safe, non-secret artifact IDs -- never the raw matched text."""
    errors = []
    for kind, artifact_id, split, v1_id, ratio in find_v1_contamination_matches(cases, corpus):
        errors.append(
            f"v1 contamination: {kind} {artifact_id!r} ({split}) is {ratio:.3f} similar to v1 case {v1_id!r}, "
            "prohibited by ADR-003 outside the development split"
        )
    return errors


def check_no_orphan_documents(corpus: list[dict], cases: dict[str, list[dict]]) -> list[str]:
    """Every corpus document must be referenced by at least one case (Code
    X Phase 12D re-audit, Critical #2): this is the invariant that lets
    `find_v1_contamination_matches`'s referenced-document scan stand in
    for a full-corpus scan, with no gap for an unreferenced document to
    bypass the v1-reuse policy."""
    referenced: set[str] = set()
    for split in SPLITS:
        for c in cases.get(split, []):
            for doc_id in c.get("relevant_document_ids") or []:
                if isinstance(doc_id, str):  # malformed reference reported separately by check_schemas
                    referenced.add(doc_id)
    orphans = sorted(
        d.get("document_id") for d in corpus
        if isinstance(d.get("document_id"), str) and d.get("document_id") not in referenced
    )
    if orphans:
        return [f"corpus document(s) not referenced by any case, bypassing document-level contamination scans: {orphans}"]
    return []


def check_no_cross_split_secret_reuse(corpus: list[dict], cases: dict[str, list[dict]]) -> list[str]:
    """Verbatim credential-shaped values (bearer tokens, API keys,
    password/secret assignments -- NOT the one canonical, documented
    FAKE-SECRET canary marker, which is an intentional fixed format
    reused by design) must never appear identically in documents
    belonging to two different splits."""
    errors = []
    doc_split: dict[str, set[str]] = {}
    for split in SPLITS:
        for c in cases.get(split, []):
            for doc_id in c.get("relevant_document_ids") or []:
                if isinstance(doc_id, str):  # malformed reference reported separately by check_schemas
                    doc_split.setdefault(doc_id, set()).add(split)

    value_to_docs: dict[str, set[str]] = {}
    for doc in corpus:
        content = doc.get("content", "")
        if not isinstance(content, str):
            continue  # non-string content is reported separately by check_schemas; never crash here
        doc_id = doc.get("document_id")
        if not isinstance(doc_id, str):
            continue  # malformed document_id is reported separately by check_schemas
        for match in _SECRET_LIKE_PATTERN.finditer(content):
            value = match.group(0)
            if CANONICAL_CANARY in value or value == CANONICAL_CANARY:
                continue
            value_to_docs.setdefault(value, set()).add(doc_id)

    for value, doc_ids in value_to_docs.items():
        splits_seen: set[str] = set()
        for doc_id in doc_ids:
            splits_seen |= doc_split.get(doc_id, set())
        if len(splits_seen) > 1:
            errors.append(
                f"credential-shaped value reused verbatim across splits {sorted(splits_seen)}: {value!r}"
            )
    return errors


# ---------------------------------------------------------------------------
# Authoring provenance and bilingual/translation contamination
# (Code X Phase 12D re-audit, Critical #1)
# ---------------------------------------------------------------------------


def check_authoring_provenance(
    corpus: list[dict], cases: dict[str, list[dict]], provenance: list[dict]
) -> list[str]:
    """Cross-checks `datasets/v2/design/authoring-provenance.jsonl` against
    the real case/corpus text: every generated query and every corpus
    document must have exactly one matching provenance entry, of the
    correct `artifact_type`, whose `normalized_text_hash` matches
    `build_v2_benchmark.normalized_text_hash` recomputed from the actual
    artifact text right now (a missing, duplicate, or dishonest -- i.e.
    stale/incorrect -- hash mapping fails). Also independently re-derives
    that no `semantic_group_id`/`translation_group_id` value in the
    provenance file is reused across two different splits, directly from
    the committed file rather than trusting the generator's own logic."""
    errors: list[str] = []
    if not isinstance(provenance, list):
        return ["authoring-provenance.jsonl root is not a list of records"]

    seen_ids: dict[str, int] = {}
    by_artifact_id: dict[str, dict] = {}
    for entry in provenance:
        if not isinstance(entry, dict):
            errors.append("authoring-provenance.jsonl contains a non-object record")
            continue
        keys = set(entry)
        missing = PROVENANCE_REQUIRED_FIELDS - keys
        extra = keys - PROVENANCE_REQUIRED_FIELDS
        if missing:
            errors.append(f"authoring-provenance.jsonl entry is missing fields: {sorted(missing)}")
        if extra:
            errors.append(f"authoring-provenance.jsonl entry has unexpected fields: {sorted(extra)}")
        artifact_id = entry.get("artifact_id")
        if not isinstance(artifact_id, str) or not artifact_id.strip():
            errors.append("authoring-provenance.jsonl has an entry with a missing/invalid artifact_id")
            continue
        seen_ids[artifact_id] = seen_ids.get(artifact_id, 0) + 1
        by_artifact_id[artifact_id] = entry

        # Type-first (Code X Phase 12D re-audit): every field below is
        # validated via a helper that confirms the value is a plain string
        # BEFORE any `in ALLOWED_SET` membership test, so a malformed
        # provenance entry (e.g. `split=[]`, `split={}`) is always a clean
        # validation error, never an unhandled `TypeError: unhashable
        # type` -- this was the exact class of crash the re-audit found.
        validate_string_enum(errors, entry.get("artifact_type"), f"authoring-provenance entry for {artifact_id!r} artifact_type", {"query", "document"})
        split = entry.get("split")
        split_ok = validate_string_enum(errors, split, f"authoring-provenance entry for {artifact_id!r} split", SPLIT_VALUES)
        validate_string_enum(errors, entry.get("language"), f"authoring-provenance entry for {artifact_id!r} language", EXPECTED_LANGUAGES)
        validate_string_enum(errors, entry.get("scenario_family"), f"authoring-provenance entry for {artifact_id!r} scenario_family", REQUIRED_FAMILIES)
        authoring_set = entry.get("authoring_set")
        if not validate_string_enum(errors, authoring_set, f"authoring-provenance entry for {artifact_id!r} authoring_set", SPLIT_VALUES):
            pass
        elif split_ok and authoring_set != split:
            errors.append(
                f"authoring-provenance entry for {artifact_id!r} has authoring_set "
                f"{authoring_set!r} inconsistent with split {split!r}"
            )
        validate_string_field(errors, entry.get("semantic_group_id"), f"authoring-provenance entry for {artifact_id!r} semantic_group_id")
        translation_group = entry.get("translation_group_id")
        if translation_group is not None:
            validate_string_field(errors, translation_group, f"authoring-provenance entry for {artifact_id!r} translation_group_id")
        text_hash = entry.get("normalized_text_hash")
        if not validate_string_field(errors, text_hash, f"authoring-provenance entry for {artifact_id!r} normalized_text_hash", allow_empty=True):
            pass
        elif re.fullmatch(r"[0-9a-f]{64}", text_hash) is None:
            errors.append(f"authoring-provenance entry for {artifact_id!r} has invalid normalized_text_hash")

    dupes = sorted(k for k, v in seen_ids.items() if v > 1)
    if dupes:
        errors.append(f"authoring-provenance.jsonl has duplicate artifact_id(s): {dupes}")

    expected_artifact_ids = {
        c.get("case_id")
        for split in SPLITS
        for c in cases.get(split, [])
        if isinstance(c.get("case_id"), str)
    } | {
        d.get("document_id") for d in corpus if isinstance(d.get("document_id"), str)
    }
    extra_artifact_ids = sorted(set(by_artifact_id) - expected_artifact_ids)
    if extra_artifact_ids:
        errors.append(
            "authoring-provenance.jsonl has entry/entries for unknown artifact_id(s): "
            f"{extra_artifact_ids}"
        )

    for split in SPLITS:
        for case in cases.get(split, []):
            case_id = case.get("case_id")
            if not isinstance(case_id, str):
                continue  # non-string case_id is reported separately by check_schemas
            entry = by_artifact_id.get(case_id)
            if entry is None:
                errors.append(f"case {case_id!r} has no matching authoring-provenance entry")
                continue
            if entry.get("artifact_type") != "query":
                errors.append(
                    f"authoring-provenance entry for {case_id!r} has artifact_type "
                    f"{entry.get('artifact_type')!r}, expected 'query'"
                )
            for field, expected_value in (
                ("split", split),
                ("authoring_set", split),
                ("language", case.get("language")),
                ("scenario_family", case.get("scenario_family")),
            ):
                if entry.get(field) != expected_value:
                    errors.append(
                        f"authoring-provenance {field} for {case_id!r} is {entry.get(field)!r}, "
                        f"expected {expected_value!r}"
                    )
            query = case.get("query")
            if isinstance(query, str):
                expected_hash = _generator.normalized_text_hash(query)
                if entry.get("normalized_text_hash") != expected_hash:
                    errors.append(f"authoring-provenance normalized_text_hash for {case_id!r} does not match the actual query text")

    doc_splits: dict[str, set[str]] = {}
    for split in SPLITS:
        for case in cases.get(split, []):
            for doc_id in case.get("relevant_document_ids") or []:
                if isinstance(doc_id, str):
                    doc_splits.setdefault(doc_id, set()).add(split)

    for doc in corpus:
        doc_id = doc.get("document_id")
        if not isinstance(doc_id, str):
            continue  # non-string document_id is reported separately by check_schemas
        entry = by_artifact_id.get(doc_id)
        if entry is None:
            errors.append(f"document {doc_id!r} has no matching authoring-provenance entry")
            continue
        if entry.get("artifact_type") != "document":
            errors.append(
                f"authoring-provenance entry for {doc_id!r} has artifact_type "
                f"{entry.get('artifact_type')!r}, expected 'document'"
            )
        expected_splits = doc_splits.get(doc_id, set())
        if len(expected_splits) == 1:
            expected_split = next(iter(expected_splits))
            for field, expected_value in (
                ("split", expected_split),
                ("authoring_set", expected_split),
                ("language", doc.get("language")),
                ("scenario_family", doc.get("scenario_family")),
            ):
                if entry.get(field) != expected_value:
                    errors.append(
                        f"authoring-provenance {field} for {doc_id!r} is {entry.get(field)!r}, "
                        f"expected {expected_value!r}"
                    )
        elif len(expected_splits) > 1:
            errors.append(f"document {doc_id!r} is referenced across multiple splits: {sorted(expected_splits)}")
        content = doc.get("content")
        if isinstance(content, str):
            expected_hash = _generator.normalized_text_hash(content)
            if entry.get("normalized_text_hash") != expected_hash:
                errors.append(f"authoring-provenance normalized_text_hash for {doc_id!r} does not match the actual document content")

    # A bilingual case and the documents authored for that case must remain
    # linked to the same provenance group. This is an explicit benchmark
    # authoring relationship, not a claim of general translation detection.
    for split in SPLITS:
        for case in cases.get(split, []):
            if case.get("language") != "bilingual":
                continue
            case_id = case.get("case_id")
            if not isinstance(case_id, str):
                continue  # non-string case_id is reported separately by check_schemas
            query_entry = by_artifact_id.get(case_id)
            if query_entry is None:
                continue
            query_group = query_entry.get("translation_group_id")
            for doc_id in case.get("relevant_document_ids") or []:
                if not isinstance(doc_id, str):
                    continue  # non-string reference is reported separately by check_schemas
                doc_entry = by_artifact_id.get(doc_id)
                if doc_entry is not None and doc_entry.get("translation_group_id") != query_group:
                    errors.append(
                        f"bilingual case {case_id!r} and document {doc_id!r} do not share "
                        "the same translation_group_id"
                    )

    group_owner: dict[str, str] = {}
    for entry in provenance:
        if not isinstance(entry, dict):
            continue
        split = entry.get("split")
        for field in ("semantic_group_id", "translation_group_id"):
            value = entry.get(field)
            if not value:
                continue
            key = f"{field}:{value}"
            owner = group_owner.get(key)
            if owner is not None and owner != split:
                errors.append(f"authoring-provenance {field} {value!r} is reused across splits ({owner!r} and {split!r})")
            group_owner[key] = split

    return errors


def check_bilingual_contamination(cases: dict[str, list[dict]]) -> list[str]:
    """Benchmark-specific lexical control (NOT general semantic duplicate
    detection -- see docs/benchmark-v2-methodology.md Section 10b):
    canonicalizes each query with `BILINGUAL_LEXICON`'s reviewed EN/VI
    phrase table, then flags a cross-split pair whose canonicalized forms
    are highly similar either by contiguous-sequence ratio
    (`BILINGUAL_SIMILARITY_THRESHOLD`) or by order-insensitive token
    overlap (`BILINGUAL_JACCARD_THRESHOLD`, so a clause-reordered direct
    translation is still caught even though reordering lowers the
    sequence-matcher ratio). Catches an exact EN/VI translation or an
    obvious bilingual rewrite that
    `check_cross_split_contamination`'s raw-text fingerprint cannot see,
    because a genuine translation shares almost no lexical surface form
    with its source language."""
    errors: list[str] = []
    exemptions = _load_exemptions()

    canon_by_split: dict[str, list[tuple[str, str]]] = {s: [] for s in SPLITS}
    for split in SPLITS:
        for c in cases.get(split, []):
            case_id = c.get("case_id")
            query = c.get("query")
            if case_id is None or not isinstance(query, str):
                continue
            canon_by_split[split].append((case_id, _canonicalize_bilingual(query)))

    for split_a, split_b in (("development", "validation"), ("development", "holdout"), ("validation", "holdout")):
        for id_a, canon_a in canon_by_split[split_a]:
            for id_b, canon_b in canon_by_split[split_b]:
                if not canon_a or not canon_b:
                    continue
                if _is_exempt(exemptions, "bilingual", id_a, id_b):
                    continue
                ratio = _similarity(canon_a, canon_b)
                jaccard = _token_jaccard(canon_a, canon_b)
                if ratio >= BILINGUAL_SIMILARITY_THRESHOLD or jaccard >= BILINGUAL_JACCARD_THRESHOLD:
                    errors.append(
                        f"bilingual/translation contamination (sequence={ratio:.3f}, jaccard={jaccard:.3f}): "
                        f"{id_a!r} ({split_a}) vs {id_b!r} ({split_b})"
                    )
    return errors


# ---------------------------------------------------------------------------
# Other repository invariants
# ---------------------------------------------------------------------------


def check_no_database_files() -> list[str]:
    errors = []
    for pattern in ("*.db", "*.sqlite", "*.sqlite3"):
        for match in OUT_DIR.rglob(pattern):
            errors.append(f"unexpected database file under datasets/v2/: {_rel(match)}")
    return errors


def check_source_keys(corpus: list[dict]) -> list[str]:
    errors = []
    for doc in corpus:
        doc_id = safe_record_identifier(doc, "document_id", fallback="<missing document_id>")
        source_key = doc.get("source_key")
        if not _safe_in(source_key, KNOWN_SOURCE_KEYS):
            errors.append(f"document {doc_id!r} has unrecognized source_key {source_key!r}")
        if source_key == "v2-unregistered-source-key" and doc.get("scenario_family") != "provenance_denied_at_ingestion":
            errors.append(
                f"document {doc_id!r} uses the deliberately-invalid source_key outside "
                "the provenance_denied_at_ingestion family"
            )
    return errors


def check_no_runtime_label_coupling() -> list[str]:
    """Static source scan: no file under app/ may import/read
    datasets/v2/labels or datasets/v2/cases."""
    errors = []
    app_dir = ROOT / "app"
    for py_file in app_dir.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        if "datasets/v2" in text or "datasets\\v2" in text or "benchmark-v2" in text:
            errors.append(f"{_rel(py_file)} references datasets/v2 -- runtime code must never do this")
    return errors


def check_manifest_structure() -> list[str]:
    """Lightweight structural sanity check only -- SHA-256 recomputation
    and drift detection is scripts/freeze_v2_benchmark.py's job
    (`freeze`/`verify` modes). This just guards against an obviously
    malformed or unsafe manifest shape."""
    if not MANIFEST_PATH.exists():
        return []
    errors = []
    try:
        with MANIFEST_PATH.open(encoding="utf-8") as f:
            manifest = json.load(f)
    except json.JSONDecodeError as exc:
        return [f"manifest {_rel(MANIFEST_PATH)} is not valid JSON ({exc})"]

    files = manifest.get("files")
    if not isinstance(files, list):
        return [f"manifest {_rel(MANIFEST_PATH)} has no 'files' list"]

    paths = [e.get("path") for e in files if isinstance(e, dict)]
    for p in paths:
        if not isinstance(p, str) or Path(p).is_absolute() or ":" in p or "\\" in p:
            errors.append(f"manifest contains an unsafe path entry: {p!r}")
    if paths != sorted(p for p in paths if isinstance(p, str)):
        errors.append("manifest file entries are not sorted by path")
    if manifest.get("file_count") != len(files):
        errors.append("manifest file_count does not match the number of file entries")
    return errors


# ---------------------------------------------------------------------------
# Optional, non-gating diagnostic against the CURRENT guard implementation
# ---------------------------------------------------------------------------

_ALLOW_FAMILIES = {
    "clean_benign_rag", "benign_security_discussion", "legitimate_authority_language",
    "academic_discussion_of_injection", "benign_secret_like_identifier",
    "mixed_trust_benign_retrieval",
}
_REJECT_AT_LEAST_ONE_FAMILIES = {
    "malicious_low_trust_source", "compromised_trusted_source",
    "all_context_blocked_multi_malicious", "leakage_context_exclusion",
}
_MIXED_ACCEPT_AND_REJECT_FAMILIES = {"mixed_benign_malicious_retrieval"}
_SANITIZE_FAMILIES = {
    "zero_width_whitespace_variant", "markdown_html_concealment",
    "leakage_dlp_mechanism_reference",
}
_NO_INDIVIDUAL_REJECTION_FAMILIES = {
    "multi_chunk_coordination", "fragment_beyond_per_chunk_prefix",
}


def diagnose_against_current_guards(
    corpus: list[dict], cases: dict[str, list[dict]], labels: dict[str, list[dict]],
    *, include_holdout: bool,
) -> list[str]:
    """NON-GATING diagnostic report only -- never called by default, never
    affects `main()`'s return code, never rewrites a label. Disagreement
    between a hand-authored label and the CURRENT guard implementation is
    expected evaluation evidence for a future Phase 12E run, not proof the
    benchmark is wrong; this exists purely as an optional developer sanity
    check. See the module docstring and
    docs/benchmark-v2-methodology.md Section 9 for the full rationale."""
    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from app.guards.input_guard import evaluate_input
        from app.guards.rag_guard import evaluate_rag_context
        from app.schemas.requests import RAGContextChunk
    except Exception as exc:  # noqa: BLE001
        return [f"DIAGNOSTIC: could not import guard modules: {exc}"]

    scoped_splits = ("development", "validation") + (("holdout",) if include_holdout else ())
    docs_by_id = {d.get("document_id"): d for d in corpus if isinstance(d.get("document_id"), str)}
    _STOPPING = {"block", "human_review"}

    def _chunk_decision(doc_id: str) -> str | None:
        doc = docs_by_id.get(doc_id)
        if doc is None:
            return None
        chunk = RAGContextChunk(doc_id=doc_id, text=doc.get("content", ""), metadata={})
        return evaluate_rag_context([chunk]).decision.value

    lines: list[str] = [
        "DIAGNOSTIC (non-gating): current-guard agreement report.",
        "Disagreement below is expected evaluation evidence, not a benchmark defect.",
    ]
    agree = 0
    disagree = 0
    for split in scoped_splits:
        label_by_id = {l.get("case_id"): l for l in labels.get(split, []) if isinstance(l.get("case_id"), str)}
        for case in cases.get(split, []):
            family = case.get("scenario_family")
            case_id = case.get("case_id")
            label = label_by_id.get(case_id) if isinstance(case_id, str) else None
            if label is None:
                continue
            expected = label.get("expected_final_decision")

            if family == "direct_injection":
                actual = evaluate_input(case.get("query", "")).decision.value
                match = actual == expected
            elif family in _ALLOW_FAMILIES:
                actual = "allow" if all(
                    _chunk_decision(d) == "allow" for d in case.get("relevant_document_ids") or []
                ) else "not-allow"
                match = actual == "allow"
            elif family in _REJECT_AT_LEAST_ONE_FAMILIES:
                decisions = [_chunk_decision(d) for d in case.get("relevant_document_ids") or []]
                actual = "rejected" if any(d in _STOPPING for d in decisions) else "not-rejected"
                match = actual == "rejected"
            elif family in _MIXED_ACCEPT_AND_REJECT_FAMILIES:
                decisions = [_chunk_decision(d) for d in case.get("relevant_document_ids") or []]
                match = any(d not in _STOPPING for d in decisions) and any(d in _STOPPING for d in decisions)
                actual = "mixed" if match else "not-mixed"
            elif family in _SANITIZE_FAMILIES:
                decisions = [_chunk_decision(d) for d in case.get("relevant_document_ids") or []]
                match = all(d == "sanitize" for d in decisions)
                actual = "sanitize" if match else str(decisions)
            elif family in _NO_INDIVIDUAL_REJECTION_FAMILIES:
                decisions = [_chunk_decision(d) for d in case.get("relevant_document_ids") or []]
                match = not any(d in _STOPPING for d in decisions)
                actual = "no-individual-rejection" if match else str(decisions)
            else:
                continue  # not statically guard-decidable (ingestion/retrieval/route behavior)

            if match:
                agree += 1
            else:
                disagree += 1
                lines.append(f"  DISAGREE {case_id!r} ({family}): label expected {expected!r}, guard actual {actual!r}")

    lines.append(f"Summary: {agree} agree, {disagree} disagree (scope: {', '.join(scoped_splits)}).")
    return lines


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--diagnose-current-guards", action="store_true",
        help="Print a NON-GATING report of where labels currently agree/disagree with the real guard "
             "implementation. Never affects the exit code. Development+validation only unless combined "
             "with --include-holdout-diagnostic.",
    )
    parser.add_argument(
        "--include-holdout-diagnostic", action="store_true",
        help="Only meaningful with --diagnose-current-guards: also include the holdout split in the "
             "non-gating diagnostic report (off by default to avoid casually exposing holdout ground truth).",
    )
    args = parser.parse_args(argv)

    # Primary safety mechanism is type-first preflight validation throughout
    # every check function below (Code X Phase 12D malformed-value re-audit):
    # check_schemas() and check_authoring_provenance() reject any list/dict/
    # number/bool/null field before it can reach a set/dict/hash operation,
    # so no dependent check ever consumes a value whose type validation
    # failed. This outer try/except is a last-resort boundary only, kept in
    # case an unforeseen case still slips through; it must never become the
    # primary mechanism, and it deliberately never echoes exception
    # internals (message text may embed absolute paths or raw artifact
    # content) — only a generic, safe, non-traceback message.
    try:
        return _run_validation(args)
    except ValidationError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    except Exception:
        print("FAIL: an unexpected internal error occurred during validation.", file=sys.stderr)
        return 1


def _run_validation(args: argparse.Namespace) -> int:
    corpus = _load_jsonl(CORPUS_FILE)
    cases = {s: _load_jsonl(CASES_DIR / f"{s}.jsonl") for s in SPLITS}
    labels = {s: _load_jsonl(LABELS_DIR / f"{s}.jsonl") for s in SPLITS}
    provenance = _load_jsonl(PROVENANCE_FILE)

    # Type/schema validation is a hard preflight. Do not feed malformed
    # values into normalization, similarity, reference, or provenance code;
    # this keeps every bad artifact on the controlled validation path.
    schema_errors = check_schemas(corpus, cases, labels)
    if schema_errors:
        print(f"FAIL: {len(schema_errors)} validation error(s):", file=sys.stderr)
        for err in sorted(schema_errors):
            print(f"  - {err}", file=sys.stderr)
        return 1

    all_errors: list[str] = []
    all_errors += check_split_and_language_consistency(cases, labels)
    all_errors += check_counts(cases)
    all_errors += check_family_registry(cases)
    all_errors += check_language_coverage(cases)
    all_errors += check_class_distribution(labels)
    all_errors += check_case_label_mapping(cases, labels)
    all_errors += check_referential_integrity(corpus, cases)
    all_errors += check_no_orphan_documents(corpus, cases)
    all_errors += check_no_duplicate_ids(corpus, cases)
    all_errors += check_no_duplicate_external_ids(corpus)
    all_errors += check_no_normalized_duplicate_queries(cases)
    all_errors += check_cross_split_contamination(corpus, cases, labels)
    all_errors += check_bilingual_contamination(cases)
    all_errors += check_authoring_provenance(corpus, cases, provenance)
    all_errors += check_v1_contamination(cases, corpus)
    all_errors += check_no_cross_split_secret_reuse(corpus, cases)
    all_errors += check_no_database_files()
    all_errors += check_source_keys(corpus)
    all_errors += check_no_runtime_label_coupling()
    all_errors += check_manifest_structure()

    if all_errors:
        print(f"FAIL: {len(all_errors)} validation error(s):", file=sys.stderr)
        for err in sorted(all_errors):
            print(f"  - {err}", file=sys.stderr)
        return 1

    total = sum(len(cases[s]) for s in SPLITS)
    print(f"OK: {len(corpus)} documents, {total} cases across {len(SPLITS)} splits, all checks passed "
          "(guard-independent; see --diagnose-current-guards for an optional, non-gating guard-agreement report).")

    if args.diagnose_current_guards:
        print()
        for line in diagnose_against_current_guards(
            corpus, cases, labels, include_holdout=args.include_holdout_diagnostic
        ):
            print(line)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
