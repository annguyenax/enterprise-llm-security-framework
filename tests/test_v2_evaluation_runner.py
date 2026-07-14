"""Phase 12E.3 development/validation runner integrity and safety tests."""
from __future__ import annotations

import copy
import hashlib
import json
import multiprocessing
import os
import shutil
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.decisions import Decision
from app.core.pipeline import GuardProfile, RagPipelineResult, StageResult
from app.services.llm_provider import (
    BaseLLMProvider,
    LLMProviderRequest,
    LLMProviderResponse,
)
from scripts import run_v2_evaluation as runner


TEST_BRANCH = "phase-12e-2-test"
TEST_COMMIT = "a" * 40


class _OfflineTestProvider(BaseLLMProvider):
    def generate(self, _request: LLMProviderRequest) -> LLMProviderResponse:
        return LLMProviderResponse(
            text="offline test response",
            provider_name="offline-test",
            model_name="offline-test-v1",
            is_mock=True,
        )


class _StubWorker:
    def __init__(self, response):
        self.response = response

    def execute(self, _task, _timeout_seconds):
        return self.response


@pytest.fixture(autouse=True)
def _offline_environment(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    for name in runner.PRODUCTION_CREDENTIAL_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def _state(*, branch: str = TEST_BRANCH, commit: str = TEST_COMMIT, dirty: bool = False):
    return runner.RepositoryState(branch=branch, commit=commit, dirty=dirty)


def _request(tmp_path: Path, *config_ids: str) -> runner.RunRequest:
    return runner.RunRequest(
        split="development",
        config_ids=tuple(config_ids or ("C0_all_on",)),
        output_root=tmp_path / "output",
        expected_branch=TEST_BRANCH,
        expected_commit=TEST_COMMIT,
        provider_id="mock",
        case_timeout_seconds=30.0,
    )


def _hooks(
    tmp_path: Path,
    state: runner.RepositoryState | None = None,
    *,
    worker_entrypoint=None,
    worker_lifecycle_observer=None,
):
    return runner.RunnerHooks(
        repository_state_loader=lambda _root: state or _state(),
        run_id_factory=lambda config_id: f"{config_id}-test-run",
        temp_parent=tmp_path / "runtime",
        worker_entrypoint=worker_entrypoint,
        worker_lifecycle_observer=worker_lifecycle_observer,
    )


def _send_probe_outcome(connection) -> None:
    outcome = runner.ScopeOutcome(
        final_decision="allow",
        stop_reason="allowed",
        provider_called=True,
        retrieved_count=0,
        accepted_context_count=0,
        rejected_context_count=0,
        redaction_count=0,
        dlp_finding_categories={},
        stage_results=(),
        pipeline_pre_audit_ms=1.0,
        end_to_end_with_audit_ms=2.0,
    )
    connection.send(
        {
            "kind": "outcome",
            "outcome": runner._scope_outcome_to_transport(outcome),  # noqa: SLF001
        }
    )


def _timeout_probe_worker(connection, _init_payload) -> None:
    connection.send(
        {
            "kind": "ready",
            "protocol_version": runner.WORKER_PROTOCOL_VERSION,
            "worker_pid": os.getpid(),
        }
    )
    while True:
        task = connection.recv()
        if task == {
            "kind": "stop",
            "protocol_version": runner.WORKER_PROTOCOL_VERSION,
        }:
            connection.send(
                {
                    "kind": "stopped",
                    "protocol_version": runner.WORKER_PROTOCOL_VERSION,
                }
            )
            return
        if task["case"]["case_id"] == "V2-DEV-0001":
            while True:
                time.sleep(60)
        _send_probe_outcome(connection)


def _corrupting_timeout_probe_worker(connection, init_payload) -> None:
    connection.send(
        {
            "kind": "ready",
            "protocol_version": runner.WORKER_PROTOCOL_VERSION,
            "worker_pid": os.getpid(),
        }
    )
    task = connection.recv()
    if task.get("kind") != "case":
        return
    with Path(init_payload["database_path"]).open("ab") as handle:
        handle.write(b"state-corruption-probe")
        handle.flush()
        os.fsync(handle.fileno())
    while True:
        time.sleep(60)


def _copy_benchmark(tmp_path: Path) -> Path:
    destination = tmp_path / "benchmark-v2"
    shutil.copytree(runner.ROOT / "datasets" / "v2", destination)
    return destination


def _load_written_result(written: runner.WrittenRun) -> dict:
    return json.loads(written.result_path.read_text(encoding="utf-8"))


def _minimal_case(scope: str = "end_to_end") -> dict:
    return {
        "case_id": "case-1",
        "evaluation_scope": scope,
        "scenario_family": "family-does-not-drive-dispatch",
        "query": "ordinary lookup",
        "top_k": 5,
        "relevant_document_ids": [],
    }


def _minimal_label() -> dict:
    return {
        "category": "benign",
        "allowed_final_decisions": ["allow"],
        "allowed_stop_reasons": ["allowed"],
        "expected_provider_called": True,
    }


def _pipeline_result() -> RagPipelineResult:
    return RagPipelineResult(
        request_id="safe-request-id",
        final_decision=Decision.ALLOW,
        answer="raw answer that must never be projected",
        retrieved_count=1,
        accepted_context_count=1,
        rejected_context_count=0,
        stage_results=(
            StageResult(
                stage="input_guard",
                decision=Decision.ALLOW,
                reason_code="input_guard_decision",
                detail="raw detail that must never be projected",
            ),
        ),
        redaction_count=0,
        dlp_finding_categories={},
        latency_ms={"input_guard": 1.5, "total": 2.0},
        stop_reason="allowed",
        provider_called=True,
    )


def test_registry_has_exact_c0_to_c7_profiles_and_order():
    assert tuple(runner.CONFIG_REGISTRY) == tuple(item[0] for item in runner.CONFIG_DEFINITIONS)
    runner.validate_config_registry(runner.CONFIG_REGISTRY)
    actual = {
        config_id: tuple(getattr(config.profile, name) for name in runner.GUARD_FIELDS)
        for config_id, config in runner.CONFIG_REGISTRY.items()
    }
    assert actual == dict(runner.CONFIG_DEFINITIONS)


def test_profile_and_config_hashes_are_stable_and_content_derived():
    first = runner.CONFIG_REGISTRY["C3_no_context"]
    rebuilt = runner.EvaluationConfig(
        config_id="C3_no_context",
        profile=GuardProfile(
            input_guard=True,
            provenance_guard=True,
            rag_context_guard=False,
            aggregate_context_guard=False,
            dlp=True,
            output_guard=True,
        ),
    )
    assert first.profile.profile_id == rebuilt.profile.profile_id
    assert first.config_hash == rebuilt.config_hash
    assert first.config_hash != runner.CONFIG_REGISTRY["C0_all_on"].config_hash


def test_registry_rejects_name_boolean_mismatch():
    changed = dict(runner.CONFIG_REGISTRY)
    changed["C1_no_input"] = runner.EvaluationConfig(
        "C1_no_input", GuardProfile()
    )
    with pytest.raises(runner.IntegrityError, match="booleans mismatch"):
        runner.validate_config_registry(changed)


@pytest.mark.parametrize(
    "argv",
    [
        ["--split", "holdout", "--config", "C0_all_on"],
        ["--split", "unknown", "--config", "C0_all_on"],
        ["--split", "development", "--config", "custom_profile"],
        ["--split", "development", "--provider", "external", "--config", "C0_all_on"],
        [
            "--split",
            "development",
            "--config",
            "C0_all_on",
            "--input-guard",
            "false",
        ],
    ],
)
def test_cli_rejects_holdout_custom_profiles_and_external_providers(argv):
    full = [
        *argv,
        "--output-root",
        "safe-output",
        "--expected-branch",
        TEST_BRANCH,
        "--expected-commit",
        TEST_COMMIT,
    ]
    with pytest.raises(SystemExit) as exc:
        runner.build_parser().parse_args(full)
    assert exc.value.code == 2


def test_cli_accepts_validation_as_a_supported_split():
    args = runner.build_parser().parse_args(
        [
            "--split",
            "validation",
            "--config",
            "C0_all_on",
            "--output-root",
            "safe-output",
            "--expected-branch",
            TEST_BRANCH,
            "--expected-commit",
            TEST_COMMIT,
        ]
    )
    assert args.split == "validation"


def test_preflight_rejects_dirty_tree_before_output_is_created(tmp_path):
    request = _request(tmp_path)
    with pytest.raises(runner.IntegrityError, match="working tree"):
        runner.preflight(request, hooks=_hooks(tmp_path, _state(dirty=True)))
    assert not request.output_root.exists()


@pytest.mark.parametrize(
    "state",
    [
        _state(branch="wrong-branch"),
        _state(commit="b" * 40),
    ],
)
def test_preflight_rejects_wrong_branch_or_commit_without_write(tmp_path, state):
    request = _request(tmp_path)
    with pytest.raises(runner.IntegrityError):
        runner.preflight(request, hooks=_hooks(tmp_path, state))
    assert not request.output_root.exists()


def test_preflight_rejects_invalid_expected_commit_before_write(tmp_path):
    request = dataclasses_replace(_request(tmp_path), expected_commit="short")
    with pytest.raises(runner.IntegrityError, match="full lowercase"):
        runner.preflight(request, hooks=_hooks(tmp_path))
    assert not request.output_root.exists()


def test_holdout_preflight_rejects_before_manifest_loader_or_output(tmp_path, monkeypatch):
    request = dataclasses_replace(_request(tmp_path), split="holdout")
    monkeypatch.setattr(
        runner,
        "verify_frozen_manifest",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("manifest reached")),
    )
    monkeypatch.setattr(
        runner,
        "load_split_benchmark",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("loader reached")),
    )
    with pytest.raises(runner.IntegrityError, match="holdout is prohibited"):
        runner.preflight(request, hooks=_hooks(tmp_path))
    assert not request.output_root.exists()


