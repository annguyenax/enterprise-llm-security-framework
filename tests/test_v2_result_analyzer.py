"""Phase 12E.3 result-analyzer integrity and methodology tests."""
from __future__ import annotations

import copy
import csv
import hashlib
import json
import shutil
from pathlib import Path

import pytest

from app.core.decisions import Decision
from app.core.pipeline import RagPipelineResult, StageResult
from scripts import analyze_v2_results as analyzer
from scripts import run_v2_evaluation as runner


TEST_BRANCH = "phase-12e-3-test"
TEST_COMMIT = "c" * 40


def _state() -> runner.RepositoryState:
    return runner.RepositoryState(
        branch=TEST_BRANCH,
        commit=TEST_COMMIT,
        dirty=False,
    )


def _hooks() -> analyzer.AnalyzerHooks:
    return analyzer.AnalyzerHooks(repository_state_loader=lambda _root: _state())


def _runner_projected_ablation_stages() -> tuple[dict, ...]:
    result = RagPipelineResult(
        request_id="safe-request-id",
        final_decision=Decision.ALLOW,
        answer="raw answer that must not enter telemetry",
        retrieved_count=1,
        accepted_context_count=1,
        rejected_context_count=0,
        stage_results=(
            StageResult(
                stage="input_guard",
                decision=None,
                reason_code="input_guard_disabled_ablation",
                detail="raw disabled-stage detail",
            ),
            StageResult(
                stage="retrieval",
                decision=None,
                reason_code="retrieval_completed",
                detail="raw informational-stage detail",
            ),
            StageResult(
                stage="rag_context_guard",
                decision=Decision.ALLOW,
                reason_code="context_guard_allow",
                detail="raw enabled-stage detail",
            ),
        ),
        latency_ms={"retrieval": 0.5, "rag_context_guard": 1.5, "total": 2.0},
        stop_reason="allowed",
        provider_called=True,
    )
    return runner._project_stage_results(  # noqa: SLF001
        result, runner.CONFIG_REGISTRY["C1_no_input"].profile
    )


def _safe_outcome(
    label: dict, *, stage_results: tuple[dict, ...] = ()
) -> runner.ScopeOutcome:
    return runner.ScopeOutcome(
        final_decision=label["allowed_final_decisions"][0],
        stop_reason=label["allowed_stop_reasons"][0],
        provider_called=bool(label["expected_provider_called"]),
        retrieved_count=0,
        accepted_context_count=0,
        rejected_context_count=0,
        redaction_count=0,
        dlp_finding_categories={},
        stage_results=stage_results,
        pipeline_pre_audit_ms=1.0,
        end_to_end_with_audit_ms=2.0,
    )


