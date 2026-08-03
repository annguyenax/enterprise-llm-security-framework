#!/usr/bin/env python3
"""Analyze one complete Phase 12E development or validation C0-C7 matrix."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import re
import shutil
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import load_settings
from app.core.decisions import Decision
from scripts import run_v2_evaluation as runner


ANALYSIS_SCHEMA_VERSION = 1
ANALYSIS_MANIFEST_SCHEMA_VERSION = 1

# Phase 12E.4: holdout analysis artifacts carry their own schema identity so a
# holdout artifact can never be processed by a development/validation reader and
# vice versa. The development/validation constants above are unchanged.
HOLDOUT_ANALYSIS_SCHEMA_VERSION = 1
HOLDOUT_ANALYSIS_MANIFEST_SCHEMA_VERSION = 1

# The runner declares the same two identities so it can validate an
# authorization's analysis contract before claiming an attempt root, without
# importing this module. They must never drift apart.
assert HOLDOUT_ANALYSIS_SCHEMA_VERSION == runner.HOLDOUT_ANALYSIS_SCHEMA_VERSION
assert (
    HOLDOUT_ANALYSIS_MANIFEST_SCHEMA_VERSION
    == runner.HOLDOUT_ANALYSIS_MANIFEST_SCHEMA_VERSION
)
HOLDOUT_IDENTITY_KEYS = (
    "authorization_id",
    "holdout_authorization_sha256",
    "attempt",
    "supersedes_authorization_sha256",
    "holdout_authorized",
)
ANALYSIS_CONTRACT_VERSION = 1
CSV_SCHEMA_VERSION = 1
RATE_REPORTING_MIN_N = 10
WILSON_CONFIDENCE_LEVEL = 0.95
WILSON_Z_95 = 1.959963984540054
MAPPING_VERSION = "phase12e3-family-map-v2"

WILSON_CAVEAT = (
    "Confidence intervals describe only uncertainty within this specific synthetic "
    "benchmark sample; they do not establish generalized performance ranges for "
    "production systems or unseen attack vectors."
)
LEAKAGE_CAVEAT = (
    "The deterministic Mock Provider does not echo retrieved context, so these cases "
    "exercise context exclusion and leakage-control mechanisms; they do not demonstrate "
    "real end-to-end data exfiltration prevention."
)
NON_ADDITIVITY_CAVEAT = (
    "Sum of per-guard deltas is not a partition of the C0-C6 AOMR gap; guards may overlap."
)
MARGINAL_CLAIM_TEMPLATE = (
    "Disabling Guard G changed the Allowed Outcome Match Rate by Δ on the paired "
    "benchmark subset."
)
LATENCY_NOTE = (
    "Samples originate from decision-determinism repetitions, not a frozen scientific "
    "latency protocol."
)

ANALYSIS_GROUPS: dict[str, tuple[str, ...]] = {
    "direct_injection": ("direct_injection",),
    "indirect_injection": (
        "all_context_blocked_multi_malicious",
        "compromised_trusted_source",
        "indirect_retrieved_injection",
        "malicious_low_trust_source",
        "markdown_html_concealment",
        "mixed_benign_malicious_retrieval",
        "multi_chunk_coordination",
        "zero_width_whitespace_variant",
    ),
    "leakage_mechanisms": (
        "leakage_context_exclusion",
        "leakage_dlp_mechanism_reference",
    ),
    "benign_control": (
        "academic_discussion_of_injection",
        "benign_secret_like_identifier",
        "benign_security_discussion",
        "benign_trap_query",
        "clean_benign_rag",
        "fragment_near_aggregate_budget",
        "legitimate_authority_language",
        "mixed_trust_benign_retrieval",
        "no_retrieval_hit",
    ),
}
NON_MATRIX_FAMILIES = (
    "availability_failure_case",
    "fragment_beyond_per_chunk_prefix",
    "provenance_denied_at_ingestion",
)
GROUP_REPORT_ORDER = (
    "direct_injection",
    "indirect_injection",
    "leakage_mechanisms",
    "benign_control",
)
MARGINAL_DEFINITIONS = (
    ("input_guard", "C1_no_input", False),
    ("provenance_guard", "C2_no_provenance", False),
    ("context_guards", "C3_no_context", False),
    ("dlp", "C4_no_dlp", True),
    ("output_guard", "C5_no_output", True),
)

RESULT_MANIFEST_KEYS = frozenset(
    {
        "schema_version",
        "result_file",
        "result_sha256",
        "result_size_bytes",
        "result_schema_version",
        "experiment_id",
        "run_id",
        "run_status",
        "config_id",
        "config_hash",
        "profile_id",
        "provider_id",
        "provider_behavior_hash",
        "git_commit",
        "benchmark_manifest_sha256",
        "expected_case_set_sha256",
    }
)
RESULT_KEYS = frozenset(
    {
        "schema_version",
        "experiment_id",
        "run_id",
        "run_status",
        "config_id",
        "config_hash",
        "profile_id",
        "guard_profile",
        "environment",
        "split",
        "provider_id",
        "provider_behavior_hash",
        "safety_limits",
        "expected_case_count",
        "expected_case_set_sha256",
        "expected_case_sets_by_scope",
        "completed_case_count",
        "error_case_count",
        "timeout_case_count",
        "skipped_case_count",
        "cases",
        "aggregate",
    }
)
ENVIRONMENT_KEYS = frozenset(
    {
        "git_commit",
        "git_branch",
        "git_dirty",
        "python_version",
        "platform",
        "cpu",
        "benchmark_manifest_sha256",
        "benchmark_manifest_status",
        "dependencies",
        "dependencies_sha256",
        "enable_audit_log",
        "guard_profile",
        "provider_id",
        "provider_behavior_hash",
        "repetitions",
        "warmup",
        "aggregate_context_limit",
        "provider_output_limit",
        "result_schema_version",
    }
)
SAFETY_LIMIT_KEYS = frozenset(
    {
        "query_max_chars",
        "query_max_terms",
        "retrieval_max_top_k",
        "rag_max_top_k",
        "ingestion_max_batch_size",
        "document_max_chars",
        "chunk_max_chars",
        "chunk_overlap_chars",
        "aggregate_context_limit",
        "provider_output_limit",
        "case_timeout_seconds",
        "temporary_sqlite_required",
        "network_disabled",
    }
)
CASE_KEYS = frozenset(
    {
        "case_id",
        "case_ordinal",
        "config_id",
        "config_hash",
        "profile_id",
        "split",
        "scenario_family",
        "category",
        "evaluation_scope",
        "observation_namespace",
        "git_commit",
        "benchmark_manifest_sha256",
        "case_status",
        "error_category",
        "expected_outcome",
        "actual_final_decision",
        "actual_stop_reason",
        "actual_provider_called",
        "actual_retrieved_count",
        "actual_accepted_context_count",
        "actual_rejected_context_count",
        "actual_redaction_count",
        "actual_dlp_finding_categories",
        "actual_document_ingestion_status",
        "actual_target_document_hit_count",
        "correct",
        "leakage_eligible",
        "leakage_observed",
        "stage_results",
        "latency_ms_samples",
    }
)
EXPECTED_OUTCOME_KEYS = frozenset(
    {"allowed_final_decisions", "allowed_stop_reasons", "provider_called"}
)
STAGE_KEYS = frozenset(
    {"stage", "enabled", "decision", "reason_code", "execution_time_ms"}
)
VALID_STAGE_DECISIONS = frozenset(decision.value for decision in Decision)
LATENCY_SAMPLE_KEYS = frozenset(
    {"pipeline_pre_audit_total", "end_to_end_with_audit"}
)
AGGREGATE_KEYS = frozenset(
    {"n_end_to_end", "aomr", "fpr", "fnr", "marginal_contribution", "metrics_computed", "note"}
)

RATE_KEYS = frozenset(
    {
        "numerator",
        "denominator",
        "n",
        "defined",
        "reporting_eligible",
        "value",
        "ineligibility_reason",
        "wilson_95",
    }
)
WILSON_KEYS = frozenset({"low", "high", "eligible"})
CONFUSION_KEYS = frozenset({"TP", "FN", "TN", "FP", "n_M", "n_B"})
FAMILY_ROW_KEYS = frozenset(
    {"scenario_family", "evaluation_scope", "analysis_group", "matched", "total", "error_count"}
)
MARGINAL_KEYS = frozenset(
    {
        "guard",
        "baseline_config_id",
        "ablated_config_id",
        "paired_case_ids_sha256",
        "paired_n_M",
        "both_correct",
        "baseline_only",
        "ablated_only",
        "both_incorrect",
        "baseline_aomr_numerator",
        "baseline_aomr_denominator",
        "ablated_aomr_numerator",
        "ablated_aomr_denominator",
        "delta_value",
        "non_additivity_caveat",
        "claim_template",
        "mock_provider_limitation",
    }
)
ANALYSIS_KEYS = frozenset(
    {
        "schema_version",
        "analysis_contract_version",
        "analysis_contract_sha256",
        "analyzer_commit",
        "split",
        "experiment_id",
        "benchmark_manifest_sha256",
        "mapping_version",
        "mapping_sha256",
        "rate_reporting_min_n",
        "wilson_confidence_level",
        "wilson_continuity_correction",
        "wilson_caveat",
        "input_manifests",
        "identity",
        "family_to_group",
        "non_matrix_families",
        "leakage_mechanisms_caveat",
        "configs",
        "marginal",
        "latency",
        "claims_control",
    }
)
INPUT_MANIFEST_ENTRY_KEYS = frozenset(
    {
        "config_id",
        "manifest_path_basename",
        "manifest_sha256",
        "result_sha256",
        "result_size_bytes",
        "run_id",
        "run_status",
        "config_hash",
        "expected_case_set_sha256",
    }
)
ANALYSIS_IDENTITY_KEYS = frozenset(
    {
        "git_branch",
        "git_commit",
        "git_dirty",
        "provider_id",
        "provider_behavior_hash",
        "dependencies_sha256",
    }
)
CONFIG_ANALYSIS_KEYS = frozenset(
    {
        "config_hash",
        "profile_id",
        "run_id",
        "run_status",
        "guard_profile",
        "expected_case_count",
        "expected_case_set_sha256",
        "coverage",
        "successful_coverage",
        "error_rate",
        "confusion",
        "aomr",
        "mismatch_rate",
        "fpr",
        "by_analysis_group",
        "by_family",
    }
)
GROUP_RESULT_KEYS = frozenset({"confusion", "aomr", "fpr"})
NON_MATRIX_RESULT_KEYS = frozenset({"case_count", "matched", "error_count"})
NON_MATRIX_SCOPE_KEYS = frozenset(
    {"component", "availability_fault", "residual_risk_only"}
)
LATENCY_KEYS = frozenset(
    {
        "protocol",
        "repetitions_observed",
        "warmup_observed",
        "reportable",
        "p50",
        "p95",
        "required_future_gate",
        "note",
    }
)
CLAIMS_CONTROL_KEYS = frozenset(
    {
        "abr_enabled",
        "macro_enabled",
        "family_rates_enabled",
        "tiny_n_rate_suppression_enabled",
        "latency_reportable",
        "no_p_values",
        "no_family_percentages",
        "benchmark_comparison_not_causal",
        "c4_c5_mock_limitation",
        "leakage_not_real_exfiltration",
    }
)
ANALYSIS_MANIFEST_KEYS = frozenset(
    {
        "schema_version",
        "analysis_file",
        "analysis_sha256",
        "analysis_size_bytes",
        "table_file",
        "table_sha256",
        "table_size_bytes",
        "analysis_schema_version",
        "analysis_contract_sha256",
        "mapping_version",
        "mapping_sha256",
        "split",
        "experiment_id",
        "analyzer_commit",
        "benchmark_manifest_sha256",
        "rate_reporting_min_n",
        "abr_enabled",
        "macro_metrics_enabled",
        "latency_reportable",
        "input_manifest_sha256_list",
    }
)
ANALYSIS_MANIFEST_INPUT_KEYS = frozenset(
    {
        "config_id",
        "run_id",
        "run_status",
        "config_hash",
        "manifest_sha256",
        "result_sha256",
    }
)

CSV_FIELDS = (
    "split",
    "experiment_id",
    "config_id",
    "metric_scope",
    "scope_id",
    "TP",
    "FN",
    "TN",
    "FP",
    "n_M",
    "n_B",
    "aomr_numerator",
    "aomr_denominator",
    "aomr_defined",
    "aomr_reporting_eligible",
    "aomr_value",
    "aomr_ineligibility_reason",
    "mismatch_numerator",
    "mismatch_denominator",
    "mismatch_defined",
    "mismatch_reporting_eligible",
    "mismatch_value",
    "mismatch_ineligibility_reason",
    "fpr_numerator",
    "fpr_denominator",
    "fpr_defined",
    "fpr_reporting_eligible",
    "fpr_value",
    "fpr_ineligibility_reason",
    "wilson_aomr_low",
    "wilson_aomr_high",
    "wilson_aomr_eligible",
    "wilson_fpr_low",
    "wilson_fpr_high",
    "wilson_fpr_eligible",
    "coverage_value",
    "successful_coverage_value",
    "error_rate_value",
    "family_matched",
    "family_total",
    "family_error_count",
    "delta_value",
    "mock_provider_limitation",
    "baseline_config_id",
    "ablated_config_id",
    "paired_case_ids_sha256",
    "paired_n_M",
    "both_correct",
    "baseline_only",
    "ablated_only",
    "both_incorrect",
    "baseline_aomr_numerator",
    "baseline_aomr_denominator",
    "ablated_aomr_numerator",
    "ablated_aomr_denominator",
)

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


class AnalysisError(RuntimeError):
    """Controlled analyzer failure with a stable, content-free category."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class AnalysisIntegrityError(AnalysisError):
    """Identity or schema failure that prohibits analysis publication."""


@dataclass(frozen=True)
class AnalysisRequest:
    split: str
    expected_branch: str
    expected_commit: str
    output_root: Path
    result_manifests: tuple[Path, ...]


@dataclass(frozen=True)
class HoldoutAnalysisRequest:
    """Authorized holdout analysis request.

    A separate type from `AnalysisRequest` so the ordinary path can never carry
    holdout, and so `_validate_request`'s SUPPORTED_SPLITS gate stays intact.
    Branch, commit, attempt root and every contract identity come from the
    external authorization, not from CLI flags.
    """

    authorization_path: Path
    result_manifests: tuple[Path, ...]

    @property
    def split(self) -> str:
        raise AttributeError(
            "HoldoutAnalysisRequest has no split; holdout is not a SUPPORTED_SPLITS member"
        )


@dataclass(frozen=True)
class AnalyzerHooks:
    repository_state_loader: Callable[[Path], runner.RepositoryState] = field(
        default=lambda root: runner.read_repository_state(root)
    )