def test_preflight_rejects_unknown_result_schema_before_write(tmp_path, monkeypatch):
    request = _request(tmp_path)
    monkeypatch.setattr(runner, "RESULT_SCHEMA_VERSION", 99)
    with pytest.raises(runner.IntegrityError, match="schema identity"):
        runner.preflight(request, hooks=_hooks(tmp_path))
    assert not request.output_root.exists()


@pytest.mark.parametrize(
    "changes",
    [
        {"retrieval_max_batch_size": 0},
        {"retrieval_max_query_chars": -1},
        {"retrieval_max_query_terms": 0},
        {"retrieval_chunk_max_chars": 0},
        {"retrieval_busy_timeout_ms": -1},
        {"retrieval_chunk_max_chars": 100, "retrieval_chunk_overlap_chars": 100},
    ],
)
def test_invalid_runner_safety_limits_fail_preflight_contract(changes):
    settings = dataclasses_replace(runner.load_settings(), **changes)
    with pytest.raises(runner.IntegrityError, match="positive|overlap"):
        runner._settings_safety_limits(settings, 30.0)  # noqa: SLF001


@pytest.mark.parametrize(
    "timeout",
    [0.0, -1.0, float("nan"), float("inf"), True, "1", None],
)
def test_invalid_case_timeout_is_rejected(timeout):
    with pytest.raises(runner.IntegrityError, match="finite positive"):
        runner._settings_safety_limits(runner.load_settings(), timeout)  # noqa: SLF001