def _build_matrix(root: Path, *, split: str = "development") -> tuple[Path, ...]:
    benchmark_root = runner.ROOT / "datasets" / "v2"
    manifest = runner.verify_frozen_manifest(benchmark_root)
    benchmark = runner.load_split_benchmark(benchmark_root, split)
    repository = _state()
    settings = runner.load_settings()
    provider = runner.default_provider_spec(runner.SUPPORTED_PROVIDER_ID, settings)
    safety_limits = runner._settings_safety_limits(settings, 30.0)  # noqa: SLF001
    dependencies = ["phase12e3-test-fixture==1"]
    dependencies_sha256 = runner._sha256_bytes(  # noqa: SLF001
        runner._canonical_json_bytes(dependencies)  # noqa: SLF001
    )
    experiment_id = runner._experiment_id(  # noqa: SLF001
        repository,
        manifest,
        provider,
        safety_limits,
        dependencies_sha256,
        split,
    )
    expected_by_config, scopes_by_config = runner._expected_case_sets(  # noqa: SLF001
        benchmark, tuple(runner.CONFIG_REGISTRY)
    )
    cases_by_id = {case["case_id"]: case for case in benchmark.cases}
    output_root = root / "i"
    manifest_paths: list[Path] = []

    for config_id, config in runner.CONFIG_REGISTRY.items():
        expected_ids = expected_by_config[config_id]
        records = []
        for ordinal, case_id in enumerate(expected_ids):
            case = cases_by_id[case_id]
            label = benchmark.labels_by_id[case_id]
            stage_results = (
                _runner_projected_ablation_stages()
                if config_id == "C1_no_input" and ordinal == 0
                else ()
            )
            first = runner._case_completed_record(  # noqa: SLF001
                case=case,
                label=label,
                config=config,
                ordinal=ordinal,
                repository=repository,
                manifest=manifest,
                split=split,
                outcome=_safe_outcome(label, stage_results=stage_results),
            )
            records.append(runner._merge_repetition_latency(first, first))  # noqa: SLF001

        scope_sets = {
            scope: {
                "count": len(case_ids),
                "sha256": runner._case_set_hash(case_ids),  # noqa: SLF001
            }
            for scope, case_ids in scopes_by_config[config_id].items()
        }
        artifact = {
            "schema_version": runner.RESULT_SCHEMA_VERSION,
            "experiment_id": experiment_id,
            "run_id": f"{config_id}-synthetic-run",
            "run_status": "complete",
            "config_id": config_id,
            "config_hash": config.config_hash,
            "profile_id": config.profile.profile_id,
            "guard_profile": config.profile_payload,
            "environment": {
                "git_commit": repository.commit,
                "git_branch": repository.branch,
                "git_dirty": False,
                "python_version": "3-test",
                "platform": "test-platform",
                "cpu": "test-cpu",
                "benchmark_manifest_sha256": manifest.sha256,
                "benchmark_manifest_status": manifest.status,
                "dependencies": dependencies,
                "dependencies_sha256": dependencies_sha256,
                "enable_audit_log": True,
                "guard_profile": config.profile.profile_id,
                "provider_id": provider.provider_id,
                "provider_behavior_hash": provider.behavior_hash,
                "repetitions": 2,
                "warmup": 0,
                "aggregate_context_limit": settings.rag_max_aggregate_context_chars,
                "provider_output_limit": settings.dlp_max_inspect_chars,
                "result_schema_version": runner.RESULT_SCHEMA_VERSION,
            },
            "split": split,
            "provider_id": provider.provider_id,
            "provider_behavior_hash": provider.behavior_hash,
            "safety_limits": safety_limits,
            "expected_case_count": len(expected_ids),
            "expected_case_set_sha256": runner._case_set_hash(expected_ids),  # noqa: SLF001
            "expected_case_sets_by_scope": scope_sets,
            "completed_case_count": len(records),
            "error_case_count": 0,
            "timeout_case_count": 0,
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
        result_bytes = runner._canonical_json_bytes(artifact)  # noqa: SLF001
        result_manifest = {
            "schema_version": runner.RESULT_MANIFEST_SCHEMA_VERSION,
            "result_file": "result.json",
            "result_sha256": hashlib.sha256(result_bytes).hexdigest(),
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
        directory = output_root / config_id
        directory.mkdir(parents=True)
        (directory / "result.json").write_bytes(result_bytes)
        manifest_path = directory / "result-manifest.json"
        manifest_path.write_bytes(  # noqa: SLF001
            runner._canonical_json_bytes(result_manifest)
        )
        manifest_paths.append(manifest_path)
    return tuple(manifest_paths)


def _request(
    root: Path,
    manifests: tuple[Path, ...],
    *,
    split: str = "development",
    name: str = "analysis-output",
) -> analyzer.AnalysisRequest:
    return analyzer.AnalysisRequest(
        split=split,
        expected_branch=TEST_BRANCH,
        expected_commit=TEST_COMMIT,
        output_root=root / name,
        result_manifests=manifests,
    )


def _clone_manifests(manifests: tuple[Path, ...], root: Path) -> tuple[Path, ...]:
    copies = []
    for index, manifest in enumerate(manifests):
        destination = root / f"input-{index}"
        shutil.copytree(manifest.parent, destination)
        copies.append(destination / "result-manifest.json")
    return tuple(copies)


def _rewrite_result(manifest_path: Path, mutate) -> dict:
    result_path = manifest_path.parent / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    mutate(result)
    result_bytes = runner._canonical_json_bytes(result)  # noqa: SLF001
    result_path.write_bytes(result_bytes)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["result_sha256"] = hashlib.sha256(result_bytes).hexdigest()
    manifest["result_size_bytes"] = len(result_bytes)
    for manifest_field, result_field in (
        ("result_schema_version", "schema_version"),
        ("experiment_id", "experiment_id"),
        ("run_id", "run_id"),
        ("run_status", "run_status"),
        ("config_id", "config_id"),
        ("config_hash", "config_hash"),
        ("profile_id", "profile_id"),
        ("provider_id", "provider_id"),
        ("provider_behavior_hash", "provider_behavior_hash"),
        ("expected_case_set_sha256", "expected_case_set_sha256"),
    ):
        manifest[manifest_field] = result[result_field]
    manifest["git_commit"] = result["environment"]["git_commit"]
    manifest["benchmark_manifest_sha256"] = result["environment"][
        "benchmark_manifest_sha256"
    ]
    manifest_path.write_bytes(runner._canonical_json_bytes(manifest))  # noqa: SLF001
    return result


def _rewrite_manifest(manifest_path: Path, mutate) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mutate(manifest)
    manifest_path.write_bytes(runner._canonical_json_bytes(manifest))  # noqa: SLF001


def _make_first_case_error(result: dict) -> None:
    record = result["cases"][0]
    record["case_status"] = "error"
    record["error_category"] = "case_execution_error"
    for field_name in (
        "actual_final_decision",
        "actual_stop_reason",
        "actual_provider_called",
        "actual_retrieved_count",
        "actual_accepted_context_count",
        "actual_rejected_context_count",
        "actual_redaction_count",
        "actual_document_ingestion_status",
        "actual_target_document_hit_count",
    ):
        record[field_name] = None
    record["actual_dlp_finding_categories"] = {}
    record["correct"] = False
    record["stage_results"] = []
    record["latency_ms_samples"] = {
        "pipeline_pre_audit_total": [],
        "end_to_end_with_audit": [],
    }
    result["run_status"] = "partial"
    result["completed_case_count"] -= 1
    result["error_case_count"] = 1


def test_analyzer_accepts_runner_projected_disabled_stage_contract():
    projected = list(_runner_projected_ablation_stages())

    assert projected[0] == {
        "stage": "input_guard",
        "enabled": False,
        "decision": None,
        "reason_code": "input_guard_disabled_ablation",
        "execution_time_ms": None,
    }
    assert projected[1]["enabled"] is True
    assert projected[1]["decision"] == "allow"
    assert projected[1]["reason_code"] == "retrieval_completed"
    assert projected[2]["enabled"] is True
    assert projected[2]["decision"] == "allow"
    assert all("detail" not in stage for stage in projected)
    analyzer._validate_stage_results(projected, "case.stage_results")  # noqa: SLF001


def test_analyzer_rejects_non_null_decision_for_disabled_stage():
    projected = list(_runner_projected_ablation_stages())
    projected[0] = {**projected[0], "decision": "allow"}

    with pytest.raises(analyzer.AnalysisIntegrityError, match="must be null"):
        analyzer._validate_stage_results(projected, "case.stage_results")  # noqa: SLF001


@pytest.mark.parametrize("invalid_decision", [None, "unexpected"])
def test_analyzer_requires_supported_non_null_decision_for_enabled_stage(invalid_decision):
    projected = list(_runner_projected_ablation_stages())
    projected[1] = {**projected[1], "decision": invalid_decision}

    with pytest.raises(analyzer.AnalysisIntegrityError):
        analyzer._validate_stage_results(projected, "case.stage_results")  # noqa: SLF001


@pytest.fixture(scope="module")
def synthetic_matrix(tmp_path_factory) -> tuple[Path, tuple[Path, ...]]:
    root = tmp_path_factory.mktemp("phase12e3-matrix")
    return root, _build_matrix(root)


@pytest.fixture(scope="module")
def successful_analysis(synthetic_matrix):
    root, manifests = synthetic_matrix
    written = analyzer.analyze_results(
        _request(root, manifests),
        hooks=_hooks(),
    )
    return root, manifests, written


def test_authentic_ablated_runner_stage_record_passes_full_analysis(successful_analysis):
    _root, manifests, _written = successful_analysis
    c1_manifest = next(path for path in manifests if path.parent.name == "C1_no_input")
    result = json.loads((c1_manifest.parent / "result.json").read_text(encoding="utf-8"))
    projected = result["cases"][0]["stage_results"]

    assert projected == list(_runner_projected_ablation_stages())


def test_analyzer_publishes_exact_three_canonical_deterministic_files(
    successful_analysis,
    tmp_path,
):
    _root, manifests, first = successful_analysis
    second = analyzer.analyze_results(
        _request(tmp_path, manifests, name="second-analysis"),
        hooks=_hooks(),
    )
    assert sorted(path.name for path in first.output_directory.iterdir()) == [
        "analysis-manifest.json",
        "analysis-table.csv",
        "analysis.json",
    ]
    for filename in ("analysis.json", "analysis-table.csv", "analysis-manifest.json"):
        first_bytes = (first.output_directory / filename).read_bytes()
        second_bytes = (second.output_directory / filename).read_bytes()
        assert first_bytes == second_bytes
        assert first_bytes.endswith(b"\n")

    analysis_bytes = first.analysis_path.read_bytes()
    analysis = json.loads(analysis_bytes)
    assert analysis_bytes == runner._canonical_json_bytes(analysis)  # noqa: SLF001
    manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
    assert manifest["analysis_sha256"] == hashlib.sha256(analysis_bytes).hexdigest()
    assert manifest["analysis_size_bytes"] == len(analysis_bytes)
    table_bytes = first.table_path.read_bytes()
    assert manifest["table_sha256"] == hashlib.sha256(table_bytes).hexdigest()
    assert manifest["table_size_bytes"] == len(table_bytes)


def test_analysis_has_exact_family_counts_raw_rows_and_latency_policy(successful_analysis):
    analysis = json.loads(successful_analysis[2].analysis_path.read_text(encoding="utf-8"))
    assert len(analysis["configs"]["C0_all_on"]["by_family"]) == 23
    assert all(
        len(config["by_family"]) == 20
        for config_id, config in analysis["configs"].items()
        if config_id != "C0_all_on"
    )
    for config in analysis["configs"].values():
        for row in config["by_family"]:
            assert set(row) == analyzer.FAMILY_ROW_KEYS
            assert not ({"rate", "value", "percentage", "ci", "wilson_95"} & set(row))
    assert analysis["latency"]["reportable"] is False
    assert analysis["latency"]["p50"] is None
    assert analysis["latency"]["p95"] is None
    assert analysis["latency"]["repetitions_observed"] == 2
    assert analysis["latency"]["warmup_observed"] == 0


def test_analysis_contains_no_abr_metric_macro_object_or_forbidden_claim(successful_analysis):
    analysis = json.loads(successful_analysis[2].analysis_path.read_text(encoding="utf-8"))

    def keys(value):
        if isinstance(value, dict):
            return set(value) | {key for nested in value.values() for key in keys(nested)}
        if isinstance(value, list):
            return {key for nested in value for key in keys(nested)}
        return set()

    serialized = successful_analysis[2].analysis_path.read_text(encoding="utf-8")
    table = successful_analysis[2].table_path.read_text(encoding="utf-8")
    assert "abr" not in keys(analysis)
    assert "macro" not in keys(analysis)
    assert "Attack" + " Block Rate" not in serialized
    assert "Attack" + " Block Rate" not in table
    header = next(csv.reader(table.splitlines()))
    assert "abr" not in header
    assert "macro" not in header
    assert {
        "baseline_config_id",
        "ablated_config_id",
        "paired_case_ids_sha256",
        "both_correct",
        "baseline_only",
        "ablated_only",
        "both_incorrect",
    } <= set(header)


def test_marginal_pairs_are_complete_and_mock_limitations_are_explicit(successful_analysis):
    analysis = json.loads(successful_analysis[2].analysis_path.read_text(encoding="utf-8"))
    rows = analysis["marginal"]
    assert [row["ablated_config_id"] for row in rows] == [
        "C1_no_input",
        "C2_no_provenance",
        "C3_no_context",
        "C4_no_dlp",
        "C5_no_output",
    ]
    for row in rows:
        assert (
            row["both_correct"]
            + row["baseline_only"]
            + row["ablated_only"]
            + row["both_incorrect"]
            == row["paired_n_M"]
        )
    assert [row["mock_provider_limitation"] for row in rows] == [
        False,
        False,
        False,
        True,
        True,
    ]


def test_rate_policy_handles_zero_small_and_reportable_denominators():
    zero = analyzer.make_rate(0, 0, wilson=True)
    assert zero == {
        "numerator": 0,
        "denominator": 0,
        "n": 0,
        "defined": False,
        "reporting_eligible": False,
        "value": None,
        "ineligibility_reason": "zero_denominator",
        "wilson_95": {"low": None, "high": None, "eligible": False},
    }
    small = analyzer.make_rate(4, 9, wilson=True)
    assert small["defined"] is True
    assert small["reporting_eligible"] is False
    assert small["value"] is None
    assert small["ineligibility_reason"] == "n_below_10"
    assert small["wilson_95"]["eligible"] is False
    eligible = analyzer.make_rate(5, 10, wilson=True)
    assert eligible["value"] == 0.5
    assert eligible["reporting_eligible"] is True
    assert eligible["wilson_95"]["eligible"] is True
    assert 0 <= eligible["wilson_95"]["low"] < eligible["wilson_95"]["high"] <= 1


def test_mapping_is_complete_disjoint_and_rejects_data_exfiltration_group():
    benchmark = runner.load_split_benchmark(
        runner.ROOT / "datasets" / "v2", "development"
    )
    analyzer.validate_family_mapping(benchmark)
    mapped = [
        family
        for families in analyzer.ANALYSIS_GROUPS.values()
        for family in families
    ]
    assert len(mapped) == len(set(mapped)) == 20
    assert set(analyzer.ANALYSIS_GROUPS["leakage_mechanisms"]) == {
        "leakage_context_exclusion",
        "leakage_dlp_mechanism_reference",
    }
    changed = dict(analyzer.ANALYSIS_GROUPS)
    changed["data_exfiltration"] = ()
    with pytest.raises(analyzer.AnalysisError, match="unsupported analysis group"):
        analyzer.validate_family_mapping(benchmark, groups=changed)


def test_parser_accepts_validation_but_not_holdout_without_executing_either():
    args = analyzer.build_parser().parse_args(
        [
            "--split",
            "validation",
            "--expected-branch",
            TEST_BRANCH,
            "--expected-commit",
            TEST_COMMIT,
            "--output-root",
            "external-output",
            *sum(
                (["--result-manifest", f"input-{index}/result-manifest.json"] for index in range(8)),
                [],
            ),
        ]
    )
    assert args.split == "validation"
    with pytest.raises(SystemExit) as exc:
        analyzer.build_parser().parse_args(
            [
                "--split",
                "holdout",
                "--expected-branch",
                TEST_BRANCH,
                "--expected-commit",
                TEST_COMMIT,
                "--output-root",
                "external-output",
                *sum(
                    (["--result-manifest", f"input-{index}/result-manifest.json"] for index in range(8)),
                    [],
                ),
            ]
        )
    assert exc.value.code == 2


def test_direct_holdout_request_fails_before_repository_or_input_access(tmp_path):
    reached = []
    request = analyzer.AnalysisRequest(
        split="holdout",
        expected_branch=TEST_BRANCH,
        expected_commit=TEST_COMMIT,
        output_root=tmp_path / "must-not-exist",
        result_manifests=tuple(tmp_path / str(index) for index in range(8)),
    )
    hooks = analyzer.AnalyzerHooks(
        repository_state_loader=lambda _root: reached.append(True) or _state()
    )
    with pytest.raises(analyzer.AnalysisError, match="holdout is prohibited"):
        analyzer.analyze_results(request, hooks=hooks)
    assert reached == []
    assert not request.output_root.exists()


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda manifest: manifest.__setitem__("schema_version", 99), "schema"),
        (lambda manifest: manifest.__setitem__("result_sha256", "0" * 64), "SHA-256"),
        (
            lambda manifest: manifest.__setitem__(
                "result_size_bytes", manifest["result_size_bytes"] + 1
            ),
            "byte size",
        ),
    ],
)
def test_bad_manifest_schema_hash_or_size_aborts_without_output(
    synthetic_matrix,
    tmp_path,
    mutation,
    message,
):
    _root, source = synthetic_matrix
    manifests = _clone_manifests(source, tmp_path / "copies")
    _rewrite_manifest(manifests[0], mutation)
    request = _request(tmp_path, manifests)
    with pytest.raises(analyzer.AnalysisError, match=message):
        analyzer.analyze_results(request, hooks=_hooks())
    assert not request.output_root.exists()


