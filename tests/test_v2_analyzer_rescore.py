"""Synthetic rescore contracts. No holdout records or provider execution."""
from __future__ import annotations

import builtins
import copy
import hashlib
import io
import json
import os
import socket
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.config import OLLAMA_PRIMARY_MODEL
from app.core.decisions import Decision
from scripts import analyze_v2_results as analyzer
from scripts import run_v2_evaluation as runner

ANALYZER_COMMIT = "d" * 40
EXECUTION_COMMIT = "cc38fae8dc889b96f84c3adce176fe8e42a66961"
SENTINEL = "SYNTHETIC-CASE-DO-NOT-EXPORT"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, payload):
    raw = runner._canonical_json_bytes(payload)
    path.write_bytes(raw)
    return raw


@pytest.fixture(autouse=True)
def no_real_holdout_or_network(monkeypatch):
    # Tests control their own process environment. Production must reject even
    # equal-valued overrides; the parameterized negatives below prove that.
    for key in tuple(os.environ):
        if analyzer._PROVIDER_ENV_RE.match(key):
            monkeypatch.delenv(key)
    def forbidden(*args, **kwargs):
        pytest.fail("provider/network execution is prohibited")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    for owner, name in ((builtins, "open"), (io, "open")):
        original = getattr(owner, name)
        def guarded(file, mode="r", *args, _original=original, **kwargs):
            if isinstance(file, (str, os.PathLike)):
                path = Path(file).absolute()
                if path in {runner.ROOT / "datasets/v2/cases/holdout.jsonl",
                            runner.ROOT / "datasets/v2/labels/holdout.jsonl"}:
                    pytest.fail("real holdout must never be opened")
            return _original(file, mode, *args, **kwargs)
        monkeypatch.setattr(owner, name, guarded)


def synthetic_benchmark(split="holdout"):
    """SYNTHETIC / MOCK / in-sample: 60 cases, 52 end-to-end, 23 families."""
    families = [f for values in analyzer.ANALYSIS_GROUPS.values() for f in values]
    inventory = [(families[i % len(families)], "end_to_end") for i in range(52)]
    inventory += [("provenance_denied_at_ingestion", "component")] * 2
    inventory += [("availability_failure_case", "availability_fault")] * 4
    inventory += [("fragment_beyond_per_chunk_prefix", "residual_risk_only")] * 2
    cases, labels = [], {}
    for index, (family, scope) in enumerate(inventory):
        case_id = f"{SENTINEL}-{index:04d}"
        cases.append(dict(case_id=case_id, split=split, scenario_family=family, evaluation_scope=scope))
        labels[case_id] = dict(category="benign" if family in analyzer.ANALYSIS_GROUPS["benign_control"] else "malicious",
            allowed_final_decisions=[Decision.ALLOW.value], allowed_stop_reasons=["allowed"],
            expected_provider_called=True, scenario_family=family)
    # Exercise every runner-legal category and expected provider-call value.
    labels[cases[0]["case_id"]].update(category="mixed", expected_provider_called=None)
    labels[cases[1]["case_id"]]["category"] = "neutral"
    labels[cases[2]["case_id"]]["expected_provider_called"] = False
    return runner.LoadedBenchmark((), tuple(cases), labels)


def fixture_provider(settings, blobs):
    # Independent descriptor oracle copied from the execution runner contract.
    descriptor = dict(provider_id="ollama", implementation="app.services.providers.ollama.OllamaLLMProvider",
        implementation_sha256=sha(blobs["app/services/providers/ollama.py"]),
        model_tag=settings.llm_model_name, model_digest_expected=settings.ollama_model_digest,
        model_quantization_expected=settings.ollama_model_quantization,
        ollama_version_expected=settings.ollama_expected_version,
        options={key: getattr(settings, "ollama_" + key) for key in ("temperature", "seed", "num_ctx", "num_predict")},
        think=settings.ollama_think, repeat_count=settings.llm_repeat_count,
        endpoint="http://127.0.0.1:11434/api/chat", network="http_loopback",
        timeout_seconds=settings.llm_provider_timeout_seconds, keep_alive="30m",
        retry_policy=dict(max_retries=2, backoff_seconds=[0.5, 1.0], http_statuses=[500],
                          connection_errors=["connection_refused", "connection_reset", "timeout"]))
    return runner.ProviderSpec("ollama", lambda: pytest.fail("provider factory called"), descriptor)


def build_matrix(root, benchmark, repository, manifest, provider, settings, auth=None, *, network_disabled=None):
    split = benchmark.cases[0]["split"]
    schema = runner.HOLDOUT_RESULT_SCHEMA_VERSION if auth else runner.RESULT_SCHEMA_VERSION
    safety = runner._settings_safety_limits(settings, 30.0)
    if auth and provider.provider_id == "ollama":
        safety["network_disabled"] = False  # Match holdout_preflight without executing it.
    if network_disabled is not None:
        safety["network_disabled"] = network_disabled
    dependencies = ["synthetic-fixture==1"]
    dependency_hash = sha(runner._canonical_json_bytes(dependencies))
    experiment = runner._experiment_id(repository, manifest, provider, safety, dependency_hash, split)
    ids, scopes = runner._expected_case_sets(benchmark, tuple(runner.CONFIG_REGISTRY))
    by_id = {c["case_id"]: c for c in benchmark.cases}
    paths = []
    for config_id, config in runner.CONFIG_REGISTRY.items():
        records = []
        for ordinal, case_id in enumerate(ids[config_id]):
            label = benchmark.labels_by_id[case_id]
            outcome = runner.ScopeOutcome(final_decision=label["allowed_final_decisions"][0],
                stop_reason=label["allowed_stop_reasons"][0], provider_called=True,
                retrieved_count=0, accepted_context_count=0, rejected_context_count=0,
                redaction_count=0, dlp_finding_categories={}, stage_results=(),
                pipeline_pre_audit_ms=1.0, end_to_end_with_audit_ms=2.0)
            first = runner._case_completed_record(case=by_id[case_id], label=label, config=config,
                ordinal=ordinal, repository=repository, manifest=manifest, split=split, outcome=outcome)
            records.append(runner._merge_repetition_latency(first, first))
        env = dict(git_commit=repository.commit, git_branch=repository.branch, git_dirty=False,
            python_version="3-fixture", platform="synthetic", cpu="synthetic",
            benchmark_manifest_sha256=manifest.sha256, benchmark_manifest_status="final",
            dependencies=dependencies, dependencies_sha256=dependency_hash, enable_audit_log=True,
            guard_profile=config.profile.profile_id, provider_id=provider.provider_id,
            provider_behavior_hash=provider.behavior_hash, repetitions=2, warmup=0,
            aggregate_context_limit=settings.rag_max_aggregate_context_chars,
            provider_output_limit=settings.dlp_max_inspect_chars, result_schema_version=schema)
        result = dict(schema_version=schema, experiment_id=experiment, run_id=f"{config_id}-fixture-run",
            run_status="complete", config_id=config_id, config_hash=config.config_hash,
            profile_id=config.profile.profile_id, guard_profile=config.profile_payload, environment=env,
            split=split, provider_id=provider.provider_id, provider_behavior_hash=provider.behavior_hash,
            safety_limits=safety, expected_case_count=len(records), expected_case_set_sha256=runner._case_set_hash(ids[config_id]),
            expected_case_sets_by_scope={scope: dict(count=len(values), sha256=runner._case_set_hash(values))
                                        for scope, values in scopes[config_id].items()},
            completed_case_count=len(records), error_case_count=0, timeout_case_count=0, skipped_case_count=0,
            cases=records, aggregate=dict(n_end_to_end=sum(c["evaluation_scope"] == "end_to_end" for c in records),
                aomr=None, fpr=None, fnr=None, marginal_contribution=None, metrics_computed=False,
                note="computed by the analysis step, not the runner"))
        if auth:
            result.update({key: analyzer._holdout_identity_value(auth, key) for key in analyzer.HOLDOUT_IDENTITY_KEYS})
        directory = root / "runs" / experiment / config_id / result["run_id"]
        directory.mkdir(parents=True)
        raw = write_json(directory / "result.json", result)
        result_manifest = dict(schema_version=1, result_file="result.json", result_sha256=sha(raw),
            result_size_bytes=len(raw), result_schema_version=schema, git_commit=repository.commit,
            benchmark_manifest_sha256=manifest.sha256)
        for key in ("experiment_id", "run_id", "run_status", "config_id", "config_hash", "profile_id",
                    "provider_id", "provider_behavior_hash", "expected_case_set_sha256"):
            result_manifest[key] = result[key]
        if auth:
            result_manifest.update({key: result[key] for key in analyzer.HOLDOUT_IDENTITY_KEYS})
        path = directory / "result-manifest.json"
        write_json(path, result_manifest)
        paths.append(path)
    return tuple(paths)