def test_invalid_timeout_aborts_run_before_artifact_creation(tmp_path):
    request = dataclasses_replace(_request(tmp_path), case_timeout_seconds=0.0)
    with pytest.raises(runner.IntegrityError, match="finite positive"):
        runner.run_development_evaluation(request, hooks=_hooks(tmp_path))
    assert not request.output_root.exists()


def test_timeout_participates_in_safety_and_experiment_identity(tmp_path):
    first = runner.preflight(
        dataclasses_replace(_request(tmp_path), case_timeout_seconds=1.0),
        hooks=_hooks(tmp_path),
    )
    second = runner.preflight(
        dataclasses_replace(_request(tmp_path), case_timeout_seconds=2.0),
        hooks=_hooks(tmp_path),
    )
    assert first.safety_limits["case_timeout_seconds"] == 1.0
    assert second.safety_limits["case_timeout_seconds"] == 2.0
    assert first.experiment_id != second.experiment_id


def test_manifest_is_final_and_verifies_exactly_nine_files():
    identity = runner.verify_frozen_manifest(runner.ROOT / "datasets" / "v2")
    assert identity.status == "final"
    assert identity.file_count == 9
    assert len(identity.sha256) == 64


@pytest.mark.parametrize("relative_path", runner.REQUIRED_FROZEN_PATHS)
def test_each_frozen_artifact_mismatch_is_rejected(tmp_path, relative_path):
    benchmark = _copy_benchmark(tmp_path)
    target = benchmark / Path(*relative_path.split("/"))
    target.write_bytes(target.read_bytes() + b"\n")
    with pytest.raises(runner.IntegrityError, match="frozen artifact mismatch"):
        runner.verify_frozen_manifest(benchmark)


def test_manifest_mismatch_aborts_preflight_without_output(tmp_path):
    benchmark = _copy_benchmark(tmp_path)
    target = benchmark / "labels" / "development.jsonl"
    target.write_bytes(target.read_bytes() + b"\n")
    request = _request(tmp_path)
    with pytest.raises(runner.IntegrityError, match="frozen artifact mismatch"):
        runner.preflight(
            request,
            benchmark_root=benchmark,
            hooks=_hooks(tmp_path),
        )
    assert not request.output_root.exists()


def test_candidate_manifest_is_rejected(tmp_path):
    benchmark = _copy_benchmark(tmp_path)
    manifest_path = benchmark / "manifests" / "benchmark-v2-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["manifest_status"] = "candidate"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(runner.IntegrityError, match="must be final"):
        runner.verify_frozen_manifest(benchmark)


def test_unexpected_frozen_directory_file_is_rejected(tmp_path):
    benchmark = _copy_benchmark(tmp_path)
    (benchmark / "cases" / "unexpected.jsonl").write_text("{}\n", encoding="utf-8")
    with pytest.raises(runner.IntegrityError, match="artifact set differs"):
        runner.verify_frozen_manifest(benchmark)


def test_development_cases_load_in_stable_case_id_order():
    benchmark = runner.load_development_benchmark(runner.ROOT / "datasets" / "v2")
    case_ids = tuple(case["case_id"] for case in benchmark.cases)
    assert case_ids == tuple(sorted(case_ids))
    assert len(case_ids) == 30
    assert benchmark.labels_by_id["V2-DEV-0021"]["expected_provider_called"] is None


def test_validation_cases_load_only_validation_in_stable_order():
    benchmark = runner.load_split_benchmark(
        runner.ROOT / "datasets" / "v2",
        "validation",
    )
    case_ids = tuple(case["case_id"] for case in benchmark.cases)
    assert len(case_ids) == 30
    assert case_ids == tuple(sorted(case_ids))
    assert all(case["split"] == "validation" for case in benchmark.cases)
    assert set(case_ids) == set(benchmark.labels_by_id)