def test_exact_eight_manifest_contract_rejects_missing_and_duplicate_arguments(
    synthetic_matrix,
    tmp_path,
):
    _root, manifests = synthetic_matrix
    for invalid in (manifests[:-1], (*manifests[:-1], manifests[0])):
        request = _request(tmp_path, tuple(invalid), name=f"invalid-{len(invalid)}")
        with pytest.raises(analyzer.AnalysisError, match="manifest"):
            analyzer.analyze_results(request, hooks=_hooks())
        assert not request.output_root.exists()


def test_duplicate_config_and_unknown_config_abort_without_output(synthetic_matrix, tmp_path):
    _root, source = synthetic_matrix
    manifests = _clone_manifests(source, tmp_path / "duplicate")
    duplicate_c0 = tmp_path / "duplicate-c0"
    shutil.copytree(manifests[0].parent, duplicate_c0)
    duplicate_matrix = (manifests[0], duplicate_c0 / "result-manifest.json", *manifests[2:])
    duplicate_request = _request(tmp_path, duplicate_matrix, name="duplicate-output")
    with pytest.raises(analyzer.AnalysisError, match="same configuration"):
        analyzer.analyze_results(duplicate_request, hooks=_hooks())
    assert not duplicate_request.output_root.exists()

    unknown = _clone_manifests(source, tmp_path / "unknown")
    _rewrite_result(unknown[1], lambda result: result.__setitem__("config_id", "C8_unknown"))
    unknown_request = _request(tmp_path, unknown, name="unknown-output")
    with pytest.raises(analyzer.AnalysisError, match="unknown configuration"):
        analyzer.analyze_results(unknown_request, hooks=_hooks())
    assert not unknown_request.output_root.exists()