@pytest.fixture
def attempt(tmp_path, monkeypatch):
    p = analyzer.OFFICIAL_RESCORE_PROFILE
    root = tmp_path / "synthetic-input"
    root.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    settings = replace(runner.load_settings(), llm_provider="ollama", llm_model_name=OLLAMA_PRIMARY_MODEL)
    blobs = {name: (runner.ROOT / name).read_bytes() for name in (
        "app/core/config.py", "scripts/run_v2_evaluation.py", "app/services/providers/ollama.py")}
    provider = fixture_provider(settings, blobs)
    payload = dict(schema_version=1, authorization_id="0f9a1c2d-3e4b-4a5c-8d6e-7f8091a2b3c4",
        issued_at_utc="2026-11-11T14:00:00Z", issued_by=p.issued_by, purpose=runner.HOLDOUT_AUTHORIZATION_PURPOSE,
        execution_branch=p.execution_branch, execution_commit=p.execution_commit, benchmark_manifest_sha256="a" * 64,
        provider_id="ollama", config_ids=list(runner.CONFIG_REGISTRY),
        config_hashes={k: v.config_hash for k, v in runner.CONFIG_REGISTRY.items()},
        result_schema_version=1, result_manifest_schema_version=1, analysis_schema_version=1,
        analysis_manifest_schema_version=1, analysis_contract_sha256=analyzer.ANALYSIS_CONTRACT_SHA256,
        mapping_sha256=analyzer.MAPPING_SHA256, output_root=str(root), attempt=1,
        supersedes_authorization_sha256=None, holdout_authorized=True)
    auth_path = tmp_path / "authorization.json"
    auth_raw = runner._canonical_authorization_bytes(payload)
    auth_path.write_bytes(auth_raw)
    auth = runner.parse_holdout_authorization(auth_path)
    frozen = dict(execution_commit=p.execution_commit, provider_id="ollama", run_id=p.run_id,
        temperature=0.0, seed=42, num_ctx=4096, num_predict=512, model_tag=settings.llm_model_name,
        model_digest_expected=settings.ollama_model_digest, model_quantization_expected=settings.ollama_model_quantization,
        ollama_version_expected=settings.ollama_expected_version, think=False, repeat_count=1,
        authorization_sha256=auth.authorization_sha256, provider_behavior_hash=provider.behavior_hash)
    freeze_path = tmp_path / "freeze.json"
    freeze_raw = write_json(freeze_path, frozen)
    execution = runner.RepositoryState(p.execution_branch, p.execution_commit, False)
    manifest = runner.ManifestIdentity(payload["benchmark_manifest_sha256"], "final", 0)
    receipt = runner.build_start_receipt(auth, repository=execution, manifest=manifest,
                                         started_at_utc="2026-11-11T14:01:00Z")
    write_json(root / "start-receipt.json", receipt)
    paths = build_matrix(root, synthetic_benchmark(), execution, manifest, provider, settings, auth)
    bindings = tuple(analyzer.ResultBinding(path.parent.parent.name, sha(path.read_bytes()),
        sha((path.parent / "result.json").read_bytes()), (path.parent / "result.json").stat().st_size) for path in paths)
    profile = replace(p, output_root=str(root), authorization_sha256=sha(auth_raw), freeze_sha256=sha(freeze_raw), bindings=bindings)
    monkeypatch.setattr(analyzer, "OFFICIAL_RESCORE_PROFILE", profile)
    calls = []
    def blob_loader(root, commit, path):
        calls.append((commit, path))
        return blobs[path]
    state = runner.RepositoryState("feat/002-003-spec-v5", ANALYZER_COMMIT, False)
    hooks = analyzer.AnalyzerHooks(repository_state_loader=lambda root: state, git_blob_loader=blob_loader)
    output = tmp_path / f"p2-analysis-cc38fae-{ANALYZER_COMMIT}"
    request = analyzer.RescoreRequest(profile.binding_profile, root, auth_path, sha(auth_raw),
        freeze_path, sha(freeze_raw), bindings, ANALYZER_COMMIT, output)
    for name in ("load_authorized_holdout_benchmark", "_load_frozen_split"):
        monkeypatch.setattr(runner, name, lambda *a, **k: pytest.fail("rescore tried to read dataset records"))
    monkeypatch.setattr(analyzer, "_load_authorized_holdout_benchmark_for_analysis",
                        lambda *a, **k: pytest.fail("rescore tried the legacy holdout loader"))
    monkeypatch.setattr(runner, "_verify_holdout_identity_preclaim",
                        lambda *a, **k: pytest.fail("rescore tried runner execution verifier"))
    monkeypatch.setattr(analyzer, "load_settings", lambda: pytest.fail("rescore tried live settings"))
    return SimpleNamespace(root=root, repo=repo, request=request, hooks=hooks, paths=paths, auth=auth,
        state=state, blobs=blobs, calls=calls, profile=profile, settings=settings, manifest=manifest,
        monkeypatch=monkeypatch)