def test_split_participates_in_experiment_and_record_identity(tmp_path):
    development = runner.preflight(_request(tmp_path), hooks=_hooks(tmp_path))
    validation = runner.preflight(
        dataclasses_replace(_request(tmp_path), split="validation"),
        hooks=_hooks(tmp_path),
    )
    assert development.experiment_id != validation.experiment_id

    record = runner._case_completed_record(  # noqa: SLF001
        case=_minimal_case(),
        label=_minimal_label(),
        config=runner.CONFIG_REGISTRY["C0_all_on"],
        ordinal=0,
        repository=_state(),
        manifest=runner.ManifestIdentity("b" * 64, "final", 9),
        split="validation",
        outcome=runner.ScopeOutcome(
            final_decision="allow",
            stop_reason="allowed",
            provider_called=True,
            retrieved_count=0,
            accepted_context_count=0,
            rejected_context_count=0,
            redaction_count=0,
            dlp_finding_categories={},
            stage_results=(),
            pipeline_pre_audit_ms=1.0,
            end_to_end_with_audit_ms=2.0,
        ),
    )
    assert record["split"] == "validation"
    output_path = runner._run_directory(  # noqa: SLF001
        tmp_path,
        {
            "experiment_id": validation.experiment_id,
            "provider_id": "mock",
            "split": "validation",
            "config_id": "C0_all_on",
            "run_id": "validation-run",
        },
    )
    assert "validation" in output_path.parts


def test_expected_case_sets_are_config_and_scope_specific():
    benchmark = runner.load_development_benchmark(runner.ROOT / "datasets" / "v2")
    overall, by_scope = runner._expected_case_sets(  # noqa: SLF001
        benchmark, ("C0_all_on", "C6_none")
    )
    assert len(overall["C0_all_on"]) == 30
    assert len(overall["C6_none"]) == 26
    assert tuple(by_scope["C6_none"]) == ("end_to_end",)
    assert {scope: len(ids) for scope, ids in by_scope["C0_all_on"].items()} == {
        "end_to_end": 26,
        "component": 1,
        "availability_fault": 2,
        "residual_risk_only": 1,
    }


def test_expected_case_set_hash_is_order_sensitive_and_stable():
    ids = ("case-a", "case-b")
    assert runner._case_set_hash(ids) == runner._case_set_hash(ids)  # noqa: SLF001
    assert runner._case_set_hash(ids) != runner._case_set_hash(tuple(reversed(ids)))  # noqa: SLF001


def test_output_root_cannot_overlap_benchmark_or_unapproved_repo_path(tmp_path):
    benchmark = runner.ROOT / "datasets" / "v2"
    with pytest.raises(runner.IntegrityError, match="overlaps"):
        runner._validate_output_root(benchmark, runner.ROOT, benchmark)  # noqa: SLF001
    with pytest.raises(runner.IntegrityError, match="only under"):
        runner._validate_output_root(runner.ROOT / "data" / "bad", runner.ROOT, benchmark)  # noqa: SLF001
    assert runner._validate_output_root(tmp_path / "external", runner.ROOT, benchmark)  # noqa: SLF001


def test_external_or_unapproved_provider_is_rejected():
    external = runner.ProviderSpec(
        provider_id="external",
        factory=_OfflineTestProvider,
        behavior_descriptor={"provider_id": "external", "version": 1},
        offline=False,
        test_only=False,
    )
    with pytest.raises(runner.IntegrityError, match="offline"):
        runner._validate_provider(external, allow_test_provider=False)  # noqa: SLF001

    scripted = dataclasses_replace(external, offline=True, test_only=True)
    with pytest.raises(runner.IntegrityError, match="disabled"):
        runner._validate_provider(scripted, allow_test_provider=False)  # noqa: SLF001
    runner._validate_provider(scripted, allow_test_provider=True)  # noqa: SLF001


