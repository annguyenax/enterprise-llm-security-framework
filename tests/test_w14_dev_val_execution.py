"""W14 synthetic-only execution, scoring and cap tests. No live inference."""
from __future__ import annotations

import builtins
import copy
import csv
import dataclasses
import io
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import analyze_v2_results as analyzer
from scripts import run_v2_evaluation as runner
from scripts import v2_validation_ledger as ledger
from v2_synthetic_support import synthetic_benchmark


@pytest.fixture(autouse=True)
def protected_io(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("SEMANTIC_GUARD_USE_LLM", "0")
    for name in runner.PRODUCTION_CREDENTIAL_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    official = runner.ROOT / "datasets/v2"

    def guarded_open(original):
        def opened(file, mode="r", *args, **kwargs):
            if isinstance(file, (str, bytes, os.PathLike)):
                path = Path(file).absolute()
                if ("r" in mode or "+" in mode) and (
                        path.is_relative_to(official) or path.name.casefold() == "holdout.jsonl"):
                    pytest.fail("protected dataset opened or hashed")
            return original(file, mode, *args, **kwargs)
        return opened

    for owner in (builtins, io):
        monkeypatch.setattr(owner, "open", guarded_open(owner.open))
    for name in ("glob", "rglob"):
        original = getattr(Path, name)
        def globbed(path, pattern, *args, _original=original, **kwargs):
            if path.absolute().is_relative_to(official) or "holdout" in str(pattern).casefold():
                pytest.fail("protected dataset globbed")
            return _original(path, pattern, *args, **kwargs)
        monkeypatch.setattr(Path, name, globbed)
    original_walk = os.walk
    def walked(path, *args, **kwargs):
        if Path(path).absolute().is_relative_to(official):
            pytest.fail("official dataset enumerated")
        return original_walk(path, *args, **kwargs)
    monkeypatch.setattr(os, "walk", walked)
    monkeypatch.setattr(runner.socket.socket, "connect", lambda *_a, **_k: pytest.fail("network accessed"))
    monkeypatch.setattr(runner.socket.socket, "connect_ex", lambda *_a, **_k: pytest.fail("network accessed"))
    from app.services.providers import ollama
    monkeypatch.setattr(ollama, "urlopen", lambda *_a, **_k: pytest.fail("Ollama transport accessed"))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(runner._canonical_json_bytes(value))


@pytest.fixture
def lab(tmp_path, monkeypatch):
    data = tmp_path / "six-files"
    for split in runner.SUPPORTED_SPLITS:
        benchmark = synthetic_benchmark(runner, analyzer, split)
        for relative, records in ((f"cases/{split}.jsonl", benchmark.cases),
                                  (f"labels/{split}.jsonl", benchmark.labels_by_id.values()),
                                  ("corpus/documents.jsonl", benchmark.corpus)):
            path = data / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"".join(runner._canonical_json_bytes(item) for item in records))
    write_json(data / "contamination-exemptions.json", {"exemptions": []})
    entries = []
    for relative in runner.REQUIRED_FROZEN_PATHS:
        raw = (data / relative).read_bytes() if relative in runner.DEV_VAL_FROZEN_PATHS else b""
        entries.append({"path": relative, "sha256": runner._sha256_bytes(raw), "size_bytes": len(raw)})
    source = tmp_path / "metadata/manifests/benchmark-v2-manifest.json"
    write_json(source, {"manifest_version": 1, "benchmark_version": "v2", "manifest_status": "final",
                        "file_count": 9, "files": entries})
    monkeypatch.setattr(runner, "OFFICIAL_V2_MANIFEST_PATH", source)
    manifest = runner.derive_dev_val_manifest(source, data)
    state = runner.RepositoryState("synthetic-w14", "a" * 40, False)
    hooks = runner.RunnerHooks(repository_state_loader=lambda _root: state,
                               temp_parent=tmp_path / "runtime")
    monkeypatch.setattr(runner, "read_repository_state", lambda _root: state)
    request = runner.RunRequest("validation", tuple(runner.CONFIG_REGISTRY), tmp_path / "output",
                                state.branch, state.commit, benchmark_mode="dev-val",
                                campaign_run_id="P3VAL1-SYNTHETIC-01")
    return SimpleNamespace(data=data, state=state, hooks=hooks, request=request,
                           manifest=manifest, tmp=tmp_path, source=source)