def run(a, **changes):
    return analyzer.analyze_authorized_ollama_rescore(replace(a.request, **changes), repo_root=a.repo, hooks=a.hooks)


def rebind(a, *, config=0, result_change=None, manifest_change=None):
    """Mutate a synthetic input, then bind its actual new bytes for gate tests."""
    path = a.paths[config]
    result_path = path.parent / "result.json"
    result = json.loads(result_path.read_bytes())
    manifest = json.loads(path.read_bytes())
    if result_change:
        result_change(result)
    raw = write_json(result_path, result)
    manifest.update(result_sha256=sha(raw), result_size_bytes=len(raw))
    if manifest_change:
        manifest_change(manifest)
    manifest_raw = write_json(path, manifest)
    bindings = list(a.request.bindings)
    bindings[config] = analyzer.ResultBinding(bindings[config].config_id, sha(manifest_raw), sha(raw), len(raw))
    a.profile = replace(a.profile, bindings=tuple(bindings))
    a.request = replace(a.request, bindings=tuple(bindings))
    a.monkeypatch.setattr(analyzer, "OFFICIAL_RESCORE_PROFILE", a.profile)


def rebind_identity_file(a, kind, change):
    path = getattr(a.request, kind)
    payload = json.loads(path.read_bytes())
    change(payload)
    raw = runner._canonical_authorization_bytes(payload) if kind == "authorization" else runner._canonical_json_bytes(payload)
    path.write_bytes(raw)
    key = kind + "_sha256"
    a.profile = replace(a.profile, **{key: sha(raw)})
    a.request = replace(a.request, **{key: sha(raw)})
    a.monkeypatch.setattr(analyzer, "OFFICIAL_RESCORE_PROFILE", a.profile)


def cli(a):
    req = a.request
    args = ["rescore-authorized-ollama"]
    for key in ("binding_profile", "attempt_root", "authorization", "authorization_sha256", "freeze",
                "freeze_sha256", "expected_analyzer_commit", "output_root"):
        args.extend(["--" + key.replace("_", "-"), str(getattr(req, key))])
    for b in req.bindings:
        args.extend(["--result-binding", f"{b.config_id}={b.manifest_sha256}:{b.result_sha256}:{b.result_size_bytes}"])
    return args


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_production_profile_literals_match_official():
    p = analyzer.OFFICIAL_RESCORE_PROFILE
    assert p.execution_commit == EXECUTION_COMMIT
    assert analyzer._FULL_SHA_RE.fullmatch(p.execution_commit)
    assert (p.binding_profile, p.execution_branch, p.provider_id, p.issued_by, p.attempt,
            p.output_root, p.run_id) == ("P2-20261111-cc38fae-01", "feat-002-003-spec-v5", "ollama",
        "maintainer:annguyenax", 1, r"D:\DoAnThucTap\p2-output", "P2-20261111-cc38fae-01")
    assert p.authorization_sha256 == "7b00ccec576b910f1eca9df8cea8452357e89d4a115da4f79a56327dfcb608ca"
    assert p.freeze_sha256 == "e73399c484a6fdce06950e9f8eb569bbe509737b67f5327f8dee39d81afb40a3"
    expected = [
        ("C0_all_on", "88591e6b2fc36481f3ec5ff29f68eb1036ffb7f8e4f7d657142e5359118f661a", "e927b9ddde2bd3fb91ca2f59b1502f7b3e09ae8315ddb0a124eb53b408268bc7", 166772),
        ("C1_no_input", "865d46528295c55f31c888675c5730fe40e868db434708ff053a632c27d1ec08", "3f5cf624a544d77349f778ffdeb89abc3439945a8909ef47dea358058ace13c1", 155720),
        ("C2_no_provenance", "639c22f115678a283c9d3d574a2d8a38a04c3225c76f383ad7d7ef2cdf4ce900", "32eaf2f4210ca48cb28bb7f6383a982165c511bba52370c89afc42c0833d6c53", 153302),
        ("C3_no_context", "83c1c2f926db53adb8a3f33d451c7bf6f92d10fd6c24b703b690a937a4c59518", "478de69c571ee0dd18ba6b8e95cfde8f541954bde852b952aade644f11a25cbe", 124166),
        ("C4_no_dlp", "c2dfe4ce1870daf08d0c8c74107fbe22c0017491c61095866dbcd49de840bae7", "bacb75ddc67f8aca0acae4c88a276fb42aea0c79c230ef1de0c24e3e02676eb4", 152651),
        ("C5_no_output", "5c5eaa4a18422bdf2d2e82a425aac81c40b338e6fb12566087ce5ca6091f7252", "568e7e2eb34911666d8baf91ae91ac3bd3ee1515969bc36d79949bc147f25340", 153016),
        ("C6_none", "9d5267cf1f49741d9ca6121a014279124cb6bb09c84a5f6d6de9115444a06f60", "b63e2c9338052935f39dd2b6036bfc911bab96d897d0f7a5e8beff7a587c076e", 124326),
        ("C7_no_context_no_output", "2d253760e37797fb9d7d9ae6662267fe5df82273790e4d26577aafbff3517c7e", "bb082c86d0d8ad2127c625a42a2a28852ba7d2f0b67702bb1a473b835c6d6138", 124522),
    ]
    assert [tuple(vars(b).values()) for b in p.bindings] == expected
    assert tuple(b.config_id for b in p.bindings) == tuple(runner.CONFIG_REGISTRY)


def test_authorized_ollama_rescore_end_to_end(attempt, monkeypatch, capsys):
    a = attempt
    original = analyzer.analyze_authorized_ollama_rescore
    monkeypatch.setattr(analyzer, "analyze_authorized_ollama_rescore",
                        lambda req: original(req, repo_root=a.repo, hooks=a.hooks))
    assert analyzer.main(cli(a)) == 0
    assert "FAIL" not in capsys.readouterr().err
    analysis = json.loads((a.request.output_root / "analysis.json").read_bytes())
    assert analysis["configs"]["C0_all_on"]["coverage"]["value"] == 1.0
    assert analysis["configs"]["C0_all_on"]["expected_case_count"] == 60
    assert all(analysis["configs"][key]["expected_case_count"] == 52 for key in list(runner.CONFIG_REGISTRY)[1:])