def test_production_credentials_are_rejected(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-used")
    spec = runner.default_provider_spec("mock", runner.load_settings())
    with pytest.raises(runner.IntegrityError, match="credentials"):
        runner._validate_provider_environment(spec)  # noqa: SLF001


def test_external_provider_environment_is_rejected(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "external")
    spec = runner.default_provider_spec("mock", runner.load_settings())
    with pytest.raises(runner.IntegrityError, match="must remain mock"):
        runner._validate_provider_environment(spec)  # noqa: SLF001


def test_scope_dispatch_uses_evaluation_scope_not_family(monkeypatch):
    observed: list[str] = []

    def fake_pipeline(**kwargs):
        observed.append(kwargs["case"]["scenario_family"])
        return runner.ScopeOutcome(
            final_decision="allow",
            stop_reason="allowed",
            provider_called=True,
            retrieved_count=0,
            accepted_context_count=0,
            rejected_context_count=0,
            redaction_count=0,
            dlp_finding_categories={},
            stage_results=(),
            pipeline_pre_audit_ms=1.0,
            end_to_end_with_audit_ms=2.0,
        )

    monkeypatch.setattr(runner, "_pipeline_scope_outcome", fake_pipeline)
    case = _minimal_case("end_to_end")
    case["scenario_family"] = "availability_failure_case"
    result = runner._execute_scope(  # noqa: SLF001
        case=case,
        config=runner.CONFIG_REGISTRY["C0_all_on"],
        retriever=object(),
        provider_spec=object(),
        ingestion_statuses={},
        active_settings=runner.load_settings(),
        repetition=0,
    )
    assert result.stop_reason == "allowed"
    assert observed == ["availability_failure_case"]


@pytest.mark.parametrize("scope", ["component", "availability_fault", "residual_risk_only"])
def test_non_end_to_end_scopes_are_c0_only(scope):
    case = _minimal_case(scope)
    with pytest.raises(runner.IntegrityError, match="C0-only"):
        runner._execute_scope(  # noqa: SLF001
            case=case,
            config=runner.CONFIG_REGISTRY["C6_none"],
            retriever=object(),
            provider_spec=object(),
            ingestion_statuses={},
            active_settings=runner.load_settings(),
            repetition=0,
        )


def test_pipeline_receives_only_query_top_k_and_selected_internal_profile(monkeypatch):
    captured: dict = {}
    commits: list[tuple] = []

    def fake_run(**kwargs):
        captured.update(kwargs)
        return _pipeline_result(), object()

    monkeypatch.setattr(runner, "run_rag_query_uncommitted", fake_run)
    monkeypatch.setattr(runner, "commit_rag_query_audit", lambda *args: commits.append(args))
    case = _minimal_case()
    case["relevant_document_ids"] = ["must-not-influence-retrieval"]
    runner._pipeline_scope_outcome(  # noqa: SLF001
        case=case,
        config=runner.CONFIG_REGISTRY["C6_none"],
        retriever=object(),
        provider_spec=runner.ProviderSpec(
            provider_id="offline-test",
            factory=_OfflineTestProvider,
            behavior_descriptor={"version": 1},
            test_only=True,
        ),
        request_id="request",
        ingestion_status=None,
    )
    assert set(captured) == {
        "query", "top_k", "retriever", "request_id", "provider", "guard_profile"
    }
    assert "relevant_document_ids" not in captured
    assert captured["guard_profile"] == runner.CONFIG_REGISTRY["C6_none"].profile
    assert len(commits) == 1


def test_component_retrieval_uses_frozen_query_not_relevant_document_ids():
    observed = []

    class SpyRetriever:
        def search(self, query):
            observed.append(query)
            return SimpleNamespace(hits=(), total_hits=0)

    case = _minimal_case("component")
    case["query"] = "frozen component query"
    case["relevant_document_ids"] = ["must-not-drive-query"]
    outcome = runner._execute_scope(  # noqa: SLF001
        case=case,
        config=runner.CONFIG_REGISTRY["C0_all_on"],
        retriever=SpyRetriever(),
        provider_spec=object(),
        ingestion_statuses={"must-not-drive-query": "rejected"},
        active_settings=runner.load_settings(),
        corpus_by_id={
            "must-not-drive-query": {
                "source_key": "v2-unregistered-source-key",
                "external_id": "must-not-drive-query",
            }
        },
        repetition=0,
    )
    assert len(observed) == 1
    assert observed[0].query == "frozen component query"
    assert observed[0].top_k == case["top_k"]
    assert "must-not-drive-query" not in observed[0].query
    assert outcome.provider_called is False
    assert outcome.retrieved_count == 0
    assert outcome.target_document_hit_count == 0


def test_safe_stage_projection_excludes_detail_and_marks_disabled_stage():
    projected = runner._project_stage_results(  # noqa: SLF001
        _pipeline_result(), runner.CONFIG_REGISTRY["C1_no_input"].profile
    )
    assert projected == (
        {
            "stage": "input_guard",
            "enabled": False,
            "decision": "allow",
            "reason_code": "input_guard_decision",
            "execution_time_ms": 1.5,
        },
    )
    assert "detail" not in projected[0]


@pytest.mark.parametrize(
    "payload",
    [
        {"query": "raw"},
        {"answer": "raw"},
        {"nested": [{"detail": "raw"}]},
        {"value": "V2TOK00001"},
        {"value": "C:\\private\\machine-path"},
        {"value": "/private/machine-path"},
        {"value": float("nan")},
    ],
)
def test_recursive_forbidden_artifact_scan_fails_closed(payload):
    with pytest.raises(runner.IntegrityError):
        runner.scan_forbidden_artifact_content(payload)


def test_case_exception_record_is_safe_and_fixed():
    record = runner._execute_case_record(  # noqa: SLF001
        case=_minimal_case(),
        label=_minimal_label(),
        config=runner.CONFIG_REGISTRY["C0_all_on"],
        ordinal=0,
        repetition=0,
        worker=_StubWorker(
            {
                "kind": "case_error",
                "error_category": "case_execution_error",
                "state_trustworthy": True,
            }
        ),
        repository=_state(),
        manifest=runner.ManifestIdentity("b" * 64, "final", 9),
        split="development",
        timeout_seconds=30.0,
        timeout_recovery_check=lambda _case: None,
    )
    assert record["case_status"] == "error"
    assert record["error_category"] == "case_execution_error"
    assert record["correct"] is False
    assert "secret exception text" not in json.dumps(record)


def test_case_timeout_record_is_safe_and_fixed():
    recovered = []
    record = runner._execute_case_record(  # noqa: SLF001
        case=_minimal_case(),
        label=_minimal_label(),
        config=runner.CONFIG_REGISTRY["C0_all_on"],
        ordinal=0,
        repetition=0,
        worker=_StubWorker(
            {
                "kind": "timeout",
                "error_category": "case_timeout",
                "terminated_worker_pid": 123,
            }
        ),
        repository=_state(),
        manifest=runner.ManifestIdentity("b" * 64, "final", 9),
        split="development",
        timeout_seconds=30.0,
        timeout_recovery_check=lambda case: recovered.append(case["case_id"]),
    )
    assert record["case_status"] == "timeout"
    assert record["error_category"] == "case_timeout"
    assert record["actual_final_decision"] is None
    assert recovered == ["case-1"]


def test_missing_and_duplicate_case_records_are_rejected():
    records = [
        {"case_id": "a", "evaluation_scope": "end_to_end"},
        {"case_id": "a", "evaluation_scope": "end_to_end"},
    ]
    with pytest.raises(runner.IntegrityError, match="duplicate"):
        runner.validate_case_completeness(records, ("a", "b"), {"end_to_end": ("a", "b")})
    with pytest.raises(runner.IntegrityError, match="incomplete"):
        runner.validate_case_completeness(records[:1], ("a", "b"), {"end_to_end": ("a", "b")})


def test_complete_and_partial_status_semantics_are_explicit():
    complete = runner.summarize_case_statuses(
        [{"case_status": "completed"}, {"case_status": "completed"}]
    )
    assert complete == {
        "run_status": "complete",
        "completed_case_count": 2,
        "error_case_count": 0,
        "timeout_case_count": 0,
    }
    partial = runner.summarize_case_statuses(
        [{"case_status": "completed"}, {"case_status": "error"}, {"case_status": "timeout"}]
    )
    assert partial["run_status"] == "partial"
    assert partial["error_case_count"] == 1
    assert partial["timeout_case_count"] == 1
    with pytest.raises(runner.IntegrityError, match="unsupported"):
        runner.summarize_case_statuses([{"case_status": "skipped"}])


def test_deterministic_projection_ignores_only_latency():
    first = {
        "case_id": "a",
        "actual_final_decision": "allow",
        "stage_results": [{"stage": "x", "execution_time_ms": 1.0}],
        "latency_ms_samples": {"end_to_end_with_audit": [2.0]},
    }
    second = copy.deepcopy(first)
    second["stage_results"][0]["execution_time_ms"] = 99.0
    second["latency_ms_samples"] = {"end_to_end_with_audit": [100.0]}
    assert runner._deterministic_projection(first) == runner._deterministic_projection(second)  # noqa: SLF001
    second["actual_final_decision"] = "block"
    assert runner._deterministic_projection(first) != runner._deterministic_projection(second)  # noqa: SLF001
    with pytest.raises(runner.IntegrityError, match="content-free telemetry"):
        runner.validate_repetition_determinism([first], [second])
    with pytest.raises(runner.IntegrityError, match="counts differ"):
        runner.validate_repetition_determinism([first], [])


def test_canonical_json_is_sorted_utf8_and_rejects_nan():
    encoded = runner._canonical_json_bytes({"z": "Tiếng Việt", "a": 1})  # noqa: SLF001
    assert encoded == '{"a":1,"z":"Tiếng Việt"}\n'.encode()
    with pytest.raises(ValueError):
        runner._canonical_json_bytes({"x": float("nan")})  # noqa: SLF001


@pytest.fixture(scope="module")
def c0_integration_run(tmp_path_factory):
    root = tmp_path_factory.mktemp("phase12e2-c0")
    request = _request(root, "C0_all_on")
    written = runner.run_development_evaluation(
        request,
        hooks=_hooks(root),
    )
    return root, request, written[0]


@pytest.fixture(scope="module")
def c6_integration_run(tmp_path_factory):
    root = tmp_path_factory.mktemp("phase12e2-c6")
    request = _request(root, "C6_none")
    written = runner.run_development_evaluation(
        request,
        hooks=_hooks(root),
    )
    return root, request, written[0]


def test_temporary_sqlite_is_cleaned_when_corpus_setup_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(
        runner,
        "_ingest_corpus",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("setup failed")),
    )
    request = _request(tmp_path, "C6_none")
    with pytest.raises(RuntimeError, match="setup failed"):
        runner.run_development_evaluation(request, hooks=_hooks(tmp_path))
    assert not request.output_root.exists()
    runtime = tmp_path / "runtime"
    assert not list(runtime.glob("phase12e2-*"))