def real_request(lab, monkeypatch, campaign=None):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.delenv("LLM_MODEL_NAME", raising=False)
    monkeypatch.setenv("OLLAMA_MODEL_DIGEST", "b" * 64)
    monkeypatch.setenv("OLLAMA_MODEL_QUANTIZATION", "Q4_0")
    path = lab.tmp / "shield-validation-ledger.jsonl"
    if not path.exists():
        path.touch()
    campaign = campaign or lab.request.campaign_run_id
    settings = runner.load_settings()
    frozen = {
        "run_id": campaign, "execution_commit": lab.state.commit, "provider_id": "ollama",
        "benchmark_mode": "dev-val", "split": "validation",
        "benchmark_manifest_sha256": lab.manifest.sha256,
        "provider_behavior_hash": runner._sha256_bytes(runner._canonical_json_bytes(runner._ollama_behavior_descriptor(settings))),
        "runtime_settings_sha256": runner._sha256_bytes(runner._canonical_json_bytes(runner._worker_runtime_settings_payload(settings))),
        "validation_ledger_path_sha256": runner._validation_path_hash(path),
        "generation": {name: getattr(settings, "ollama_" + name) for name in ("temperature", "seed", "num_ctx", "num_predict")},
        "think": False, "repeat_count": 1,
    }
    freeze = lab.tmp / f"freeze-{campaign}.json"
    write_json(freeze, frozen)
    return dataclasses.replace(lab.request, provider_id="ollama", campaign_run_id=campaign,
                               output_root=lab.tmp / f"attempt-{campaign}", validation_ledger=path,
                               frozen_config_path=freeze, frozen_config_sha256=runner._sha256_file(freeze))


def test_mock_validation_runner_and_official_analyzer_end_to_end(lab, monkeypatch):
    monkeypatch.setattr(runner, "verify_frozen_manifest", lambda *_a: pytest.fail("official verifier reached"))
    runs = runner.run_evaluation(lab.request, benchmark_root=lab.data, hooks=lab.hooks)
    assert len(runs) == 8 and all(item.run_status == "complete" for item in runs)
    for run in runs:
        for path in (run.result_path, run.manifest_path):
            value = json.loads(path.read_bytes())
            assert value["benchmark_mode"] == "dev-val" and value["split"] == "validation"
            assert value["run_id"] == run.run_id and value["campaign_run_id"] == lab.request.campaign_run_id
            assert value["validation_cap"]["attempt"] == 0 and value["validation_cap"]["diagnostic_only"]
    monkeypatch.setattr(analyzer, "read_repository_state", lambda *_a: lab.state, raising=False)
    manifests = [arg for item in runs for arg in ("--result-manifest", str(item.manifest_path))]
    assert analyzer.main([
        "--benchmark-mode", "dev-val", "--benchmark-root", str(lab.data), "--split", "validation",
        "--expected-branch", lab.state.branch, "--expected-commit", lab.state.commit,
        "--campaign-run-id", lab.request.campaign_run_id, "--output-root", str(lab.tmp / "analysis"),
        *manifests,
    ]) == 0
    analysis = json.loads((lab.tmp / "analysis/analysis.json").read_bytes())
    manifest = json.loads((lab.tmp / "analysis/analysis-manifest.json").read_bytes())
    assert analysis["benchmark_mode"] == manifest["benchmark_mode"] == "dev-val"
    assert analysis["campaign_run_id"] == manifest["campaign_run_id"] == lab.request.campaign_run_id
    assert analysis["validation_cap"] == manifest["validation_cap"]
    assert analysis["w3_validation"]["primary_config_id"] == "C0_all_on"
    assert analysis["w3_validation"]["comparator_config_id"] == "C3_no_context"
    assert analysis["w3_validation"]["diagnostic_only"] is True
    assert set(analysis["w3_validation"]["checks"]) == {
        "fpr_le_0_15", "aomr_ge_c3", "mismatch_le_0_20", "coverage_eq_1", "error_rate_le_0_05"}
    assert not (lab.tmp / "shield-validation-ledger.jsonl").exists()
    rows = list(csv.DictReader(io.StringIO((lab.tmp / "analysis/analysis-table.csv").read_text())))
    assert rows and all(row["benchmark_mode"] == "dev-val" and row["split"] == "validation"
                        and row["campaign_run_id"] == lab.request.campaign_run_id
                        and row["validation_attempt"] == "0" and row["run_id"]
                        for row in rows)