def test_synthetic_mock_in_sample_runner_legal_ollama_rescore(attempt):
    """SYNTHETIC / MOCK / in-sample only; Ollama-shaped artifacts, no inference."""
    assert len(attempt.paths) == 8
    for path in attempt.paths:
        result = json.loads((path.parent / "result.json").read_bytes())
        assert result["provider_id"] == "ollama"
        assert result["schema_version"] == runner.HOLDOUT_RESULT_SCHEMA_VERSION
        assert result["safety_limits"]["network_disabled"] is False
        assert result["safety_limits"]["temporary_sqlite_required"] is True
        assert all(result[key] == analyzer._holdout_identity_value(attempt.auth, key)
                   for key in analyzer.HOLDOUT_IDENTITY_KEYS)
        records = result["cases"]
        assert {record["category"] for record in records} == {"benign", "malicious", "mixed", "neutral"}
        assert {record["expected_outcome"]["provider_called"] for record in records} == {True, False, None}
        assert all(type(record["actual_provider_called"]) is bool for record in records)
        assert all(len(record["latency_ms_samples"][key]) == 2
                   for record in records for key in analyzer.LATENCY_SAMPLE_KEYS)

    written = run(attempt)
    analysis = json.loads(written.analysis_path.read_bytes())
    assert tuple(analysis["configs"]) == tuple(runner.CONFIG_REGISTRY)
    for config in analysis["configs"].values():
        # 52 end-to-end slots: 31 malicious, one mixed, one neutral, 19 benign.
        assert config["confusion"] == dict(TP=32, FN=0, TN=19, FP=0, n_M=32, n_B=19)
        assert config["aomr"]["numerator"] == config["aomr"]["denominator"] == 32
        assert config["fpr"]["numerator"] == 0
        assert config["fpr"]["denominator"] == 19


@pytest.mark.parametrize("value", [0, 1, "true", [], {}])
def test_rescore_rejects_non_boolean_non_null_expected_provider_call(attempt, value):
    rebind(attempt, result_change=lambda obj: obj["cases"][0]["expected_outcome"].update(provider_called=value))
    with pytest.raises(analyzer.AnalysisError, match="expected provider call must be boolean"):
        run(attempt)
    assert not attempt.request.output_root.exists()


@pytest.mark.parametrize("field,value", [
    ("network_disabled", True), ("network_disabled", 0), ("network_disabled", None),
    ("temporary_sqlite_required", False),
])
def test_verified_ollama_safety_flags_remain_strict(attempt, field, value):
    context, inputs = analyzer._verify_holdout_rescore_identity_preclaim(
        attempt.request, repo_root=attempt.repo, hooks=attempt.hooks)
    result = copy.deepcopy(inputs[0].result)
    result["safety_limits"][field] = value
    with pytest.raises(analyzer.AnalysisError) as error:
        analyzer._validate_result(replace(inputs[0], result=result), repository=attempt.state,
            manifest_identity=attempt.manifest, benchmark=synthetic_benchmark(),
            expected_split="holdout", context=context)
    assert error.value.code == "safety_identity"
    assert field in str(error.value)


@pytest.mark.parametrize("value", [None, 0])
def test_rescore_completed_actual_provider_call_remains_boolean(attempt, value):
    rebind(attempt, result_change=lambda obj: obj["cases"][0].update(actual_provider_called=value))
    with pytest.raises(analyzer.AnalysisError, match="actual_provider_called must be boolean"):
        run(attempt)
    assert not attempt.request.output_root.exists()


def test_rescore_splits_execution_and_analyzer_commit(attempt):
    written = run(attempt)
    doc = json.loads(written.analysis_path.read_bytes())
    assert doc["identity"]["git_commit"] == doc["execution_commit"] == EXECUTION_COMMIT
    assert doc["analyzer_commit"] == doc["analyzer_repository"]["git_commit"] == ANALYZER_COMMIT
    assert doc["identity"]["git_dirty"] is doc["analyzer_repository"]["git_dirty"] is False


def test_rescore_records_live_branch_separately(attempt):
    doc = json.loads(run(attempt).analysis_path.read_bytes())
    assert doc["identity"]["git_branch"] == "feat-002-003-spec-v5"
    assert doc["analyzer_repository"]["git_branch"] == "feat/002-003-spec-v5"


@pytest.mark.parametrize("kind", ["staged", "unstaged", "untracked"])
def test_rescore_rejects_dirty_analyzer_repository(attempt, kind):
    hooks = replace(attempt.hooks, repository_state_loader=lambda root: replace(attempt.state, dirty=True))
    with pytest.raises(analyzer.AnalysisError, match="clean"):
        analyzer.analyze_authorized_ollama_rescore(attempt.request, repo_root=attempt.repo, hooks=hooks)
    assert not attempt.request.output_root.exists()


@pytest.mark.parametrize("head", ["e" * 40, EXECUTION_COMMIT, "bad"])
def test_rescore_rejects_unexpected_analyzer_head(attempt, head):
    with pytest.raises(analyzer.AnalysisError):
        run(attempt, expected_analyzer_commit=head)


@pytest.mark.parametrize("kind", ["authorization", "freeze"])
@pytest.mark.parametrize("explicit", [False, True])
def test_rescore_rejects_identity_hash_mismatch(attempt, kind, explicit):
    if explicit:
        with pytest.raises(analyzer.AnalysisError):
            run(attempt, **{kind + "_sha256": "0" * 64})
    else:
        getattr(attempt.request, kind).write_bytes(b"{}\n")
        with pytest.raises(analyzer.AnalysisError, match="bytes differ"):
            run(attempt)
    assert not attempt.request.output_root.exists()


@pytest.mark.parametrize("config", range(8))
@pytest.mark.parametrize("artifact", ["manifest", "result"])
def test_rescore_rejects_manifest_or_result_hash_mismatch(attempt, config, artifact):
    path = attempt.paths[config] if artifact == "manifest" else attempt.paths[config].parent / "result.json"
    raw = path.read_bytes()
    path.write_bytes(raw.replace(b"complete", b"invalide", 1))
    with pytest.raises(analyzer.AnalysisError):
        run(attempt)
    assert not attempt.request.output_root.exists()


def test_rescore_rejects_result_size_mismatch(attempt):
    with (attempt.paths[0].parent / "result.json").open("ab") as handle:
        handle.write(b" ")
    with pytest.raises(analyzer.AnalysisError, match="size"):
        run(attempt)


@pytest.mark.parametrize("kind", ["missing", "duplicate", "extra"])
def test_rescore_requires_exact_config_inventory(attempt, kind):
    args = cli(attempt)
    if kind == "missing":
        args = args[:-2]
    elif kind == "duplicate":
        args[-1] = args[-3]
    else:
        args += ["--result-binding", "C8_extra=" + "0" * 64 + ":" + "0" * 64 + ":1"]
    parsed = analyzer.build_rescore_parser().parse_args(args[1:])
    with pytest.raises(analyzer.AnalysisError):
        analyzer._rescore_request_from_args(parsed)