@dataclass(frozen=True)
class VerifiedInput:
    manifest_path: Path
    manifest_sha256: str
    manifest: Mapping[str, Any]
    result_sha256: str
    result_size_bytes: int
    result: Mapping[str, Any]


@dataclass(frozen=True)
class WrittenAnalysis:
    output_directory: Path
    analysis_path: Path
    table_path: Path
    manifest_path: Path


def _mapping_payload(
    groups: Mapping[str, Sequence[str]] = ANALYSIS_GROUPS,
    non_matrix_families: Sequence[str] = NON_MATRIX_FAMILIES,
) -> dict[str, Any]:
    return {
        "mapping_version": MAPPING_VERSION,
        "groups": {name: list(values) for name, values in groups.items()},
        "non_matrix_families": list(non_matrix_families),
    }


MAPPING_SHA256 = runner._sha256_bytes(  # noqa: SLF001
    runner._canonical_json_bytes(_mapping_payload())  # noqa: SLF001
)
ANALYSIS_CONTRACT = {
    "abr_enabled": False,
    "analysis_manifest_schema_version": ANALYSIS_MANIFEST_SCHEMA_VERSION,
    "analysis_schema_version": ANALYSIS_SCHEMA_VERSION,
    "config_registry_version": runner.CONFIG_REGISTRY_VERSION,
    "csv_schema_version": CSV_SCHEMA_VERSION,
    "latency_reportable": False,
    "macro_metrics_enabled": False,
    "mapping_sha256": MAPPING_SHA256,
    "mapping_version": MAPPING_VERSION,
    "primary_scopes": ["end_to_end"],
    "rate_reporting_min_n": RATE_REPORTING_MIN_N,
    "wilson_confidence_level": WILSON_CONFIDENCE_LEVEL,
    "wilson_continuity_correction": False,
}
ANALYSIS_CONTRACT_SHA256 = runner._sha256_bytes(  # noqa: SLF001
    runner._canonical_json_bytes(ANALYSIS_CONTRACT)  # noqa: SLF001
)


def _fail(code: str, message: str) -> None:
    raise AnalysisIntegrityError(code, message)