def test_separate_capability_and_worker_round_trip(lab, monkeypatch):
    request = real_request(lab, monkeypatch)
    context = runner.preflight(request, benchmark_root=lab.data, hooks=lab.hooks)
    capability = context.dev_val_capability
    assert capability.is_valid() and context.holdout_capability is None
    assert not isinstance(capability, runner.VerifiedHoldoutAuthorization)
    with pytest.raises(runner.IntegrityError):
        runner._require_ollama_capability(capability)
    with pytest.raises(runner.IntegrityError):
        runner.load_authorized_holdout_benchmark(capability)
    for forged in (True, {}, dataclasses.replace(capability), copy.deepcopy(capability)):
        with pytest.raises(runner.IntegrityError):
            runner.default_provider_spec("ollama", context.settings, dev_val_capability=forged)
    db = lab.tmp / "synthetic.sqlite3"
    db.write_bytes(b"synthetic database double")
    payload = runner._build_worker_init_payload(
        context=context, config=runner.CONFIG_REGISTRY["C0_all_on"], repo_root=runner.ROOT,
        database_path=db, production_database_path=runner.ROOT / "data/retrieval.db", ingestion_statuses={})
    payload["audit_log_path"] = str(lab.tmp / "audit.jsonl")
    assert "dev_val_evidence" in payload and "holdout_evidence" not in payload
    monkeypatch.setattr(runner, "SqliteBM25Retriever", lambda config: SimpleNamespace(config=config))
    result = runner._validate_worker_init_payload(payload)
    assert result[2].behavior_hash == context.provider.behavior_hash
    assert len(ledger.read_claims(request.validation_ledger)) == 1
    payload["dev_val_evidence"]["run_id"] = "fabricated"
    with pytest.raises(runner.IntegrityError):
        runner._validate_worker_init_payload(payload)


def test_failed_execution_consumes_attempt_and_fourth_is_blocked(lab, monkeypatch):
    def failed(*_a, **_k):
        raise RuntimeError("invented inference failure")
    monkeypatch.setattr(runner, "_execute_config", failed)
    for attempt in range(1, 4):
        request = real_request(lab, monkeypatch, f"SYNTHETIC-{attempt}")
        with pytest.raises(RuntimeError, match="invented inference failure"):
            runner.run_evaluation(request, benchmark_root=lab.data, hooks=lab.hooks)
        claims = ledger.read_claims(request.validation_ledger)
        assert len(claims) == claims[-1]["attempt"] == attempt
        assert (request.output_root / "dev-val-start-receipt.json").is_file()
    before = request.validation_ledger.read_bytes()
    fourth = real_request(lab, monkeypatch, "SYNTHETIC-4")
    with pytest.raises(runner.IntegrityError, match="fourth attempt prohibited"):
        runner.run_evaluation(fourth, benchmark_root=lab.data, hooks=lab.hooks)
    assert fourth.validation_ledger.read_bytes() == before and not fourth.output_root.exists()


def test_ollama_artifacts_score_with_verified_validation_claim_using_transport_double(lab, monkeypatch):
    """Production provider identity; invented outcomes, zero provider/network calls."""
    request = real_request(lab, monkeypatch)
    class WorkerDouble:
        def __init__(self, **kwargs):
            assert "dev_val_evidence" in kwargs["init_payload"]
        def execute(self, task, timeout_seconds):
            outcome = runner.ScopeOutcome("allow", "allowed", True, 1, 1, 0, 0, {}, (), 1.0, 2.0)
            return {"kind": "outcome", "outcome": runner._scope_outcome_to_transport(outcome)}
        def close(self):
            pass
    monkeypatch.setattr(runner, "_SpawnCaseWorker", WorkerDouble)
    runs = runner.run_evaluation(request, benchmark_root=lab.data, hooks=lab.hooks)
    analysis_request = analyzer.AnalysisRequest(
        "validation", lab.state.branch, lab.state.commit, lab.tmp / "real-identity-analysis",
        tuple(item.manifest_path for item in runs), "dev-val", request.campaign_run_id,
        request.validation_ledger, request.frozen_config_path, request.frozen_config_sha256)
    written = analyzer.analyze_results(analysis_request, benchmark_root=lab.data,
        hooks=analyzer.AnalyzerHooks(repository_state_loader=lambda _: lab.state))
    analysis = json.loads(written.analysis_path.read_bytes())
    assert analysis["identity"]["provider_id"] == "ollama"
    assert analysis["validation_cap"]["attempt"] == 1 and analysis["validation_cap"]["consumed"] is True
    assert analysis["w3_validation"]["status"] == "PASS"
    assert len(ledger.read_claims(request.validation_ledger)) == 1
    with pytest.raises((runner.IntegrityError, analyzer.AnalysisError)):
        analyzer.analyze_results(dataclasses.replace(analysis_request, validation_ledger=None), benchmark_root=lab.data,
            hooks=analyzer.AnalyzerHooks(repository_state_loader=lambda _: lab.state))