@pytest.mark.parametrize("flag", ["--allow-non-mock", "--skip-integrity", "--force", "--provider", "--binding-prof", "--unknown"])
def test_rescore_parser_rejects_unknown_and_abbreviated_options(attempt, flag):
    with pytest.raises(SystemExit):
        analyzer.main(cli(attempt) + [flag, "x"])


@pytest.mark.parametrize("binding", ["C0_all_on=bad", "C0_all_on=" + "A" * 64 + ":" + "0" * 64 + ":1",
                                     "C0_all_on=" + "0" * 64 + ":" + "0" * 64 + ":0",
                                     "C0_all_on=" + "0" * 64 + ":" + "0" * 64 + ":1.2"])
def test_rescore_parser_rejects_bad_digest_and_size(attempt, binding):
    args = cli(attempt)
    args[-1] = binding
    with pytest.raises(SystemExit):
        analyzer.main(args)


def test_rescore_requires_authorization(attempt):
    args = cli(attempt)
    index = args.index("--authorization")
    del args[index:index + 2]
    with pytest.raises(SystemExit):
        analyzer.main(args)
    attempt.request.authorization.unlink()
    with pytest.raises(OSError):
        run(attempt)
    assert not attempt.request.output_root.exists()


@pytest.mark.parametrize("location", ["authorization", "freeze", "manifest", "result", "environment"])
def test_rescore_rejects_cloud_provider(attempt, location):
    if location in {"authorization", "freeze"}:
        rebind_identity_file(attempt, location, lambda obj: obj.update(provider_id="openai"))
    elif location == "manifest":
        rebind(attempt, manifest_change=lambda obj: obj.update(provider_id="openai"))
    else:
        rebind(attempt, result_change=lambda obj: (obj if location == "result" else obj["environment"]).update(provider_id="openai"))
    with pytest.raises((analyzer.AnalysisError, runner.RunnerError)):
        run(attempt)


def test_rescore_uses_execution_pinned_settings(attempt):
    run(attempt)
    assert attempt.calls == [(EXECUTION_COMMIT, path) for path in attempt.blobs]


@pytest.mark.parametrize("key", ["LLM_PROVIDER", "LLM_MODEL_NAME", "LLM_PROVIDER_TIMEOUT_SECONDS", "LLM_REPEAT_COUNT",
    "OLLAMA_MODEL_DIGEST", "OLLAMA_MODEL_QUANTIZATION", "OLLAMA_BACKUP_MODEL_NAME", "OLLAMA_BACKUP_MODEL_DIGEST",
    "OLLAMA_BACKUP_MODEL_QUANTIZATION", "OLLAMA_EXPECTED_VERSION", "OLLAMA_TEMPERATURE", "OLLAMA_SEED",
    "OLLAMA_NUM_CTX", "OLLAMA_NUM_PREDICT", "OLLAMA_THINK", "OLLAMA_MAX_RETRIES", "OLLAMA_KEEP_ALIVE",
    "OLLAMA_EMBEDDING_BASE_URL", "PREFIX_OLLAMA_MODEL"])