def _exact_keys(value: Any, expected: frozenset[str], location: str) -> Mapping[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        _fail("schema_keys", f"{location} has an unsupported field set")
    return value


def _string(value: Any, location: str, *, safe_id: bool = False) -> str:
    if not isinstance(value, str) or not value:
        _fail("schema_type", f"{location} must be a non-empty string")
    if safe_id and not _SAFE_ID_RE.fullmatch(value):
        _fail("unsafe_identifier", f"{location} contains unsupported characters")
    return value


def _hash(value: Any, location: str) -> str:
    if not isinstance(value, str) or not _HASH_RE.fullmatch(value):
        _fail("schema_hash", f"{location} must be a lowercase SHA-256")
    return value


def _integer(value: Any, location: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail("schema_type", f"{location} must be an integer >= {minimum}")
    return value


def _boolean(value: Any, location: str) -> bool:
    if type(value) is not bool:
        _fail("schema_type", f"{location} must be boolean")
    return value


def _finite_number(value: Any, location: str, *, nullable: bool = False) -> float | None:
    if value is None and nullable:
        return None
    if type(value) not in {int, float} or not math.isfinite(value) or value < 0:
        _fail("schema_type", f"{location} must be a finite non-negative number")
    return float(value)


def _finite_signed_number(value: Any, location: str) -> float:
    if type(value) not in {int, float} or not math.isfinite(value):
        _fail("schema_type", f"{location} must be a finite number")
    return float(value)


def _strict_json(raw: bytes, location: str) -> Mapping[str, Any]:
    class DuplicateKey(ValueError):
        pass

    def pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise DuplicateKey(key)
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise ValueError(value)

    try:
        text = raw.decode("utf-8")
        value = json.loads(
            text,
            object_pairs_hook=pairs_hook,
            parse_constant=reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError, DuplicateKey, ValueError) as exc:
        raise AnalysisIntegrityError("invalid_json", f"{location} is not strict UTF-8 JSON") from exc
    if not isinstance(value, dict):
        _fail("schema_type", f"{location} must contain an object")
    try:
        canonical = runner._canonical_json_bytes(value)  # noqa: SLF001
    except (TypeError, ValueError) as exc:
        raise AnalysisIntegrityError("invalid_json", f"{location} is not canonical JSON-safe") from exc
    if raw != canonical:
        _fail("noncanonical_json", f"{location} is not canonical JSON")
    return value


def _contains_symlink(path: Path) -> bool:
    current = path
    while True:
        if current.exists() and current.is_symlink():
            return True
        if current.parent == current:
            return False
        current = current.parent


def _resolve_manifest_path(path: Path) -> Path:
    expanded = path.expanduser()
    if ".." in expanded.parts:
        _fail("unsafe_manifest_path", "result manifest path traversal is prohibited")
    absolute = Path(os.path.abspath(expanded))
    if absolute.name != "result-manifest.json" or _contains_symlink(absolute):
        _fail("unsafe_manifest_path", "result manifest must be a direct non-symlink file")
    try:
        resolved = absolute.resolve(strict=True)
    except OSError as exc:
        raise AnalysisIntegrityError("manifest_unreadable", "result manifest is unavailable") from exc
    if not resolved.is_file() or resolved.parent != absolute.parent.resolve():
        _fail("unsafe_manifest_path", "result manifest escaped its declared directory")
    return resolved


def _validate_holdout_identity_fields(payload: Mapping[str, Any], location: str) -> None:
    """Strict shape check for the five safe holdout identity fields."""
    _string(payload["authorization_id"], f"{location}.authorization_id")
    if not runner._CANONICAL_UUID_RE.fullmatch(payload["authorization_id"]):  # noqa: SLF001
        _fail("holdout_identity", f"{location}.authorization_id must be a canonical lowercase UUID")
    _hash(payload["holdout_authorization_sha256"], f"{location}.holdout_authorization_sha256")
    attempt = payload["attempt"]
    if type(attempt) is not int or attempt < 1:
        _fail("holdout_identity", f"{location}.attempt must be an integer >= 1")
    supersedes = payload["supersedes_authorization_sha256"]
    if attempt == 1:
        if supersedes is not None:
            _fail("holdout_identity", f"{location}.attempt 1 must not supersede an authorization")
    else:
        _hash(supersedes, f"{location}.supersedes_authorization_sha256")
    if payload["holdout_authorized"] is not True:
        _fail("holdout_identity", f"{location}.holdout_authorized must be boolean true")


def _read_verified_input(path: Path, *, holdout: bool = False) -> VerifiedInput:
    """Read and structurally verify one result manifest and its result.json.

    `holdout=True` selects the Phase 12E.4 holdout contract: the holdout
    manifest/result schema identities plus the five safe authorization/attempt
    identity keys. An ordinary development/validation artifact therefore fails
    holdout analysis, and a holdout artifact fails ordinary analysis.
    """
    manifest_path = _resolve_manifest_path(path)
    try:
        manifest_bytes = manifest_path.read_bytes()
    except OSError as exc:
        raise AnalysisIntegrityError("manifest_unreadable", "result manifest is unavailable") from exc
    manifest = _strict_json(manifest_bytes, "result-manifest.json")
    expected_manifest_keys = (
        RESULT_MANIFEST_KEYS | frozenset(HOLDOUT_IDENTITY_KEYS) if holdout else RESULT_MANIFEST_KEYS
    )
    _exact_keys(manifest, expected_manifest_keys, "result-manifest.json")
    runner.scan_forbidden_artifact_content(manifest)

    _integer(manifest["schema_version"], "manifest.schema_version", minimum=1)
    _integer(
        manifest["result_schema_version"],
        "manifest.result_schema_version",
        minimum=1,
    )
    expected_manifest_schema = (
        runner.HOLDOUT_RESULT_MANIFEST_SCHEMA_VERSION if holdout else runner.RESULT_MANIFEST_SCHEMA_VERSION
    )
    expected_result_schema = (
        runner.HOLDOUT_RESULT_SCHEMA_VERSION if holdout else runner.RESULT_SCHEMA_VERSION
    )
    if manifest["schema_version"] != expected_manifest_schema:
        _fail("manifest_schema", "result manifest schema is unsupported")
    if manifest["result_schema_version"] != expected_result_schema:
        _fail("result_schema", "result schema identity is unsupported")
    if holdout:
        _validate_holdout_identity_fields(manifest, "manifest")
    if _string(manifest["result_file"], "manifest.result_file") != "result.json":
        _fail("unsafe_result_path", "result manifest must reference sibling result.json")
    _hash(manifest["result_sha256"], "manifest.result_sha256")
    _integer(manifest["result_size_bytes"], "manifest.result_size_bytes", minimum=1)
    for field_name in (
        "experiment_id",
        "config_hash",
        "provider_behavior_hash",
        "benchmark_manifest_sha256",
        "expected_case_set_sha256",
    ):
        _hash(manifest[field_name], f"manifest.{field_name}")
    for field_name in ("run_id", "config_id", "profile_id", "provider_id"):
        _string(manifest[field_name], f"manifest.{field_name}", safe_id=True)
    if not _FULL_SHA_RE.fullmatch(_string(manifest["git_commit"], "manifest.git_commit")):
        _fail("schema_hash", "manifest.git_commit must be a full lowercase SHA-1")
    run_status = _string(manifest["run_status"], "manifest.run_status", safe_id=True)
    if run_status not in {"complete", "partial"}:
        _fail("run_status", "manifest run_status is unsupported")

    result_path = manifest_path.parent / "result.json"
    if result_path.is_symlink() or _contains_symlink(result_path):
        _fail("unsafe_result_path", "result.json symlinks are prohibited")
    try:
        resolved_result = result_path.resolve(strict=True)
        result_bytes = resolved_result.read_bytes()
    except OSError as exc:
        raise AnalysisIntegrityError("result_unreadable", "sibling result.json is unavailable") from exc
    if resolved_result.parent != manifest_path.parent or resolved_result.name != "result.json":
        _fail("unsafe_result_path", "result.json escaped the manifest directory")
    if len(result_bytes) != manifest["result_size_bytes"]:
        _fail("result_size", "result.json byte size does not match its manifest")
    result_sha256 = hashlib.sha256(result_bytes).hexdigest()
    if result_sha256 != manifest["result_sha256"]:
        _fail("result_hash", "result.json SHA-256 does not match its manifest")
    result = _strict_json(result_bytes, "result.json")
    runner.scan_forbidden_artifact_content(result)

    return VerifiedInput(
        manifest_path=manifest_path,
        manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        manifest=manifest,
        result_sha256=result_sha256,
        result_size_bytes=len(result_bytes),
        result=result,
    )


def _validate_stage_results(value: Any, location: str) -> None:
    if not isinstance(value, list):
        _fail("case_schema", f"{location} must be a list")
    for index, stage in enumerate(value):
        item = _exact_keys(stage, STAGE_KEYS, f"{location}[{index}]")
        _string(item["stage"], f"{location}[{index}].stage", safe_id=True)
        enabled = _boolean(item["enabled"], f"{location}[{index}].enabled")
        if enabled:
            decision = _string(
                item["decision"], f"{location}[{index}].decision", safe_id=True
            )
            if decision not in VALID_STAGE_DECISIONS:
                _fail(
                    "case_schema",
                    f"{location}[{index}].decision is not a supported decision",
                )
        elif item["decision"] is not None:
            _fail(
                "case_schema",
                f"{location}[{index}].decision must be null when the stage is disabled",
            )
        _string(item["reason_code"], f"{location}[{index}].reason_code", safe_id=True)
        _finite_number(
            item["execution_time_ms"],
            f"{location}[{index}].execution_time_ms",
            nullable=True,
        )


def _validate_latency_samples(value: Any, status: str, location: str) -> None:
    samples = _exact_keys(value, LATENCY_SAMPLE_KEYS, location)
    for key in LATENCY_SAMPLE_KEYS:
        items = samples[key]
        if not isinstance(items, list):
            _fail("case_schema", f"{location}.{key} must be a list")
        for index, item in enumerate(items):
            _finite_number(item, f"{location}.{key}[{index}]")
        if len(items) not in ({0, 2} if key == "pipeline_pre_audit_total" else {0, 2}):
            _fail("case_schema", f"{location}.{key} has an unsupported repetition count")
    if status == "completed" and len(samples["end_to_end_with_audit"]) != 2:
        _fail("case_schema", "completed cases must contain two determinism timings")
    if status != "completed" and any(samples[key] for key in LATENCY_SAMPLE_KEYS):
        _fail("case_schema", "failed cases must not contain timing samples")


def _validate_case_record(
    record: Any,
    *,
    ordinal: int,
    expected_case: Mapping[str, Any],
    expected_label: Mapping[str, Any],
    config: runner.EvaluationConfig,
    split: str,
    git_commit: str,
    benchmark_manifest_sha256: str,
) -> Mapping[str, Any]:
    location = f"cases[{ordinal}]"
    item = _exact_keys(record, CASE_KEYS, location)
    _integer(item["case_ordinal"], f"{location}.case_ordinal")
    if item["case_id"] != expected_case["case_id"] or item["case_ordinal"] != ordinal:
        _fail("case_identity", f"{location} identity or ordering changed")
    expected_pairs = {
        "config_id": config.config_id,
        "config_hash": config.config_hash,
        "profile_id": config.profile.profile_id,
        "split": split,
        "scenario_family": expected_case["scenario_family"],
        "category": expected_label["category"],
        "evaluation_scope": expected_case["evaluation_scope"],
        "observation_namespace": runner.OBSERVATION_NAMESPACES[
            expected_case["evaluation_scope"]
        ],
        "git_commit": git_commit,
        "benchmark_manifest_sha256": benchmark_manifest_sha256,
    }
    for field_name, expected in expected_pairs.items():
        if item[field_name] != expected:
            _fail("case_identity", f"{location}.{field_name} disagrees with frozen identity")

    expected_outcome = _exact_keys(
        item["expected_outcome"], EXPECTED_OUTCOME_KEYS, f"{location}.expected_outcome"
    )
    if expected_outcome != {
        "allowed_final_decisions": list(expected_label["allowed_final_decisions"]),
        "allowed_stop_reasons": list(expected_label["allowed_stop_reasons"]),
        "provider_called": expected_label["expected_provider_called"],
    }:
        _fail("case_label", f"{location}.expected_outcome disagrees with frozen label")

    if type(item["correct"]) is not bool:
        _fail("case_schema", f"{location}.correct must be boolean")
    if type(item["leakage_eligible"]) is not bool or type(item["leakage_observed"]) is not bool:
        _fail("case_schema", f"{location} leakage flags must be boolean")
    if not isinstance(item["actual_dlp_finding_categories"], dict):
        _fail("case_schema", f"{location}.actual_dlp_finding_categories must be an object")
    for key, count in item["actual_dlp_finding_categories"].items():
        _string(key, f"{location}.actual_dlp_finding_categories key", safe_id=True)
        _integer(count, f"{location}.actual_dlp_finding_categories.{key}")
    _validate_stage_results(item["stage_results"], f"{location}.stage_results")

    status = _string(item["case_status"], f"{location}.case_status", safe_id=True)
    if status not in {"completed", "error", "timeout"}:
        _fail("case_status", f"{location}.case_status is unsupported")
    _validate_latency_samples(item["latency_ms_samples"], status, f"{location}.latency_ms_samples")
    if status == "completed":
        if item["error_category"] is not None:
            _fail("case_status", f"{location}.error_category must be null")
        actual_decision = _string(
            item["actual_final_decision"], f"{location}.actual_final_decision", safe_id=True
        )
        actual_reason = _string(
            item["actual_stop_reason"], f"{location}.actual_stop_reason", safe_id=True
        )
        if type(item["actual_provider_called"]) is not bool:
            _fail("case_schema", f"{location}.actual_provider_called must be boolean")
        for field_name in (
            "actual_retrieved_count",
            "actual_accepted_context_count",
            "actual_rejected_context_count",
            "actual_redaction_count",
        ):
            _integer(item[field_name], f"{location}.{field_name}")
        for field_name in (
            "actual_document_ingestion_status",
            "actual_target_document_hit_count",
        ):
            value = item[field_name]
            if field_name.endswith("status"):
                if value is not None:
                    _string(value, f"{location}.{field_name}", safe_id=True)
            elif value is not None:
                _integer(value, f"{location}.{field_name}")
        recomputed = (
            actual_decision in expected_outcome["allowed_final_decisions"]
            and actual_reason in expected_outcome["allowed_stop_reasons"]
        )
        if item["correct"] is not recomputed:
            _fail("stored_correct_mismatch", f"{location}.correct disagrees with recomputation")
    else:
        expected_category = "case_timeout" if status == "timeout" else "case_execution_error"
        if item["error_category"] != expected_category or item["correct"] is not False:
            _fail("case_status", f"{location} failure classification is inconsistent")
        nullable_actuals = (
            "actual_final_decision",
            "actual_stop_reason",
            "actual_provider_called",
            "actual_retrieved_count",
            "actual_accepted_context_count",
            "actual_rejected_context_count",
            "actual_redaction_count",
            "actual_document_ingestion_status",
            "actual_target_document_hit_count",
        )
        if any(item[field_name] is not None for field_name in nullable_actuals):
            _fail("case_status", f"{location} failure record contains an actual outcome")
        if item["actual_dlp_finding_categories"] or item["stage_results"]:
            _fail("case_status", f"{location} failure record contains runtime telemetry")
    return item


def _validate_result(
    verified: VerifiedInput,
    *,
    request: AnalysisRequest | None = None,
    repository: runner.RepositoryState,
    manifest_identity: runner.ManifestIdentity,
    benchmark: runner.LoadedBenchmark,
    expected_split: str | None = None,
) -> None:
    if expected_split is None:
        if request is None:
            _fail("split_mismatch", "an expected split is required to validate a result")
        expected_split = request.split
    holdout = expected_split == runner.HOLDOUT_SPLIT
    expected_result_keys = RESULT_KEYS | frozenset(HOLDOUT_IDENTITY_KEYS) if holdout else RESULT_KEYS
    result = _exact_keys(verified.result, expected_result_keys, "result.json")
    manifest = verified.manifest
    _integer(result["schema_version"], "result.schema_version", minimum=1)
    expected_result_schema = (
        runner.HOLDOUT_RESULT_SCHEMA_VERSION if holdout else runner.RESULT_SCHEMA_VERSION
    )
    if result["schema_version"] != expected_result_schema:
        _fail("result_schema", "result.json schema is unsupported")
    if holdout:
        _validate_holdout_identity_fields(result, "result")
    result_split = _string(result["split"], "result.split", safe_id=True)
    if holdout:
        if result_split != runner.HOLDOUT_SPLIT:
            _fail("split_mismatch", "result split is not the authorized holdout split")
    elif result_split not in runner.SUPPORTED_SPLITS or result_split != expected_split:
        _fail("split_mismatch", "result split does not match the requested supported split")
    config_id = _string(result["config_id"], "result.config_id", safe_id=True)
    if config_id not in runner.CONFIG_REGISTRY:
        _fail("config_identity", "result contains an unknown configuration")
    config = runner.CONFIG_REGISTRY[config_id]
    for field_name in (
        "experiment_id",
        "config_hash",
        "provider_behavior_hash",
        "expected_case_set_sha256",
    ):
        _hash(result[field_name], f"result.{field_name}")
    for field_name in ("run_id", "profile_id", "provider_id"):
        _string(result[field_name], f"result.{field_name}", safe_id=True)
    result_run_status = _string(result["run_status"], "result.run_status", safe_id=True)
    if result_run_status not in {"complete", "partial"}:
        _fail("run_status", "result run_status is unsupported")
    if result["config_hash"] != config.config_hash:
        _fail("config_identity", "result config hash disagrees with the canonical registry")
    if result["profile_id"] != config.profile.profile_id:
        _fail("config_identity", "result profile identity disagrees with the canonical registry")
    if result["guard_profile"] != config.profile_payload:
        _fail("config_identity", "result guard booleans disagree with the canonical registry")

    environment = _exact_keys(result["environment"], ENVIRONMENT_KEYS, "result.environment")
    safety_limits = _exact_keys(result["safety_limits"], SAFETY_LIMIT_KEYS, "result.safety_limits")
    if result["provider_id"] != runner.SUPPORTED_PROVIDER_ID:
        _fail("provider_identity", "only mock provider results may be analyzed")
    common_expected = {
        "git_commit": repository.commit,
        "git_branch": repository.branch,
        "git_dirty": False,
        "benchmark_manifest_sha256": manifest_identity.sha256,
        "benchmark_manifest_status": "final",
        "guard_profile": config.profile.profile_id,
        "provider_id": result["provider_id"],
        "provider_behavior_hash": result["provider_behavior_hash"],
        "repetitions": 2,
        "warmup": 0,
        # The embedded environment block must describe the artifact it lives
        # in, so a holdout result declares the holdout schema here too.
        "result_schema_version": expected_result_schema,
    }
    for field_name, expected in common_expected.items():
        if environment[field_name] != expected:
            _fail("result_identity", f"result.environment.{field_name} is inconsistent")
    _boolean(environment["git_dirty"], "result.environment.git_dirty")
    _integer(environment["repetitions"], "result.environment.repetitions", minimum=1)
    _integer(environment["warmup"], "result.environment.warmup")
    _hash(
        environment["benchmark_manifest_sha256"],
        "result.environment.benchmark_manifest_sha256",
    )
    _hash(
        environment["provider_behavior_hash"],
        "result.environment.provider_behavior_hash",
    )
    for field_name in (
        "git_branch",
        "git_commit",
        "benchmark_manifest_status",
        "guard_profile",
        "provider_id",
    ):
        _string(environment[field_name], f"result.environment.{field_name}", safe_id=True)
    if not _boolean(environment["enable_audit_log"], "result.environment.enable_audit_log"):
        _fail("result_identity", "evaluation audit logging must remain enabled")
    dependencies = environment["dependencies"]
    if not isinstance(dependencies, list) or not all(isinstance(item, str) and item for item in dependencies):
        _fail("dependency_identity", "result dependency inventory is malformed")
    if dependencies != sorted(set(dependencies), key=lambda value: (value.casefold(), value)):
        _fail("dependency_identity", "result dependency inventory is not canonical")
    expected_dependency_hash = runner._sha256_bytes(  # noqa: SLF001
        runner._canonical_json_bytes(dependencies)  # noqa: SLF001
    )
    if environment["dependencies_sha256"] != expected_dependency_hash:
        _fail("dependency_identity", "result dependency hash is inconsistent")
    _hash(environment["dependencies_sha256"], "result.environment.dependencies_sha256")
    for field_name in ("python_version", "platform", "cpu"):
        _string(environment[field_name], f"result.environment.{field_name}")
    for field_name in ("aggregate_context_limit", "provider_output_limit"):
        _integer(environment[field_name], f"result.environment.{field_name}", minimum=1)
    if environment["aggregate_context_limit"] != safety_limits["aggregate_context_limit"]:
        _fail("safety_identity", "aggregate context limits disagree")
    if environment["provider_output_limit"] != safety_limits["provider_output_limit"]:
        _fail("safety_identity", "provider output limits disagree")
    for key, value in safety_limits.items():
        if key in {"temporary_sqlite_required", "network_disabled"}:
            if value is not True:
                _fail("safety_identity", f"{key} must remain enabled")
        elif key == "chunk_overlap_chars":
            _integer(value, f"result.safety_limits.{key}")
        elif key == "case_timeout_seconds":
            if type(value) not in {int, float} or not math.isfinite(value) or value <= 0:
                _fail("safety_identity", "case timeout must be finite and positive")
        else:
            _integer(value, f"result.safety_limits.{key}", minimum=1)

    expected_experiment_id = runner._sha256_bytes(  # noqa: SLF001
        runner._canonical_json_bytes(  # noqa: SLF001
            {
                # Must mirror runner._experiment_id: a holdout experiment binds
                # the holdout result schema, never the ordinary version 2.
                "result_schema_version": expected_result_schema,
                "config_registry_version": runner.CONFIG_REGISTRY_VERSION,
                "config_hashes": {
                    known_id: runner.CONFIG_REGISTRY[known_id].config_hash
                    for known_id in runner.CONFIG_REGISTRY
                },
                "split": result_split,
                "git_commit": environment["git_commit"],
                "benchmark_manifest_sha256": environment["benchmark_manifest_sha256"],
                "provider_id": result["provider_id"],
                "provider_behavior_hash": result["provider_behavior_hash"],
                "safety_limits": dict(safety_limits),
                "dependencies_sha256": environment["dependencies_sha256"],
            }
        )
    )
    if result["experiment_id"] != expected_experiment_id:
        _fail("experiment_identity", "result experiment identity does not match its contract")

    manifest_pairs = {
        "schema_version": (
            runner.HOLDOUT_RESULT_MANIFEST_SCHEMA_VERSION
            if holdout
            else runner.RESULT_MANIFEST_SCHEMA_VERSION
        ),
        "result_schema_version": expected_result_schema,
        "result_sha256": verified.result_sha256,
        "result_size_bytes": verified.result_size_bytes,
        "experiment_id": result["experiment_id"],
        "run_id": result["run_id"],
        "run_status": result["run_status"],
        "config_id": result["config_id"],
        "config_hash": result["config_hash"],
        "profile_id": result["profile_id"],
        "provider_id": result["provider_id"],
        "provider_behavior_hash": result["provider_behavior_hash"],
        "git_commit": environment["git_commit"],
        "benchmark_manifest_sha256": environment["benchmark_manifest_sha256"],
        "expected_case_set_sha256": result["expected_case_set_sha256"],
    }
    for field_name, expected in manifest_pairs.items():
        if manifest[field_name] != expected:
            _fail("manifest_result_mismatch", f"manifest.{field_name} disagrees with result.json")

    expected_ids_by_config, expected_scopes_by_config = runner._expected_case_sets(  # noqa: SLF001
        benchmark, (config_id,)
    )
    expected_ids = expected_ids_by_config[config_id]
    expected_scopes = expected_scopes_by_config[config_id]
    if result["expected_case_count"] != len(expected_ids):
        _fail("case_completeness", "expected case count disagrees with frozen split")
    _integer(result["expected_case_count"], "result.expected_case_count", minimum=1)
    if result["expected_case_set_sha256"] != runner._case_set_hash(expected_ids):  # noqa: SLF001
        _fail("case_completeness", "expected case-set hash disagrees with frozen split")
    scope_table = result["expected_case_sets_by_scope"]
    if not isinstance(scope_table, dict) or set(scope_table) != set(expected_scopes):
        _fail("case_completeness", "scope identity set disagrees with the configuration")
    for scope, case_ids in expected_scopes.items():
        scope_entry = _exact_keys(
            scope_table[scope], frozenset({"count", "sha256"}), f"scope.{scope}"
        )
        if scope_entry != {"count": len(case_ids), "sha256": runner._case_set_hash(case_ids)}:  # noqa: SLF001
            _fail("case_completeness", f"scope identity mismatch: {scope}")

    cases = result["cases"]
    if not isinstance(cases, list) or len(cases) != len(expected_ids):
        _fail("case_completeness", "result case list has an unexpected length")
    cases_by_id = {case["case_id"]: case for case in benchmark.cases}
    seen: set[str] = set()
    validated: list[Mapping[str, Any]] = []
    for ordinal, case_id in enumerate(expected_ids):
        if ordinal >= len(cases) or not isinstance(cases[ordinal], dict):
            _fail("case_completeness", "result case list is malformed")
        record_case_id = _string(
            cases[ordinal].get("case_id"), f"cases[{ordinal}].case_id", safe_id=True
        )
        if record_case_id in seen:
            _fail("duplicate_case", "result contains a duplicate case")
        seen.add(record_case_id)
        validated.append(
            _validate_case_record(
                cases[ordinal],
                ordinal=ordinal,
                expected_case=cases_by_id[case_id],
                expected_label=benchmark.labels_by_id[case_id],
                config=config,
                split=expected_split,
                git_commit=repository.commit,
                benchmark_manifest_sha256=manifest_identity.sha256,
            )
        )
    if tuple(item["case_id"] for item in validated) != expected_ids:
        _fail("case_completeness", "result case ordering or membership changed")

    counts = runner.summarize_case_statuses(validated)
    if result["run_status"] != counts["run_status"]:
        _fail("run_status", "top-level run status disagrees with case statuses")
    for field_name, expected in (
        ("completed_case_count", counts["completed_case_count"]),
        ("error_case_count", counts["error_case_count"]),
        ("timeout_case_count", counts["timeout_case_count"]),
        ("skipped_case_count", 0),
    ):
        _integer(result[field_name], f"result.{field_name}")
        if result[field_name] != expected:
            _fail("run_status", f"{field_name} disagrees with case statuses")
    aggregate = _exact_keys(result["aggregate"], AGGREGATE_KEYS, "result.aggregate")
    _integer(aggregate["n_end_to_end"], "result.aggregate.n_end_to_end")
    if aggregate["n_end_to_end"] != sum(item["evaluation_scope"] == "end_to_end" for item in validated):
        _fail("aggregate_placeholder", "runner aggregate scope count is inconsistent")
    if any(aggregate[key] is not None for key in ("aomr", "fpr", "fnr", "marginal_contribution")):
        _fail("aggregate_placeholder", "runner must not precompute aggregate metrics")
    if aggregate["metrics_computed"] is not False:
        _fail("aggregate_placeholder", "runner metrics_computed must remain false")
    _string(aggregate["note"], "result.aggregate.note")


def _common_identity_projection(result: Mapping[str, Any]) -> dict[str, Any]:
    environment = result["environment"]
    return {
        "schema_version": result["schema_version"],
        "experiment_id": result["experiment_id"],
        "split": result["split"],
        "provider_id": result["provider_id"],
        "provider_behavior_hash": result["provider_behavior_hash"],
        "safety_limits": result["safety_limits"],
        "environment": {
            key: value
            for key, value in environment.items()
            if key != "guard_profile"
        },
    }


def _validate_common_inputs(
    inputs: Sequence[VerifiedInput],
    *,
    request: AnalysisRequest,
    repository: runner.RepositoryState,
    manifest_identity: runner.ManifestIdentity,
) -> tuple[VerifiedInput, ...]:
    by_config: dict[str, VerifiedInput] = {}
    for item in inputs:
        config_id = item.result["config_id"]
        if config_id in by_config:
            _fail("duplicate_config", "multiple manifests claim the same configuration")
        by_config[config_id] = item
    expected_ids = tuple(runner.CONFIG_REGISTRY)
    if set(by_config) != set(expected_ids):
        _fail("config_matrix", "analysis requires exactly one canonical C0-C7 manifest")
    ordered = tuple(by_config[config_id] for config_id in expected_ids)
    baseline = runner._canonical_json_bytes(_common_identity_projection(ordered[0].result))  # noqa: SLF001
    for item in ordered:
        if runner._canonical_json_bytes(_common_identity_projection(item.result)) != baseline:  # noqa: SLF001
            _fail("mixed_identity", "result matrix mixes experiment or environment identities")
        environment = item.result["environment"]
        if environment["git_commit"] != repository.commit or environment["git_branch"] != repository.branch:
            _fail("mixed_identity", "result repository identity differs from the analyzer")
        if environment["benchmark_manifest_sha256"] != manifest_identity.sha256:
            _fail("mixed_identity", "result benchmark identity differs from the current freeze")
        if item.result["split"] != request.split:
            _fail("mixed_identity", "result matrix mixes split identities")
    return ordered


def validate_family_mapping(
    benchmark: runner.LoadedBenchmark,
    *,
    groups: Mapping[str, Sequence[str]] = ANALYSIS_GROUPS,
    non_matrix_families: Sequence[str] = NON_MATRIX_FAMILIES,
) -> None:
    if "data_exfiltration" in groups:
        _fail("mapping_group", "unsupported analysis group name")
    if tuple(groups) != tuple(ANALYSIS_GROUPS):
        _fail("mapping_group", "analysis group registry changed")
    if any(tuple(values) != tuple(sorted(values)) for values in groups.values()):
        _fail("mapping_order", "family lists must be sorted")
    if tuple(non_matrix_families) != tuple(sorted(non_matrix_families)):
        _fail("mapping_order", "non-matrix family list must be sorted")
    if _mapping_payload(groups, non_matrix_families) != _mapping_payload():
        _fail("mapping_drift", "frozen family mapping changed")

    mapped = [family for values in groups.values() for family in values]
    if len(mapped) != 20 or len(mapped) != len(set(mapped)):
        _fail("mapping_overlap", "matrix family mapping has omissions or overlaps")
    all_families = set(mapped) | set(non_matrix_families)
    frozen_families = {case["scenario_family"] for case in benchmark.cases}
    if all_families != frozen_families or len(frozen_families) != 23:
        _fail("mapping_coverage", "mapping does not cover exactly the frozen 23 families")
    scope_by_family: dict[str, set[str]] = {}
    category_by_family: dict[str, set[str]] = {}
    for case in benchmark.cases:
        family = case["scenario_family"]
        scope_by_family.setdefault(family, set()).add(case["evaluation_scope"])
        category_by_family.setdefault(family, set()).add(
            benchmark.labels_by_id[case["case_id"]]["category"]
        )
    if any(scope_by_family[family] != {"end_to_end"} for family in mapped):
        _fail("mapping_scope", "non-end-to-end family entered an analysis group")
    if any("end_to_end" in scope_by_family[family] for family in non_matrix_families):
        _fail("mapping_scope", "end-to-end family was marked non-matrix")
    if any(category_by_family[family] != {"benign"} for family in groups["benign_control"]):
        _fail("mapping_category", "benign_control contains a non-benign family")


def _wilson_interval(numerator: int, denominator: int) -> tuple[float, float]:
    proportion = numerator / denominator
    z2 = WILSON_Z_95**2
    scale = 1.0 + z2 / denominator
    center = (proportion + z2 / (2.0 * denominator)) / scale
    half = (
        WILSON_Z_95
        * math.sqrt(
            proportion * (1.0 - proportion) / denominator
            + z2 / (4.0 * denominator**2)
        )
        / scale
    )
    return max(0.0, center - half), min(1.0, center + half)


def make_rate(numerator: int, denominator: int, *, wilson: bool = False) -> dict[str, Any]:
    _integer(numerator, "rate.numerator")
    _integer(denominator, "rate.denominator")
    if numerator > denominator:
        _fail("rate_counts", "rate numerator cannot exceed denominator")
    defined = denominator > 0
    eligible = denominator >= RATE_REPORTING_MIN_N
    reason = None if eligible else ("zero_denominator" if denominator == 0 else "n_below_10")
    value = numerator / denominator if eligible else None
    wilson_value: dict[str, Any] = {"low": None, "high": None, "eligible": False}
    if eligible and wilson:
        low, high = _wilson_interval(numerator, denominator)
        wilson_value = {"low": low, "high": high, "eligible": True}
    return {
        "numerator": numerator,
        "denominator": denominator,
        "n": denominator,
        "defined": defined,
        "reporting_eligible": eligible,
        "value": value,
        "ineligibility_reason": reason,
        "wilson_95": wilson_value,
    }


def _confusion(records: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = {"TP": 0, "FN": 0, "TN": 0, "FP": 0, "n_M": 0, "n_B": 0}
    for record in records:
        if record["evaluation_scope"] != "end_to_end":
            continue
        category = record["category"]
        correct = record["correct"]
        if category in {"malicious", "mixed"}:
            counts["n_M"] += 1
            counts["TP" if correct else "FN"] += 1
        elif category == "benign":
            counts["n_B"] += 1
            counts["TN" if correct else "FP"] += 1
    return counts


def _metrics_from_records(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    confusion = _confusion(records)
    return {
        "confusion": confusion,
        "aomr": make_rate(confusion["TP"], confusion["n_M"], wilson=True),
        "mismatch_rate": make_rate(confusion["FN"], confusion["n_M"]),
        "fpr": make_rate(confusion["FP"], confusion["n_B"], wilson=True),
    }


def _family_to_group_lookup() -> dict[str, str]:
    return {
        family: group
        for group, families in ANALYSIS_GROUPS.items()
        for family in families
    }


def _build_config_analysis(item: VerifiedInput) -> dict[str, Any]:
    result = item.result
    records = list(result["cases"])
    expected_count = result["expected_case_count"]
    completed = sum(record["case_status"] == "completed" for record in records)
    failures = sum(record["case_status"] in {"error", "timeout"} for record in records)
    overall = _metrics_from_records(records)
    lookup = _family_to_group_lookup()

    by_group: dict[str, Any] = {}
    for group in GROUP_REPORT_ORDER:
        group_records = [record for record in records if record["scenario_family"] in ANALYSIS_GROUPS[group]]
        metrics = _metrics_from_records(group_records)
        by_group[group] = {
            "confusion": metrics["confusion"],
            "aomr": None if group == "benign_control" else metrics["aomr"],
            "fpr": metrics["fpr"] if group == "benign_control" else None,
        }

    families = sorted({record["scenario_family"] for record in records})
    family_rows = []
    for family in families:
        family_records = [record for record in records if record["scenario_family"] == family]
        scopes = {record["evaluation_scope"] for record in family_records}
        if len(scopes) != 1:
            _fail("family_scope", "one family appears in multiple evaluation scopes")
        family_rows.append(
            {
                "scenario_family": family,
                "evaluation_scope": next(iter(scopes)),
                "analysis_group": lookup.get(family),
                "matched": sum(record["correct"] for record in family_records),
                "total": len(family_records),
                "error_count": sum(
                    record["case_status"] in {"error", "timeout"} for record in family_records
                ),
            }
        )
    expected_family_count = 23 if result["config_id"] == "C0_all_on" else 20
    if len(family_rows) != expected_family_count:
        _fail("family_completeness", "configuration family row count is incomplete")

    config_output: dict[str, Any] = {
        "config_hash": result["config_hash"],
        "profile_id": result["profile_id"],
        "run_id": result["run_id"],
        "run_status": result["run_status"],
        "guard_profile": result["guard_profile"],
        "expected_case_count": expected_count,
        "expected_case_set_sha256": result["expected_case_set_sha256"],
        "coverage": make_rate(len(records), expected_count),
        "successful_coverage": make_rate(completed, expected_count),
        "error_rate": make_rate(failures, expected_count),
        **overall,
        "by_analysis_group": by_group,
        "by_family": family_rows,
    }
    if result["config_id"] == "C0_all_on":
        config_output["non_matrix"] = {
            scope: {
                "case_count": len(scope_records),
                "matched": sum(record["correct"] for record in scope_records),
                "error_count": sum(
                    record["case_status"] in {"error", "timeout"} for record in scope_records
                ),
            }
            for scope in ("component", "availability_fault", "residual_risk_only")
            if (scope_records := [record for record in records if record["evaluation_scope"] == scope])
        }
    return config_output


def _build_marginal(configs: Mapping[str, Mapping[str, Any]], inputs: Sequence[VerifiedInput]) -> list[dict[str, Any]]:
    records_by_config = {
        item.result["config_id"]: {
            record["case_id"]: record
            for record in item.result["cases"]
            if record["evaluation_scope"] == "end_to_end"
            and record["category"] in {"malicious", "mixed"}
        }
        for item in inputs
    }
    baseline_id = "C0_all_on"
    baseline = records_by_config[baseline_id]
    rows: list[dict[str, Any]] = []
    for guard, ablated_id, mock_limitation in MARGINAL_DEFINITIONS:
        ablated = records_by_config[ablated_id]
        paired_ids = tuple(sorted(baseline))
        if paired_ids != tuple(sorted(ablated)):
            _fail("marginal_pairing", "marginal configurations do not share the same M cases")
        both_correct = baseline_only = ablated_only = both_incorrect = 0
        for case_id in paired_ids:
            baseline_correct = baseline[case_id]["correct"]
            ablated_correct = ablated[case_id]["correct"]
            if baseline_correct and ablated_correct:
                both_correct += 1
            elif baseline_correct:
                baseline_only += 1
            elif ablated_correct:
                ablated_only += 1
            else:
                both_incorrect += 1
        baseline_rate = configs[baseline_id]["aomr"]
        ablated_rate = configs[ablated_id]["aomr"]
        delta = None
        if baseline_rate["value"] is not None and ablated_rate["value"] is not None:
            delta = baseline_rate["value"] - ablated_rate["value"]
        rows.append(
            {
                "guard": guard,
                "baseline_config_id": baseline_id,
                "ablated_config_id": ablated_id,
                "paired_case_ids_sha256": runner._case_set_hash(paired_ids),  # noqa: SLF001
                "paired_n_M": len(paired_ids),
                "both_correct": both_correct,
                "baseline_only": baseline_only,
                "ablated_only": ablated_only,
                "both_incorrect": both_incorrect,
                "baseline_aomr_numerator": baseline_rate["numerator"],
                "baseline_aomr_denominator": baseline_rate["denominator"],
                "ablated_aomr_numerator": ablated_rate["numerator"],
                "ablated_aomr_denominator": ablated_rate["denominator"],
                "delta_value": delta,
                "non_additivity_caveat": NON_ADDITIVITY_CAVEAT,
                "claim_template": MARGINAL_CLAIM_TEMPLATE,
                "mock_provider_limitation": mock_limitation,
            }
        )
    return rows


def _validate_primary_matrix(inputs: Sequence[VerifiedInput]) -> None:
    partial = [item.result["config_id"] for item in inputs if item.result["run_status"] != "complete"]
    if partial:
        _fail("partial_matrix", "partial runs are diagnostic only and cannot enter primary metrics")


def _build_analysis(
    inputs: Sequence[VerifiedInput],
    *,
    request: AnalysisRequest,
    repository: runner.RepositoryState,
    manifest_identity: runner.ManifestIdentity,
) -> dict[str, Any]:
    configs = {
        item.result["config_id"]: _build_config_analysis(item)
        for item in inputs
    }
    analysis = {
        "schema_version": ANALYSIS_SCHEMA_VERSION,
        "analysis_contract_version": ANALYSIS_CONTRACT_VERSION,
        "analysis_contract_sha256": ANALYSIS_CONTRACT_SHA256,
        "analyzer_commit": repository.commit,
        "split": request.split,
        "experiment_id": inputs[0].result["experiment_id"],
        "benchmark_manifest_sha256": manifest_identity.sha256,
        "mapping_version": MAPPING_VERSION,
        "mapping_sha256": MAPPING_SHA256,
        "rate_reporting_min_n": RATE_REPORTING_MIN_N,
        "wilson_confidence_level": WILSON_CONFIDENCE_LEVEL,
        "wilson_continuity_correction": False,
        "wilson_caveat": WILSON_CAVEAT,
        "input_manifests": [
            {
                "config_id": item.result["config_id"],
                "manifest_path_basename": item.manifest_path.name,
                "manifest_sha256": item.manifest_sha256,
                "result_sha256": item.result_sha256,
                "result_size_bytes": item.result_size_bytes,
                "run_id": item.result["run_id"],
                "run_status": item.result["run_status"],
                "config_hash": item.result["config_hash"],
                "expected_case_set_sha256": item.result["expected_case_set_sha256"],
            }
            for item in inputs
        ],
        "identity": {
            "git_branch": repository.branch,
            "git_commit": repository.commit,
            "git_dirty": False,
            "provider_id": inputs[0].result["provider_id"],
            "provider_behavior_hash": inputs[0].result["provider_behavior_hash"],
            "dependencies_sha256": inputs[0].result["environment"]["dependencies_sha256"],
        },
        "family_to_group": dict(sorted(_family_to_group_lookup().items())),
        "non_matrix_families": list(NON_MATRIX_FAMILIES),
        "leakage_mechanisms_caveat": LEAKAGE_CAVEAT,
        "configs": configs,
        "marginal": _build_marginal(configs, inputs),
        "latency": {
            "protocol": "determinism_repetitions_only",
            "repetitions_observed": 2,
            "warmup_observed": 0,
            "reportable": False,
            "p50": None,
            "p95": None,
            "required_future_gate": "audited_latency_protocol_before_phase_12e_4",
            "note": LATENCY_NOTE,
        },
        "claims_control": {
            "abr_enabled": False,
            "macro_enabled": False,
            "family_rates_enabled": False,
            "tiny_n_rate_suppression_enabled": True,
            "latency_reportable": False,
            "no_p_values": True,
            "no_family_percentages": True,
            "benchmark_comparison_not_causal": True,
            "c4_c5_mock_limitation": True,
            "leakage_not_real_exfiltration": True,
        },
    }
    _validate_generated_analysis(analysis, holdout=request.split == runner.HOLDOUT_SPLIT)
    runner.scan_forbidden_artifact_content(analysis)
    return analysis


def _validate_rate_shape(
    value: Any,
    location: str,
    *,
    wilson_allowed: bool,
) -> None:
    rate = _exact_keys(value, RATE_KEYS, location)
    numerator = _integer(rate["numerator"], f"{location}.numerator")
    denominator = _integer(rate["denominator"], f"{location}.denominator")
    _integer(rate["n"], f"{location}.n")
    if numerator > denominator or rate["n"] != denominator:
        _fail("analysis_shape", f"{location} has inconsistent rate counts")
    defined = _boolean(rate["defined"], f"{location}.defined")
    eligible = _boolean(
        rate["reporting_eligible"], f"{location}.reporting_eligible"
    )
    expected_defined = denominator > 0
    expected_eligible = denominator >= RATE_REPORTING_MIN_N
    expected_reason = (
        None
        if expected_eligible
        else ("zero_denominator" if denominator == 0 else "n_below_10")
    )
    expected_value = numerator / denominator if expected_eligible else None
    if (
        defined is not expected_defined
        or eligible is not expected_eligible
        or rate["ineligibility_reason"] != expected_reason
        or rate["value"] != expected_value
    ):
        _fail("analysis_shape", f"{location} violates the rate-reporting policy")
    wilson = _exact_keys(rate["wilson_95"], WILSON_KEYS, f"{location}.wilson_95")
    wilson_eligible = _boolean(
        wilson["eligible"], f"{location}.wilson_95.eligible"
    )
    expected_wilson = expected_eligible and wilson_allowed
    if wilson_eligible is not expected_wilson:
        _fail("analysis_shape", f"{location} has an inconsistent Wilson status")
    if expected_wilson:
        low = _finite_number(wilson["low"], f"{location}.wilson_95.low")
        high = _finite_number(wilson["high"], f"{location}.wilson_95.high")
        if low is None or high is None or low > high or high > 1.0:
            _fail("analysis_shape", f"{location} has an invalid Wilson interval")
    elif wilson["low"] is not None or wilson["high"] is not None:
        _fail("analysis_shape", f"{location} emitted an ineligible Wilson interval")


def _validate_confusion_shape(value: Any, location: str) -> None:
    confusion = _exact_keys(value, CONFUSION_KEYS, location)
    for key in CONFUSION_KEYS:
        _integer(confusion[key], f"{location}.{key}")
    if (
        confusion["TP"] + confusion["FN"] != confusion["n_M"]
        or confusion["TN"] + confusion["FP"] != confusion["n_B"]
    ):
        _fail("analysis_shape", f"{location} has inconsistent confusion counts")


def _validate_generated_analysis(value: Any, *, holdout: bool = False) -> None:
    analysis = _exact_keys(value, ANALYSIS_KEYS, "analysis")
    static_pairs = {
        "schema_version": ANALYSIS_SCHEMA_VERSION,
        "analysis_contract_version": ANALYSIS_CONTRACT_VERSION,
        "analysis_contract_sha256": ANALYSIS_CONTRACT_SHA256,
        "mapping_version": MAPPING_VERSION,
        "mapping_sha256": MAPPING_SHA256,
        "rate_reporting_min_n": RATE_REPORTING_MIN_N,
        "wilson_confidence_level": WILSON_CONFIDENCE_LEVEL,
        "wilson_continuity_correction": False,
        "wilson_caveat": WILSON_CAVEAT,
        "leakage_mechanisms_caveat": LEAKAGE_CAVEAT,
    }
    for field_name, expected in static_pairs.items():
        if analysis[field_name] != expected:
            _fail("analysis_shape", f"analysis.{field_name} changed")
    _hash(analysis["experiment_id"], "analysis.experiment_id")
    _hash(
        analysis["benchmark_manifest_sha256"],
        "analysis.benchmark_manifest_sha256",
    )
    if not _FULL_SHA_RE.fullmatch(_string(analysis["analyzer_commit"], "analysis.analyzer_commit")):
        _fail("analysis_shape", "analysis.analyzer_commit is not a full SHA-1")
    analysis_split = _string(analysis["split"], "analysis.split", safe_id=True)
    allowed_analysis_splits = (
        (runner.HOLDOUT_SPLIT,) if holdout else runner.SUPPORTED_SPLITS
    )
    if analysis_split not in allowed_analysis_splits:
        _fail("analysis_shape", "analysis.split is unsupported")

    input_manifests = analysis["input_manifests"]
    if not isinstance(input_manifests, list) or len(input_manifests) != len(
        runner.CONFIG_REGISTRY
    ):
        _fail("analysis_shape", "analysis input manifest list is incomplete")
    for expected_config_id, entry in zip(
        runner.CONFIG_REGISTRY, input_manifests, strict=True
    ):
        item = _exact_keys(
            entry,
            INPUT_MANIFEST_ENTRY_KEYS,
            f"analysis.input_manifests.{expected_config_id}",
        )
        if item["config_id"] != expected_config_id or item["manifest_path_basename"] != "result-manifest.json":
            _fail("analysis_shape", "analysis input manifest identity changed")
        for field_name in (
            "manifest_sha256",
            "result_sha256",
            "config_hash",
            "expected_case_set_sha256",
        ):
            _hash(item[field_name], f"analysis.input_manifests.{field_name}")
        _integer(item["result_size_bytes"], "analysis.input_manifests.result_size_bytes", minimum=1)
        _string(item["run_id"], "analysis.input_manifests.run_id", safe_id=True)
        if item["run_status"] != "complete":
            _fail("analysis_shape", "primary analysis contains a partial input")

    identity = _exact_keys(analysis["identity"], ANALYSIS_IDENTITY_KEYS, "analysis.identity")
    _string(identity["git_branch"], "analysis.identity.git_branch", safe_id=True)
    if identity["git_commit"] != analysis["analyzer_commit"] or identity["git_dirty"] is not False:
        _fail("analysis_shape", "analysis repository identity is inconsistent")
    if identity["provider_id"] != runner.SUPPORTED_PROVIDER_ID:
        _fail("analysis_shape", "analysis provider identity is unsupported")
    _hash(identity["provider_behavior_hash"], "analysis.identity.provider_behavior_hash")
    _hash(identity["dependencies_sha256"], "analysis.identity.dependencies_sha256")
    if analysis["family_to_group"] != dict(sorted(_family_to_group_lookup().items())):
        _fail("analysis_shape", "analysis family mapping changed")
    if analysis["non_matrix_families"] != list(NON_MATRIX_FAMILIES):
        _fail("analysis_shape", "analysis non-matrix families changed")

    configs = analysis["configs"]
    if not isinstance(configs, dict) or tuple(configs) != tuple(runner.CONFIG_REGISTRY):
        _fail("analysis_shape", "analysis config matrix is incomplete or unordered")
    for config_id, canonical_config in runner.CONFIG_REGISTRY.items():
        expected_keys = (
            CONFIG_ANALYSIS_KEYS | {"non_matrix"}
            if config_id == "C0_all_on"
            else CONFIG_ANALYSIS_KEYS
        )
        config = _exact_keys(configs[config_id], frozenset(expected_keys), f"analysis.configs.{config_id}")
        if (
            config["config_hash"] != canonical_config.config_hash
            or config["profile_id"] != canonical_config.profile.profile_id
            or config["guard_profile"] != canonical_config.profile_payload
            or config["run_status"] != "complete"
        ):
            _fail("analysis_shape", f"analysis config identity changed: {config_id}")
        _string(config["run_id"], f"analysis.configs.{config_id}.run_id", safe_id=True)
        _integer(config["expected_case_count"], f"analysis.configs.{config_id}.expected_case_count", minimum=1)
        _hash(config["expected_case_set_sha256"], f"analysis.configs.{config_id}.expected_case_set_sha256")
        _validate_rate_shape(config["coverage"], f"analysis.configs.{config_id}.coverage", wilson_allowed=False)
        _validate_rate_shape(
            config["successful_coverage"],
            f"analysis.configs.{config_id}.successful_coverage",
            wilson_allowed=False,
        )
        _validate_rate_shape(config["error_rate"], f"analysis.configs.{config_id}.error_rate", wilson_allowed=False)
        _validate_confusion_shape(config["confusion"], f"analysis.configs.{config_id}.confusion")
        _validate_rate_shape(config["aomr"], f"analysis.configs.{config_id}.aomr", wilson_allowed=True)
        _validate_rate_shape(
            config["mismatch_rate"],
            f"analysis.configs.{config_id}.mismatch_rate",
            wilson_allowed=False,
        )
        _validate_rate_shape(config["fpr"], f"analysis.configs.{config_id}.fpr", wilson_allowed=True)

        by_group = config["by_analysis_group"]
        if not isinstance(by_group, dict) or set(by_group) != set(GROUP_REPORT_ORDER):
            _fail("analysis_shape", f"analysis group set changed: {config_id}")
        for group in GROUP_REPORT_ORDER:
            group_result = _exact_keys(
                by_group[group], GROUP_RESULT_KEYS, f"analysis.configs.{config_id}.{group}"
            )
            _validate_confusion_shape(
                group_result["confusion"], f"analysis.configs.{config_id}.{group}.confusion"
            )
            if group == "benign_control":
                if group_result["aomr"] is not None:
                    _fail("analysis_shape", "benign_control must not emit AOMR")
                _validate_rate_shape(
                    group_result["fpr"],
                    f"analysis.configs.{config_id}.{group}.fpr",
                    wilson_allowed=True,
                )
            else:
                if group_result["fpr"] is not None:
                    _fail("analysis_shape", f"{group} must not emit FPR")
                _validate_rate_shape(
                    group_result["aomr"],
                    f"analysis.configs.{config_id}.{group}.aomr",
                    wilson_allowed=True,
                )

        family_rows = config["by_family"]
        expected_family_count = 23 if config_id == "C0_all_on" else 20
        if not isinstance(family_rows, list) or len(family_rows) != expected_family_count:
            _fail("analysis_shape", f"analysis family count changed: {config_id}")
        family_names: list[str] = []
        for index, row in enumerate(family_rows):
            family = _exact_keys(
                row, FAMILY_ROW_KEYS, f"analysis.configs.{config_id}.by_family[{index}]"
            )
            family_name = _string(
                family["scenario_family"],
                f"analysis.configs.{config_id}.by_family[{index}].scenario_family",
                safe_id=True,
            )
            family_names.append(family_name)
            if family["analysis_group"] != _family_to_group_lookup().get(family_name):
                _fail("analysis_shape", f"analysis family group changed: {family_name}")
            for count_name in ("matched", "total", "error_count"):
                _integer(family[count_name], f"analysis.family.{family_name}.{count_name}")
            if family["matched"] > family["total"] or family["error_count"] > family["total"]:
                _fail("analysis_shape", f"analysis family counts are inconsistent: {family_name}")
        if family_names != sorted(family_names) or len(family_names) != len(set(family_names)):
            _fail("analysis_shape", f"analysis family order changed: {config_id}")

        if config_id == "C0_all_on":
            non_matrix = _exact_keys(
                config["non_matrix"], NON_MATRIX_SCOPE_KEYS, "analysis.configs.C0_all_on.non_matrix"
            )
            for scope, scope_value in non_matrix.items():
                entry = _exact_keys(
                    scope_value,
                    NON_MATRIX_RESULT_KEYS,
                    f"analysis.configs.C0_all_on.non_matrix.{scope}",
                )
                for field_name in NON_MATRIX_RESULT_KEYS:
                    _integer(entry[field_name], f"analysis.non_matrix.{scope}.{field_name}")

    marginal_rows = analysis["marginal"]
    if not isinstance(marginal_rows, list) or len(marginal_rows) != len(MARGINAL_DEFINITIONS):
        _fail("analysis_shape", "analysis marginal list is incomplete")
    for definition, row in zip(MARGINAL_DEFINITIONS, marginal_rows, strict=True):
        guard, ablated_id, mock_limitation = definition
        marginal = _exact_keys(row, MARGINAL_KEYS, f"analysis.marginal.{guard}")
        if (
            marginal["guard"] != guard
            or marginal["baseline_config_id"] != "C0_all_on"
            or marginal["ablated_config_id"] != ablated_id
            or marginal["non_additivity_caveat"] != NON_ADDITIVITY_CAVEAT
            or marginal["claim_template"] != MARGINAL_CLAIM_TEMPLATE
            or marginal["mock_provider_limitation"] is not mock_limitation
        ):
            _fail("analysis_shape", f"analysis marginal identity changed: {guard}")
        _hash(marginal["paired_case_ids_sha256"], f"analysis.marginal.{guard}.paired_case_ids_sha256")
        for field_name in (
            "paired_n_M",
            "both_correct",
            "baseline_only",
            "ablated_only",
            "both_incorrect",
            "baseline_aomr_numerator",
            "baseline_aomr_denominator",
            "ablated_aomr_numerator",
            "ablated_aomr_denominator",
        ):
            _integer(marginal[field_name], f"analysis.marginal.{guard}.{field_name}")
        if sum(
            marginal[field_name]
            for field_name in ("both_correct", "baseline_only", "ablated_only", "both_incorrect")
        ) != marginal["paired_n_M"]:
            _fail("analysis_shape", f"analysis marginal pairs are inconsistent: {guard}")
        if marginal["delta_value"] is not None:
            _finite_signed_number(
                marginal["delta_value"], f"analysis.marginal.{guard}.delta_value"
            )

    latency = _exact_keys(analysis["latency"], LATENCY_KEYS, "analysis.latency")
    if latency != {
        "protocol": "determinism_repetitions_only",
        "repetitions_observed": 2,
        "warmup_observed": 0,
        "reportable": False,
        "p50": None,
        "p95": None,
        "required_future_gate": "audited_latency_protocol_before_phase_12e_4",
        "note": LATENCY_NOTE,
    }:
        _fail("analysis_shape", "analysis latency policy changed")
    claims = _exact_keys(
        analysis["claims_control"], CLAIMS_CONTROL_KEYS, "analysis.claims_control"
    )
    if claims != {
        "abr_enabled": False,
        "macro_enabled": False,
        "family_rates_enabled": False,
        "tiny_n_rate_suppression_enabled": True,
        "latency_reportable": False,
        "no_p_values": True,
        "no_family_percentages": True,
        "benchmark_comparison_not_causal": True,
        "c4_c5_mock_limitation": True,
        "leakage_not_real_exfiltration": True,
    }:
        _fail("analysis_shape", "analysis claims controls changed")


def _csv_boolean(value: bool | None) -> str:
    if value is None:
        return ""
    return "true" if value else "false"


def _csv_number(value: Any) -> str:
    if value is None:
        return ""
    if type(value) is float:
        if not math.isfinite(value):
            _fail("csv_value", "CSV contains a non-finite value")
        return f"{value:.6f}"
    return str(value)


def _blank_csv_row(split: str, experiment_id: str) -> dict[str, str]:
    row = {field: "" for field in CSV_FIELDS}
    row["split"] = split
    row["experiment_id"] = experiment_id
    return row


def _set_confusion(row: dict[str, str], confusion: Mapping[str, int]) -> None:
    for key in CONFUSION_KEYS:
        row[key] = str(confusion[key])


def _set_rate(row: dict[str, str], prefix: str, rate: Mapping[str, Any] | None) -> None:
    if rate is None:
        return
    row[f"{prefix}_numerator"] = str(rate["numerator"])
    row[f"{prefix}_denominator"] = str(rate["denominator"])
    row[f"{prefix}_defined"] = _csv_boolean(rate["defined"])
    row[f"{prefix}_reporting_eligible"] = _csv_boolean(rate["reporting_eligible"])
    row[f"{prefix}_value"] = _csv_number(rate["value"])
    row[f"{prefix}_ineligibility_reason"] = rate["ineligibility_reason"] or ""


def _build_csv(analysis: Mapping[str, Any]) -> bytes:
    rows: list[dict[str, str]] = []
    split = analysis["split"]
    experiment_id = analysis["experiment_id"]
    for config_id in runner.CONFIG_REGISTRY:
        config = analysis["configs"][config_id]
        overall = _blank_csv_row(split, experiment_id)
        overall.update({"config_id": config_id, "metric_scope": "overall", "scope_id": "end_to_end"})
        _set_confusion(overall, config["confusion"])
        _set_rate(overall, "aomr", config["aomr"])
        _set_rate(overall, "mismatch", config["mismatch_rate"])
        _set_rate(overall, "fpr", config["fpr"])
        overall["wilson_aomr_low"] = _csv_number(config["aomr"]["wilson_95"]["low"])
        overall["wilson_aomr_high"] = _csv_number(config["aomr"]["wilson_95"]["high"])
        overall["wilson_aomr_eligible"] = _csv_boolean(config["aomr"]["wilson_95"]["eligible"])
        overall["wilson_fpr_low"] = _csv_number(config["fpr"]["wilson_95"]["low"])
        overall["wilson_fpr_high"] = _csv_number(config["fpr"]["wilson_95"]["high"])
        overall["wilson_fpr_eligible"] = _csv_boolean(config["fpr"]["wilson_95"]["eligible"])
        overall["coverage_value"] = _csv_number(config["coverage"]["value"])
        overall["successful_coverage_value"] = _csv_number(config["successful_coverage"]["value"])
        overall["error_rate_value"] = _csv_number(config["error_rate"]["value"])
        rows.append(overall)

        for group in GROUP_REPORT_ORDER:
            group_result = config["by_analysis_group"][group]
            row = _blank_csv_row(split, experiment_id)
            row.update({"config_id": config_id, "metric_scope": "analysis_group", "scope_id": group})
            _set_confusion(row, group_result["confusion"])
            _set_rate(row, "aomr", group_result["aomr"])
            _set_rate(row, "fpr", group_result["fpr"])
            if group_result["aomr"] is not None:
                row["wilson_aomr_low"] = _csv_number(group_result["aomr"]["wilson_95"]["low"])
                row["wilson_aomr_high"] = _csv_number(group_result["aomr"]["wilson_95"]["high"])
                row["wilson_aomr_eligible"] = _csv_boolean(group_result["aomr"]["wilson_95"]["eligible"])
            if group_result["fpr"] is not None:
                row["wilson_fpr_low"] = _csv_number(group_result["fpr"]["wilson_95"]["low"])
                row["wilson_fpr_high"] = _csv_number(group_result["fpr"]["wilson_95"]["high"])
                row["wilson_fpr_eligible"] = _csv_boolean(group_result["fpr"]["wilson_95"]["eligible"])
            rows.append(row)

        for family in config["by_family"]:
            row = _blank_csv_row(split, experiment_id)
            row.update(
                {
                    "config_id": config_id,
                    "metric_scope": "family",
                    "scope_id": family["scenario_family"],
                    "family_matched": str(family["matched"]),
                    "family_total": str(family["total"]),
                    "family_error_count": str(family["error_count"]),
                }
            )
            rows.append(row)

    for marginal in analysis["marginal"]:
        row = _blank_csv_row(split, experiment_id)
        row.update(
            {
                "config_id": marginal["baseline_config_id"],
                "metric_scope": "marginal",
                "scope_id": marginal["guard"],
                "delta_value": _csv_number(marginal["delta_value"]),
                "mock_provider_limitation": _csv_boolean(marginal["mock_provider_limitation"]),
                "baseline_config_id": marginal["baseline_config_id"],
                "ablated_config_id": marginal["ablated_config_id"],
                "paired_case_ids_sha256": marginal["paired_case_ids_sha256"],
                "paired_n_M": str(marginal["paired_n_M"]),
                "both_correct": str(marginal["both_correct"]),
                "baseline_only": str(marginal["baseline_only"]),
                "ablated_only": str(marginal["ablated_only"]),
                "both_incorrect": str(marginal["both_incorrect"]),
                "baseline_aomr_numerator": str(marginal["baseline_aomr_numerator"]),
                "baseline_aomr_denominator": str(marginal["baseline_aomr_denominator"]),
                "ablated_aomr_numerator": str(marginal["ablated_aomr_numerator"]),
                "ablated_aomr_denominator": str(marginal["ablated_aomr_denominator"]),
            }
        )
        rows.append(row)

    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    csv_bytes = output.getvalue().encode("utf-8")
    if b"\r\n" in csv_bytes or csv_bytes.startswith(b"\xef\xbb\xbf"):
        _fail("csv_encoding", "analysis CSV must use UTF-8 LF without BOM")
    return csv_bytes


def _analysis_output_root(
    output_root: Path,
    *,
    repo_root: Path,
    benchmark_root: Path,
    input_directories: Sequence[Path],
) -> Path:
    expanded = output_root.expanduser()
    if ".." in expanded.parts:
        _fail("output_containment", "analysis output path traversal is prohibited")
    resolved = Path(os.path.abspath(expanded)).resolve()
    repo = repo_root.resolve()
    benchmark = benchmark_root.resolve()
    if resolved == repo or runner._is_within(resolved, repo):  # noqa: SLF001
        _fail("output_containment", "analysis output must remain outside the repository")
    if resolved == benchmark or runner._is_within(resolved, benchmark):  # noqa: SLF001
        _fail("output_containment", "analysis output overlaps frozen benchmark input")
    settings = load_settings()
    production_db = Path(settings.retrieval_db_path)
    if not production_db.is_absolute():
        production_db = repo / production_db
    production_db = production_db.resolve()
    if resolved == production_db or runner._is_within(production_db, resolved):  # noqa: SLF001
        _fail("output_containment", "analysis output overlaps production retrieval state")
    for directory in input_directories:
        input_root = directory.resolve()
        if (
            resolved == input_root
            or runner._is_within(resolved, input_root)  # noqa: SLF001
            or runner._is_within(input_root, resolved)  # noqa: SLF001
        ):
            _fail("output_containment", "analysis output overlaps an input result tree")
    if resolved.exists():
        _fail("analysis_exists", "analysis destination already exists; overwrite refused")
    if _contains_symlink(resolved.parent):
        _fail("output_containment", "analysis output parent may not traverse a symlink")
    return resolved


def _build_analysis_manifest(
    analysis_bytes: bytes,
    table_bytes: bytes,
    analysis: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": ANALYSIS_MANIFEST_SCHEMA_VERSION,
        "analysis_file": "analysis.json",
        "analysis_sha256": hashlib.sha256(analysis_bytes).hexdigest(),
        "analysis_size_bytes": len(analysis_bytes),
        "table_file": "analysis-table.csv",
        "table_sha256": hashlib.sha256(table_bytes).hexdigest(),
        "table_size_bytes": len(table_bytes),
        "analysis_schema_version": ANALYSIS_SCHEMA_VERSION,
        "analysis_contract_sha256": ANALYSIS_CONTRACT_SHA256,
        "mapping_version": MAPPING_VERSION,
        "mapping_sha256": MAPPING_SHA256,
        "split": analysis["split"],
        "experiment_id": analysis["experiment_id"],
        "analyzer_commit": analysis["analyzer_commit"],
        "benchmark_manifest_sha256": analysis["benchmark_manifest_sha256"],
        "rate_reporting_min_n": RATE_REPORTING_MIN_N,
        "abr_enabled": False,
        "macro_metrics_enabled": False,
        "latency_reportable": False,
        "input_manifest_sha256_list": [
            {
                "config_id": item["config_id"],
                "run_id": item["run_id"],
                "run_status": item["run_status"],
                "config_hash": item["config_hash"],
                "manifest_sha256": item["manifest_sha256"],
                "result_sha256": item["result_sha256"],
            }
            for item in analysis["input_manifests"]
        ],
    }


def _validate_analysis_manifest(
    value: Any,
    *,
    analysis_bytes: bytes,
    table_bytes: bytes,
    analysis: Mapping[str, Any],
) -> None:
    manifest = _exact_keys(value, ANALYSIS_MANIFEST_KEYS, "analysis-manifest")
    expected_pairs = {
        "schema_version": ANALYSIS_MANIFEST_SCHEMA_VERSION,
        "analysis_file": "analysis.json",
        "analysis_sha256": hashlib.sha256(analysis_bytes).hexdigest(),
        "analysis_size_bytes": len(analysis_bytes),
        "table_file": "analysis-table.csv",
        "table_sha256": hashlib.sha256(table_bytes).hexdigest(),
        "table_size_bytes": len(table_bytes),
        "analysis_schema_version": ANALYSIS_SCHEMA_VERSION,
        "analysis_contract_sha256": ANALYSIS_CONTRACT_SHA256,
        "mapping_version": MAPPING_VERSION,
        "mapping_sha256": MAPPING_SHA256,
        "split": analysis["split"],
        "experiment_id": analysis["experiment_id"],
        "analyzer_commit": analysis["analyzer_commit"],
        "benchmark_manifest_sha256": analysis["benchmark_manifest_sha256"],
        "rate_reporting_min_n": RATE_REPORTING_MIN_N,
        "abr_enabled": False,
        "macro_metrics_enabled": False,
        "latency_reportable": False,
    }
    for field_name, expected in expected_pairs.items():
        if manifest[field_name] != expected:
            _fail("analysis_manifest", f"analysis-manifest.{field_name} is inconsistent")
    inputs = manifest["input_manifest_sha256_list"]
    if not isinstance(inputs, list) or len(inputs) != len(runner.CONFIG_REGISTRY):
        _fail("analysis_manifest", "analysis manifest input list is incomplete")
    for expected_config_id, item in zip(runner.CONFIG_REGISTRY, inputs, strict=True):
        entry = _exact_keys(
            item,
            ANALYSIS_MANIFEST_INPUT_KEYS,
            f"analysis-manifest.inputs.{expected_config_id}",
        )
        source = next(
            source
            for source in analysis["input_manifests"]
            if source["config_id"] == expected_config_id
        )
        expected_entry = {
            "config_id": expected_config_id,
            "run_id": source["run_id"],
            "run_status": source["run_status"],
            "config_hash": source["config_hash"],
            "manifest_sha256": source["manifest_sha256"],
            "result_sha256": source["result_sha256"],
        }
        if entry != expected_entry:
            _fail("analysis_manifest", "analysis manifest input identity changed")


def _publish_directory_atomically(staging_directory: Path, final_directory: Path) -> None:
    os.rename(staging_directory, final_directory)


def _remove_staging_best_effort(staging_directory: Path) -> None:
    try:
        shutil.rmtree(staging_directory)
    except (FileNotFoundError, OSError):
        pass


def _publish_analysis(output_root: Path, analysis: Mapping[str, Any], table_bytes: bytes) -> WrittenAnalysis:
    runner.scan_forbidden_artifact_content(analysis)
    analysis_bytes = runner._canonical_json_bytes(analysis)  # noqa: SLF001
    manifest = _build_analysis_manifest(analysis_bytes, table_bytes, analysis)
    _validate_analysis_manifest(
        manifest,
        analysis_bytes=analysis_bytes,
        table_bytes=table_bytes,
        analysis=analysis,
    )
    runner.scan_forbidden_artifact_content(manifest)
    manifest_bytes = runner._canonical_json_bytes(manifest)  # noqa: SLF001

    if output_root.exists():
        _fail("analysis_exists", "analysis destination already exists; overwrite refused")
    output_root.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".tmp-analysis-", dir=output_root.parent))
    try:
        payloads = (
            (staging / "analysis.json", analysis_bytes),
            (staging / "analysis-table.csv", table_bytes),
            (staging / "analysis-manifest.json", manifest_bytes),
        )
        for path, payload in payloads:
            with path.open("xb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        for path, payload in payloads:
            if path.read_bytes() != payload:
                _fail("analysis_write_integrity", "staged analysis bytes changed before publish")
        parsed_analysis = _strict_json((staging / "analysis.json").read_bytes(), "analysis.json")
        parsed_manifest = _strict_json(
            (staging / "analysis-manifest.json").read_bytes(),
            "analysis-manifest.json",
        )
        _validate_generated_analysis(parsed_analysis)
        _validate_analysis_manifest(
            parsed_manifest,
            analysis_bytes=analysis_bytes,
            table_bytes=table_bytes,
            analysis=parsed_analysis,
        )
        runner.scan_forbidden_artifact_content(parsed_analysis)
        runner.scan_forbidden_artifact_content(parsed_manifest)
        if output_root.exists():
            _fail("analysis_exists", "analysis destination appeared before publish")
        _publish_directory_atomically(staging, output_root)
    except Exception:
        try:
            _remove_staging_best_effort(staging)
        except Exception:
            pass
        raise
    return WrittenAnalysis(
        output_directory=output_root,
        analysis_path=output_root / "analysis.json",
        table_path=output_root / "analysis-table.csv",
        manifest_path=output_root / "analysis-manifest.json",
    )


def _validate_request(request: AnalysisRequest) -> None:
    if request.split not in runner.SUPPORTED_SPLITS:
        _fail("split_not_allowed", "analysis split must be development or validation; holdout is prohibited")
    if not _SAFE_ID_RE.fullmatch(request.expected_branch):
        _fail("expected_branch", "expected branch contains unsupported characters")
    if not _FULL_SHA_RE.fullmatch(request.expected_commit):
        _fail("expected_commit", "expected commit must be a full lowercase SHA-1")
    if len(request.result_manifests) != len(runner.CONFIG_REGISTRY):
        _fail("manifest_count", "exactly eight explicit result manifests are required")
    if len({str(path) for path in request.result_manifests}) != len(request.result_manifests):
        _fail("manifest_count", "duplicate result manifest arguments are prohibited")


def analyze_results(
    request: AnalysisRequest,
    *,
    repo_root: Path = ROOT,
    benchmark_root: Path | None = None,
    hooks: AnalyzerHooks | None = None,
) -> WrittenAnalysis:
    _validate_request(request)
    active_hooks = hooks or AnalyzerHooks()
    repository = active_hooks.repository_state_loader(repo_root)
    if repository.branch != request.expected_branch:
        _fail("branch_mismatch", "repository branch does not match the expected identity")
    if repository.commit != request.expected_commit:
        _fail("commit_mismatch", "repository commit does not match the expected identity")
    if repository.dirty:
        _fail("git_dirty", "working tree must be clean before analysis")

    benchmark_path = (benchmark_root or repo_root / "datasets" / "v2").resolve()
    manifest_identity = runner.verify_frozen_manifest(benchmark_path)
    runner.validate_config_registry(runner.CONFIG_REGISTRY)
    inputs = tuple(_read_verified_input(path) for path in request.result_manifests)
    resolved_paths = [item.manifest_path for item in inputs]
    if len(set(resolved_paths)) != len(resolved_paths):
        _fail("manifest_count", "multiple arguments resolve to the same result manifest")
    benchmark = runner.load_split_benchmark(benchmark_path, request.split)
    for item in inputs:
        _validate_result(
            item,
            request=request,
            repository=repository,
            manifest_identity=manifest_identity,
            benchmark=benchmark,
        )
    ordered = _validate_common_inputs(
        inputs,
        request=request,
        repository=repository,
        manifest_identity=manifest_identity,
    )
    validate_family_mapping(benchmark)
    _validate_primary_matrix(ordered)
    output_root = _analysis_output_root(
        request.output_root,
        repo_root=repo_root,
        benchmark_root=benchmark_path,
        input_directories=[item.manifest_path.parent for item in ordered],
    )
    analysis = _build_analysis(
        ordered,
        request=request,
        repository=repository,
        manifest_identity=manifest_identity,
    )
    table_bytes = _build_csv(analysis)
    return _publish_analysis(output_root, analysis, table_bytes)


def _verify_holdout_analysis_authorization(
    request: HoldoutAnalysisRequest,
    *,
    repo_root: Path,
    benchmark_root: Path,
    hooks: AnalyzerHooks,
) -> tuple[runner.HoldoutAuthorization, runner.VerifiedHoldoutAuthorization, Path]:
    """Independently re-verify the authorization. Never trusts runner artifacts.

    The analyzer parses the external canonical file itself and recomputes every
    identity, so a tampered or absent authorization cannot be compensated for by
    a hash a runner artifact happens to carry.
    """
    # Parsing enforces canonical bytes AND external-path containment.
    authorization = runner.parse_holdout_authorization(
        request.authorization_path, repo_root=repo_root, benchmark_root=benchmark_root
    )

    # One shared verifier performs repository identity, every contract/schema/
    # mapping gate and the FINAL manifest check, then mints a genuine
    # capability through the runner's closure-private registrar. The analyzer
    # re-derives all of this itself and never trusts a runner artifact hash.
    try:
        capability = runner.verify_holdout_authorization_for_analysis(
            authorization,
            attempt_root=Path(authorization.output_root),
            repo_root=repo_root,
            benchmark_root=benchmark_root,
            hooks=runner.RunnerHooks(repository_state_loader=hooks.repository_state_loader),
            analysis_contract_sha256=ANALYSIS_CONTRACT_SHA256,
            mapping_sha256=MAPPING_SHA256,
        )
    except runner.RunnerError as exc:
        _fail(exc.code, str(exc))

    attempt_root = capability.attempt_root
    receipt_path = attempt_root / "start-receipt.json"
    if receipt_path.is_symlink() or not receipt_path.is_file():
        _fail("attempt_root", "authorized attempt root has no regular start receipt")
    receipt = _strict_json(receipt_path.read_bytes(), "start-receipt.json")
    try:
        runner.verify_start_receipt(
            receipt,
            authorization,
            repository=capability.repository,
            manifest=capability.manifest,
        )
    except runner.RunnerError as exc:
        _fail(exc.code, str(exc))

    return authorization, capability, attempt_root


def _validate_holdout_matrix(
    inputs: Sequence[VerifiedInput],
    *,
    authorization: runner.HoldoutAuthorization,
) -> tuple[VerifiedInput, ...]:
    """Require exactly one complete C0-C7 attempt under one authorization."""
    if len(inputs) != len(runner.CONFIG_REGISTRY):
        _fail("manifest_count", "exactly eight holdout result manifests are required")

    by_config: dict[str, VerifiedInput] = {}
    for item in inputs:
        config_id = item.manifest["config_id"]
        if config_id not in runner.CONFIG_REGISTRY:
            _fail("config_identity", "holdout matrix contains an unknown configuration")
        if config_id in by_config:
            _fail("config_identity", "holdout matrix contains a duplicate configuration")
        by_config[config_id] = item
    missing = [config_id for config_id in runner.CONFIG_REGISTRY if config_id not in by_config]
    if missing:
        _fail("config_identity", "holdout matrix is missing one or more approved configurations")

    for item in inputs:
        manifest = item.manifest
        result = item.result
        if manifest["run_status"] != "complete" or result["run_status"] != "complete":
            _fail("run_status", "every holdout run must be complete; partial matrices are rejected")
        if manifest["authorization_id"] != authorization.authorization_id:
            _fail("authorization_mismatch", "holdout matrix mixes authorization identities")
        if manifest["holdout_authorization_sha256"] != authorization.authorization_sha256:
            _fail("authorization_mismatch", "holdout matrix mixes authorization hashes")
        if manifest["attempt"] != authorization.attempt:
            _fail("attempt_mismatch", "holdout matrix mixes attempts")
        if (
            manifest["supersedes_authorization_sha256"]
            != authorization.supersedes_authorization_sha256
        ):
            _fail("attempt_mismatch", "holdout matrix mixes supersedes lineage")
        if manifest["git_commit"] != authorization.execution_commit:
            _fail("commit_mismatch", "holdout matrix mixes implementation commits")
        if manifest["provider_id"] != runner.SUPPORTED_PROVIDER_ID:
            _fail("provider_identity", "holdout matrix contains a non-mock provider result")
        if manifest["benchmark_manifest_sha256"] != authorization.benchmark_manifest_sha256:
            _fail("benchmark_manifest", "holdout matrix mixes benchmark identities")
        expected_hash = runner.CONFIG_REGISTRY[manifest["config_id"]].config_hash
        if manifest["config_hash"] != authorization.config_hashes[manifest["config_id"]]:
            _fail("config_identity", "holdout result config hash disagrees with the authorization")
        if manifest["config_hash"] != expected_hash:
            _fail("config_identity", "holdout result config hash disagrees with the registry")

    behavior_hashes = {item.manifest["provider_behavior_hash"] for item in inputs}
    if len(behavior_hashes) != 1:
        _fail("provider_identity", "holdout matrix mixes provider behavior identities")
    experiment_ids = {item.manifest["experiment_id"] for item in inputs}
    if len(experiment_ids) != 1:
        _fail("experiment_identity", "holdout matrix mixes experiment identities")

    # Benchmark-independent expected-case-set shape. C0 covers all four
    # evaluation scopes while C1-C7 cover end_to_end only, so C0's case-set hash
    # must differ from the single hash the other seven share. This catches a
    # uniformly rewritten expected_case_set_sha256 without reading any record;
    # the hash VALUE itself is verified against the benchmark in Stage B.
    ordered_configs = list(runner.CONFIG_REGISTRY)
    case_set_by_config = {
        item.manifest["config_id"]: item.manifest["expected_case_set_sha256"] for item in inputs
    }
    ablated = {case_set_by_config[config_id] for config_id in ordered_configs[1:]}
    if len(ablated) != 1:
        _fail("case_completeness", "ablated holdout configurations disagree on the expected case set")
    if case_set_by_config[ordered_configs[0]] in ablated:
        _fail(
            "case_completeness",
            "C0 expected-case set must differ from the ablated configurations",
        )

    return tuple(by_config[config_id] for config_id in runner.CONFIG_REGISTRY)


def analyze_holdout_results(
    request: HoldoutAnalysisRequest,
    *,
    repo_root: Path = ROOT,
    benchmark_root: Path | None = None,
    hooks: AnalyzerHooks | None = None,
) -> WrittenAnalysis:
    """Analyze exactly one authorized, complete C0-C7 holdout attempt.

    Gate order: authorization is parsed and independently verified, then the
    frozen manifest bytes, then every result manifest and result identity, then
    the full-matrix cross-checks. Only after all of those pass are frozen
    holdout records loaded through the dedicated authorized loader.
    """
    active_hooks = hooks or AnalyzerHooks()
    benchmark_path = (benchmark_root or repo_root / "datasets" / "v2").resolve()

    if len(request.result_manifests) != len(runner.CONFIG_REGISTRY):
        _fail("manifest_count", "exactly eight holdout result manifests are required")
    if len({str(path) for path in request.result_manifests}) != len(request.result_manifests):
        _fail("manifest_count", "duplicate result manifest arguments are prohibited")

    # ---- STAGE A: everything verifiable WITHOUT frozen holdout records -----
    authorization, capability, attempt_root = _verify_holdout_analysis_authorization(
        request,
        repo_root=repo_root,
        benchmark_root=benchmark_path,
        hooks=active_hooks,
    )
    repository = capability.repository
    manifest_identity = capability.manifest

    inputs = tuple(_read_verified_input(path, holdout=True) for path in request.result_manifests)
    resolved_paths = [item.manifest_path for item in inputs]
    if len(set(resolved_paths)) != len(resolved_paths):
        _fail("manifest_count", "multiple arguments resolve to the same result manifest")
    for item in inputs:
        if not runner._is_within(item.manifest_path, attempt_root):  # noqa: SLF001
            _fail("attempt_root", "result manifest lies outside the authorized attempt root")

    # Per-result identity that needs no benchmark record. Codex finding: these
    # ran only AFTER the holdout split had already been loaded.
    for item in inputs:
        _validate_holdout_result_identity(
            item, authorization=authorization, repository=repository, manifest=manifest_identity
        )
    ordered = _validate_holdout_matrix(inputs, authorization=authorization)

    output_root = attempt_root / "analysis"
    if output_root.exists():
        _fail("analysis_exists", "authorized attempt root already contains an analysis directory")

    # ---- STAGE B: only now may frozen holdout records be read --------------
    benchmark = _load_authorized_holdout_benchmark_for_analysis(
        capability, benchmark_root=benchmark_path, repo_root=repo_root
    )

    for item in ordered:
        _validate_result(
            item,
            repository=repository,
            manifest_identity=manifest_identity,
            benchmark=benchmark,
            expected_split=runner.HOLDOUT_SPLIT,
        )
    validate_family_mapping(benchmark)
    _validate_primary_matrix(ordered)

    analysis = _build_analysis(
        ordered,
        request=_holdout_analysis_shim(authorization, output_root),
        repository=repository,
        manifest_identity=manifest_identity,
    )
    analysis["schema_version"] = HOLDOUT_ANALYSIS_SCHEMA_VERSION
    analysis["split"] = runner.HOLDOUT_SPLIT
    for key in HOLDOUT_IDENTITY_KEYS:
        analysis[key] = _holdout_identity_value(authorization, key)
    validate_holdout_analysis_document(analysis, authorization=authorization)
    _assert_no_authorization_disclosure(analysis, authorization, attempt_root)

    table_bytes = _build_csv(analysis)
    return _publish_holdout_analysis(output_root, analysis, table_bytes, authorization, attempt_root)


def _validate_holdout_result_identity(
    verified: VerifiedInput,
    *,
    authorization: runner.HoldoutAuthorization,
    repository: runner.RepositoryState,
    manifest: runner.ManifestIdentity,
) -> None:
    """Stage A per-result identity. Reads no benchmark record."""
    result = verified.result
    location = "result.json"
    for payload, where in ((verified.manifest, "manifest"), (result, "result")):
        if payload.get("authorization_id") != authorization.authorization_id:
            _fail("authorization_mismatch", f"{where} authorization id does not match")
        if payload.get("holdout_authorization_sha256") != authorization.authorization_sha256:
            _fail("authorization_mismatch", f"{where} authorization hash does not match")
        if payload.get("attempt") != authorization.attempt:
            _fail("attempt_mismatch", f"{where} attempt does not match the authorization")
        if payload.get("supersedes_authorization_sha256") != (
            authorization.supersedes_authorization_sha256
        ):
            _fail("attempt_mismatch", f"{where} supersedes lineage does not match")
        if payload.get("holdout_authorized") is not True:
            _fail("holdout_identity", f"{where} holdout_authorized must be boolean true")

    if result.get("split") != runner.HOLDOUT_SPLIT:
        _fail("split_mismatch", f"{location} split is not the authorized holdout split")
    if result.get("run_status") != "complete" or verified.manifest.get("run_status") != "complete":
        _fail("run_status", "every holdout run must be complete; partial matrices are rejected")
    if result.get("schema_version") != runner.HOLDOUT_RESULT_SCHEMA_VERSION:
        _fail("result_schema", f"{location} schema is not the holdout result schema")
    if verified.manifest.get("schema_version") != runner.HOLDOUT_RESULT_MANIFEST_SCHEMA_VERSION:
        _fail("manifest_schema", "manifest schema is not the holdout result-manifest schema")

    environment = result.get("environment")
    if not isinstance(environment, dict):
        _fail("result_identity", f"{location}.environment is missing")
    if environment.get("result_schema_version") != runner.HOLDOUT_RESULT_SCHEMA_VERSION:
        _fail("result_identity", f"{location}.environment.result_schema_version is inconsistent")
    if environment.get("git_branch") != repository.branch:
        _fail("branch_mismatch", f"{location} branch does not match the verified repository")
    if environment.get("git_commit") != repository.commit:
        _fail("commit_mismatch", f"{location} commit does not match the verified repository")
    if environment.get("git_dirty") is not False:
        _fail("git_dirty", f"{location} was produced from a dirty tree")
    if environment.get("benchmark_manifest_sha256") != manifest.sha256:
        _fail("benchmark_manifest", f"{location} benchmark identity does not match")

    if result.get("provider_id") != runner.SUPPORTED_PROVIDER_ID:
        _fail("provider_identity", f"{location} is not a mock-provider result")
    config_id = result.get("config_id")
    if config_id not in runner.CONFIG_REGISTRY:
        _fail("config_identity", f"{location} contains an unknown configuration")
    config = runner.CONFIG_REGISTRY[config_id]
    if result.get("config_hash") != authorization.config_hashes.get(config_id):
        _fail("config_identity", f"{location} config hash disagrees with the authorization")
    if result.get("config_hash") != config.config_hash:
        _fail("config_identity", f"{location} config hash disagrees with the canonical registry")

    # ---- Codex finding: these were previously deferred to the POST-loader
    # _validate_result path, so a mutated provider_behavior_hash or
    # experiment_id still caused the frozen holdout split to be read. They are
    # all benchmark-independent and now run in Stage A.
    if result.get("profile_id") != config.profile.profile_id:
        _fail("config_identity", f"{location} profile identity disagrees with the registry")
    if result.get("guard_profile") != config.profile_payload:
        _fail("config_identity", f"{location} guard booleans disagree with the registry")

    expected_behavior_hash = _expected_provider_behavior_hash()
    if result.get("provider_behavior_hash") != expected_behavior_hash:
        _fail("provider_identity", f"{location} provider behavior hash does not match the mock provider")
    if environment.get("provider_behavior_hash") != expected_behavior_hash:
        _fail("provider_identity", f"{location}.environment provider behavior hash is inconsistent")
    if verified.manifest.get("provider_behavior_hash") != expected_behavior_hash:
        _fail("provider_identity", "manifest provider behavior hash does not match the mock provider")
    if environment.get("provider_id") != runner.SUPPORTED_PROVIDER_ID:
        _fail("provider_identity", f"{location}.environment provider is not the mock provider")
    if environment.get("guard_profile") != config.profile.profile_id:
        _fail("config_identity", f"{location}.environment guard profile disagrees with the registry")
    if environment.get("benchmark_manifest_status") != "final":
        _fail("benchmark_manifest", f"{location} was not produced against the FINAL manifest")

    dependencies = environment.get("dependencies")
    if not isinstance(dependencies, list) or not all(isinstance(d, str) for d in dependencies):
        _fail("dependency_identity", f"{location}.environment dependencies are malformed")
    expected_dependency_hash = runner._sha256_bytes(  # noqa: SLF001
        runner._canonical_json_bytes(list(dependencies))  # noqa: SLF001
    )
    if environment.get("dependencies_sha256") != expected_dependency_hash:
        _fail("dependency_identity", f"{location}.environment dependency hash is inconsistent")

    expected_case_set = result.get("expected_case_set_sha256")
    _hash(expected_case_set, f"{location}.expected_case_set_sha256")
    if verified.manifest.get("expected_case_set_sha256") != expected_case_set:
        _fail("manifest_result_mismatch", "manifest expected-case-set hash disagrees with result.json")

    safety_limits = result.get("safety_limits")
    if not isinstance(safety_limits, dict):
        _fail("safety_identity", f"{location}.safety_limits is missing")
    expected_experiment_id = runner._sha256_bytes(  # noqa: SLF001
        runner._canonical_json_bytes(  # noqa: SLF001
            {
                "result_schema_version": runner.HOLDOUT_RESULT_SCHEMA_VERSION,
                "config_registry_version": runner.CONFIG_REGISTRY_VERSION,
                "config_hashes": {
                    known_id: runner.CONFIG_REGISTRY[known_id].config_hash
                    for known_id in runner.CONFIG_REGISTRY
                },
                "split": runner.HOLDOUT_SPLIT,
                "git_commit": environment["git_commit"],
                "benchmark_manifest_sha256": environment["benchmark_manifest_sha256"],
                "provider_id": result["provider_id"],
                "provider_behavior_hash": result["provider_behavior_hash"],
                "safety_limits": dict(safety_limits),
                "dependencies_sha256": environment["dependencies_sha256"],
            }
        )
    )
    if result.get("experiment_id") != expected_experiment_id:
        _fail("experiment_identity", f"{location} experiment identity does not match its contract")
    if verified.manifest.get("experiment_id") != expected_experiment_id:
        _fail("manifest_result_mismatch", "manifest experiment identity disagrees with result.json")


def _expected_provider_behavior_hash() -> str:
    """Behavior hash of the only provider an authorized holdout run may use."""
    spec = runner.default_provider_spec(runner.SUPPORTED_PROVIDER_ID, load_settings())
    return spec.behavior_hash


def validate_holdout_analysis_document(
    analysis: Any, *, authorization: runner.HoldoutAuthorization
) -> None:
    """Dedicated exact-key validation of the FINAL holdout analysis document.

    Codex finding: the holdout extension was previously applied by mutating an
    ordinary-shaped dict after validation, so the extended document itself was
    never validated.
    """
    if not isinstance(analysis, dict):
        _fail("analysis_shape", "holdout analysis is not a JSON object")
    expected = ANALYSIS_KEYS | frozenset(HOLDOUT_IDENTITY_KEYS)
    _exact_keys(analysis, expected, "holdout analysis.json")
    if analysis["schema_version"] != HOLDOUT_ANALYSIS_SCHEMA_VERSION:
        _fail("analysis_schema", "holdout analysis schema version is unsupported")
    if analysis["split"] != runner.HOLDOUT_SPLIT:
        _fail("analysis_shape", "holdout analysis split must be holdout")
    _validate_holdout_identity_fields(analysis, "holdout analysis")
    for key in HOLDOUT_IDENTITY_KEYS:
        if analysis[key] != _holdout_identity_value(authorization, key):
            _fail("holdout_identity", f"holdout analysis {key} does not match the authorization")
    runner.scan_forbidden_artifact_content(analysis)


def validate_holdout_analysis_manifest_document(
    manifest: Any, *, authorization: runner.HoldoutAuthorization
) -> None:
    """Dedicated exact-key validation of the FINAL holdout analysis manifest."""
    if not isinstance(manifest, dict):
        _fail("analysis_shape", "holdout analysis manifest is not a JSON object")
    expected = ANALYSIS_MANIFEST_KEYS | frozenset(HOLDOUT_IDENTITY_KEYS)
    _exact_keys(manifest, expected, "holdout analysis-manifest.json")
    if manifest["schema_version"] != HOLDOUT_ANALYSIS_MANIFEST_SCHEMA_VERSION:
        _fail("analysis_schema", "holdout analysis-manifest schema version is unsupported")
    if manifest["analysis_schema_version"] != HOLDOUT_ANALYSIS_SCHEMA_VERSION:
        _fail("analysis_schema", "holdout analysis-manifest references a wrong analysis schema")
    if manifest["split"] != runner.HOLDOUT_SPLIT:
        _fail("analysis_shape", "holdout analysis-manifest split must be holdout")
    _validate_holdout_identity_fields(manifest, "holdout analysis-manifest")
    for key in HOLDOUT_IDENTITY_KEYS:
        if manifest[key] != _holdout_identity_value(authorization, key):
            _fail(
                "holdout_identity",
                f"holdout analysis-manifest {key} does not match the authorization",
            )
    runner.scan_forbidden_artifact_content(manifest)


def _holdout_identity_value(authorization: runner.HoldoutAuthorization, key: str) -> Any:
    return {
        "authorization_id": authorization.authorization_id,
        "holdout_authorization_sha256": authorization.authorization_sha256,
        "attempt": authorization.attempt,
        "supersedes_authorization_sha256": authorization.supersedes_authorization_sha256,
        "holdout_authorized": True,
    }[key]


def _holdout_analysis_shim(
    authorization: runner.HoldoutAuthorization, output_root: Path
) -> AnalysisRequest:
    """Internal-only adapter so `_build_analysis` keeps its existing contract.

    This never reaches `_validate_request`, so holdout is never admitted to the
    ordinary path; it only carries identity values the builder already reads.
    """
    return AnalysisRequest(
        split=runner.HOLDOUT_SPLIT,
        expected_branch=authorization.execution_branch,
        expected_commit=authorization.execution_commit,
        output_root=output_root,
        result_manifests=(),
    )


def _load_authorized_holdout_benchmark_for_analysis(
    capability: runner.VerifiedHoldoutAuthorization,
    *,
    benchmark_root: Path,
    repo_root: Path,
) -> runner.LoadedBenchmark:
    """Defer the actual record read to the runner's single authorized loader.

    Codex finding: the analyzer previously forged a capability by calling the
    (now removed) module-level token helper. It must instead obtain a genuine
    capability from `verify_holdout_authorization_for_analysis`, which mints it
    through the runner's closure-private registrar.
    """
    return runner.load_authorized_holdout_benchmark(
        capability, benchmark_root=benchmark_root, repo_root=repo_root
    )


def _assert_no_authorization_disclosure(
    payload: Any, authorization: runner.HoldoutAuthorization, attempt_root: Path
) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    for secret in (authorization.output_root, str(attempt_root)):
        if not secret:
            continue
        # On Windows a path serializes with escaped separators, so the raw
        # string would not appear verbatim; compare both encodings.
        escaped = json.dumps(secret, ensure_ascii=False)[1:-1]
        if secret in serialized or escaped in serialized:
            _fail("forbidden_artifact_path", "analysis discloses the absolute attempt root")
    try:
        runner._assert_no_absolute_path(payload)  # noqa: SLF001
    except runner.IntegrityError as exc:
        _fail("forbidden_artifact_path", f"analysis contains an absolute path: {exc}")


def _publish_holdout_analysis(
    output_root: Path,
    analysis: Mapping[str, Any],
    table_bytes: bytes,
    authorization: runner.HoldoutAuthorization,
    attempt_root: Path,
) -> WrittenAnalysis:
    analysis_bytes = runner._canonical_json_bytes(analysis)  # noqa: SLF001
    manifest = _build_analysis_manifest(
        analysis_bytes=analysis_bytes, table_bytes=table_bytes, analysis=analysis
    )
    manifest = dict(manifest)
    manifest["schema_version"] = HOLDOUT_ANALYSIS_MANIFEST_SCHEMA_VERSION
    manifest["analysis_schema_version"] = HOLDOUT_ANALYSIS_SCHEMA_VERSION
    for key in HOLDOUT_IDENTITY_KEYS:
        manifest[key] = _holdout_identity_value(authorization, key)
    validate_holdout_analysis_manifest_document(manifest, authorization=authorization)
    _assert_no_authorization_disclosure(manifest, authorization, attempt_root)
    manifest_bytes = runner._canonical_json_bytes(manifest)  # noqa: SLF001

    if output_root.exists():
        _fail("analysis_exists", "analysis destination already exists; overwrite refused")
    output_root.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".tmp-holdout-analysis-", dir=output_root.parent))
    try:
        payloads = (
            (staging / "analysis.json", analysis_bytes),
            (staging / "analysis-table.csv", table_bytes),
            (staging / "analysis-manifest.json", manifest_bytes),
        )
        for path, payload in payloads:
            with path.open("xb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        for path, payload in payloads:
            if path.read_bytes() != payload:
                _fail("analysis_write_integrity", "staged analysis bytes changed before publish")
        if output_root.exists():
            _fail("analysis_exists", "analysis destination appeared before publish")
        _publish_directory_atomically(staging, output_root)
    except Exception:
        try:
            _remove_staging_best_effort(staging)
        except Exception:
            pass
        raise
    return WrittenAnalysis(
        output_directory=output_root,
        analysis_path=output_root / "analysis.json",
        table_path=output_root / "analysis-table.csv",
        manifest_path=output_root / "analysis-manifest.json",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    # --split accepts only development/validation. Holdout is reachable solely
    # through --holdout-authorization.
    parser.add_argument("--split", choices=list(runner.SUPPORTED_SPLITS))
    parser.add_argument(
        "--holdout-authorization",
        type=Path,
        help=(
            "Path to the external canonical maintainer authorization. Selects "
            "authorized holdout analysis; incompatible with --split."
        ),
    )
    parser.add_argument("--expected-branch")
    parser.add_argument("--expected-commit")
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--result-manifest", required=True, action="append", type=Path)
    return parser


def _holdout_analysis_request_from_args(args: argparse.Namespace) -> HoldoutAnalysisRequest:
    if args.split is not None:
        _fail("cli_holdout_split", "--split must not be combined with --holdout-authorization")
    if args.expected_branch is not None or args.expected_commit is not None:
        _fail(
            "cli_holdout_identity",
            "holdout identity comes from the authorization, not --expected-branch/--expected-commit",
        )
    if args.output_root is not None:
        _fail(
            "cli_holdout_output",
            "holdout analysis writes to the authorized attempt root; --output-root is prohibited",
        )
    return HoldoutAnalysisRequest(
        authorization_path=args.holdout_authorization,
        result_manifests=tuple(args.result_manifest),
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.holdout_authorization is not None:
        try:
            holdout_request = _holdout_analysis_request_from_args(args)
            written = analyze_holdout_results(holdout_request)
        except AnalysisError as exc:
            print(f"FAIL [{exc.code}]: {exc}", file=sys.stderr)
            return 1
        except runner.RunnerError as exc:
            print(f"FAIL [{exc.code}]: {exc}", file=sys.stderr)
            return 1
        except Exception:
            print("FAIL [internal_error]: analyzer failed closed.", file=sys.stderr)
            return 1
        print(f"OK: wrote authorized holdout analysis to {written.output_directory.name}.")
        return 0

    if args.split is None:
        print("FAIL [cli_split_required]: --split is required unless --holdout-authorization is used.", file=sys.stderr)
        return 1
    if args.expected_branch is None or args.expected_commit is None:
        print("FAIL [cli_identity_required]: --expected-branch and --expected-commit are required.", file=sys.stderr)
        return 1
    if args.output_root is None:
        print("FAIL [cli_output_required]: --output-root is required.", file=sys.stderr)
        return 1

    request = AnalysisRequest(
        split=args.split,
        expected_branch=args.expected_branch,
        expected_commit=args.expected_commit,
        output_root=args.output_root,
        result_manifests=tuple(args.result_manifest),
    )
    try:
        written = analyze_results(request)
    except AnalysisError as exc:
        print(f"FAIL [{exc.code}]: {exc}", file=sys.stderr)
        return 1
    except Exception:
        print("FAIL [internal_error]: analyzer failed closed.", file=sys.stderr)
        return 1
    print(f"OK: wrote analysis for split {args.split} to {written.output_directory.name}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