def test_case_errors_publish_only_a_partial_diagnostic_run(tmp_path, monkeypatch):
    def error_record(**kwargs):
        return runner._case_error_record(  # noqa: SLF001
            case=kwargs["case"],
            label=kwargs["label"],
            config=kwargs["config"],
            ordinal=kwargs["ordinal"],
            repository=kwargs["repository"],
            manifest=kwargs["manifest"],
            split=kwargs["split"],
            status="error",
            error_category="case_execution_error",
        )

    monkeypatch.setattr(runner, "_execute_case_record", error_record)
    written = runner.run_development_evaluation(
        _request(tmp_path, "C6_none"),
        hooks=_hooks(tmp_path),
    )
    result = _load_written_result(written[0])
    assert result["run_status"] == "partial"
    assert result["completed_case_count"] == 0
    assert result["error_case_count"] == 26
    assert result["timeout_case_count"] == 0
    assert all(record["correct"] is False for record in result["cases"])


def test_non_deterministic_repetitions_abort_without_result(tmp_path, monkeypatch):
    def changing_record(**kwargs):
        outcome = runner.ScopeOutcome(
            final_decision=("allow" if kwargs["repetition"] == 0 else "block"),
            stop_reason="allowed",
            provider_called=False,
            retrieved_count=0,
            accepted_context_count=0,
            rejected_context_count=0,
            redaction_count=0,
            dlp_finding_categories={},
            stage_results=(),
            pipeline_pre_audit_ms=1.0,
            end_to_end_with_audit_ms=2.0,
        )
        return runner._case_completed_record(  # noqa: SLF001
            case=kwargs["case"],
            label=kwargs["label"],
            config=kwargs["config"],
            ordinal=kwargs["ordinal"],
            repository=kwargs["repository"],
            manifest=kwargs["manifest"],
            split=kwargs["split"],
            outcome=outcome,
        )

    monkeypatch.setattr(runner, "_execute_case_record", changing_record)
    request = _request(tmp_path, "C6_none")
    with pytest.raises(runner.IntegrityError, match="content-free telemetry"):
        runner.run_development_evaluation(request, hooks=_hooks(tmp_path))
    assert not request.output_root.exists()
    assert not list((tmp_path / "runtime").glob("phase12e2-*"))