def test_mixed_identity_and_experiment_contract_mismatch_abort(synthetic_matrix, tmp_path):
    _root, source = synthetic_matrix
    mixed = _clone_manifests(source, tmp_path / "mixed")
    _rewrite_result(
        mixed[1],
        lambda result: result["environment"].__setitem__("platform", "other-platform"),
    )
    mixed_request = _request(tmp_path, mixed, name="mixed-output")
    with pytest.raises(analyzer.AnalysisError, match="mixes experiment or environment"):
        analyzer.analyze_results(mixed_request, hooks=_hooks())
    assert not mixed_request.output_root.exists()

    wrong_experiment = _clone_manifests(source, tmp_path / "experiment")
    _rewrite_result(
        wrong_experiment[1],
        lambda result: result.__setitem__("experiment_id", "d" * 64),
    )
    experiment_request = _request(tmp_path, wrong_experiment, name="experiment-output")
    with pytest.raises(analyzer.AnalysisError, match="experiment identity"):
        analyzer.analyze_results(experiment_request, hooks=_hooks())
    assert not experiment_request.output_root.exists()


def test_partial_matrix_is_validated_then_rejected_before_metrics(synthetic_matrix, tmp_path):
    _root, source = synthetic_matrix
    manifests = _clone_manifests(source, tmp_path / "partial")
    _rewrite_result(manifests[0], _make_first_case_error)
    request = _request(tmp_path, manifests)
    with pytest.raises(analyzer.AnalysisError, match="diagnostic only"):
        analyzer.analyze_results(request, hooks=_hooks())
    assert not request.output_root.exists()