@pytest.mark.parametrize("value", ["42", "changed"])
def test_rescore_rejects_provider_environment_overrides(attempt, monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(analyzer.AnalysisError, match="override"):
        run(attempt)


@pytest.mark.parametrize("name", [".env", ".env.local", "settings.local.json", "config.local.toml"])
def test_rescore_rejects_local_provider_settings_overrides(attempt, name):
    (attempt.repo / name).write_text("OLLAMA_SEED=42\n", encoding="utf-8")
    with pytest.raises(analyzer.AnalysisError, match="override"):
        run(attempt)


@pytest.mark.parametrize("location", ["freeze", "settings", "result", "manifest", "environment"])
def test_rescore_rejects_inconsistent_ollama_behavior(attempt, location):
    if location == "settings":
        attempt.blobs["app/core/config.py"] = attempt.blobs["app/core/config.py"].replace(b'"4096"', b'"8192"')
    elif location == "freeze":
        rebind_identity_file(attempt, "freeze", lambda obj: obj.update(provider_behavior_hash="0" * 64))
    elif location == "manifest":
        rebind(attempt, manifest_change=lambda obj: obj.update(provider_behavior_hash="0" * 64))
    else:
        rebind(attempt, result_change=lambda obj: (obj if location == "result" else obj["environment"]).update(provider_behavior_hash="0" * 64))
    with pytest.raises((analyzer.AnalysisError, runner.RunnerError)):
        run(attempt)


@pytest.mark.parametrize("field,value", [("git_commit", "e" * 40), ("git_branch", "wrong-branch"), ("git_dirty", True)])
def test_rescore_rejects_execution_identity_mismatch(attempt, field, value):
    rebind(attempt, result_change=lambda obj: obj["environment"].update({field: value}))
    with pytest.raises(analyzer.AnalysisError):
        run(attempt)


@pytest.mark.parametrize("kind,field,value", [("authorization", "attempt", 2), ("authorization", "issued_by", "other"),
    ("authorization", "execution_commit", "e" * 40), ("authorization", "execution_branch", "wrong"),
    ("freeze", "run_id", "wrong")])
def test_rescore_rejects_authorization_or_run_identity(attempt, kind, field, value):
    rebind_identity_file(attempt, kind, lambda obj: obj.update({field: value}))
    with pytest.raises((analyzer.AnalysisError, runner.RunnerError)):
        run(attempt)


@pytest.mark.parametrize("kind", ["missing", "invalid", "other-commit", "other-authorization"])
def test_rescore_rejects_missing_or_invalid_receipt(attempt, kind):
    path = attempt.root / "start-receipt.json"
    if kind == "missing":
        path.unlink()
    elif kind == "invalid":
        path.write_bytes(b"{}\n")
    else:
        obj = json.loads(path.read_bytes())
        obj["execution_commit" if kind == "other-commit" else "holdout_authorization_sha256"] = "e" * (40 if kind == "other-commit" else 64)
        write_json(path, obj)
    with pytest.raises((analyzer.AnalysisError, runner.RunnerError, OSError)):
        run(attempt)


def test_rescore_rejects_incomplete_result(attempt):
    rebind(attempt, result_change=lambda obj: obj.update(run_status="partial"),
           manifest_change=lambda obj: obj.update(run_status="partial"))
    with pytest.raises(analyzer.AnalysisError, match="complete"):
        run(attempt)


@pytest.mark.parametrize("change", ["membership", "category", "expected_outcome", "hash", "family"])
def test_rescore_rejects_c1_inventory_or_label_drift(attempt, change):
    def mutate(obj):
        if change == "membership":
            obj["cases"][0]["case_id"] = "wrong-case"
        elif change == "category":
            obj["cases"][0]["category"] = "benign"
        elif change == "expected_outcome":
            obj["cases"][0]["expected_outcome"]["provider_called"] = False
        elif change == "family":
            obj["cases"][0]["scenario_family"] = "unknown"
        else:
            obj["expected_case_set_sha256"] = "0" * 64
    rebind(attempt, config=1, result_change=mutate)
    with pytest.raises(analyzer.AnalysisError):
        run(attempt)


@pytest.mark.parametrize("kind", ["count", "scope", "family", "correct", "duplicate"])
def test_rescore_validates_full_c0_inventory_and_scoring(attempt, kind):
    def mutate(obj):
        if kind == "count":
            obj["cases"].pop()
        elif kind == "scope":
            obj["cases"][-1]["evaluation_scope"] = "component"
        elif kind == "family":
            for record in obj["cases"]:
                if record["scenario_family"] == "fragment_beyond_per_chunk_prefix":
                    record["scenario_family"] = "unknown"
        elif kind == "correct":
            obj["cases"][0]["correct"] = False
        else:
            obj["cases"][1]["case_id"] = obj["cases"][0]["case_id"]
    rebind(attempt, result_change=mutate)
    with pytest.raises(analyzer.AnalysisError):
        run(attempt)


@pytest.mark.parametrize("kind", ["attempt", "analysis", "repo", "dataset", "parent-missing", "traversal", "bad-name"])
def test_rescore_rejects_unsafe_output(attempt, kind):
    base = f"p2-analysis-cc38fae-{ANALYZER_COMMIT}"
    paths = dict(attempt=attempt.root, analysis=attempt.root / "analysis", repo=attempt.repo / base,
        dataset=attempt.repo / "datasets/v2" / base, **{"parent-missing": attempt.root.parent / "missing" / base,
        "traversal": attempt.root / ".." / base, "bad-name": attempt.root.parent / "output"})
    with pytest.raises(analyzer.AnalysisError):
        run(attempt, output_root=paths[kind])
    assert not attempt.request.output_root.exists()


@pytest.mark.parametrize("kind", ["file", "empty-directory", "nonempty-directory", "dangling-link"])
def test_rescore_rejects_existing_output(attempt, kind):
    out = attempt.request.output_root
    if kind == "file":
        out.write_text("existing", encoding="utf-8")
    elif kind == "dangling-link":
        out.symlink_to(out.parent / "absent", target_is_directory=True)
    else:
        out.mkdir()
        if kind == "nonempty-directory":
            (out / "existing").write_text("existing", encoding="utf-8")
    with pytest.raises(analyzer.AnalysisError):
        run(attempt)


def test_rescore_rejects_resolved_path_escape(attempt):
    alias = attempt.root.parent / "alias"
    alias.symlink_to(attempt.root, target_is_directory=True)
    with pytest.raises(analyzer.AnalysisError):
        run(attempt, output_root=alias / attempt.request.output_root.name)
    assert analyzer._path_within(r"d:/DOANTHUCTAP/p2-output/x/../analysis", r"D:\DoAnThucTap\p2-output")
    assert not analyzer._path_within(r"D:\DoAnThucTap\p2-output-other", r"D:\DoAnThucTap\p2-output")


def observe_input_mutations(monkeypatch, root):
    """Observe write, mkdir, rename, replace and delete, including failed calls."""
    for name in ("mkdir", "unlink", "rmdir", "rename", "replace", "chmod", "touch"):
        original = getattr(Path, name)
        def guarded(path, *args, _original=original, **kwargs):
            assert not path.absolute().is_relative_to(root), "input mutation attempted"
            if args and isinstance(args[0], (Path, str)) and _original.__name__ in {"rename", "replace"}:
                assert not Path(args[0]).absolute().is_relative_to(root)
            return _original(path, *args, **kwargs)
        monkeypatch.setattr(Path, name, guarded)
    original_open = Path.open
    def guarded_open(path, mode="r", *args, **kwargs):
        if any(flag in mode for flag in "wax+"):
            assert not path.absolute().is_relative_to(root), "input write attempted"
        return original_open(path, mode, *args, **kwargs)
    monkeypatch.setattr(Path, "open", guarded_open)


def test_rescore_never_mutates_inputs(attempt, monkeypatch):
    before = snapshot(attempt.root)
    observe_input_mutations(monkeypatch, attempt.root)
    run(attempt)
    assert snapshot(attempt.root) == before


def test_rescore_writes_only_aggregate_artifacts(attempt, capsys):
    written = run(attempt)
    assert {p.name for p in written.output_directory.iterdir()} == {"analysis.json", "analysis-table.csv", "analysis-manifest.json"}
    for path in written.output_directory.iterdir():
        raw = path.read_text(encoding="utf-8")
        assert SENTINEL not in raw
        assert str(attempt.root) not in raw
        assert '"cases"' not in raw
    assert SENTINEL not in str(capsys.readouterr())


def test_rescore_manifest_binds_analysis_artifacts(attempt):
    written = run(attempt)
    manifest = json.loads(written.manifest_path.read_bytes())
    for kind, path in (("analysis", written.analysis_path), ("table", written.table_path)):
        raw = path.read_bytes()
        assert manifest[kind + "_sha256"] == sha(raw)
        assert manifest[kind + "_size_bytes"] == len(raw)
    assert "manifest_sha256" not in manifest


def test_analysis_metadata_does_not_authorize_ollama(attempt):
    doc = json.loads(run(attempt).analysis_path.read_bytes())
    with pytest.raises(analyzer.AnalysisError):
        analyzer.validate_holdout_analysis_document(doc, authorization=attempt.auth)
    with pytest.raises(analyzer.AnalysisError):
        analyzer.VerifiedHoldoutAnalysisContext()
    with pytest.raises(analyzer.AnalysisError):
        analyzer._expected_provider_behavior_hash(context=object())


@pytest.mark.parametrize("network_disabled", [True, False])
def test_legacy_mock_analysis_end_to_end(tmp_path, monkeypatch, network_disabled):
    settings = runner.load_settings()
    provider = runner.default_provider_spec("mock", settings)
    repository = runner.RepositoryState("mock-fixture", "c" * 40, False)
    manifest = runner.ManifestIdentity("a" * 64, "final", 0)
    benchmark = synthetic_benchmark("development")
    paths = build_matrix(tmp_path / "input", benchmark, repository, manifest, provider, settings,
                         network_disabled=network_disabled)
    monkeypatch.setattr(runner, "verify_frozen_manifest", lambda root: manifest)
    monkeypatch.setattr(runner, "load_split_benchmark", lambda root, split: benchmark)
    req = analyzer.AnalysisRequest("development", repository.branch, repository.commit, tmp_path / "mock-analysis", paths)
    if not network_disabled:
        with pytest.raises(analyzer.AnalysisError) as error:
            analyzer.analyze_results(req, hooks=analyzer.AnalyzerHooks(repository_state_loader=lambda root: repository))
        assert error.value.code == "safety_identity"
        assert "network_disabled" in str(error.value)
        assert not req.output_root.exists()
        return
    written = analyzer.analyze_results(req, hooks=analyzer.AnalyzerHooks(repository_state_loader=lambda root: repository))
    doc = json.loads(written.analysis_path.read_bytes())
    assert doc["identity"]["provider_id"] == "mock"
    assert doc["identity"]["git_commit"] == doc["analyzer_commit"] == repository.commit
    assert "execution_commit" not in doc and "rescore_binding" not in doc
    assert doc["configs"]["C0_all_on"]["coverage"]["value"] == 1.0


@pytest.mark.parametrize("provider", ["ollama", "openai"])
def test_legacy_paths_reject_unauthorized_non_mock(attempt, provider):
    item = analyzer._read_verified_input(attempt.paths[0], holdout=True)
    result = copy.deepcopy(item.result)
    result["provider_id"] = provider
    with pytest.raises(analyzer.AnalysisError):
        analyzer._validate_result(replace(item, result=result), repository=runner.RepositoryState(
            attempt.profile.execution_branch, EXECUTION_COMMIT, False), manifest_identity=attempt.manifest,
            benchmark=synthetic_benchmark(), expected_split="holdout")
    with pytest.raises(analyzer.AnalysisError):
        analyzer._validate_holdout_matrix([analyzer._read_verified_input(p, holdout=True) for p in attempt.paths], authorization=attempt.auth)


@pytest.mark.parametrize("marker", ["bound-path", "authorization", "receipt", "broken-receipt", "broken-authorization"])
def test_legacy_rejects_official_and_ambiguous_input(attempt, monkeypatch, marker):
    a = attempt
    paths = a.paths
    if marker == "bound-path":
        paths = (a.root / "unreadable" / "result-manifest.json",) * 8
    elif marker == "authorization":
        (a.root / "holdout-authorization.json").write_bytes(a.request.authorization.read_bytes())
        (a.root / "start-receipt.json").unlink()
    elif marker == "broken-receipt":
        (a.root / "start-receipt.json").write_bytes(b"bad")
    elif marker == "broken-authorization":
        (a.root / "holdout-authorization.json").write_bytes(b"bad")
        (a.root / "start-receipt.json").unlink()
    # For marker tests, the alias root is deliberately different from the
    # profile path: the linked marker must independently protect the input.
    if marker != "bound-path":
        monkeypatch.setattr(analyzer, "OFFICIAL_RESCORE_PROFILE", replace(a.profile, output_root=str(a.root.parent / "official-alias")))
    before = snapshot(a.root)
    observe_input_mutations(monkeypatch, a.root)
    request = analyzer.AnalysisRequest("development", "unused", "c" * 40, a.root / "analysis", paths)
    with pytest.raises((analyzer.AnalysisError, runner.RunnerError)):
        analyzer.analyze_results(request, repo_root=a.repo)
    assert snapshot(a.root) == before
    holdout_request = analyzer.HoldoutAnalysisRequest(a.request.authorization, a.paths)
    with pytest.raises((analyzer.AnalysisError, runner.RunnerError)):
        analyzer.analyze_holdout_results(holdout_request, repo_root=a.repo)


def test_legacy_rejects_output_under_official_root(attempt, monkeypatch):
    observe_input_mutations(monkeypatch, attempt.root)
    with pytest.raises(analyzer.AnalysisError):
        analyzer._publish_analysis(attempt.root / "analysis", {}, b"")


@pytest.mark.parametrize("kind", ["commit", "branch", "dirty"])
def test_runner_preclaim_remains_strict(tmp_path, kind):
    # Use the real runner verifier; it fails before needing any dataset.
    auth = SimpleNamespace(execution_branch="execution", execution_commit=EXECUTION_COMMIT)
    state = runner.RepositoryState("execution", EXECUTION_COMMIT, False)
    state = replace(state, **{"commit": "d" * 40} if kind == "commit" else
                    {"branch": "analyzer"} if kind == "branch" else {"dirty": True})
    with pytest.raises(runner.RunnerError):
        runner._verify_holdout_identity_preclaim(auth, repo_root=tmp_path, benchmark_path=tmp_path,
            analysis_contract_sha256=analyzer.ANALYSIS_CONTRACT_SHA256, mapping_sha256=analyzer.MAPPING_SHA256,
            settings=None, case_timeout_seconds=None,
            hooks=runner.RunnerHooks(repository_state_loader=lambda root: state))


def test_rescore_output_failure_does_not_touch_inputs(attempt, monkeypatch):
    before = snapshot(attempt.root)
    original = Path.open
    def fail_csv(path, mode="r", *args, **kwargs):
        if path.name == "analysis-table.csv" and mode == "xb":
            raise OSError("synthetic disk failure")
        return original(path, mode, *args, **kwargs)
    monkeypatch.setattr(Path, "open", fail_csv)
    observe_input_mutations(monkeypatch, attempt.root)
    with pytest.raises(OSError):
        run(attempt)
    assert snapshot(attempt.root) == before
    assert (attempt.request.output_root / "analysis.json").exists()
    with pytest.raises(analyzer.AnalysisError):
        run(attempt)


@pytest.mark.parametrize("failed_command", ["cat-file", "show"])
def test_git_blob_reader_checks_returncode(monkeypatch, tmp_path, failed_command):
    calls = []
    def execute(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=1 if args[1] == failed_command else 0, stdout=b"bogus", stderr=b"secret")
    monkeypatch.setattr(analyzer.subprocess, "run", execute)
    with pytest.raises(analyzer.AnalysisError, match="unavailable"):
        analyzer._read_git_blob(tmp_path, EXECUTION_COMMIT, "app/core/config.py")
    assert calls[-1][1] == failed_command


def test_git_blob_reader_reads_actual_execution_object():
    raw = analyzer._read_git_blob(runner.ROOT, EXECUTION_COMMIT, "app/core/config.py")
    assert b"class Settings" in raw


@pytest.mark.parametrize("option", ["binding-profile", "authorization", "output-root"])
def test_rescore_parser_rejects_duplicate_singleton_options(attempt, option):
    args = cli(attempt)
    value = args[args.index("--" + option) + 1]
    with pytest.raises(SystemExit):
        analyzer.main(args + ["--" + option, value])


@pytest.mark.parametrize("change", ["profile", "digest", "size"])
def test_rescore_rejects_explicit_binding_different_from_profile(attempt, change):
    if change == "profile":
        request = replace(attempt.request, binding_profile="unknown")
    else:
        bindings = list(attempt.request.bindings)
        bindings[0] = replace(bindings[0], **({"manifest_sha256": "0" * 64} if change == "digest"
                                            else {"result_size_bytes": bindings[0].result_size_bytes + 1}))
        request = replace(attempt.request, bindings=tuple(bindings))
    with pytest.raises(analyzer.AnalysisError, match="official profile"):
        analyzer.analyze_authorized_ollama_rescore(request, repo_root=attempt.repo, hooks=attempt.hooks)
    assert not request.output_root.exists()


@pytest.mark.parametrize("field", ["execution_commit", "analyzer_commit", "analyzer_repository", "rescore_binding", "identity"])
def test_rescore_shape_requires_context_binding(attempt, field):
    context, _ = analyzer._verify_holdout_rescore_identity_preclaim(attempt.request, repo_root=attempt.repo, hooks=attempt.hooks)
    doc = json.loads(run(attempt).analysis_path.read_bytes())
    if field == "analyzer_repository":
        doc[field]["git_dirty"] = True
    elif field == "rescore_binding":
        doc[field]["results"][0]["result_size_bytes"] += 1
    elif field == "identity":
        doc[field]["provider_behavior_hash"] = "0" * 64
    else:
        doc[field] = "e" * 40
    with pytest.raises(analyzer.AnalysisError):
        analyzer.validate_holdout_analysis_document(doc, authorization=attempt.auth, context=context)


def test_copied_context_cannot_grant_provider_access(attempt):
    context, _ = analyzer._verify_holdout_rescore_identity_preclaim(attempt.request, repo_root=attempt.repo, hooks=attempt.hooks)
    with pytest.raises(analyzer.AnalysisError):
        analyzer._expected_provider_behavior_hash(context=copy.copy(context))
    with pytest.raises(TypeError):
        context.authorization.config_hashes["C0_all_on"] = "0" * 64


def test_verified_context_cannot_authorize_development(attempt):
    context, inputs = analyzer._verify_holdout_rescore_identity_preclaim(attempt.request, repo_root=attempt.repo, hooks=attempt.hooks)
    with pytest.raises(analyzer.AnalysisError, match="only to holdout"):
        analyzer._validate_result(inputs[0], repository=attempt.state, manifest_identity=attempt.manifest,
                                  benchmark=synthetic_benchmark(), expected_split="development", context=context)


@pytest.mark.parametrize("sink", ["rename", "delete", "holdout-publish"])
def test_all_legacy_write_sinks_protect_official_root(attempt, monkeypatch, sink):
    before = snapshot(attempt.root)
    observe_input_mutations(monkeypatch, attempt.root)
    with pytest.raises(analyzer.AnalysisError):
        if sink == "rename":
            analyzer._publish_directory_atomically(attempt.repo / "staging", attempt.root / "analysis")
        elif sink == "delete":
            analyzer._remove_staging_best_effort(attempt.root / "analysis")
        else:
            analyzer._publish_holdout_analysis(attempt.root / "analysis", {}, b"", attempt.auth, attempt.root)
    assert snapshot(attempt.root) == before


@pytest.mark.parametrize("dirty_status", ["M  tracked.py", " M tracked.py", "?? untracked.py"])
def test_rescore_repository_reader_includes_all_dirty_states(monkeypatch, tmp_path, dirty_status):
    def execute(args, **kwargs):
        assert kwargs["env"]["GIT_OPTIONAL_LOCKS"] == "0"
        if args[1] == "branch":
            value = "analyzer-branch\n"
        elif args[1] == "rev-parse":
            value = ANALYZER_COMMIT + "\n"
        else:
            assert args == ["git", "status", "--porcelain=v1", "--untracked-files=all"]
            value = dirty_status + "\n"
        return SimpleNamespace(returncode=0, stdout=value)
    monkeypatch.setattr(analyzer.subprocess, "run", execute)
    state = analyzer._read_rescore_repository_state(tmp_path)
    assert state == runner.RepositoryState("analyzer-branch", ANALYZER_COMMIT, True)


def test_rescore_repository_reader_checks_returncode(monkeypatch, tmp_path):
    monkeypatch.setattr(analyzer.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=1, stdout=""))
    with pytest.raises(analyzer.AnalysisError):
        analyzer._read_rescore_repository_state(tmp_path)