def test_spawn_timeout_terminates_worker_continues_and_publishes_one_safe_record(
    tmp_path,
):
    events = []
    request = dataclasses_replace(
        _request(tmp_path, "C6_none"),
        case_timeout_seconds=0.25,
    )
    written = runner.run_development_evaluation(
        request,
        hooks=_hooks(
            tmp_path,
            worker_entrypoint=_timeout_probe_worker,
            worker_lifecycle_observer=lambda event, pid: events.append((event, pid)),
        ),
    )
    result = _load_written_result(written[0])
    timeout_records = [
        record for record in result["cases"] if record["case_status"] == "timeout"
    ]
    assert result["run_status"] == "partial"
    assert result["timeout_case_count"] == 1
    assert result["completed_case_count"] == 25
    assert len(timeout_records) == 1
    assert timeout_records[0]["case_id"] == "V2-DEV-0001"
    assert timeout_records[0]["correct"] is False
    assert timeout_records[0]["error_category"] == "case_timeout"
    assert next(
        record for record in result["cases"] if record["case_id"] == "V2-DEV-0002"
    )["case_status"] == "completed"

    serialized = json.dumps(result, ensure_ascii=False)
    assert "V2TOK" not in serialized
    assert "Traceback" not in serialized
    assert "exception_message" not in serialized
    assert result["safety_limits"]["case_timeout_seconds"] == 0.25

    terminated = {pid for event, pid in events if event == "terminate"}
    joined = {pid for event, pid in events if event == "joined"}
    assert len(terminated) == 2
    assert terminated <= joined
    assert not [
        child
        for child in multiprocessing.active_children()
        if child.name.startswith("phase12e2-case-worker-")
    ]


def test_timeout_state_corruption_aborts_instead_of_continuing(tmp_path):
    events = []
    request = dataclasses_replace(
        _request(tmp_path, "C6_none"),
        case_timeout_seconds=0.25,
    )
    with pytest.raises(runner.IntegrityError, match="retrieval state changed"):
        runner.run_development_evaluation(
            request,
            hooks=_hooks(
                tmp_path,
                worker_entrypoint=_corrupting_timeout_probe_worker,
                worker_lifecycle_observer=lambda event, pid: events.append((event, pid)),
            ),
        )
    assert not request.output_root.exists()
    assert any(event == "terminate" for event, _pid in events)
    assert not [
        child
        for child in multiprocessing.active_children()
        if child.name.startswith("phase12e2-case-worker-")
    ]
    assert not list((tmp_path / "runtime").glob("phase12e2-*"))


def test_c0_integration_dispatches_all_scopes_and_rejected_doc_is_not_retrieved(
    c0_integration_run,
):
    _root, _request_value, written = c0_integration_run
    result = _load_written_result(written)
    assert result["run_status"] == "complete"
    assert result["expected_case_count"] == 30
    assert result["completed_case_count"] == 30
    assert result["error_case_count"] == 0
    assert result["timeout_case_count"] == 0
    scopes = {scope: 0 for scope in runner.EVALUATION_SCOPES}
    for record in result["cases"]:
        scopes[record["evaluation_scope"]] += 1
    assert scopes == runner.EXPECTED_SCOPE_COUNTS_BY_SPLIT["development"]

    component = next(record for record in result["cases"] if record["evaluation_scope"] == "component")
    assert component["actual_document_ingestion_status"] == "rejected"
    assert component["actual_retrieved_count"] >= 0
    assert component["actual_target_document_hit_count"] == 0
    assert component["actual_provider_called"] is False

    availability = [
        record for record in result["cases"] if record["evaluation_scope"] == "availability_fault"
    ]
    assert all(record["actual_stop_reason"] == "top_k_rejected" for record in availability)
    assert all(record["actual_provider_called"] is False for record in availability)


def test_c6_integration_is_end_to_end_only_with_all_guards_disabled(c6_integration_run):
    root, _request_value, written = c6_integration_run
    result = _load_written_result(written)
    assert result["run_status"] == "complete"
    assert result["expected_case_count"] == 26
    assert {record["evaluation_scope"] for record in result["cases"]} == {"end_to_end"}
    assert all(value is False for value in result["guard_profile"].values())
    assert result["provider_id"] == "mock"
    assert result["safety_limits"]["temporary_sqlite_required"] is True
    assert result["safety_limits"]["network_disabled"] is True
    disabled_reasons = {
        stage["reason_code"]
        for record in result["cases"]
        for stage in record["stage_results"]
        if stage["enabled"] is False
    }
    assert disabled_reasons
    assert not list((root / "runtime").glob("phase12e2-*"))


