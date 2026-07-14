#!/usr/bin/env python3
"""Run the Phase 12E.3 development/validation ablation foundation offline.

This runner intentionally does not calculate aggregate metrics. It verifies
repository and benchmark identity, builds one temporary SQLite corpus per
configuration, executes one supported frozen split, projects results through an
explicit content-free allowlist, and publishes immutable diagnostic artifacts.
Holdout evaluation is not accepted by this phase.
"""
from __future__ import annotations

import argparse
import contextlib
import dataclasses
import hashlib
import importlib.metadata
import inspect
import json
import math
import multiprocessing
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from multiprocessing.connection import Connection
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import Settings, load_settings
from app.core.decisions import Decision
from app.core.pipeline import GuardProfile, RagPipelineResult
from app.core.source_policy import resolve_source_policy
from app.retrieval.models import IngestionDocument, RetrievalQuery
from app.retrieval.sqlite_bm25 import (
    FTS5UnavailableError,
    IngestionBatchError,
    SqliteBM25Config,
    SqliteBM25Retriever,
)
from app.services import audit_logger, ingestion as ingestion_module
from app.services.chunking import ChunkingConfig
from app.services.ingestion import (
    IngestionService,
    IngestionServiceConfig,
    _derive_document_id,
)
from app.services.llm_provider import BaseLLMProvider, MockLLMProvider
from app.services.rag_query import (
    STOP_TOP_K_REJECTED,
    audit_top_k_rejected,
    commit_rag_query_audit,
    run_rag_query_uncommitted,
)


RESULT_SCHEMA_VERSION = 2
RESULT_MANIFEST_SCHEMA_VERSION = 1
SUPPORTED_SPLITS = ("development", "validation")
SUPPORTED_PROVIDER_ID = "mock"
CONFIG_REGISTRY_VERSION = 1
WORKER_PROTOCOL_VERSION = 1
WORKER_STARTUP_TIMEOUT_SECONDS = 30.0
WORKER_SHUTDOWN_TIMEOUT_SECONDS = 5.0

GUARD_FIELDS = (
    "input_guard",
    "provenance_guard",
    "rag_context_guard",
    "aggregate_context_guard",
    "dlp",
    "output_guard",
)
GUARD_STAGE_TO_FIELD = {
    "input_guard": "input_guard",
    "provenance_guard": "provenance_guard",
    "rag_context_guard": "rag_context_guard",
    "aggregate_context_guard": "aggregate_context_guard",
    "dlp": "dlp",
    "output_guard": "output_guard",
}

CONFIG_DEFINITIONS: tuple[tuple[str, tuple[bool, ...]], ...] = (
    ("C0_all_on", (True, True, True, True, True, True)),
    ("C1_no_input", (False, True, True, True, True, True)),
    ("C2_no_provenance", (True, False, True, True, True, True)),
    ("C3_no_context", (True, True, False, False, True, True)),
    ("C4_no_dlp", (True, True, True, True, False, True)),
    ("C5_no_output", (True, True, True, True, True, False)),
    ("C6_none", (False, False, False, False, False, False)),
    ("C7_no_context_no_output", (True, True, False, False, True, False)),
)

EVALUATION_SCOPES = (
    "end_to_end",
    "component",
    "availability_fault",
    "residual_risk_only",
)
EXPECTED_SCOPE_COUNTS_BY_SPLIT = {
    split: {
        "end_to_end": 26,
        "component": 1,
        "availability_fault": 2,
        "residual_risk_only": 1,
    }
    for split in SUPPORTED_SPLITS
}
OBSERVATION_NAMESPACES = {
    "end_to_end": "ablation_matrix",
    "component": "component_integrity",
    "availability_fault": "availability_robustness",
    "residual_risk_only": "residual_risk_descriptive",
}

REQUIRED_FROZEN_PATHS = (
    "cases/development.jsonl",
    "cases/holdout.jsonl",
    "cases/validation.jsonl",
    "contamination-exemptions.json",
    "corpus/documents.jsonl",
    "design/authoring-provenance.jsonl",
    "labels/development.jsonl",
    "labels/holdout.jsonl",
    "labels/validation.jsonl",
)
FROZEN_SUBDIRECTORIES = ("corpus", "cases", "labels", "design")

SAFE_ERROR_CATEGORIES = frozenset({"case_execution_error", "case_timeout"})
FORBIDDEN_FIELD_NAMES = frozenset(
    {
        "query",
        "raw_query",
        "normalized_query",
        "effective_query",
        "prompt",
        "sanitized_prompt",
        "text",
        "content",
        "answer",
        "generated_answer",
        "context_chunks",
        "retrieved_chunks",
        "relevant_document_ids",
        "audit_ctx",
        "detail",
        "secret",
        "secret_value",
        "canary",
        "stack_trace",
        "traceback",
        "exception",
        "exception_message",
    }
)
PRODUCTION_CREDENTIAL_ENV_VARS = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "GOOGLE_API_KEY",
    "GEMINI_API_KEY",
    "COHERE_API_KEY",
    "MISTRAL_API_KEY",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
)

_SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_SAFE_REASON_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,127}$")
_WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")
_CANARY_VALUE_RE = re.compile(r"(?:V2TOK\d+|FAKE-SECRET-|BEGIN [A-Z ]*PRIVATE KEY)", re.I)