@pytest.mark.parametrize("defect", ["missing", "duplicate", "stored_correct"])
def test_case_completeness_and_stored_correct_are_recomputed(
    synthetic_matrix,
    tmp_path,
    defect,
):
    _root, source = synthetic_matrix
    manifests = _clone_manifests(source, tmp_path / defect)

    def mutate(result):
        if defect == "missing":
            result["cases"].pop()
        elif defect == "duplicate":
            result["cases"][1] = copy.deepcopy(result["cases"][0])
        else:
            result["cases"][0]["correct"] = False

    _rewrite_result(manifests[0], mutate)
    request = _request(tmp_path, manifests)
    with pytest.raises(analyzer.AnalysisError):
        analyzer.analyze_results(request, hooks=_hooks())
    assert not request.output_root.exists()


@pytest.mark.parametrize(
    "mutation",
    [
        lambda result: result.__setitem__("query", "must-not-persist"),
        lambda result: result["environment"].__setitem__(
            "platform", "C:\\private\\machine-path"
        ),
    ],
)
def test_forbidden_fields_and_absolute_paths_abort_without_output(
    synthetic_matrix,
    tmp_path,
    mutation,
):
    _root, source = synthetic_matrix
    manifests = _clone_manifests(source, tmp_path / "forbidden")
    _rewrite_result(manifests[0], mutation)
    request = _request(tmp_path, manifests)
    with pytest.raises((analyzer.AnalysisError, runner.IntegrityError)):
        analyzer.analyze_results(request, hooks=_hooks())
    assert not request.output_root.exists()