def test_artifact_projection_contains_no_raw_runtime_content(c0_integration_run):
    _root, _request_value, written = c0_integration_run
    raw = written.result_path.read_text(encoding="utf-8")
    assert "V2TOK" not in raw
    assert '"answer":' not in raw
    assert '"raw_query":' not in raw
    assert '"detail":' not in raw
    assert "audit_ctx" not in raw
    runner.scan_forbidden_artifact_content(json.loads(raw))


def test_result_is_canonical_and_manifest_matches_hash_and_size(c0_integration_run):
    _root, _request_value, written = c0_integration_run
    result_bytes = written.result_path.read_bytes()
    parsed = json.loads(result_bytes)
    assert result_bytes == runner._canonical_json_bytes(parsed)  # noqa: SLF001

    manifest = json.loads(written.manifest_path.read_text(encoding="utf-8"))
    assert manifest["result_file"] == "result.json"
    assert manifest["result_sha256"] == hashlib.sha256(result_bytes).hexdigest()
    assert manifest["result_size_bytes"] == len(result_bytes)
    assert manifest["git_commit"] == TEST_COMMIT


def test_runner_leaves_aggregate_metrics_uncomputed(c0_integration_run):
    _root, _request_value, written = c0_integration_run
    aggregate = _load_written_result(written)["aggregate"]
    assert aggregate["metrics_computed"] is False
    assert aggregate["aomr"] is None
    assert aggregate["fpr"] is None
    assert aggregate["fnr"] is None
    assert aggregate["marginal_contribution"] is None


def test_no_overwrite_of_existing_run_directory(c0_integration_run):
    _root, _request_value, written = c0_integration_run
    artifact = _load_written_result(written)
    output_root = written.result_path.parents[6]
    with pytest.raises(runner.IntegrityError, match="overwrite refused"):
        runner._publish_artifact(output_root, artifact)  # noqa: SLF001


def test_failed_atomic_publish_removes_temporary_directory(
    c0_integration_run, tmp_path, monkeypatch
):
    _root, _request_value, written = c0_integration_run
    artifact = _load_written_result(written)
    artifact["run_id"] = "C0_all_on-atomic-failure"
    output_root = tmp_path / "atomic-output"
    final_directory = runner._run_directory(output_root, artifact)  # noqa: SLF001
    publish_error = OSError("rename failed")

    def fail_final_publish(staging_directory, requested_final_directory):
        assert requested_final_directory == final_directory
        result_path = staging_directory / "result.json"
        manifest_path = staging_directory / "result-manifest.json"
        assert result_path.is_file()
        assert manifest_path.is_file()
        result_bytes = result_path.read_bytes()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["result_sha256"] == hashlib.sha256(result_bytes).hexdigest()
        assert manifest["result_size_bytes"] == len(result_bytes)
        raise publish_error

    monkeypatch.setattr(runner, "_publish_directory_atomically", fail_final_publish)
    with pytest.raises(OSError, match="^rename failed$") as captured:
        runner._publish_artifact(output_root, artifact)  # noqa: SLF001
    assert captured.value is publish_error
    assert not final_directory.exists()
    assert not list(final_directory.parent.glob(".tmp-*"))
    assert not list(output_root.rglob("result.json"))
    assert not list(output_root.rglob("result-manifest.json"))


def test_atomic_publish_cleanup_failure_does_not_mask_original_error(
    c0_integration_run, tmp_path, monkeypatch
):
    _root, _request_value, written = c0_integration_run
    artifact = _load_written_result(written)
    artifact["run_id"] = "C0_all_on-cleanup-failure"
    output_root = tmp_path / "cleanup-failure-output"
    final_directory = runner._run_directory(output_root, artifact)  # noqa: SLF001
    publish_error = OSError("rename failed")

    def fail_final_publish(_staging_directory, _final_directory):
        raise publish_error

    def fail_cleanup(_staging_directory):
        raise OSError("cleanup failed")

    monkeypatch.setattr(runner, "_publish_directory_atomically", fail_final_publish)
    monkeypatch.setattr(runner, "_remove_staging_directory_best_effort", fail_cleanup)

    with pytest.raises(OSError, match="^rename failed$") as captured:
        runner._publish_artifact(output_root, artifact)  # noqa: SLF001
    assert captured.value is publish_error
    assert not final_directory.exists()

    # The injected cleanup failure deliberately leaves staging behind.
    for staging_directory in final_directory.parent.glob(".tmp-*"):
        shutil.rmtree(staging_directory)


def test_each_case_has_two_latency_repetitions_when_pipeline_reached(c0_integration_run):
    _root, _request_value, written = c0_integration_run
    result = _load_written_result(written)
    for record in result["cases"]:
        assert len(record["latency_ms_samples"]["end_to_end_with_audit"]) == 2
        if record["evaluation_scope"] in {"end_to_end", "residual_risk_only"}:
            assert len(record["latency_ms_samples"]["pipeline_pre_audit_total"]) == 2
        else:
            assert record["latency_ms_samples"]["pipeline_pre_audit_total"] == []


def dataclasses_replace(value, **changes):
    """Local tiny helper keeps the test imports focused on runner contracts."""
    import dataclasses

    return dataclasses.replace(value, **changes)