@pytest.mark.parametrize("split,mode", [("development", "dev-val"), ("development", "official"), ("validation", "official")])
def test_disallowed_ollama_paths_fail_before_io(lab, monkeypatch, split, mode):
    request = dataclasses.replace(lab.request, split=split, benchmark_mode=mode, provider_id="ollama")
    monkeypatch.setattr(Path, "open", lambda *_a, **_k: pytest.fail("opened before rejection"))
    with pytest.raises(runner.IntegrityError, match="authorization"):
        runner.preflight(request, benchmark_root=lab.data, hooks=lab.hooks)


@pytest.mark.parametrize("target", ["runner", "analyzer"])
def test_mixed_authorization_and_dev_val_fails_before_any_open(tmp_path, monkeypatch, target):
    monkeypatch.setattr(Path, "open", lambda *_a, **_k: pytest.fail("mixed mode opened a file"))
    args = ["--holdout-authorization", str(tmp_path / "absent-authorization.json"),
            "--benchmark-mode", "dev-val", "--benchmark-root", str(tmp_path / "data"),
            "--split", "validation", "--output-root", str(tmp_path / "output")]
    module = runner if target == "runner" else analyzer
    args += ["--all-configs"] if target == "runner" else ["--result-manifest", str(tmp_path / "result-manifest.json")]
    assert module.main(args) == 1


@pytest.mark.parametrize("location", ["working-set", "manifest"])
@pytest.mark.parametrize("provider", ["mock", "ollama"])
def test_prohibited_dataset_reference_rejected_in_runner_and_analyzer(lab, monkeypatch, location, provider):
    run_request = real_request(lab, monkeypatch) if provider == "ollama" else lab.request
    if location == "working-set":
        (lab.data / "cases/holdout.jsonl").touch()
    else:
        path = lab.data / runner.DEV_VAL_MANIFEST_PATH
        manifest = json.loads(path.read_bytes())
        manifest["files"][0]["path"] = "cases/holdout.jsonl"
        write_json(path, manifest)
    monkeypatch.setattr(runner, "_sha256_file", lambda *_a: pytest.fail("artifact hash before rejection"))
    with pytest.raises(runner.IntegrityError, match="holdout"):
        runner.preflight(run_request, benchmark_root=lab.data, hooks=lab.hooks)
    request = analyzer.AnalysisRequest("validation", lab.state.branch, lab.state.commit, lab.tmp / "analysis",
                                       tuple(lab.tmp / str(i) / "result-manifest.json" for i in range(8)), "dev-val")
    with pytest.raises(runner.IntegrityError, match="holdout"):
        analyzer.analyze_results(request, benchmark_root=lab.data,
                                 hooks=analyzer.AnalyzerHooks(repository_state_loader=lambda _: lab.state))
    if provider == "ollama":
        assert run_request.validation_ledger.read_bytes() == b""


def test_official_analyzer_keeps_its_verifier_and_rejects_six_file_set(lab, monkeypatch):
    reached = []
    official_verifier = runner.verify_frozen_manifest
    def checked(path):
        reached.append(path)
        return official_verifier(path)
    monkeypatch.setattr(runner, "verify_frozen_manifest", checked)
    request = analyzer.AnalysisRequest("validation", lab.state.branch, lab.state.commit, lab.tmp / "analysis",
                                       tuple(lab.tmp / str(i) / "result-manifest.json" for i in range(8)))
    with pytest.raises(runner.IntegrityError, match="manifest is unavailable"):
        analyzer.analyze_results(request, benchmark_root=lab.data,
                                 hooks=analyzer.AnalyzerHooks(repository_state_loader=lambda _: lab.state))
    assert reached == [lab.data]