def test_malformed_unhashable_identifiers_fail_closed_without_type_error(
    synthetic_matrix,
    tmp_path,
):
    _root, source = synthetic_matrix
    manifests = _clone_manifests(source, tmp_path / "unhashable")
    _rewrite_result(manifests[0], lambda result: result.__setitem__("config_id", []))
    request = _request(tmp_path, manifests)
    with pytest.raises(analyzer.AnalysisError):
        analyzer.analyze_results(request, hooks=_hooks())
    assert not request.output_root.exists()


def test_external_output_policy_and_no_overwrite(successful_analysis, tmp_path):
    _root, manifests, written = successful_analysis
    internal_request = analyzer.AnalysisRequest(
        split="development",
        expected_branch=TEST_BRANCH,
        expected_commit=TEST_COMMIT,
        output_root=runner.ROOT / "analysis-must-not-be-created",
        result_manifests=manifests,
    )
    with pytest.raises(analyzer.AnalysisError, match="outside the repository"):
        analyzer.analyze_results(internal_request, hooks=_hooks())
    assert not internal_request.output_root.exists()

    overwrite_request = _request(tmp_path, manifests, name="already-exists")
    overwrite_request.output_root.mkdir()
    with pytest.raises(analyzer.AnalysisError, match="overwrite refused"):
        analyzer.analyze_results(overwrite_request, hooks=_hooks())
    assert not list(overwrite_request.output_root.iterdir())
    assert written.output_directory.exists()