@pytest.mark.parametrize("key,value", [("LLM_PROVIDER", "ollama"), ("LLM_MODEL_NAME", OLLAMA_PRIMARY_MODEL),
    ("LLM_PROVIDER_TIMEOUT_SECONDS", "30"), ("LLM_REPEAT_COUNT", "1"), ("OLLAMA_TEMPERATURE", "0.0"),
    ("OLLAMA_SEED", "42"), ("OLLAMA_NUM_CTX", "4096"), ("OLLAMA_NUM_PREDICT", "512"),
    ("OLLAMA_THINK", "false"), ("OLLAMA_MAX_RETRIES", "2"), ("OLLAMA_KEEP_ALIVE", "30m")])
def test_equal_valued_provider_overrides_still_fail(attempt, monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(analyzer.AnalysisError) as error:
        run(attempt)
    assert error.value.code == "settings_override"


def test_rescore_rejects_extra_manifest_in_attempt(attempt):
    extra = attempt.root / "runs" / "extra-experiment" / "C0_all_on" / "extra-run"
    extra.mkdir(parents=True)
    (extra / "result-manifest.json").write_bytes(attempt.paths[0].read_bytes())
    with pytest.raises(analyzer.AnalysisError) as error:
        run(attempt)
    assert error.value.code == "manifest_count"


def test_preclaim_does_not_issue_context_on_invalid_input(attempt):
    before = set(analyzer._VERIFIED_RESCORE_CONTEXTS)
    rebind(attempt, result_change=lambda obj: obj["environment"].update(git_dirty=True))
    with pytest.raises(analyzer.AnalysisError):
        analyzer._verify_holdout_rescore_identity_preclaim(attempt.request, repo_root=attempt.repo, hooks=attempt.hooks)
    assert set(analyzer._VERIFIED_RESCORE_CONTEXTS) == before


def test_legacy_official_input_is_blocked_even_with_external_output(attempt, monkeypatch):
    observe_input_mutations(monkeypatch, attempt.root)
    request = analyzer.AnalysisRequest("development", "unused", "c" * 40,
                                       attempt.request.output_root, attempt.paths)
    with pytest.raises(analyzer.AnalysisError) as error:
        analyzer.analyze_results(request, repo_root=attempt.repo)
    assert error.value.code == "official_input"
    assert not request.output_root.exists()


def test_default_mock_invocation_cannot_write_into_official_root(attempt, monkeypatch):
    observe_input_mutations(monkeypatch, attempt.root)
    request = analyzer.AnalysisRequest("development", "unused", "c" * 40,
        attempt.root / "analysis", (attempt.repo / "result-manifest.json",) * 8)
    with pytest.raises(analyzer.AnalysisError) as error:
        analyzer.analyze_results(request, repo_root=attempt.repo)
    assert error.value.code == "official_input"