class RunnerError(RuntimeError):
    """Controlled CLI failure with a stable, non-sensitive category."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class IntegrityError(RunnerError):
    """Fatal identity or safety failure; no result artifact may be written."""


@dataclass(frozen=True)
class EvaluationConfig:
    config_id: str
    profile: GuardProfile

    @property
    def profile_payload(self) -> dict[str, bool]:
        return {name: getattr(self.profile, name) for name in GUARD_FIELDS}

    @property
    def config_payload(self) -> dict[str, Any]:
        return {"config_id": self.config_id, **self.profile_payload}

    @property
    def config_hash(self) -> str:
        return _sha256_bytes(_canonical_json_bytes(self.config_payload))


def _build_config_registry() -> dict[str, EvaluationConfig]:
    registry: dict[str, EvaluationConfig] = {}
    for config_id, values in CONFIG_DEFINITIONS:
        profile = GuardProfile(**dict(zip(GUARD_FIELDS, values, strict=True)))
        registry[config_id] = EvaluationConfig(config_id=config_id, profile=profile)
    return registry


CONFIG_REGISTRY = _build_config_registry()


@dataclass(frozen=True)
class RepositoryState:
    branch: str
    commit: str
    dirty: bool


@dataclass(frozen=True)
class ManifestIdentity:
    sha256: str
    status: str
    file_count: int


@dataclass(frozen=True)
class ProviderSpec:
    provider_id: str
    factory: Callable[[], BaseLLMProvider]
    behavior_descriptor: Mapping[str, Any]
    offline: bool = True
    test_only: bool = False

    @property
    def behavior_hash(self) -> str:
        return _sha256_bytes(_canonical_json_bytes(dict(self.behavior_descriptor)))


@dataclass(frozen=True)
class LoadedBenchmark:
    corpus: tuple[dict[str, Any], ...]
    cases: tuple[dict[str, Any], ...]
    labels_by_id: Mapping[str, dict[str, Any]]


@dataclass(frozen=True)
class RunRequest:
    split: str
    config_ids: tuple[str, ...]
    output_root: Path
    expected_branch: str
    expected_commit: str
    provider_id: str = SUPPORTED_PROVIDER_ID
    case_timeout_seconds: float = 30.0


@dataclass(frozen=True)
class PreflightContext:
    request: RunRequest
    repository: RepositoryState
    benchmark_root: Path
    manifest: ManifestIdentity
    benchmark: LoadedBenchmark
    provider: ProviderSpec
    settings: Settings
    dependencies: tuple[str, ...]
    dependencies_sha256: str
    safety_limits: Mapping[str, Any]
    experiment_id: str
    expected_ids_by_config: Mapping[str, tuple[str, ...]]
    expected_scope_ids_by_config: Mapping[str, Mapping[str, tuple[str, ...]]]


@dataclass(frozen=True)
class ScopeOutcome:
    final_decision: str
    stop_reason: str
    provider_called: bool
    retrieved_count: int
    accepted_context_count: int
    rejected_context_count: int
    redaction_count: int
    dlp_finding_categories: Mapping[str, int]
    stage_results: tuple[dict[str, Any], ...]
    pipeline_pre_audit_ms: float | None
    end_to_end_with_audit_ms: float
    document_ingestion_status: str | None = None
    target_document_hit_count: int | None = None


@dataclass(frozen=True)
class WorkerRuntimeSettings:
    llm_model_name: str
    retrieval_busy_timeout_ms: int
    retrieval_max_query_chars: int
    retrieval_max_query_terms: int
    retrieval_max_top_k: int
    rag_max_top_k: int
    rag_max_aggregate_context_chars: int
    dlp_max_inspect_chars: int


@dataclass(frozen=True)
class WrittenRun:
    config_id: str
    run_id: str
    run_status: str
    result_path: Path
    manifest_path: Path


@dataclass(frozen=True)
class RunnerHooks:
    repository_state_loader: Callable[[Path], RepositoryState] = field(
        default=lambda root: read_repository_state(root)
    )
    provider_spec_loader: Callable[[str, Settings], ProviderSpec] = field(
        default=lambda provider_id, active_settings: default_provider_spec(
            provider_id, active_settings
        )
    )
    run_id_factory: Callable[[str], str] = field(default=lambda config_id: _new_run_id(config_id))
    temp_parent: Path | None = None
    allow_test_provider: bool = False
    worker_entrypoint: Callable[[Connection, Mapping[str, Any]], None] | None = None
    worker_lifecycle_observer: Callable[[str, int], None] | None = None


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _safe_location(value: str) -> str:
    if not _SAFE_IDENTIFIER_RE.fullmatch(value):
        raise IntegrityError("unsafe_identifier", "an identity contains unsupported characters")
    return value


def _require_string(record: Mapping[str, Any], field_name: str, location: str) -> str:
    value = record.get(field_name)
    if not isinstance(value, str) or not value:
        raise IntegrityError("benchmark_schema", f"{location}.{field_name} must be a string")
    return value


def _load_jsonl(path: Path, location: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                if not raw_line.strip():
                    continue
                value = json.loads(raw_line)
                if not isinstance(value, dict):
                    raise IntegrityError(
                        "benchmark_schema", f"{location}:{line_number} must contain an object"
                    )
                records.append(value)
    except UnicodeError as exc:
        raise IntegrityError("benchmark_encoding", f"{location} is not valid UTF-8") from exc
    except json.JSONDecodeError as exc:
        raise IntegrityError("benchmark_json", f"{location}:{exc.lineno} is not valid JSON") from exc
    return records


def read_repository_state(repo_root: Path) -> RepositoryState:
    def run_git(*args: str) -> str:
        try:
            completed = subprocess.run(
                ["git", *args],
                cwd=repo_root,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise IntegrityError("git_state_unavailable", "repository identity could not be read") from exc
        return completed.stdout.strip()

    branch = run_git("branch", "--show-current")
    commit = run_git("rev-parse", "HEAD")
    dirty = bool(run_git("status", "--porcelain=v1", "--untracked-files=all"))
    return RepositoryState(branch=branch, commit=commit, dirty=dirty)


def _iter_frozen_artifact_paths(benchmark_root: Path) -> tuple[str, ...]:
    paths: list[str] = []
    for subdirectory in FROZEN_SUBDIRECTORIES:
        directory = benchmark_root / subdirectory
        if directory.exists():
            paths.extend(
                path.relative_to(benchmark_root).as_posix()
                for path in directory.rglob("*")
                if path.is_file()
            )
    policy = benchmark_root / "contamination-exemptions.json"
    if policy.is_file():
        paths.append("contamination-exemptions.json")
    return tuple(sorted(paths))


def verify_frozen_manifest(benchmark_root: Path) -> ManifestIdentity:
    manifest_path = benchmark_root / "manifests" / "benchmark-v2-manifest.json"
    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise IntegrityError("manifest_unreadable", "benchmark manifest is unavailable or malformed") from exc

    if not isinstance(manifest, dict) or manifest.get("manifest_status") != "final":
        raise IntegrityError("manifest_not_final", "benchmark manifest status must be final")
    if manifest.get("manifest_version") != 1 or manifest.get("benchmark_version") != "v2":
        raise IntegrityError("manifest_identity", "benchmark manifest identity is unsupported")
    entries = manifest.get("files")
    if not isinstance(entries, list) or manifest.get("file_count") != len(entries):
        raise IntegrityError("manifest_structure", "benchmark manifest file table is malformed")

    seen_paths: list[str] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise IntegrityError("manifest_structure", f"manifest.files[{index}] is malformed")
        relative = entry.get("path")
        digest = entry.get("sha256")
        size = entry.get("size_bytes")
        if not isinstance(relative, str):
            raise IntegrityError("manifest_path", f"manifest.files[{index}].path is invalid")
        pure = PurePosixPath(relative)
        if (
            pure.is_absolute()
            or ".." in pure.parts
            or "\\" in relative
            or ":" in relative
            or relative != pure.as_posix()
        ):
            raise IntegrityError("manifest_path", f"manifest path entry {index} is unsafe")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise IntegrityError("manifest_digest", f"manifest digest entry {index} is invalid")
        if type(size) is not int or size < 0:
            raise IntegrityError("manifest_size", f"manifest size entry {index} is invalid")

        artifact = (benchmark_root / Path(*pure.parts)).resolve()
        root = benchmark_root.resolve()
        if not _is_within(artifact, root) or not artifact.is_file():
            raise IntegrityError("manifest_missing_artifact", f"frozen artifact missing: {relative}")
        if artifact.stat().st_size != size or _sha256_file(artifact) != digest:
            raise IntegrityError("manifest_artifact_mismatch", f"frozen artifact mismatch: {relative}")
        seen_paths.append(relative)

    if tuple(seen_paths) != tuple(sorted(seen_paths)):
        raise IntegrityError("manifest_order", "benchmark manifest paths are not sorted")
    if tuple(seen_paths) != REQUIRED_FROZEN_PATHS:
        raise IntegrityError("manifest_file_set", "benchmark manifest must cover exactly nine artifacts")
    if _iter_frozen_artifact_paths(benchmark_root) != REQUIRED_FROZEN_PATHS:
        raise IntegrityError("manifest_unexpected_artifact", "benchmark artifact set differs from the freeze")

    return ManifestIdentity(
        sha256=_sha256_bytes(manifest_bytes),
        status="final",
        file_count=len(entries),
    )


def validate_config_registry(registry: Mapping[str, EvaluationConfig]) -> None:
    expected_ids = tuple(item[0] for item in CONFIG_DEFINITIONS)
    if tuple(registry) != expected_ids:
        raise IntegrityError("config_registry", "configuration registry order or names changed")
    for config_id, values in CONFIG_DEFINITIONS:
        config = registry.get(config_id)
        if config is None or config.config_id != config_id:
            raise IntegrityError("config_registry", "configuration registry identity mismatch")
        actual = tuple(getattr(config.profile, name) for name in GUARD_FIELDS)
        if actual != values:
            raise IntegrityError("config_registry", f"configuration booleans mismatch: {config_id}")
        if config.profile.profile_id != GuardProfile(**dict(zip(GUARD_FIELDS, values, strict=True))).profile_id:
            raise IntegrityError("config_registry", f"profile identity mismatch: {config_id}")
        if not re.fullmatch(r"[0-9a-f]{64}", config.config_hash):
            raise IntegrityError("config_registry", f"configuration hash invalid: {config_id}")


def default_provider_spec(
    provider_id: str,
    active_settings: Settings | WorkerRuntimeSettings,
) -> ProviderSpec:
    if provider_id != SUPPORTED_PROVIDER_ID:
        raise IntegrityError("provider_not_allowed", "only the offline mock provider is approved")
    source_hash = _sha256_bytes(inspect.getsource(MockLLMProvider.generate).encode("utf-8"))
    descriptor = {
        "provider_id": SUPPORTED_PROVIDER_ID,
        "implementation": "app.services.llm_provider.MockLLMProvider.generate",
        "implementation_sha256": source_hash,
        "model_name": active_settings.llm_model_name,
        "network": "disabled",
        "behavior_version": 1,
    }
    return ProviderSpec(
        provider_id=SUPPORTED_PROVIDER_ID,
        factory=lambda: MockLLMProvider(model_name=active_settings.llm_model_name),
        behavior_descriptor=descriptor,
        offline=True,
        test_only=False,
    )


def _validate_provider(spec: ProviderSpec, *, allow_test_provider: bool) -> None:
    _safe_location(spec.provider_id)
    if not spec.offline:
        raise IntegrityError("provider_not_offline", "provider must be explicitly offline")
    if spec.test_only and not allow_test_provider:
        raise IntegrityError("provider_test_only", "scripted test providers are disabled for CLI runs")
    if spec.provider_id != SUPPORTED_PROVIDER_ID and not (spec.test_only and allow_test_provider):
        raise IntegrityError("provider_not_allowed", "provider is not on the offline allowlist")
    if not re.fullmatch(r"[0-9a-f]{64}", spec.behavior_hash):
        raise IntegrityError("provider_identity", "provider behavior identity is invalid")
    try:
        provider = spec.factory()
    except Exception as exc:
        raise IntegrityError("provider_factory", "provider factory failed closed") from exc
    if not isinstance(provider, BaseLLMProvider):
        raise IntegrityError("provider_contract", "provider does not implement the offline contract")


def _validate_provider_environment(spec: ProviderSpec) -> None:
    configured = os.getenv("LLM_PROVIDER", SUPPORTED_PROVIDER_ID).strip().lower()
    if configured != SUPPORTED_PROVIDER_ID:
        raise IntegrityError("external_provider_environment", "LLM_PROVIDER must remain mock")
    present = [name for name in PRODUCTION_CREDENTIAL_ENV_VARS if os.getenv(name)]
    if present:
        raise IntegrityError("production_credentials_present", "production provider credentials are not allowed")
    if spec.provider_id != SUPPORTED_PROVIDER_ID and not spec.test_only:
        raise IntegrityError("external_provider", "external providers are prohibited")


def _dependency_inventory() -> tuple[str, ...]:
    values: set[str] = set()
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get("Name")
        version = distribution.version
        if not isinstance(name, str) or not name or not isinstance(version, str) or not version:
            continue
        value = f"{name}=={version}"
        if "\n" in value or "\r" in value or _looks_like_absolute_path(value):
            raise IntegrityError("dependency_identity", "dependency inventory contains an unsafe value")
        values.add(value)
    return tuple(sorted(values, key=lambda value: (value.casefold(), value)))


def _validate_output_root(output_root: Path, repo_root: Path, benchmark_root: Path) -> Path:
    resolved = output_root.expanduser().resolve()
    repo = repo_root.resolve()
    benchmark = benchmark_root.resolve()
    approved_repo_output = (repo / "reports" / "evaluation-v2").resolve()

    if resolved == repo or resolved == benchmark or _is_within(resolved, benchmark):
        raise IntegrityError("output_containment", "output root overlaps protected repository input")
    if _is_within(resolved, repo) and not _is_within(resolved, approved_repo_output):
        raise IntegrityError(
            "output_containment",
            "repository-local output is allowed only under reports/evaluation-v2",
        )
    if resolved.exists() and not resolved.is_dir():
        raise IntegrityError("output_containment", "output root must be a directory")
    return resolved


def load_split_benchmark(benchmark_root: Path, requested_split: str) -> LoadedBenchmark:
    if requested_split not in SUPPORTED_SPLITS:
        raise IntegrityError("split_not_allowed", "evaluation split must be development or validation")

    corpus = _load_jsonl(benchmark_root / "corpus" / "documents.jsonl", "corpus/documents")
    cases = _load_jsonl(
        benchmark_root / "cases" / f"{requested_split}.jsonl",
        f"cases/{requested_split}",
    )
    labels = _load_jsonl(
        benchmark_root / "labels" / f"{requested_split}.jsonl",
        f"labels/{requested_split}",
    )

    document_ids: set[str] = set()
    for index, document in enumerate(corpus):
        location = f"corpus[{index}]"
        document_id = _require_string(document, "document_id", location)
        _require_string(document, "external_id", location)
        _require_string(document, "source_key", location)
        _require_string(document, "title", location)
        _require_string(document, "content", location)
        _require_string(document, "scenario_family", location)
        mode = _require_string(document, "ingestion_mode", location)
        if mode not in {"public", "internal_only", "rejected"}:
            raise IntegrityError("benchmark_schema", f"{location}.ingestion_mode is invalid")
        if not isinstance(document.get("metadata"), dict):
            raise IntegrityError("benchmark_schema", f"{location}.metadata must be an object")
        if document_id in document_ids:
            raise IntegrityError("benchmark_duplicate", f"duplicate document identity: {document_id}")
        document_ids.add(document_id)

    labels_by_id: dict[str, dict[str, Any]] = {}
    for index, label in enumerate(labels):
        location = f"labels[{index}]"
        case_id = _require_string(label, "case_id", location)
        _require_string(label, "scenario_family", location)
        category = _require_string(label, "category", location)
        if category not in {"benign", "malicious", "mixed", "neutral"}:
            raise IntegrityError("benchmark_schema", f"{location}.category is invalid")
        for field_name in ("allowed_final_decisions", "allowed_stop_reasons"):
            values = label.get(field_name)
            if not isinstance(values, list) or not values or not all(
                isinstance(value, str) and value for value in values
            ):
                raise IntegrityError("benchmark_schema", f"{location}.{field_name} is invalid")
        expected_provider_called = label.get("expected_provider_called")
        if expected_provider_called is not None and type(expected_provider_called) is not bool:
            raise IntegrityError(
                "benchmark_schema",
                f"{location}.expected_provider_called must be boolean or null",
            )
        if case_id in labels_by_id:
            raise IntegrityError("benchmark_duplicate", f"duplicate label identity: {case_id}")
        labels_by_id[case_id] = label

    case_ids: set[str] = set()
    scope_counts = {scope: 0 for scope in EVALUATION_SCOPES}
    validated_cases: list[dict[str, Any]] = []
    for index, case in enumerate(cases):
        location = f"cases[{index}]"
        case_id = _require_string(case, "case_id", location)
        split = _require_string(case, "split", location)
        family = _require_string(case, "scenario_family", location)
        _require_string(case, "query", location)
        scope = _require_string(case, "evaluation_scope", location)
        top_k = case.get("top_k")
        relevant_ids = case.get("relevant_document_ids")
        if split != requested_split:
            raise IntegrityError("benchmark_split", f"{location}.split does not match the request")
        if scope not in EVALUATION_SCOPES:
            raise IntegrityError("benchmark_scope", f"{location}.evaluation_scope is invalid")
        if type(top_k) is not int or not 1 <= top_k <= 50:
            raise IntegrityError("benchmark_schema", f"{location}.top_k is invalid")
        if not isinstance(relevant_ids, list) or not all(
            isinstance(value, str) and value for value in relevant_ids
        ):
            raise IntegrityError("benchmark_schema", f"{location}.relevant_document_ids is invalid")
        if case_id in case_ids:
            raise IntegrityError("benchmark_duplicate", f"duplicate case identity: {case_id}")
        label = labels_by_id.get(case_id)
        if label is None or label["scenario_family"] != family:
            raise IntegrityError("benchmark_mapping", f"case-label mapping mismatch: {case_id}")
        case_ids.add(case_id)
        scope_counts[scope] += 1
        validated_cases.append(case)

    if len(validated_cases) != 30 or scope_counts != EXPECTED_SCOPE_COUNTS_BY_SPLIT[requested_split]:
        raise IntegrityError("benchmark_case_set", f"{requested_split} expected-case set changed")
    if case_ids != set(labels_by_id):
        raise IntegrityError("benchmark_mapping", f"{requested_split} case and label identities differ")

    return LoadedBenchmark(
        corpus=tuple(sorted(corpus, key=lambda item: item["document_id"])),
        cases=tuple(sorted(validated_cases, key=lambda item: item["case_id"])),
        labels_by_id=labels_by_id,
    )


def load_development_benchmark(benchmark_root: Path) -> LoadedBenchmark:
    """Backward-compatible helper for existing development-only callers."""
    return load_split_benchmark(benchmark_root, "development")


def _expected_case_sets(
    benchmark: LoadedBenchmark, config_ids: Sequence[str]
) -> tuple[dict[str, tuple[str, ...]], dict[str, dict[str, tuple[str, ...]]]]:
    overall: dict[str, tuple[str, ...]] = {}
    by_scope: dict[str, dict[str, tuple[str, ...]]] = {}
    for config_id in config_ids:
        scopes = EVALUATION_SCOPES if config_id == "C0_all_on" else ("end_to_end",)
        scope_sets = {
            scope: tuple(
                case["case_id"] for case in benchmark.cases if case["evaluation_scope"] == scope
            )
            for scope in scopes
        }
        expected = tuple(case_id for scope in scopes for case_id in scope_sets[scope])
        expected = tuple(sorted(expected))
        overall[config_id] = expected
        by_scope[config_id] = scope_sets
    return overall, by_scope


def _case_set_hash(case_ids: Sequence[str]) -> str:
    return _sha256_bytes(_canonical_json_bytes(list(case_ids)))


def _validate_result_schema_contract() -> None:
    if RESULT_SCHEMA_VERSION != 2 or RESULT_MANIFEST_SCHEMA_VERSION != 1:
        raise IntegrityError("result_schema", "result schema identity is unsupported")


def _settings_safety_limits(active_settings: Settings, case_timeout_seconds: float) -> dict[str, Any]:
    if (
        type(case_timeout_seconds) not in {int, float}
        or not math.isfinite(case_timeout_seconds)
        or case_timeout_seconds <= 0
    ):
        raise IntegrityError("case_timeout", "case timeout must be a finite positive number")
    normalized_timeout = float(case_timeout_seconds)
    positive_integer_limits = {
        "retrieval_max_batch_size": active_settings.retrieval_max_batch_size,
        "retrieval_max_document_chars": active_settings.retrieval_max_document_chars,
        "retrieval_max_query_chars": active_settings.retrieval_max_query_chars,
        "retrieval_max_query_terms": active_settings.retrieval_max_query_terms,
        "retrieval_max_top_k": active_settings.retrieval_max_top_k,
        "retrieval_chunk_max_chars": active_settings.retrieval_chunk_max_chars,
        "retrieval_busy_timeout_ms": active_settings.retrieval_busy_timeout_ms,
    }
    for name, value in positive_integer_limits.items():
        if type(value) is not int or value <= 0:
            raise IntegrityError("safety_limit", f"{name} must be a positive integer")
    overlap = active_settings.retrieval_chunk_overlap_chars
    if type(overlap) is not int or not 0 <= overlap < active_settings.retrieval_chunk_max_chars:
        raise IntegrityError(
            "safety_limit",
            "retrieval chunk overlap must be non-negative and smaller than chunk size",
        )
    return {
        "query_max_chars": active_settings.retrieval_max_query_chars,
        "query_max_terms": active_settings.retrieval_max_query_terms,
        "retrieval_max_top_k": active_settings.retrieval_max_top_k,
        "rag_max_top_k": active_settings.rag_max_top_k,
        "ingestion_max_batch_size": active_settings.retrieval_max_batch_size,
        "document_max_chars": active_settings.retrieval_max_document_chars,
        "chunk_max_chars": active_settings.retrieval_chunk_max_chars,
        "chunk_overlap_chars": active_settings.retrieval_chunk_overlap_chars,
        "aggregate_context_limit": active_settings.rag_max_aggregate_context_chars,
        "provider_output_limit": active_settings.dlp_max_inspect_chars,
        "case_timeout_seconds": normalized_timeout,
        "temporary_sqlite_required": True,
        "network_disabled": True,
    }


def _worker_runtime_settings_payload(active_settings: Settings) -> dict[str, Any]:
    return {
        "llm_model_name": active_settings.llm_model_name,
        "retrieval_busy_timeout_ms": active_settings.retrieval_busy_timeout_ms,
        "retrieval_max_query_chars": active_settings.retrieval_max_query_chars,
        "retrieval_max_query_terms": active_settings.retrieval_max_query_terms,
        "retrieval_max_top_k": active_settings.retrieval_max_top_k,
        "rag_max_top_k": active_settings.rag_max_top_k,
        "rag_max_aggregate_context_chars": active_settings.rag_max_aggregate_context_chars,
        "dlp_max_inspect_chars": active_settings.dlp_max_inspect_chars,
    }


def _load_worker_runtime_settings(value: Any) -> WorkerRuntimeSettings:
    expected_fields = {
        "llm_model_name",
        "retrieval_busy_timeout_ms",
        "retrieval_max_query_chars",
        "retrieval_max_query_terms",
        "retrieval_max_top_k",
        "rag_max_top_k",
        "rag_max_aggregate_context_chars",
        "dlp_max_inspect_chars",
    }
    if not isinstance(value, dict) or set(value) != expected_fields:
        raise IntegrityError("worker_settings", "worker settings payload is malformed")
    if not isinstance(value["llm_model_name"], str) or not value["llm_model_name"]:
        raise IntegrityError("worker_settings", "worker model identity is invalid")
    for field_name in expected_fields - {"llm_model_name"}:
        if type(value[field_name]) is not int or value[field_name] <= 0:
            raise IntegrityError("worker_settings", "worker numeric setting is invalid")
    if value["rag_max_top_k"] > value["retrieval_max_top_k"]:
        raise IntegrityError("worker_settings", "worker top-k limits are contradictory")
    return WorkerRuntimeSettings(**value)


def _experiment_id(
    repository: RepositoryState,
    manifest: ManifestIdentity,
    provider: ProviderSpec,
    safety_limits: Mapping[str, Any],
    dependencies_sha256: str,
    split: str,
) -> str:
    contract = {
        "result_schema_version": RESULT_SCHEMA_VERSION,
        "config_registry_version": CONFIG_REGISTRY_VERSION,
        "config_hashes": {
            config_id: CONFIG_REGISTRY[config_id].config_hash for config_id in CONFIG_REGISTRY
        },
        "split": split,
        "git_commit": repository.commit,
        "benchmark_manifest_sha256": manifest.sha256,
        "provider_id": provider.provider_id,
        "provider_behavior_hash": provider.behavior_hash,
        "safety_limits": dict(safety_limits),
        "dependencies_sha256": dependencies_sha256,
    }
    return _sha256_bytes(_canonical_json_bytes(contract))


def preflight(
    request: RunRequest,
    *,
    repo_root: Path = ROOT,
    benchmark_root: Path | None = None,
    hooks: RunnerHooks | None = None,
) -> PreflightContext:
    active_hooks = hooks or RunnerHooks()
    benchmark_path = (benchmark_root or repo_root / "datasets" / "v2").resolve()

    if request.split not in SUPPORTED_SPLITS:
        raise IntegrityError(
            "split_not_allowed",
            "evaluation split must be development or validation; holdout is prohibited",
        )
    if not _FULL_SHA_RE.fullmatch(request.expected_commit):
        raise IntegrityError("expected_commit", "expected commit must be a full lowercase SHA-1")
    _safe_location(request.expected_branch)
    if not request.config_ids or len(set(request.config_ids)) != len(request.config_ids):
        raise IntegrityError("config_selection", "configuration selection is empty or duplicated")
    for config_id in request.config_ids:
        if config_id not in CONFIG_REGISTRY:
            raise IntegrityError("config_not_allowed", "unknown or custom profiles are prohibited")

    repository = active_hooks.repository_state_loader(repo_root)
    if repository.branch != request.expected_branch:
        raise IntegrityError("branch_mismatch", "repository branch does not match the expected identity")
    if repository.commit != request.expected_commit:
        raise IntegrityError("commit_mismatch", "repository commit does not match the expected identity")
    if repository.dirty:
        raise IntegrityError("git_dirty", "working tree must be clean before evaluation")

    _validate_result_schema_contract()
    _validate_output_root(request.output_root, repo_root, benchmark_path)
    manifest = verify_frozen_manifest(benchmark_path)
    validate_config_registry(CONFIG_REGISTRY)

    active_settings = load_settings()
    provider = active_hooks.provider_spec_loader(request.provider_id, active_settings)
    _validate_provider(provider, allow_test_provider=active_hooks.allow_test_provider)
    _validate_provider_environment(provider)

    safety_limits = _settings_safety_limits(active_settings, request.case_timeout_seconds)
    benchmark = load_split_benchmark(benchmark_path, request.split)
    expected_ids, expected_scope_ids = _expected_case_sets(benchmark, request.config_ids)
    dependencies = _dependency_inventory()
    dependencies_hash = _sha256_bytes(_canonical_json_bytes(list(dependencies)))
    experiment_id = _experiment_id(
        repository,
        manifest,
        provider,
        safety_limits,
        dependencies_hash,
        request.split,
    )

    return PreflightContext(
        request=request,
        repository=repository,
        benchmark_root=benchmark_path,
        manifest=manifest,
        benchmark=benchmark,
        provider=provider,
        settings=active_settings,
        dependencies=dependencies,
        dependencies_sha256=dependencies_hash,
        safety_limits=safety_limits,
        experiment_id=experiment_id,
        expected_ids_by_config=expected_ids,
        expected_scope_ids_by_config=expected_scope_ids,
    )


@contextlib.contextmanager
def _network_disabled() -> Iterator[None]:
    original_socket = socket.socket
    original_create_connection = socket.create_connection

    def blocked(*_args: Any, **_kwargs: Any) -> Any:
        raise IntegrityError("network_access", "network access is disabled for evaluation")

    socket.socket = blocked  # type: ignore[assignment]
    socket.create_connection = blocked  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.socket = original_socket  # type: ignore[assignment]
        socket.create_connection = original_create_connection  # type: ignore[assignment]


@contextlib.contextmanager
def _isolated_audit_log(log_path: Path) -> Iterator[None]:
    original = audit_logger.settings
    audit_logger.settings = dataclasses.replace(
        original, log_path=str(log_path), enable_audit_log=True
    )
    try:
        yield
    finally:
        audit_logger.settings = original


@contextlib.contextmanager
def _internal_source_policy_enabled() -> Iterator[None]:
    original = ingestion_module.resolve_source_policy

    def internal_resolver(source_key: str):
        return resolve_source_policy(source_key, allow_internal=True)

    ingestion_module.resolve_source_policy = internal_resolver
    try:
        yield
    finally:
        ingestion_module.resolve_source_policy = original


def _batched(values: Sequence[Any], size: int) -> Iterator[Sequence[Any]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def _as_ingestion_document(document: Mapping[str, Any]) -> IngestionDocument:
    return IngestionDocument(
        external_id=document["external_id"],
        source_key=document["source_key"],
        title=document["title"],
        text=document["content"],
        metadata=document["metadata"],
    )


def _ingest_corpus(
    benchmark: LoadedBenchmark,
    retriever: SqliteBM25Retriever,
    active_settings: Settings,
) -> dict[str, str]:
    service = IngestionService(
        retriever,
        IngestionServiceConfig(
            max_batch_size=active_settings.retrieval_max_batch_size,
            chunking=ChunkingConfig(
                max_chunk_chars=active_settings.retrieval_chunk_max_chars,
                overlap_chars=active_settings.retrieval_chunk_overlap_chars,
                max_document_chars=active_settings.retrieval_max_document_chars,
            ),
        ),
    )
    statuses: dict[str, str] = {}

    for mode in ("public", "internal_only", "rejected"):
        documents = [document for document in benchmark.corpus if document["ingestion_mode"] == mode]
        for batch_number, batch in enumerate(
            _batched(documents, active_settings.retrieval_max_batch_size)
        ):
            inputs = [_as_ingestion_document(document) for document in batch]
            context = _internal_source_policy_enabled() if mode == "internal_only" else contextlib.nullcontext()
            with context:
                result = service.ingest_batch(
                    inputs,
                    request_id=f"phase12e2-ingest-{mode}-{batch_number:03d}",
                )
            by_external_id = {item.external_id: item for item in result.items}
            for document in batch:
                item = by_external_id.get(document["external_id"])
                if item is None:
                    raise IntegrityError("ingestion_mapping", "corpus ingestion result is incomplete")
                statuses[document["document_id"]] = item.status

    if len(statuses) != len(benchmark.corpus):
        raise IntegrityError("ingestion_completeness", "not every corpus document was processed")
    for document in benchmark.corpus:
        expected = "rejected" if document["ingestion_mode"] == "rejected" else "indexed"
        if statuses[document["document_id"]] != expected:
            raise IntegrityError("ingestion_policy", "corpus ingestion mode violated its policy")
        if expected == "rejected":
            canonical_id = _derive_document_id(
                document["source_key"].strip().lower(), document["external_id"].strip()
            )
            if retriever.get_document(canonical_id) is not None:
                raise IntegrityError("rejected_document_indexed", "rejected corpus material entered the index")
    return statuses


def _project_stage_results(result: RagPipelineResult, profile: GuardProfile) -> tuple[dict[str, Any], ...]:
    projected: list[dict[str, Any]] = []
    for stage in result.stage_results:
        if not _SAFE_REASON_RE.fullmatch(stage.reason_code):
            raise IntegrityError("unsafe_stage_reason", "stage reason code is not a safe identifier")
        profile_field = GUARD_STAGE_TO_FIELD.get(stage.stage)
        enabled = getattr(profile, profile_field) if profile_field else True
        decision = stage.decision.value if stage.decision is not None else None
        execution_time = result.latency_ms.get(stage.stage)
        projected.append(
            {
                "stage": stage.stage,
                "enabled": enabled,
                "decision": decision,
                "reason_code": stage.reason_code,
                "execution_time_ms": execution_time,
            }
        )
    return tuple(projected)


def _pipeline_scope_outcome(
    *,
    case: Mapping[str, Any],
    config: EvaluationConfig,
    retriever: SqliteBM25Retriever,
    provider_spec: ProviderSpec,
    request_id: str,
    ingestion_status: str | None,
) -> ScopeOutcome:
    provider = provider_spec.factory()
    started = time.perf_counter()
    result, audit_context = run_rag_query_uncommitted(
        query=case["query"],
        top_k=case["top_k"],
        retriever=retriever,
        request_id=request_id,
        provider=provider,
        guard_profile=config.profile,
    )
    commit_rag_query_audit(result, audit_context)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return ScopeOutcome(
        final_decision=result.final_decision.value,
        stop_reason=result.stop_reason,
        provider_called=result.provider_called,
        retrieved_count=result.retrieved_count,
        accepted_context_count=result.accepted_context_count,
        rejected_context_count=result.rejected_context_count,
        redaction_count=result.redaction_count,
        dlp_finding_categories=dict(result.dlp_finding_categories),
        stage_results=_project_stage_results(result, config.profile),
        pipeline_pre_audit_ms=result.latency_ms.get("total"),
        end_to_end_with_audit_ms=elapsed_ms,
        document_ingestion_status=ingestion_status,
    )


def _relevant_ingestion_status(
    case: Mapping[str, Any], statuses: Mapping[str, str]
) -> str | None:
    relevant = case["relevant_document_ids"]
    if not relevant:
        return None
    values = {statuses.get(document_id, "missing") for document_id in relevant}
    return next(iter(values)) if len(values) == 1 else "mixed"


def _component_scope_outcome(
    *,
    case: Mapping[str, Any],
    retriever: SqliteBM25Retriever,
    ingestion_status: str | None,
    corpus_by_id: Mapping[str, Mapping[str, Any]],
) -> ScopeOutcome:
    if ingestion_status != "rejected":
        raise IntegrityError("component_ingestion", "component rejected material was not rejected")

    target_document_ids: set[str] = set()
    for document_id in case["relevant_document_ids"]:
        document = corpus_by_id.get(document_id)
        if document is None:
            raise IntegrityError("component_identity", "component target is missing from corpus")
        target_document_ids.add(
            _derive_document_id(
                document["source_key"].strip().lower(), document["external_id"].strip()
            )
        )

    started = time.perf_counter()
    retrieval = retriever.search(
        RetrievalQuery(query=case["query"], top_k=case["top_k"])
    )
    target_hits = tuple(
        hit for hit in retrieval.hits if hit.document_id in target_document_ids
    )
    if target_hits:
        raise IntegrityError(
            "rejected_document_retrievable",
            "rejected component material became retrievable",
        )

    return ScopeOutcome(
        final_decision=Decision.ALLOW.value,
        stop_reason="no_hits",
        provider_called=False,
        retrieved_count=retrieval.total_hits,
        accepted_context_count=0,
        rejected_context_count=0,
        redaction_count=0,
        dlp_finding_categories={},
        stage_results=(),
        pipeline_pre_audit_ms=None,
        end_to_end_with_audit_ms=(time.perf_counter() - started) * 1000.0,
        document_ingestion_status=ingestion_status,
        target_document_hit_count=len(target_hits),
    )


def _execute_scope(
    *,
    case: Mapping[str, Any],
    config: EvaluationConfig,
    retriever: SqliteBM25Retriever,
    provider_spec: ProviderSpec,
    ingestion_statuses: Mapping[str, str],
    active_settings: Settings | WorkerRuntimeSettings,
    corpus_by_id: Mapping[str, Mapping[str, Any]] | None = None,
    repetition: int,
) -> ScopeOutcome:
    scope = case["evaluation_scope"]
    if scope != "end_to_end" and config.config_id != "C0_all_on":
        raise IntegrityError("scope_config", "non-end-to-end scopes are C0-only")
    request_id = _sha256_bytes(
        f"{config.config_id}:{case['case_id']}:{repetition}".encode("utf-8")
    )[:32]

    if scope == "availability_fault":
        if case["top_k"] <= active_settings.rag_max_top_k:
            raise IntegrityError("availability_contract", "availability case does not exceed top_k policy")
        started = time.perf_counter()
        audit_top_k_rejected(
            request_id=request_id,
            query=case["query"],
            configured_max_top_k=active_settings.rag_max_top_k,
        )
        return ScopeOutcome(
            final_decision=Decision.BLOCK.value,
            stop_reason=STOP_TOP_K_REJECTED,
            provider_called=False,
            retrieved_count=0,
            accepted_context_count=0,
            rejected_context_count=0,
            redaction_count=0,
            dlp_finding_categories={},
            stage_results=(),
            pipeline_pre_audit_ms=None,
            end_to_end_with_audit_ms=(time.perf_counter() - started) * 1000.0,
            document_ingestion_status=None,
        )

    ingestion_status = _relevant_ingestion_status(case, ingestion_statuses)
    if scope == "component":
        if corpus_by_id is None:
            raise IntegrityError("component_identity", "component corpus identity is unavailable")
        return _component_scope_outcome(
            case=case,
            retriever=retriever,
            ingestion_status=ingestion_status,
            corpus_by_id=corpus_by_id,
        )
    return _pipeline_scope_outcome(
        case=case,
        config=config,
        retriever=retriever,
        provider_spec=provider_spec,
        request_id=request_id,
        ingestion_status=ingestion_status,
    )


_WORKER_OUTCOME_FIELDS = frozenset(
    {
        "final_decision",
        "stop_reason",
        "provider_called",
        "retrieved_count",
        "accepted_context_count",
        "rejected_context_count",
        "redaction_count",
        "dlp_finding_categories",
        "stage_results",
        "pipeline_pre_audit_ms",
        "end_to_end_with_audit_ms",
        "document_ingestion_status",
        "target_document_hit_count",
    }
)


def _scope_outcome_to_transport(outcome: ScopeOutcome) -> dict[str, Any]:
    return {
        "final_decision": outcome.final_decision,
        "stop_reason": outcome.stop_reason,
        "provider_called": outcome.provider_called,
        "retrieved_count": outcome.retrieved_count,
        "accepted_context_count": outcome.accepted_context_count,
        "rejected_context_count": outcome.rejected_context_count,
        "redaction_count": outcome.redaction_count,
        "dlp_finding_categories": dict(outcome.dlp_finding_categories),
        "stage_results": [dict(stage) for stage in outcome.stage_results],
        "pipeline_pre_audit_ms": outcome.pipeline_pre_audit_ms,
        "end_to_end_with_audit_ms": outcome.end_to_end_with_audit_ms,
        "document_ingestion_status": outcome.document_ingestion_status,
        "target_document_hit_count": outcome.target_document_hit_count,
    }


def _transport_nonnegative_int(value: Any, field_name: str) -> int:
    if type(value) is not int or value < 0:
        raise IntegrityError("worker_protocol", f"worker {field_name} is invalid")
    return value


def _transport_timing(value: Any, field_name: str, *, nullable: bool) -> float | None:
    if value is None and nullable:
        return None
    if type(value) not in {int, float} or not math.isfinite(value) or value < 0:
        raise IntegrityError("worker_protocol", f"worker {field_name} is invalid")
    return float(value)


def _scope_outcome_from_transport(value: Any) -> ScopeOutcome:
    if not isinstance(value, dict) or set(value) != _WORKER_OUTCOME_FIELDS:
        raise IntegrityError("worker_protocol", "worker outcome shape is invalid")
    scan_forbidden_artifact_content(value, location="worker.outcome")

    final_decision = value["final_decision"]
    if final_decision not in {decision.value for decision in Decision}:
        raise IntegrityError("worker_protocol", "worker decision is invalid")
    stop_reason = value["stop_reason"]
    if not isinstance(stop_reason, str) or not _SAFE_REASON_RE.fullmatch(stop_reason):
        raise IntegrityError("worker_protocol", "worker stop reason is invalid")
    if type(value["provider_called"]) is not bool:
        raise IntegrityError("worker_protocol", "worker provider state is invalid")

    findings = value["dlp_finding_categories"]
    if not isinstance(findings, dict):
        raise IntegrityError("worker_protocol", "worker DLP findings are invalid")
    safe_findings: dict[str, int] = {}
    for category, count in findings.items():
        if not isinstance(category, str) or not _SAFE_REASON_RE.fullmatch(category):
            raise IntegrityError("worker_protocol", "worker DLP category is invalid")
        safe_findings[category] = _transport_nonnegative_int(count, "DLP count")

    stages = value["stage_results"]
    if not isinstance(stages, list):
        raise IntegrityError("worker_protocol", "worker stage results are invalid")
    safe_stages: list[dict[str, Any]] = []
    expected_stage_fields = {
        "stage",
        "enabled",
        "decision",
        "reason_code",
        "execution_time_ms",
    }
    for stage in stages:
        if not isinstance(stage, dict) or set(stage) != expected_stage_fields:
            raise IntegrityError("worker_protocol", "worker stage result shape is invalid")
        if not isinstance(stage["stage"], str) or not _SAFE_REASON_RE.fullmatch(stage["stage"]):
            raise IntegrityError("worker_protocol", "worker stage identity is invalid")
        if type(stage["enabled"]) is not bool:
            raise IntegrityError("worker_protocol", "worker stage enabled state is invalid")
        if stage["decision"] is not None and stage["decision"] not in {
            decision.value for decision in Decision
        }:
            raise IntegrityError("worker_protocol", "worker stage decision is invalid")
        if not isinstance(stage["reason_code"], str) or not _SAFE_REASON_RE.fullmatch(
            stage["reason_code"]
        ):
            raise IntegrityError("worker_protocol", "worker stage reason is invalid")
        safe_stages.append(
            {
                "stage": stage["stage"],
                "enabled": stage["enabled"],
                "decision": stage["decision"],
                "reason_code": stage["reason_code"],
                "execution_time_ms": _transport_timing(
                    stage["execution_time_ms"], "stage timing", nullable=True
                ),
            }
        )

    document_status = value["document_ingestion_status"]
    if document_status is not None and (
        not isinstance(document_status, str)
        or not _SAFE_REASON_RE.fullmatch(document_status)
    ):
        raise IntegrityError("worker_protocol", "worker ingestion status is invalid")
    target_count = value["target_document_hit_count"]
    if target_count is not None:
        target_count = _transport_nonnegative_int(target_count, "target hit count")

    return ScopeOutcome(
        final_decision=final_decision,
        stop_reason=stop_reason,
        provider_called=value["provider_called"],
        retrieved_count=_transport_nonnegative_int(value["retrieved_count"], "retrieved count"),
        accepted_context_count=_transport_nonnegative_int(
            value["accepted_context_count"], "accepted context count"
        ),
        rejected_context_count=_transport_nonnegative_int(
            value["rejected_context_count"], "rejected context count"
        ),
        redaction_count=_transport_nonnegative_int(value["redaction_count"], "redaction count"),
        dlp_finding_categories=safe_findings,
        stage_results=tuple(safe_stages),
        pipeline_pre_audit_ms=_transport_timing(
            value["pipeline_pre_audit_ms"], "pipeline timing", nullable=True
        ),
        end_to_end_with_audit_ms=_transport_timing(
            value["end_to_end_with_audit_ms"], "end-to-end timing", nullable=False
        ),
        document_ingestion_status=document_status,
        target_document_hit_count=target_count,
    )


def _validate_worker_init_payload(
    payload: Mapping[str, Any],
) -> tuple[
    EvaluationConfig,
    SqliteBM25Retriever,
    ProviderSpec,
    WorkerRuntimeSettings,
    Mapping[str, str],
    Mapping[str, Mapping[str, Any]],
    Path,
]:
    expected_fields = {
        "protocol_version",
        "config_id",
        "config_hash",
        "profile_id",
        "database_path",
        "repo_root",
        "production_database_path",
        "audit_log_path",
        "runtime_settings",
        "provider_id",
        "provider_behavior_hash",
        "ingestion_statuses",
        "corpus_by_id",
    }
    if not isinstance(payload, dict) or set(payload) != expected_fields:
        raise IntegrityError("worker_init", "worker initialization payload is malformed")
    if payload["protocol_version"] != WORKER_PROTOCOL_VERSION:
        raise IntegrityError("worker_init", "worker protocol version is unsupported")

    config_id = payload["config_id"]
    if config_id not in CONFIG_REGISTRY:
        raise IntegrityError("worker_init", "worker configuration is not approved")
    config = CONFIG_REGISTRY[config_id]
    if payload["config_hash"] != config.config_hash or payload["profile_id"] != config.profile.profile_id:
        raise IntegrityError("worker_init", "worker configuration identity changed")

    path_fields = ("database_path", "repo_root", "production_database_path", "audit_log_path")
    if not all(isinstance(payload[field_name], str) for field_name in path_fields):
        raise IntegrityError("worker_init", "worker path identity is invalid")
    database_path = Path(payload["database_path"])
    repo_root = Path(payload["repo_root"])
    production_database = Path(payload["production_database_path"])
    audit_log_path = Path(payload["audit_log_path"])
    if not all(path.is_absolute() for path in (database_path, repo_root, production_database, audit_log_path)):
        raise IntegrityError("worker_init", "worker paths must be absolute")
    database_path = database_path.resolve()
    repo_root = repo_root.resolve()
    production_database = production_database.resolve()
    audit_log_path = audit_log_path.resolve()
    if (
        not database_path.is_file()
        or _is_within(database_path, repo_root)
        or database_path == production_database
    ):
        raise IntegrityError("worker_database", "worker database boundary is invalid")
    if _is_within(audit_log_path, repo_root):
        raise IntegrityError("worker_audit", "worker audit sink must remain outside repository")

    runtime_settings = _load_worker_runtime_settings(payload["runtime_settings"])
    if _worker_runtime_settings_payload(load_settings()) != payload["runtime_settings"]:
        raise IntegrityError("worker_settings", "worker environment differs from parent settings")
    if payload["provider_id"] != SUPPORTED_PROVIDER_ID:
        raise IntegrityError("worker_provider", "worker provider is not approved")
    provider_spec = default_provider_spec(SUPPORTED_PROVIDER_ID, runtime_settings)
    _validate_provider(provider_spec, allow_test_provider=False)
    _validate_provider_environment(provider_spec)
    if payload["provider_behavior_hash"] != provider_spec.behavior_hash:
        raise IntegrityError("worker_provider", "worker provider identity changed")

    statuses = payload["ingestion_statuses"]
    corpus_by_id = payload["corpus_by_id"]
    if not isinstance(statuses, dict) or not all(
        isinstance(key, str) and isinstance(status, str)
        for key, status in statuses.items()
    ):
        raise IntegrityError("worker_init", "worker ingestion status mapping is invalid")
    if not isinstance(corpus_by_id, dict) or not all(
        isinstance(key, str)
        and isinstance(document, dict)
        and set(document) == {"source_key", "external_id"}
        and all(isinstance(item, str) and item for item in document.values())
        for key, document in corpus_by_id.items()
    ):
        raise IntegrityError("worker_init", "worker corpus identity mapping is invalid")

    retriever = SqliteBM25Retriever(
        SqliteBM25Config(
            db_path=str(database_path),
            busy_timeout_ms=runtime_settings.retrieval_busy_timeout_ms,
            max_query_chars=runtime_settings.retrieval_max_query_chars,
            max_query_terms=runtime_settings.retrieval_max_query_terms,
            max_top_k=runtime_settings.retrieval_max_top_k,
        )
    )
    return (
        config,
        retriever,
        provider_spec,
        runtime_settings,
        statuses,
        corpus_by_id,
        audit_log_path,
    )


def _case_worker_main(connection: Connection, init_payload: Mapping[str, Any]) -> None:
    """Spawn-safe worker loop. It can read the temporary DB and safe audit sink only."""
    try:
        (
            config,
            retriever,
            provider_spec,
            runtime_settings,
            ingestion_statuses,
            corpus_by_id,
            audit_log_path,
        ) = _validate_worker_init_payload(init_payload)
    except IntegrityError as exc:
        try:
            connection.send({"kind": "fatal", "error_category": exc.code})
        except (BrokenPipeError, EOFError, OSError):
            pass
        finally:
            connection.close()
        return
    except Exception:
        try:
            connection.send({"kind": "fatal", "error_category": "worker_initialization_failed"})
        except (BrokenPipeError, EOFError, OSError):
            pass
        finally:
            connection.close()
        return

    try:
        with _isolated_audit_log(audit_log_path), _network_disabled():
            connection.send(
                {
                    "kind": "ready",
                    "protocol_version": WORKER_PROTOCOL_VERSION,
                    "worker_pid": os.getpid(),
                }
            )
            while True:
                task = connection.recv()
                if task == {"kind": "stop", "protocol_version": WORKER_PROTOCOL_VERSION}:
                    connection.send(
                        {"kind": "stopped", "protocol_version": WORKER_PROTOCOL_VERSION}
                    )
                    return
                if (
                    not isinstance(task, dict)
                    or set(task) != {"kind", "protocol_version", "case", "repetition"}
                    or task.get("kind") != "case"
                    or task.get("protocol_version") != WORKER_PROTOCOL_VERSION
                    or not isinstance(task.get("case"), dict)
                    or type(task.get("repetition")) is not int
                    or task["repetition"] < 0
                ):
                    connection.send(
                        {"kind": "fatal", "error_category": "worker_task_invalid"}
                    )
                    return
                try:
                    outcome = _execute_scope(
                        case=task["case"],
                        config=config,
                        retriever=retriever,
                        provider_spec=provider_spec,
                        ingestion_statuses=ingestion_statuses,
                        active_settings=runtime_settings,
                        corpus_by_id=corpus_by_id,
                        repetition=task["repetition"],
                    )
                    response = {
                        "kind": "outcome",
                        "outcome": _scope_outcome_to_transport(outcome),
                    }
                    scan_forbidden_artifact_content(response, location="worker.response")
                    connection.send(response)
                except IntegrityError:
                    connection.send(
                        {"kind": "fatal", "error_category": "worker_integrity_failure"}
                    )
                    return
                except (FTS5UnavailableError, IngestionBatchError):
                    connection.send(
                        {"kind": "fatal", "error_category": "worker_database_failure"}
                    )
                    return
                except Exception:
                    connection.send(
                        {
                            "kind": "case_error",
                            "error_category": "case_execution_error",
                            "state_trustworthy": True,
                        }
                    )
    except (BrokenPipeError, EOFError, OSError):
        return
    finally:
        connection.close()


class _SpawnCaseWorker:
    """Parent-owned, killable spawn worker with no artifact-writing capability."""

    def __init__(
        self,
        *,
        config_id: str,
        init_payload: Mapping[str, Any],
        audit_directory: Path,
        entrypoint: Callable[[Connection, Mapping[str, Any]], None] | None,
        lifecycle_observer: Callable[[str, int], None] | None,
    ) -> None:
        self._context = multiprocessing.get_context("spawn")
        self._config_id = config_id
        self._base_init_payload = dict(init_payload)
        self._audit_directory = audit_directory
        self._entrypoint = entrypoint or _case_worker_main
        self._observer = lifecycle_observer
        self._process: multiprocessing.Process | None = None
        self._connection: Connection | None = None
        self._generation = 0

    def _observe(self, event: str, pid: int) -> None:
        if self._observer is not None:
            try:
                self._observer(event, pid)
            except Exception:
                pass

    def _drop_handles(self) -> None:
        process = self._process
        if self._connection is not None:
            self._connection.close()
        if process is not None:
            if process.pid is not None and process.is_alive():
                raise IntegrityError("worker_orphan", "live worker handle cannot be discarded")
            try:
                process.close()
            except ValueError:
                pass
        self._connection = None
        self._process = None

    def _force_stop(self) -> None:
        process = self._process
        if process is None:
            self._drop_handles()
            return
        if process.pid is None:
            self._drop_handles()
            return
        pid = process.pid or -1
        if process.is_alive():
            process.terminate()
            self._observe("terminate", pid)
            process.join(WORKER_SHUTDOWN_TIMEOUT_SECONDS)
        if process.is_alive():
            process.kill()
            self._observe("kill", pid)
            process.join(WORKER_SHUTDOWN_TIMEOUT_SECONDS)
        if process.is_alive() or process.exitcode is None:
            raise IntegrityError("worker_orphan", "worker process could not be terminated")
        self._observe("joined", pid)
        self._drop_handles()

    def _start(self) -> None:
        if self._process is not None:
            return
        self._generation += 1
        parent_connection, child_connection = self._context.Pipe(duplex=True)
        init_payload = dict(self._base_init_payload)
        init_payload["audit_log_path"] = str(
            (self._audit_directory / f"audit-worker-{self._generation:04d}.jsonl").resolve()
        )
        process = self._context.Process(
            target=self._entrypoint,
            args=(child_connection, init_payload),
            name=f"phase12e2-case-worker-{self._config_id}-{self._generation}",
            daemon=False,
        )
        self._process = process
        self._connection = parent_connection
        try:
            process.start()
            child_connection.close()
            self._observe("started", process.pid or -1)
            if not parent_connection.poll(WORKER_STARTUP_TIMEOUT_SECONDS):
                self._force_stop()
                raise IntegrityError("worker_startup", "worker did not become ready")
            try:
                ready = parent_connection.recv()
            except (EOFError, OSError) as exc:
                self._force_stop()
                raise IntegrityError("worker_startup", "worker exited before readiness") from exc
            if (
                isinstance(ready, dict)
                and ready.get("kind") == "fatal"
                and isinstance(ready.get("error_category"), str)
                and _SAFE_REASON_RE.fullmatch(ready["error_category"])
            ):
                category = ready["error_category"]
                self._force_stop()
                raise IntegrityError("worker_startup", f"worker startup failed: {category}")
            if (
                not isinstance(ready, dict)
                or ready.get("kind") != "ready"
                or ready.get("protocol_version") != WORKER_PROTOCOL_VERSION
                or ready.get("worker_pid") != process.pid
            ):
                self._force_stop()
                raise IntegrityError("worker_startup", "worker readiness response is invalid")
            if not process.is_alive():
                self._force_stop()
                raise IntegrityError("worker_startup", "worker exited after readiness")
        except Exception:
            child_connection.close()
            if self._process is not None:
                self._force_stop()
            raise

    def execute(self, task: Mapping[str, Any], timeout_seconds: float) -> dict[str, Any]:
        self._start()
        process = self._process
        connection = self._connection
        if process is None or connection is None:
            raise IntegrityError("worker_state", "worker is unavailable")
        try:
            connection.send(dict(task))
        except (BrokenPipeError, EOFError, OSError) as exc:
            self._force_stop()
            raise IntegrityError("worker_state", "worker task could not be submitted") from exc
        if not connection.poll(timeout_seconds):
            timed_out_pid = process.pid or -1
            self._force_stop()
            return {
                "kind": "timeout",
                "error_category": "case_timeout",
                "terminated_worker_pid": timed_out_pid,
            }
        try:
            response = connection.recv()
        except (EOFError, OSError) as exc:
            self._force_stop()
            raise IntegrityError("worker_state", "worker exited without a result") from exc
        if not isinstance(response, dict) or not isinstance(response.get("kind"), str):
            self._force_stop()
            raise IntegrityError("worker_protocol", "worker response is malformed")
        if response["kind"] == "fatal":
            self._force_stop()
            raise IntegrityError("worker_integrity", "worker reported a fatal integrity failure")
        if response["kind"] == "case_error" and response != {
            "kind": "case_error",
            "error_category": "case_execution_error",
            "state_trustworthy": True,
        }:
            self._force_stop()
            raise IntegrityError("worker_protocol", "worker error response is invalid")
        if response["kind"] not in {"outcome", "case_error"}:
            self._force_stop()
            raise IntegrityError("worker_protocol", "worker response kind is unsupported")
        if not process.is_alive():
            self._force_stop()
            raise IntegrityError("worker_state", "worker exited after returning a case result")
        return response

    def close(self) -> None:
        process = self._process
        connection = self._connection
        if process is None:
            return
        if connection is None or not process.is_alive():
            self._force_stop()
            return
        try:
            connection.send(
                {"kind": "stop", "protocol_version": WORKER_PROTOCOL_VERSION}
            )
            if not connection.poll(WORKER_SHUTDOWN_TIMEOUT_SECONDS):
                self._force_stop()
                raise IntegrityError("worker_shutdown", "worker did not acknowledge shutdown")
            stopped = connection.recv()
            if stopped != {
                "kind": "stopped",
                "protocol_version": WORKER_PROTOCOL_VERSION,
            }:
                self._force_stop()
                raise IntegrityError("worker_shutdown", "worker shutdown response is invalid")
            process.join(WORKER_SHUTDOWN_TIMEOUT_SECONDS)
            if process.is_alive():
                self._force_stop()
                raise IntegrityError("worker_shutdown", "worker did not exit after shutdown")
            self._observe("stopped", process.pid or -1)
            self._drop_handles()
        except (BrokenPipeError, EOFError, OSError) as exc:
            self._force_stop()
            raise IntegrityError("worker_shutdown", "worker shutdown failed") from exc


def _safe_stage_without_timing(stage: Mapping[str, Any]) -> dict[str, Any]:
    return {**stage, "execution_time_ms": None}


def _case_error_record(
    *,
    case: Mapping[str, Any],
    label: Mapping[str, Any],
    config: EvaluationConfig,
    ordinal: int,
    repository: RepositoryState,
    manifest: ManifestIdentity,
    split: str,
    status: str,
    error_category: str,
) -> dict[str, Any]:
    if error_category not in SAFE_ERROR_CATEGORIES:
        raise IntegrityError("error_category", "case error category is not allow-listed")
    expected_status = "timeout" if error_category == "case_timeout" else "error"
    if status != expected_status:
        raise IntegrityError("case_status", "case status does not match its error category")
    return {
        "case_id": case["case_id"],
        "case_ordinal": ordinal,
        "config_id": config.config_id,
        "config_hash": config.config_hash,
        "profile_id": config.profile.profile_id,
        "split": split,
        "scenario_family": case["scenario_family"],
        "category": label["category"],
        "evaluation_scope": case["evaluation_scope"],
        "observation_namespace": OBSERVATION_NAMESPACES[case["evaluation_scope"]],
        "git_commit": repository.commit,
        "benchmark_manifest_sha256": manifest.sha256,
        "case_status": status,
        "error_category": error_category,
        "expected_outcome": {
            "allowed_final_decisions": list(label["allowed_final_decisions"]),
            "allowed_stop_reasons": list(label["allowed_stop_reasons"]),
            "provider_called": label["expected_provider_called"],
        },
        "actual_final_decision": None,
        "actual_stop_reason": None,
        "actual_provider_called": None,
        "actual_retrieved_count": None,
        "actual_accepted_context_count": None,
        "actual_rejected_context_count": None,
        "actual_redaction_count": None,
        "actual_dlp_finding_categories": {},
        "actual_document_ingestion_status": None,
        "actual_target_document_hit_count": None,
        "correct": False,
        "leakage_eligible": False,
        "leakage_observed": False,
        "stage_results": [],
        "latency_ms_samples": {
            "pipeline_pre_audit_total": [],
            "end_to_end_with_audit": [],
        },
    }


def _case_completed_record(
    *,
    case: Mapping[str, Any],
    label: Mapping[str, Any],
    config: EvaluationConfig,
    ordinal: int,
    repository: RepositoryState,
    manifest: ManifestIdentity,
    split: str,
    outcome: ScopeOutcome,
) -> dict[str, Any]:
    correct = (
        outcome.final_decision in label["allowed_final_decisions"]
        and outcome.stop_reason in label["allowed_stop_reasons"]
    )
    pipeline_samples = (
        [outcome.pipeline_pre_audit_ms] if outcome.pipeline_pre_audit_ms is not None else []
    )
    return {
        "case_id": case["case_id"],
        "case_ordinal": ordinal,
        "config_id": config.config_id,
        "config_hash": config.config_hash,
        "profile_id": config.profile.profile_id,
        "split": split,
        "scenario_family": case["scenario_family"],
        "category": label["category"],
        "evaluation_scope": case["evaluation_scope"],
        "observation_namespace": OBSERVATION_NAMESPACES[case["evaluation_scope"]],
        "git_commit": repository.commit,
        "benchmark_manifest_sha256": manifest.sha256,
        "case_status": "completed",
        "error_category": None,
        "expected_outcome": {
            "allowed_final_decisions": list(label["allowed_final_decisions"]),
            "allowed_stop_reasons": list(label["allowed_stop_reasons"]),
            "provider_called": label["expected_provider_called"],
        },
        "actual_final_decision": outcome.final_decision,
        "actual_stop_reason": outcome.stop_reason,
        "actual_provider_called": outcome.provider_called,
        "actual_retrieved_count": outcome.retrieved_count,
        "actual_accepted_context_count": outcome.accepted_context_count,
        "actual_rejected_context_count": outcome.rejected_context_count,
        "actual_redaction_count": outcome.redaction_count,
        "actual_dlp_finding_categories": dict(outcome.dlp_finding_categories),
        "actual_document_ingestion_status": outcome.document_ingestion_status,
        "actual_target_document_hit_count": outcome.target_document_hit_count,
        "correct": correct,
        "leakage_eligible": False,
        "leakage_observed": False,
        "stage_results": [dict(stage) for stage in outcome.stage_results],
        "latency_ms_samples": {
            "pipeline_pre_audit_total": pipeline_samples,
            "end_to_end_with_audit": [outcome.end_to_end_with_audit_ms],
        },
    }


def _execute_case_record(
    *,
    case: Mapping[str, Any],
    label: Mapping[str, Any],
    config: EvaluationConfig,
    ordinal: int,
    repetition: int,
    worker: _SpawnCaseWorker,
    repository: RepositoryState,
    manifest: ManifestIdentity,
    split: str,
    timeout_seconds: float,
    timeout_recovery_check: Callable[[Mapping[str, Any]], None],
) -> dict[str, Any]:
    response = worker.execute(
        {
            "kind": "case",
            "protocol_version": WORKER_PROTOCOL_VERSION,
            "case": dict(case),
            "repetition": repetition,
        },
        timeout_seconds,
    )
    if response["kind"] == "timeout":
        timeout_recovery_check(case)
        return _case_error_record(
            case=case,
            label=label,
            config=config,
            ordinal=ordinal,
            repository=repository,
            manifest=manifest,
            split=split,
            status="timeout",
            error_category="case_timeout",
        )
    if response["kind"] == "case_error":
        return _case_error_record(
            case=case,
            label=label,
            config=config,
            ordinal=ordinal,
            repository=repository,
            manifest=manifest,
            split=split,
            status="error",
            error_category="case_execution_error",
        )
    outcome = _scope_outcome_from_transport(response.get("outcome"))
    return _case_completed_record(
        case=case,
        label=label,
        config=config,
        ordinal=ordinal,
        repository=repository,
        manifest=manifest,
        split=split,
        outcome=outcome,
    )


def _deterministic_projection(record: Mapping[str, Any]) -> dict[str, Any]:
    projected = dict(record)
    projected.pop("latency_ms_samples", None)
    projected["stage_results"] = [
        _safe_stage_without_timing(stage) for stage in record.get("stage_results", [])
    ]
    return projected


def validate_repetition_determinism(
    first_pass: Sequence[Mapping[str, Any]],
    second_pass: Sequence[Mapping[str, Any]],
) -> None:
    if len(first_pass) != len(second_pass):
        raise IntegrityError(
            "non_deterministic_outcome",
            "repetition case counts differ",
        )
    for first, second in zip(first_pass, second_pass, strict=True):
        if first.get("case_id") != second.get("case_id") or (
            _canonical_json_bytes(_deterministic_projection(first))
            != _canonical_json_bytes(_deterministic_projection(second))
        ):
            raise IntegrityError(
                "non_deterministic_outcome",
                "decision or content-free telemetry changed across repetitions",
            )


def _merge_repetition_latency(
    first: dict[str, Any], second: Mapping[str, Any]
) -> dict[str, Any]:
    merged = dict(first)
    merged["latency_ms_samples"] = {
        key: list(first["latency_ms_samples"].get(key, []))
        + list(second["latency_ms_samples"].get(key, []))
        for key in ("pipeline_pre_audit_total", "end_to_end_with_audit")
    }
    return merged


def validate_case_completeness(
    records: Sequence[Mapping[str, Any]],
    expected_ids: Sequence[str],
    expected_scope_ids: Mapping[str, Sequence[str]],
) -> None:
    actual_ids = [record.get("case_id") for record in records]
    if len(actual_ids) != len(set(actual_ids)):
        raise IntegrityError("duplicate_case", "result contains a duplicate case")
    if tuple(actual_ids) != tuple(expected_ids):
        raise IntegrityError("missing_or_unexpected_case", "result case set is incomplete or unexpected")
    for scope, scope_ids in expected_scope_ids.items():
        actual_scope_ids = tuple(
            record["case_id"] for record in records if record.get("evaluation_scope") == scope
        )
        if actual_scope_ids != tuple(scope_ids):
            raise IntegrityError("scope_completeness", f"scope case set mismatch: {scope}")


def summarize_case_statuses(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    counts = {"completed": 0, "error": 0, "timeout": 0}
    for record in records:
        status = record.get("case_status")
        if status not in counts:
            raise IntegrityError("case_status", "result contains an unsupported case status")
        counts[status] += 1
    return {
        "run_status": (
            "complete" if counts["error"] == 0 and counts["timeout"] == 0 else "partial"
        ),
        "completed_case_count": counts["completed"],
        "error_case_count": counts["error"],
        "timeout_case_count": counts["timeout"],
    }


def _temporary_parent(hooks: RunnerHooks, repo_root: Path) -> Path | None:
    if hooks.temp_parent is None:
        return None
    resolved = hooks.temp_parent.resolve()
    if _is_within(resolved, repo_root.resolve()):
        raise IntegrityError("temporary_path", "temporary evaluation state must be outside repository")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _build_worker_init_payload(
    *,
    context: PreflightContext,
    config: EvaluationConfig,
    repo_root: Path,
    database_path: Path,
    production_database_path: Path,
    ingestion_statuses: Mapping[str, str],
) -> dict[str, Any]:
    if context.provider.provider_id != SUPPORTED_PROVIDER_ID or context.provider.test_only:
        raise IntegrityError(
            "worker_provider",
            "process-isolated evaluation supports only the approved mock provider",
        )
    corpus_identity = {
        document["document_id"]: {
            "source_key": document["source_key"],
            "external_id": document["external_id"],
        }
        for document in context.benchmark.corpus
    }
    return {
        "protocol_version": WORKER_PROTOCOL_VERSION,
        "config_id": config.config_id,
        "config_hash": config.config_hash,
        "profile_id": config.profile.profile_id,
        "database_path": str(database_path.resolve()),
        "repo_root": str(repo_root.resolve()),
        "production_database_path": str(production_database_path.resolve()),
        "runtime_settings": _worker_runtime_settings_payload(context.settings),
        "provider_id": context.provider.provider_id,
        "provider_behavior_hash": context.provider.behavior_hash,
        "ingestion_statuses": dict(ingestion_statuses),
        "corpus_by_id": corpus_identity,
    }


def _verify_timeout_recovery_state(
    *,
    case: Mapping[str, Any],
    database_path: Path,
    database_sha256: str,
    temp_root: Path,
    context: PreflightContext,
    repo_root: Path,
    hooks: RunnerHooks,
) -> None:
    if not database_path.is_file() or _sha256_file(database_path) != database_sha256:
        raise IntegrityError(
            "timeout_state_corruption",
            "temporary retrieval state changed during timed-out execution",
        )
    sidecars = tuple(
        path
        for path in (
            Path(f"{database_path}-journal"),
            Path(f"{database_path}-wal"),
            Path(f"{database_path}-shm"),
        )
        if path.exists()
    )
    if sidecars:
        raise IntegrityError(
            "timeout_state_corruption",
            "temporary retrieval state retained an unexpected sidecar",
        )

    manifest = verify_frozen_manifest(context.benchmark_root)
    if manifest != context.manifest:
        raise IntegrityError(
            "timeout_identity_corruption",
            "benchmark identity changed during timed-out execution",
        )
    repository = hooks.repository_state_loader(repo_root)
    if repository != context.repository or repository.dirty:
        raise IntegrityError(
            "timeout_identity_corruption",
            "repository identity changed during timed-out execution",
        )

    raw_query = case["query"].encode("utf-8")
    for audit_path in sorted(temp_root.glob("audit-worker-*.jsonl")):
        audit_bytes = audit_path.read_bytes()
        if raw_query in audit_bytes or any(
            marker in audit_bytes
            for marker in (b"V2TOK", b"FAKE-SECRET-", b"BEGIN PRIVATE KEY")
        ):
            raise IntegrityError(
                "timeout_audit_leak",
                "timed-out worker audit output contains forbidden raw material",
            )


def _execute_config(
    context: PreflightContext,
    config: EvaluationConfig,
    *,
    repo_root: Path,
    hooks: RunnerHooks,
    run_id: str,
) -> dict[str, Any]:
    expected_ids = context.expected_ids_by_config[config.config_id]
    cases_by_id = {case["case_id"]: case for case in context.benchmark.cases}
    temp_parent = _temporary_parent(hooks, repo_root)
    temp_name: str | None = None
    records: list[dict[str, Any]] = []

    try:
        with tempfile.TemporaryDirectory(prefix="phase12e2-", dir=temp_parent) as temporary:
            temp_name = temporary
            temp_root = Path(temporary).resolve()
            if _is_within(temp_root, repo_root.resolve()):
                raise IntegrityError("temporary_path", "temporary evaluation state entered repository")
            database_path = temp_root / "evaluation.sqlite3"
            production_db = (repo_root / context.settings.retrieval_db_path).resolve()
            if database_path.resolve() == production_db:
                raise IntegrityError("production_database", "production retrieval database is prohibited")

            retriever = SqliteBM25Retriever(
                SqliteBM25Config(
                    db_path=str(database_path),
                    busy_timeout_ms=context.settings.retrieval_busy_timeout_ms,
                    max_query_chars=context.settings.retrieval_max_query_chars,
                    max_query_terms=context.settings.retrieval_max_query_terms,
                    max_top_k=context.settings.retrieval_max_top_k,
                )
            )
            retriever.initialize()
            with _isolated_audit_log(temp_root / "audit-ingestion.jsonl"), _network_disabled():
                ingestion_statuses = _ingest_corpus(
                    context.benchmark, retriever, context.settings
                )

            database_sha256 = _sha256_file(database_path)
            worker = _SpawnCaseWorker(
                config_id=config.config_id,
                init_payload=_build_worker_init_payload(
                    context=context,
                    config=config,
                    repo_root=repo_root,
                    database_path=database_path,
                    production_database_path=production_db,
                    ingestion_statuses=ingestion_statuses,
                ),
                audit_directory=temp_root,
                entrypoint=hooks.worker_entrypoint,
                lifecycle_observer=hooks.worker_lifecycle_observer,
            )

            def verify_timeout_recovery(case: Mapping[str, Any]) -> None:
                _verify_timeout_recovery_state(
                    case=case,
                    database_path=database_path,
                    database_sha256=database_sha256,
                    temp_root=temp_root,
                    context=context,
                    repo_root=repo_root,
                    hooks=hooks,
                )

            try:
                first_pass: list[dict[str, Any]] = []
                second_pass: list[dict[str, Any]] = []
                for ordinal, case_id in enumerate(expected_ids):
                    case = cases_by_id[case_id]
                    label = context.benchmark.labels_by_id[case_id]
                    first_pass.append(
                        _execute_case_record(
                            case=case,
                            label=label,
                            config=config,
                            ordinal=ordinal,
                            repetition=0,
                            worker=worker,
                            repository=context.repository,
                            manifest=context.manifest,
                            split=context.request.split,
                            timeout_seconds=context.request.case_timeout_seconds,
                            timeout_recovery_check=verify_timeout_recovery,
                        )
                    )
                    second_pass.append(
                        _execute_case_record(
                            case=case,
                            label=label,
                            config=config,
                            ordinal=ordinal,
                            repetition=1,
                            worker=worker,
                            repository=context.repository,
                            manifest=context.manifest,
                            split=context.request.split,
                            timeout_seconds=context.request.case_timeout_seconds,
                            timeout_recovery_check=verify_timeout_recovery,
                        )
                    )

                validate_repetition_determinism(first_pass, second_pass)
                for first, second in zip(first_pass, second_pass, strict=True):
                    records.append(_merge_repetition_latency(first, second))
            finally:
                worker.close()
    finally:
        if temp_name is not None and Path(temp_name).exists():
            raise IntegrityError("temporary_cleanup", "temporary database cleanup failed")

    validate_case_completeness(
        records,
        expected_ids,
        context.expected_scope_ids_by_config[config.config_id],
    )
    status_summary = summarize_case_statuses(records)

    expected_scope_sets = {
        scope: {
            "count": len(case_ids),
            "sha256": _case_set_hash(case_ids),
        }
        for scope, case_ids in context.expected_scope_ids_by_config[config.config_id].items()
    }
    environment = {
        "git_commit": context.repository.commit,
        "git_branch": context.repository.branch,
        "git_dirty": False,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "cpu": platform.processor() or "unknown",
        "benchmark_manifest_sha256": context.manifest.sha256,
        "benchmark_manifest_status": context.manifest.status,
        "dependencies": list(context.dependencies),
        "dependencies_sha256": context.dependencies_sha256,
        "enable_audit_log": True,
        "guard_profile": config.profile.profile_id,
        "provider_id": context.provider.provider_id,
        "provider_behavior_hash": context.provider.behavior_hash,
        "repetitions": 2,
        "warmup": 0,
        "aggregate_context_limit": context.settings.rag_max_aggregate_context_chars,
        "provider_output_limit": context.settings.dlp_max_inspect_chars,
        "result_schema_version": RESULT_SCHEMA_VERSION,
    }
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "experiment_id": context.experiment_id,
        "run_id": run_id,
        "run_status": status_summary["run_status"],
        "config_id": config.config_id,
        "config_hash": config.config_hash,
        "profile_id": config.profile.profile_id,
        "guard_profile": config.profile_payload,
        "environment": environment,
        "split": context.request.split,
        "provider_id": context.provider.provider_id,
        "provider_behavior_hash": context.provider.behavior_hash,
        "safety_limits": dict(context.safety_limits),
        "expected_case_count": len(expected_ids),
        "expected_case_set_sha256": _case_set_hash(expected_ids),
        "expected_case_sets_by_scope": expected_scope_sets,
        "completed_case_count": status_summary["completed_case_count"],
        "error_case_count": status_summary["error_case_count"],
        "timeout_case_count": status_summary["timeout_case_count"],
        "skipped_case_count": 0,
        "cases": records,
        "aggregate": {
            "n_end_to_end": sum(
                record["evaluation_scope"] == "end_to_end" for record in records
            ),
            "aomr": None,
            "fpr": None,
            "fnr": None,
            "marginal_contribution": None,
            "metrics_computed": False,
            "note": "computed by the analysis step, not the runner",
        },
    }


def _looks_like_absolute_path(value: str) -> bool:
    return (
        value.startswith("/")
        or bool(_WINDOWS_ABSOLUTE_RE.match(value))
        or value.lower().startswith("file://")
    )


def scan_forbidden_artifact_content(value: Any, *, location: str = "root") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise IntegrityError("artifact_key", f"{location} contains a non-string key")
            if key.strip().lower().replace("-", "_") in FORBIDDEN_FIELD_NAMES:
                raise IntegrityError("forbidden_artifact_field", f"forbidden artifact field: {key}")
            scan_forbidden_artifact_content(item, location=f"{location}.{key}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            scan_forbidden_artifact_content(item, location=f"{location}[{index}]")
        return
    if isinstance(value, str):
        if _looks_like_absolute_path(value):
            raise IntegrityError("absolute_path", f"{location} contains an absolute path")
        if _CANARY_VALUE_RE.search(value):
            raise IntegrityError("forbidden_artifact_value", f"{location} contains raw benchmark content")
        return
    if value is None or type(value) in {bool, int}:
        return
    if type(value) is float and math.isfinite(value):
        return
    raise IntegrityError("artifact_type", f"{location} contains a non-JSON-safe value")


def _new_run_id(config_id: str) -> str:
    return f"{config_id}-{time.time_ns():020d}-{os.getpid()}"


def _validate_run_id(run_id: str) -> None:
    _safe_location(run_id)


def _run_directory(
    output_root: Path,
    artifact: Mapping[str, Any],
) -> Path:
    return (
        output_root
        / "raw"
        / artifact["experiment_id"]
        / artifact["provider_id"]
        / artifact["split"]
        / artifact["config_id"]
        / artifact["run_id"]
    )


def _publish_directory_atomically(
    staging_directory: Path,
    final_directory: Path,
) -> None:
    """Publish one fully verified staging directory with a single rename."""
    os.rename(staging_directory, final_directory)


def _remove_staging_directory_best_effort(staging_directory: Path) -> None:
    """Remove abandoned staging data without affecting the publication error."""
    try:
        shutil.rmtree(staging_directory)
    except FileNotFoundError:
        pass
    except OSError:
        pass


def _publish_artifact(output_root: Path, artifact: dict[str, Any]) -> WrittenRun:
    scan_forbidden_artifact_content(artifact)
    result_bytes = _canonical_json_bytes(artifact)
    result_hash = _sha256_bytes(result_bytes)
    result_manifest = {
        "schema_version": RESULT_MANIFEST_SCHEMA_VERSION,
        "result_file": "result.json",
        "result_sha256": result_hash,
        "result_size_bytes": len(result_bytes),
        "result_schema_version": artifact["schema_version"],
        "experiment_id": artifact["experiment_id"],
        "run_id": artifact["run_id"],
        "run_status": artifact["run_status"],
        "config_id": artifact["config_id"],
        "config_hash": artifact["config_hash"],
        "profile_id": artifact["profile_id"],
        "provider_id": artifact["provider_id"],
        "provider_behavior_hash": artifact["provider_behavior_hash"],
        "git_commit": artifact["environment"]["git_commit"],
        "benchmark_manifest_sha256": artifact["environment"][
            "benchmark_manifest_sha256"
        ],
        "expected_case_set_sha256": artifact["expected_case_set_sha256"],
    }
    scan_forbidden_artifact_content(result_manifest)
    manifest_bytes = _canonical_json_bytes(result_manifest)

    final_directory = _run_directory(output_root, artifact)
    if final_directory.exists():
        raise IntegrityError("result_exists", "result destination already exists; overwrite refused")
    final_directory.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".tmp-{artifact['config_id']}-", dir=final_directory.parent)
    )
    try:
        result_temp = temporary / "result.json"
        manifest_temp = temporary / "result-manifest.json"
        for path, data in ((result_temp, result_bytes), (manifest_temp, manifest_bytes)):
            with path.open("xb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())

        parsed_result = json.loads(result_temp.read_text(encoding="utf-8"))
        parsed_manifest = json.loads(manifest_temp.read_text(encoding="utf-8"))
        scan_forbidden_artifact_content(parsed_result)
        scan_forbidden_artifact_content(parsed_manifest)
        if _sha256_file(result_temp) != result_hash or result_temp.stat().st_size != len(result_bytes):
            raise IntegrityError("result_write_integrity", "temporary result identity changed before publish")
        if manifest_temp.read_bytes() != manifest_bytes:
            raise IntegrityError(
                "result_write_integrity",
                "temporary result manifest changed before publish",
            )
        if final_directory.exists():
            raise IntegrityError("result_exists", "result destination appeared before publish")
        _publish_directory_atomically(temporary, final_directory)
    except Exception:
        try:
            _remove_staging_directory_best_effort(temporary)
        except Exception:
            # Cleanup remains best-effort even if a test or platform hook fails.
            pass
        raise

    return WrittenRun(
        config_id=artifact["config_id"],
        run_id=artifact["run_id"],
        run_status=artifact["run_status"],
        result_path=final_directory / "result.json",
        manifest_path=final_directory / "result-manifest.json",
    )


def run_evaluation(
    request: RunRequest,
    *,
    repo_root: Path = ROOT,
    benchmark_root: Path | None = None,
    hooks: RunnerHooks | None = None,
) -> list[WrittenRun]:
    active_hooks = hooks or RunnerHooks()
    context = preflight(
        request,
        repo_root=repo_root,
        benchmark_root=benchmark_root,
        hooks=active_hooks,
    )
    output_root = _validate_output_root(
        request.output_root,
        repo_root,
        benchmark_root or repo_root / "datasets" / "v2",
    )

    artifacts: list[dict[str, Any]] = []
    run_ids: set[str] = set()
    for config_id in request.config_ids:
        run_id = active_hooks.run_id_factory(config_id)
        _validate_run_id(run_id)
        if run_id in run_ids:
            raise IntegrityError("run_id_collision", "run identifiers must be unique")
        run_ids.add(run_id)
        artifact = _execute_config(
            context,
            CONFIG_REGISTRY[config_id],
            repo_root=repo_root,
            hooks=active_hooks,
            run_id=run_id,
        )
        scan_forbidden_artifact_content(artifact)
        artifacts.append(artifact)

    destinations = [_run_directory(output_root, artifact) for artifact in artifacts]
    if len(set(destinations)) != len(destinations) or any(path.exists() for path in destinations):
        raise IntegrityError("result_exists", "one or more result destinations already exist")
    return [_publish_artifact(output_root, artifact) for artifact in artifacts]


def run_development_evaluation(
    request: RunRequest,
    *,
    repo_root: Path = ROOT,
    benchmark_root: Path | None = None,
    hooks: RunnerHooks | None = None,
) -> list[WrittenRun]:
    """Compatibility wrapper that remains explicitly development-only."""
    if request.split != "development":
        raise IntegrityError(
            "split_not_allowed",
            "run_development_evaluation accepts only the development split",
        )
    return run_evaluation(
        request,
        repo_root=repo_root,
        benchmark_root=benchmark_root,
        hooks=hooks,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", required=True, choices=list(SUPPORTED_SPLITS))
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        "--config",
        action="append",
        choices=list(CONFIG_REGISTRY),
        help="Run one approved C0-C7 profile; repeat to select multiple profiles.",
    )
    selection.add_argument("--all-configs", action="store_true")
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--expected-branch", required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--provider", default=SUPPORTED_PROVIDER_ID, choices=[SUPPORTED_PROVIDER_ID])
    parser.add_argument("--case-timeout-seconds", type=float, default=30.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config_ids = tuple(CONFIG_REGISTRY) if args.all_configs else tuple(args.config)
    request = RunRequest(
        split=args.split,
        config_ids=config_ids,
        output_root=args.output_root,
        expected_branch=args.expected_branch,
        expected_commit=args.expected_commit,
        provider_id=args.provider,
        case_timeout_seconds=args.case_timeout_seconds,
    )
    try:
        written = run_evaluation(request)
    except RunnerError as exc:
        print(f"FAIL [{exc.code}]: {exc}", file=sys.stderr)
        return 1
    except Exception:
        print("FAIL [internal_error]: runner failed closed.", file=sys.stderr)
        return 1

    print(f"OK: wrote {len(written)} {args.split} diagnostic run(s).")
    for item in written:
        print(f"  {item.config_id}: {item.run_status} ({item.run_id})")
    print("Aggregate metrics were not computed. Holdout was not executed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