def test_atomic_publish_failure_cleans_staging_and_preserves_original_exception(
    synthetic_matrix,
    tmp_path,
    monkeypatch,
):
    _root, manifests = synthetic_matrix
    request = _request(tmp_path, manifests, name="atomic-failure")
    publish_error = OSError("rename failed")

    def fail_publish(staging: Path, final: Path):
        assert final == request.output_root
        assert sorted(path.name for path in staging.iterdir()) == [
            "analysis-manifest.json",
            "analysis-table.csv",
            "analysis.json",
        ]
        raise publish_error

    monkeypatch.setattr(analyzer, "_publish_directory_atomically", fail_publish)
    with pytest.raises(OSError, match="^rename failed$") as captured:
        analyzer.analyze_results(request, hooks=_hooks())
    assert captured.value is publish_error
    assert not request.output_root.exists()
    assert not list(request.output_root.parent.glob(".tmp-analysis-*"))


def test_atomic_cleanup_failure_does_not_mask_publish_failure(
    synthetic_matrix,
    tmp_path,
    monkeypatch,
):
    _root, manifests = synthetic_matrix
    request = _request(tmp_path, manifests, name="cleanup-failure")
    publish_error = OSError("rename failed")
    staging_paths = []

    def fail_publish(staging: Path, _final: Path):
        staging_paths.append(staging)
        raise publish_error

    monkeypatch.setattr(analyzer, "_publish_directory_atomically", fail_publish)
    monkeypatch.setattr(
        analyzer,
        "_remove_staging_best_effort",
        lambda _staging: (_ for _ in ()).throw(OSError("cleanup failed")),
    )
    with pytest.raises(OSError, match="^rename failed$") as captured:
        analyzer.analyze_results(request, hooks=_hooks())
    assert captured.value is publish_error
    assert not request.output_root.exists()
    for staging in staging_paths:
        shutil.rmtree(staging)