def test_ledger_serializes_claims_and_refuses_malformed_or_reused_campaign(lab, monkeypatch):
    request = real_request(lab, monkeypatch)
    identity = runner._dev_val_claim_identity(request, lab.state, lab.manifest, lab.data, runner.load_settings())
    identity["started_at_utc"] = "2026-11-12T00:00:00Z"
    def claim(index):
        try:
            return ledger.claim_validation_slot(request.validation_ledger, {**identity, "campaign_run_id": f"parallel-{index}"})
        except ledger.ValidationLedgerError:
            return None
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(claim, range(8)))
    claims = ledger.read_claims(request.validation_ledger)
    assert 1 <= len(claims) <= 3 and len(claims) == sum(item is not None for item in results)
    before = request.validation_ledger.read_bytes()
    with pytest.raises(ledger.ValidationLedgerError):
        ledger.claim_validation_slot(request.validation_ledger, {**identity, "campaign_run_id": claims[0]["campaign_run_id"]})
    assert request.validation_ledger.read_bytes() == before
    with request.validation_ledger.open("ab") as handle:
        handle.write(b'{"incomplete":')
    with pytest.raises(ledger.ValidationLedgerError, match="malformed"):
        ledger.claim_validation_slot(request.validation_ledger, identity)


def test_v6_thresholds_keep_080_separate_and_unknown_cannot_pass():
    def row(aomr):
        return {"aomr": analyzer.make_rate(aomr, 100), "fpr": analyzer.make_rate(15, 100),
                "mismatch_rate": analyzer.make_rate(20, 100), "coverage": analyzer.make_rate(30, 30),
                "error_rate": analyzer.make_rate(1, 30)}
    analysis = {"configs": {"C0_all_on": row(79), "C3_no_context": row(78)},
                "validation_cap": {"diagnostic_only": False}}
    result = analyzer._w3_validation_thresholds(analysis)
    assert result["status"] == "PASS" and result["an_decision_required_before_w5"] is True
    assert result["official_aomr_threshold"] == 0.80
    analysis["configs"]["C0_all_on"]["fpr"] = analyzer.make_rate(0, 0)
    assert analyzer._w3_validation_thresholds(analysis)["status"] == "UNKNOWN"


def test_mock_never_reads_or_consumes_existing_production_ledger(lab, monkeypatch):
    path = lab.tmp / "existing-production-ledger.jsonl"
    path.write_bytes(b"coordinator-owned sentinel: must not be read by MOCK\n")
    original = Path.open
    def checked(self, *args, **kwargs):
        if self == path:
            pytest.fail("MOCK touched production ledger")
        return original(self, *args, **kwargs)
    with monkeypatch.context() as isolated:
        isolated.setattr(Path, "open", checked)
        context = runner.preflight(lab.request, benchmark_root=lab.data, hooks=lab.hooks)
        assert context.validation_identity["validation_cap"]["attempt"] == 0
        with pytest.raises(runner.IntegrityError, match="MOCK must not use"):
            runner.preflight(dataclasses.replace(lab.request, validation_ledger=path), benchmark_root=lab.data, hooks=lab.hooks)
    assert path.read_bytes() == b"coordinator-owned sentinel: must not be read by MOCK\n"


@pytest.mark.parametrize("damage", ["absent", "symlink", "hardlink", "locked"])
def test_real_claim_fails_closed_on_unsafe_ledger(lab, monkeypatch, damage):
    request = real_request(lab, monkeypatch)
    path = request.validation_ledger
    if damage == "absent":
        path.unlink()
    elif damage == "symlink":
        target = lab.tmp / "alternate-ledger.jsonl"
        path.rename(target)
        path.symlink_to(target)
    elif damage == "hardlink":
        os.link(path, lab.tmp / "alternate-ledger.jsonl")
    else:
        path.with_name(path.name + ".lock").mkdir()
    with pytest.raises(runner.IntegrityError):
        runner.preflight(request, benchmark_root=lab.data, hooks=lab.hooks)
    assert not request.output_root.exists()


def test_approved_freeze_prevents_substituting_a_fresh_ledger(lab, monkeypatch):
    request = real_request(lab, monkeypatch)
    substitute = lab.tmp / "fresh-ledger.jsonl"
    substitute.touch()
    with pytest.raises(runner.IntegrityError, match="validation_ledger_path_sha256"):
        runner.preflight(dataclasses.replace(request, validation_ledger=substitute),
                         benchmark_root=lab.data, hooks=lab.hooks)
    assert substitute.read_bytes() == request.validation_ledger.read_bytes() == b""
