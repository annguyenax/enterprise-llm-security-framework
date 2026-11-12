"""P2 gates using TEST-ONLY authorization, freeze and corpus doubles.

These fixtures cannot authorize a real checkout: identities are synthetic, all
benchmark/repository loaders are replaced, and process/network entrypoints fail.
"""
from __future__ import annotations

import dataclasses
import json
import os
import socket
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest

from app.core.config import load_settings
from app.services.llm_provider import LLMProviderRequest
from app.services.providers import ollama
from scripts import run_v2_evaluation as runner


@pytest.fixture(autouse=True)
def isolated_runtime(monkeypatch):
    monkeypatch.setattr(os, "environ", {"LLM_PROVIDER": "mock", "LLM_MODEL_NAME": "mock-rag-guard-v1"})

    def forbidden(*args, **kwargs):
        raise AssertionError("real transport, benchmark, repository or process access is forbidden")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(ollama, "urlopen", forbidden)
    monkeypatch.setattr(runner, "read_repository_state", forbidden)
    monkeypatch.setattr(runner, "verify_frozen_manifest", forbidden)
    monkeypatch.setattr(runner, "_load_frozen_split", forbidden)
    monkeypatch.setattr(runner, "_load_jsonl", forbidden)
    monkeypatch.setattr(runner, "load_split_benchmark", forbidden)
    monkeypatch.setattr(runner, "load_authorized_holdout_benchmark", forbidden)
    monkeypatch.setattr(runner, "_SpawnCaseWorker", forbidden)
    monkeypatch.setattr(runner.multiprocessing, "get_context", forbidden)
    monkeypatch.setattr(runner, "_dependency_inventory", lambda: ("synthetic-dependency==1",))
    monkeypatch.setattr(runner, "_load_analyzer_contract_identities", lambda: ("b" * 64, "c" * 64))
    original = runner.parse_holdout_authorization

    def parse_fixture(path, **kwargs):
        assert "test-only-authorization" in Path(path).name, "real authorization forbidden"
        return original(path, **kwargs)

    monkeypatch.setattr(runner, "parse_holdout_authorization", parse_fixture)
    monkeypatch.setattr(ollama, "time", SimpleNamespace(monotonic=lambda: 100.0,
                                                       sleep=lambda _: None))


def _write_json(path, payload, *, canonical=False):
    raw = runner._canonical_authorization_bytes(payload) if canonical else json.dumps(payload).encode()
    path.write_bytes(raw)
    return path


@pytest.fixture
def lab(tmp_path, monkeypatch):
    repo = tmp_path / "test-only-repo"
    repo.mkdir()
    benchmark = repo / "synthetic-benchmark"
    root = tmp_path / "test-only-attempt"
    state = runner.RepositoryState("p2-test-only", "d" * 40, False)
    manifest = runner.ManifestIdentity("a" * 64, "final", 9)
    auth = {
        "schema_version": 1, "authorization_id": "0f9a1c2d-3e4b-4a5c-8d6e-7f8091a2b3c4",
        "issued_at_utc": "2026-11-11T00:00:00Z", "issued_by": runner.HOLDOUT_AUTHORIZATION_ISSUER,
        "purpose": runner.HOLDOUT_AUTHORIZATION_PURPOSE, "execution_branch": state.branch,
        "execution_commit": state.commit, "benchmark_manifest_sha256": manifest.sha256,
        "provider_id": "ollama", "config_ids": list(runner.CONFIG_REGISTRY),
        "config_hashes": {key: value.config_hash for key, value in runner.CONFIG_REGISTRY.items()},
        "result_schema_version": 1, "result_manifest_schema_version": 1,
        "analysis_schema_version": 1, "analysis_manifest_schema_version": 1,
        "analysis_contract_sha256": "b" * 64, "mapping_sha256": "c" * 64,
        "output_root": str(root), "attempt": 1, "supersedes_authorization_sha256": None,
        "holdout_authorized": True,
    }
    auth_path = _write_json(tmp_path / "test-only-authorization.json", auth, canonical=True)
    freeze = {"run_id": "test-only-P2-run", "execution_commit": state.commit, "provider_id": "ollama",
              "generation": {"temperature": 0.0, "seed": 42, "num_ctx": 4096, "num_predict": 512},
              "repeat_count": 1, "think": False}
    freeze_path = _write_json(tmp_path / "test-only-freeze.json", freeze)
    calls = []

    def repository_loader(path):
        assert path == repo
        calls.append("repository")
        return state

    def manifest_loader(path):
        assert path == benchmark.resolve()
        calls.append("manifest")
        return manifest

    def benchmark_loader(capability, **kwargs):
        assert capability.is_valid() and (root / "start-receipt.json").exists()
        assert kwargs["benchmark_root"] == benchmark.resolve()
        calls.append("benchmark")
        return runner.LoadedBenchmark(corpus=(), cases=({"case_id": "synthetic-case", "evaluation_scope": "end_to_end"},),
                                      labels_by_id={"synthetic-case": {}})

    monkeypatch.setattr(runner, "read_repository_state", repository_loader)
    monkeypatch.setattr(runner, "verify_frozen_manifest", manifest_loader)
    monkeypatch.setattr(runner, "load_authorized_holdout_benchmark", benchmark_loader)
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.delenv("LLM_MODEL_NAME")
    request = runner.HoldoutRunRequest(auth_path, root, "b" * 64, "c" * 64,
                                      frozen_config_path=freeze_path,
                                      frozen_config_sha256=runner._sha256_file(freeze_path))
    return SimpleNamespace(repo=repo, benchmark=benchmark, root=root, state=state, manifest=manifest,
                           auth=auth, auth_path=auth_path, freeze=freeze, freeze_path=freeze_path,
                           request=request, calls=calls)


def _preflight(lab, **overrides):
    return runner.holdout_preflight(dataclasses.replace(lab.request, **overrides),
                                    repo_root=lab.repo, benchmark_root=lab.benchmark)


def _rewrite_authorization(lab):
    _write_json(lab.auth_path, lab.auth, canonical=True)


def _worker_payload(lab, context):
    db = lab.root / "test-only.sqlite3"
    db.write_bytes(b"synthetic database double")
    payload = runner._build_worker_init_payload(context=context, config=runner.CONFIG_REGISTRY["C0_all_on"],
        repo_root=lab.repo, database_path=db, production_database_path=lab.repo / "production.sqlite3",
        ingestion_statuses={})
    payload["audit_log_path"] = str(lab.root / "test-only-audit.jsonl")
    return payload


def _validate_worker(monkeypatch, payload):
    monkeypatch.setattr(runner, "SqliteBM25Retriever", lambda config: SimpleNamespace(config=config))
    return runner._validate_worker_init_payload(payload)


def test_cli_default_is_effectively_mock(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(runner, "run_evaluation", lambda request: seen.append(request) or [])
    assert runner.main(["--split", "development", "--all-configs", "--output-root", str(tmp_path),
                        "--expected-branch", "test", "--expected-commit", "e" * 40]) == 0
    assert seen[0].provider_id == "mock" and seen[0].case_timeout_seconds == 30.0
    assert runner.SUPPORTED_PROVIDER_ID == "mock" and runner.SUPPORTED_SPLITS == ("development", "validation")


@pytest.mark.parametrize("split", ["development", "validation"])
def test_dev_validation_ollama_rejected_before_side_effects(lab, split):
    request = runner.RunRequest(split, tuple(runner.CONFIG_REGISTRY), lab.root, "test", "e" * 40, "ollama")
    with pytest.raises(runner.IntegrityError, match="authorization"):
        runner.preflight(request, repo_root=lab.repo, benchmark_root=lab.benchmark)
    assert not lab.calls and not lab.root.exists()


def test_cli_ollama_without_authorization_fails_before_loader(tmp_path):
    assert runner.main(["--provider", "ollama", "--split", "development", "--all-configs",
                        "--output-root", str(tmp_path)]) == 1


@pytest.mark.parametrize("explicit", [None, "ollama"])
def test_authorized_ollama_uses_verified_identity(lab, explicit):
    context = _preflight(lab, provider_id=explicit)
    assert context.provider.provider_id == "ollama" and context.provider.offline is False
    assert context.holdout_capability.is_valid()
    assert lab.calls[-1] == "benchmark"
    assert context.safety_limits["network_disabled"] is False
    assert context.safety_limits["case_timeout_seconds"] == 30.0
    assert (lab.root / "start-receipt.json").is_file()
    assert context.provider.factory().settings == context.settings


def test_authorization_mock_schema_and_descriptor_remain_compatible(lab, monkeypatch):
    lab.auth["provider_id"] = "mock"
    _rewrite_authorization(lab)
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("LLM_MODEL_NAME", "mock-rag-guard-v1")
    context = _preflight(lab, frozen_config_path=None, frozen_config_sha256=None)
    spec = runner.default_provider_spec("mock", load_settings())
    assert context.provider.behavior_descriptor == spec.behavior_descriptor
    assert set(spec.behavior_descriptor) == {"provider_id", "implementation", "implementation_sha256", "model_name", "network", "behavior_version"}
    assert spec.offline and not spec.test_only
    result = spec.factory().generate(LLMProviderRequest("x", "x", [], {}, "test"))
    assert result.is_mock
    assert not (lab.root / "ollama-runtime.json").exists()
    assert set(lab.auth) == runner.HOLDOUT_AUTHORIZATION_KEYS


def test_explicit_provider_mismatch_rejected_before_claim(lab):
    with pytest.raises(runner.IntegrityError, match="explicit provider"):
        _preflight(lab, provider_id="mock")
    assert not lab.calls and not lab.root.exists()


@pytest.mark.parametrize("extra", [["--split", "validation"], ["--config", "C0_all_on"],
                                    ["--expected-commit", "e" * 40], ["--expected-branch", "test"]])
def test_holdout_cli_forbids_split_selection_and_identity_overrides(lab, extra):
    base = ["--holdout-authorization", str(lab.auth_path), "--output-root", str(lab.root)]
    if "--config" not in extra:
        base.append("--all-configs")
    args = runner.build_parser().parse_args(base + extra)
    with pytest.raises(runner.IntegrityError):
        runner._holdout_request_from_args(args, analysis_contract_sha256="b" * 64, mapping_sha256="c" * 64)


def test_holdout_cli_requires_all_configs(lab):
    args = runner.build_parser().parse_args(["--holdout-authorization", str(lab.auth_path), "--output-root", str(lab.root)])
    with pytest.raises(runner.IntegrityError, match="all-configs"):
        runner._holdout_request_from_args(args)
    with pytest.raises(SystemExit):
        runner.build_parser().parse_args(["--split", "holdout", "--output-root", str(lab.root)])


@pytest.mark.parametrize("field,value", [("issued_by", "not-maintainer"), ("holdout_authorized", False),
    ("execution_commit", "f" * 40), ("execution_branch", "different-test-branch"),
    ("benchmark_manifest_sha256", "f" * 64), ("analysis_contract_sha256", "f" * 64),
    ("mapping_sha256", "f" * 64), ("provider_id", "cloud"), ("config_ids", []),
    ("attempt", 2), ("config_hashes", {}), ("result_schema_version", 999)])
def test_invalid_authorization_has_no_benchmark_claim_or_receipt(lab, field, value):
    lab.auth[field] = value
    _rewrite_authorization(lab)
    with pytest.raises(runner.IntegrityError):
        _preflight(lab)
    assert "benchmark" not in lab.calls and not lab.root.exists()


def test_missing_authorization_is_fail_closed(lab):
    with pytest.raises(runner.IntegrityError):
        _preflight(lab, authorization_path=lab.auth_path.with_name("test-only-authorization-missing.json"))
    assert not lab.calls and not lab.root.exists()


def test_dirty_checkout_fails_before_claim(lab, monkeypatch):
    monkeypatch.setattr(runner, "read_repository_state", lambda _: dataclasses.replace(lab.state, dirty=True))
    with pytest.raises(runner.IntegrityError, match="clean"):
        _preflight(lab)
    assert not lab.root.exists() and "benchmark" not in lab.calls


def test_one_shot_rejects_second_claim(lab):
    _preflight(lab)
    first_receipt = (lab.root / "start-receipt.json").read_bytes()
    with pytest.raises(runner.IntegrityError, match="already exists"):
        _preflight(lab)
    assert lab.calls.count("benchmark") == 1
    assert (lab.root / "start-receipt.json").read_bytes() == first_receipt


@pytest.mark.parametrize("name,value", [("temperature", "0.4"), ("seed", "7"), ("num_ctx", "2048"), ("num_predict", "64")])
def test_preflight_checks_every_frozen_generation_parameter_before_claim(lab, monkeypatch, name, value):
    monkeypatch.setenv("OLLAMA_" + name.upper(), value)
    assert getattr(load_settings(), "ollama_" + name) != lab.freeze["generation"][name]
    with pytest.raises(runner.IntegrityError, match=name):
        _preflight(lab)
    assert not lab.root.exists() and "benchmark" not in lab.calls


@pytest.mark.parametrize("change", ["missing", "hash", "commit", "provider", "run_id", "ambiguous"])
def test_freeze_reference_is_bound_and_fail_closed(lab, change):
    request = lab.request
    if change == "missing":
        request = dataclasses.replace(request, frozen_config_path=None)
    elif change == "hash":
        request = dataclasses.replace(request, frozen_config_sha256="f" * 64)
    else:
        if change == "commit":
            lab.freeze["execution_commit"] = "e" * 40
        elif change == "provider":
            lab.freeze["provider_id"] = "mock"
        elif change == "run_id":
            lab.freeze["run_id"] = "invalid run id"
        else:
            lab.freeze["temperature"] = 0.0
        _write_json(lab.freeze_path, lab.freeze)
        request = dataclasses.replace(request, frozen_config_sha256=runner._sha256_file(lab.freeze_path))
    with pytest.raises(runner.IntegrityError):
        _preflight(lab, frozen_config_path=request.frozen_config_path, frozen_config_sha256=request.frozen_config_sha256)
    assert not lab.root.exists() and "benchmark" not in lab.calls


def test_non_default_approved_freeze_is_compared_instead_of_hardcoding(lab, monkeypatch):
    lab.freeze["generation"]["seed"] = 17
    monkeypatch.setenv("OLLAMA_SEED", "17")
    _write_json(lab.freeze_path, lab.freeze)
    context = _preflight(lab, frozen_config_sha256=runner._sha256_file(lab.freeze_path))
    assert context.provider.behavior_descriptor["options"]["seed"] == 17


def test_boolean_or_fabricated_capability_cannot_unlock_ollama(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.delenv("LLM_MODEL_NAME")
    for capability in (None, True, {"authorized": True}):
        with pytest.raises(runner.IntegrityError):
            runner.default_provider_spec("ollama", load_settings(), holdout_capability=capability)
    spec = runner.ProviderSpec("ollama", lambda: None, {}, offline=False, test_only=True)
    with pytest.raises(runner.IntegrityError):
        runner._validate_provider(spec, allow_test_provider=True)


@pytest.mark.parametrize("provider", ["mock", "openai", "anthropic", ""])
def test_provider_environment_mismatch_rejected_before_claim(lab, monkeypatch, provider):
    monkeypatch.setenv("LLM_PROVIDER", provider)
    with pytest.raises(runner.IntegrityError):
        _preflight(lab)
    assert not lab.root.exists()


@pytest.mark.parametrize("credential", runner.PRODUCTION_CREDENTIAL_ENV_VARS)
def test_production_credentials_rejected_for_ollama(lab, monkeypatch, credential):
    monkeypatch.setenv(credential, "test-only-placeholder")
    with pytest.raises(runner.IntegrityError, match="credentials"):
        _preflight(lab)
    assert not lab.root.exists()


def test_ollama_provider_spec_keeps_settings_and_preclaim_checks(lab, monkeypatch):
    context = _preflight(lab, provider_id="ollama")
    bad_settings = dataclasses.replace(context.settings, llm_provider="mock")
    with pytest.raises(runner.IntegrityError, match="Ollama settings are required"):
        runner._ollama_provider_spec(bad_settings, holdout_capability=context.holdout_capability)
    monkeypatch.setenv(runner.PRODUCTION_CREDENTIAL_ENV_VARS[0], "test-only-placeholder")
    with pytest.raises(runner.IntegrityError, match="credentials"):
        runner._ollama_provider_spec(context.settings, holdout_capability=context.holdout_capability)


@pytest.mark.parametrize("url", ["http://localhost:11434", "http://127.0.0.1:80", "https://127.0.0.1:11434",
    "http://user@127.0.0.1:11434", "http://127.0.0.1:11434?x=1", "http://127.0.0.1:11434#fragment",
    "http://127.0.0.1:11434/", "http://192.0.2.1:11434"])
def test_endpoint_must_be_exact_approved_loopback(lab, monkeypatch, url):
    monkeypatch.setenv("OLLAMA_BASE_URL", url)
    with pytest.raises(runner.IntegrityError, match="127.0.0.1"):
        _preflight(lab)
    assert not lab.root.exists()


def test_worker_round_trip_binds_settings_and_claim_without_second_claim(lab, monkeypatch):
    context = _preflight(lab)
    payload = _worker_payload(lab, context)
    receipt_before = (lab.root / "start-receipt.json").read_bytes()
    result = _validate_worker(monkeypatch, payload)
    assert result[2].behavior_hash == context.provider.behavior_hash
    assert result[3] == context.settings
    assert result[2].offline is False
    assert (lab.root / "start-receipt.json").read_bytes() == receipt_before
    assert lab.calls.count("benchmark") == 1


@pytest.mark.parametrize("field,value", [("llm_model_name", "different-test-model"), ("ollama_seed", 7),
    ("ollama_temperature", 0.4), ("ollama_num_ctx", 2000), ("ollama_num_predict", 13),
    ("ollama_think", True), ("ollama_max_retries", 1), ("ollama_model_digest", "e" * 64),
    ("ollama_seed", True), ("ollama_num_ctx", 0)])
def test_worker_tampered_runtime_is_rejected_before_inference(lab, monkeypatch, field, value):
    context = _preflight(lab)
    payload = _worker_payload(lab, context)
    payload["runtime_settings"]["ollama_settings"][field] = value
    with pytest.raises(runner.IntegrityError):
        _validate_worker(monkeypatch, payload)


@pytest.mark.parametrize("target", ["provider", "hash", "receipt", "run_id", "commit", "freeze_hash", "authorization", "missing"])
def test_worker_tampered_evidence_is_rejected_before_inference(lab, monkeypatch, target):
    payload = _worker_payload(lab, _preflight(lab))
    if target == "provider":
        payload["provider_id"] = "mock"
    elif target == "hash":
        payload["provider_behavior_hash"] = "f" * 64
    elif target == "missing":
        payload.pop("holdout_evidence")
    else:
        key = {"receipt": "receipt_sha256", "run_id": "run_id", "commit": "execution_commit",
               "freeze_hash": "freeze_sha256", "authorization": "authorization_path"}[target]
        payload["holdout_evidence"][key] = "tampered-test-only"
    with pytest.raises((runner.IntegrityError, AssertionError)):
        _validate_worker(monkeypatch, payload)


def test_worker_same_env_tampering_still_fails_against_freeze(lab, monkeypatch):
    payload = _worker_payload(lab, _preflight(lab))
    monkeypatch.setenv("OLLAMA_SEED", "7")
    payload["runtime_settings"] = runner._worker_runtime_settings_payload(load_settings())
    with pytest.raises(runner.IntegrityError, match="seed"):
        _validate_worker(monkeypatch, payload)


def test_mock_worker_payload_keeps_original_protocol(lab, monkeypatch):
    lab.auth["provider_id"] = "mock"
    _rewrite_authorization(lab)
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    context = _preflight(lab)
    payload = _worker_payload(lab, context)
    assert "holdout_evidence" not in payload and "ollama_settings" not in payload["runtime_settings"]
    assert payload["protocol_version"] == 1
    assert set(payload["runtime_settings"]) == {item.name for item in dataclasses.fields(runner.WorkerRuntimeSettings)}
    result = _validate_worker(monkeypatch, payload)
    assert result[2].offline and result[2].provider_id == "mock"


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self):
        return b'{"message":{"content":"synthetic answer"},"done_reason":"stop"}'


def test_provenance_records_payload_actual_commit_and_first_failure(lab, monkeypatch):
    context = _preflight(lab)
    events = iter([HTTPError("http://127.0.0.1:11434/api/chat", 500, "synthetic", {}, None), _Response()])
    payloads = []

    def transport(request, timeout):
        payloads.append(json.loads(request.data))
        item = next(events)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(ollama, "urlopen", transport)
    provider = ollama.OllamaLLMProvider(settings=context.settings, evaluation=True,
        run_id=context.ollama_runtime["run_id"], event_sink=runner._ollama_event_sink(lab.root))
    response = provider.generate(LLMProviderRequest("test-only-prompt", "test-only-prompt", [], {}, "synthetic-id"))
    runner._write_ollama_runtime(lab.root, context.ollama_runtime)
    artifact = json.loads((lab.root / "ollama-runtime.json").read_bytes())
    assert artifact["execution_commit"] == lab.state.commit
    assert artifact["run_id"] == "test-only-P2-run" and artifact["schema_version"] == 1
    assert artifact["provider_behavior_hash"] == context.provider.behavior_hash
    request_meta = artifact["requests"]["synthetic-id"]
    assert request_meta["options"] == payloads[0]["options"] == payloads[1]["options"]
    assert request_meta["think"] == payloads[0]["think"]
    assert request_meta["model_tag"] == payloads[0]["model"]
    assert request_meta["attempt_count"] == 2 and request_meta["retry_count"] == 1
    assert request_meta["repeat_count"] == 1
    assert artifact["model_digest_observed"] is artifact["ollama_version_observed"] is None
    assert request_meta["model_digest_expected"] == context.settings.ollama_model_digest
    ends = [e for e in request_meta["attempt_trace"] if e["event"] == "attempt_end"]
    assert [e["outcome"] for e in ends] == ["retry", "success"]
    assert response.metadata["done_reason"] == "stop"
    assert "test-only-prompt" not in (lab.root / "ollama-attempts.jsonl").read_text()
    assert artifact["freeze_reference"]["sha256"] == lab.request.frozen_config_sha256


def test_started_attempt_survives_worker_timeout_without_success_metadata(lab, monkeypatch):
    context = _preflight(lab)

    class KilledWorker(BaseException):
        pass

    def killed(*args, **kwargs):
        raise KilledWorker()

    monkeypatch.setattr(ollama, "urlopen", killed)
    provider = ollama.OllamaLLMProvider(settings=context.settings, evaluation=True,
        run_id=context.ollama_runtime["run_id"], event_sink=runner._ollama_event_sink(lab.root))
    with pytest.raises(KilledWorker):
        provider.generate(LLMProviderRequest("x", "x", [], {}, "test-timeout-id"))
    runner._write_ollama_runtime(lab.root, context.ollama_runtime)
    artifact = json.loads((lab.root / "ollama-runtime.json").read_bytes())
    trace = artifact["requests"]["test-timeout-id"]["attempt_trace"]
    assert len(trace) == 1 and trace[0]["event"] == "attempt_start"
    assert not any(event.get("outcome") == "success" for event in trace)


@pytest.mark.parametrize("failure", ["empty", "500"])
def test_terminal_failure_has_durable_log_and_sidecar(lab, monkeypatch, failure):
    context = _preflight(lab)

    def transport(*args, **kwargs):
        if failure == "500":
            raise HTTPError("http://127.0.0.1:11434/api/chat", 500, "synthetic", {}, None)
        result = _Response()
        result.read = lambda: b'{"message":{"content":" "}}'
        return result

    monkeypatch.setattr(ollama, "urlopen", transport)
    provider = ollama.OllamaLLMProvider(settings=context.settings, evaluation=True,
        event_sink=runner._ollama_event_sink(lab.root), run_id=context.ollama_runtime["run_id"])
    with pytest.raises(ollama.OllamaProviderError):
        provider.generate(LLMProviderRequest("x", "x", [], {}, "test-failure-id"))
    runner._write_ollama_runtime(lab.root, context.ollama_runtime)
    meta = json.loads((lab.root / "ollama-runtime.json").read_bytes())["requests"]["test-failure-id"]
    assert meta["attempt_trace"][-1]["outcome"] in {"terminal_failure", "empty_response"}
    assert meta["attempt_count"] == (3 if failure == "500" else 1)


def test_worker_timeout_budget_is_bound_to_parent(lab, monkeypatch):
    payload = _worker_payload(lab, _preflight(lab))
    payload["holdout_evidence"]["case_timeout_seconds"] = 3600
    with pytest.raises(runner.IntegrityError, match="parent claim"):
        _validate_worker(monkeypatch, payload)


def test_loopback_network_guard_restricts_connection_and_restores_hooks(monkeypatch):
    connections = []

    class SocketDouble:
        def __init__(self, family=socket.AF_INET, type=socket.SOCK_STREAM):
            self.family, self.type = family, type

        def connect(self, address):
            connections.append(address)

        def connect_ex(self, address):
            connections.append(address)
            return 0

    def create_double(address, *args, **kwargs):
        connections.append(address)

    def dns_double(host, port, *args, **kwargs):
        return [(host, port)]

    monkeypatch.setattr(socket, "socket", SocketDouble)
    monkeypatch.setattr(socket, "create_connection", create_double)
    monkeypatch.setattr(socket, "getaddrinfo", dns_double)
    with runner._ollama_loopback_only():
        socket.socket().connect(("127.0.0.1", 11434))
        socket.create_connection(("127.0.0.1", 11434))
        assert socket.getaddrinfo("127.0.0.1", 11434) == [("127.0.0.1", 11434)]
        for address in (("127.0.0.1", 80), ("localhost", 11434), ("192.0.2.1", 11434)):
            with pytest.raises(runner.IntegrityError):
                socket.socket().connect(address)
            with pytest.raises(runner.IntegrityError):
                socket.socket().connect_ex(address)
            with pytest.raises(runner.IntegrityError):
                socket.create_connection(address)
            with pytest.raises(runner.IntegrityError):
                socket.getaddrinfo(*address)
        with pytest.raises(runner.IntegrityError):
            socket.socket(type=socket.SOCK_DGRAM).connect(("127.0.0.1", 11434))
        with pytest.raises(runner.IntegrityError):
            socket.socket().sendto(b"x", ("127.0.0.1", 11434))
    assert connections == [("127.0.0.1", 11434), ("127.0.0.1", 11434)]
    assert socket.socket is SocketDouble and socket.create_connection is create_double
    assert socket.getaddrinfo is dns_double


@pytest.mark.parametrize("failure", [False, True])
def test_worker_loop_uses_validated_settings_deadline_and_durable_sink(lab, monkeypatch, failure):
    context = _preflight(lab)
    payload = _worker_payload(lab, context)
    monkeypatch.setattr(runner, "SqliteBM25Retriever", lambda config: SimpleNamespace(config=config))
    # This is a socket double, not permission to use any real socket.
    monkeypatch.setattr(socket, "socket", type("SocketDouble", (), {}))
    monkeypatch.setattr(runner, "time", SimpleNamespace(monotonic=lambda: 100.0))
    deadline = 129.0

    def transport(request, timeout):
        assert timeout == 29.0
        if failure:
            raise HTTPError("http://127.0.0.1:11434/api/chat", 500, "synthetic", {}, None)
        return _Response()

    monkeypatch.setattr(ollama, "urlopen", transport)

    def scope_double(**kwargs):
        provider = kwargs["provider_spec"].factory()
        assert provider.settings == context.settings and provider.deadline == deadline
        provider.generate(LLMProviderRequest("private synthetic prompt", "private synthetic prompt", [], {}, "loop-test"))
        return runner.ScopeOutcome("ALLOW", "synthetic", True, 0, 0, 0, 0, {}, (), 0.0, 0.0)

    monkeypatch.setattr(runner, "_execute_scope", scope_double)
    monkeypatch.setattr(runner.os, "getpid", lambda: 12345)
    tasks = iter([{"kind": "case", "protocol_version": 1, "case": {}, "repetition": 0,
                   "deadline_monotonic": deadline}, {"kind": "stop", "protocol_version": 1}])
    sent = []
    connection = SimpleNamespace(send=sent.append, recv=lambda: next(tasks), close=lambda: None)
    runner._case_worker_main(connection, payload)
    assert [item["kind"] for item in sent] == ["ready", "case_error" if failure else "outcome", "stopped"]
    trace = (lab.root / "ollama-attempts.jsonl").read_text()
    assert "private synthetic prompt" not in trace
    assert "attempt_start" in trace and ("terminal_failure" if failure else "success") in trace
    if failure:
        assert '"http_status":500' in trace


@pytest.mark.parametrize("provider", ["mock", "ollama"])
def test_config_execution_preserves_mock_repetitions_and_ollama_repeat_count(lab, monkeypatch, provider):
    if provider == "mock":
        lab.auth["provider_id"] = "mock"
        _rewrite_authorization(lab)
        monkeypatch.setenv("LLM_PROVIDER", "mock")
    context = _preflight(lab)
    case = {**context.benchmark.cases[0], "scenario_family": "synthetic-family"}
    label = {"category": "synthetic", "allowed_final_decisions": ["ALLOW"],
             "allowed_stop_reasons": ["synthetic"], "expected_provider_called": True}
    context = dataclasses.replace(context, benchmark=runner.LoadedBenchmark((), (case,), {case["case_id"]: label}))
    repetitions, timeouts = [], []

    class RetrieverDouble:
        def __init__(self, config):
            self.config = config

        def initialize(self):
            Path(self.config.db_path).write_bytes(b"synthetic database")

    class WorkerDouble:
        def __init__(self, **kwargs):
            self.payload = kwargs["init_payload"]
            assert self.payload["provider_id"] == provider

        def execute(self, task, timeout_seconds):
            repetitions.append(task["repetition"])
            timeouts.append(timeout_seconds)
            return {"kind": "case_error", "error_category": "case_execution_error", "state_trustworthy": True}

        def close(self):
            pass

    monkeypatch.setattr(runner, "SqliteBM25Retriever", RetrieverDouble)
    monkeypatch.setattr(runner, "_SpawnCaseWorker", WorkerDouble)
    monkeypatch.setattr(runner, "_ingest_corpus", lambda *args: {})
    artifact = runner._execute_config(context, runner.CONFIG_REGISTRY["C0_all_on"], repo_root=lab.repo,
                                     hooks=runner.RunnerHooks(), run_id="test-only-config-run")
    expected_count = 2
    assert repetitions == list(range(expected_count)) and timeouts == [30.0] * expected_count
    assert artifact["environment"]["repetitions"] == expected_count
    assert artifact["run_status"] == "partial" and artifact["error_case_count"] == 1


def test_parent_refreshes_provenance_when_config_execution_raises(lab, monkeypatch):
    def transport(*args, **kwargs):
        raise HTTPError("http://127.0.0.1:11434/api/chat", 500, "synthetic", {}, None)

    monkeypatch.setattr(ollama, "urlopen", transport)

    def failed_config(context, config, **kwargs):
        provider = ollama.OllamaLLMProvider(settings=context.settings, evaluation=True,
            event_sink=runner._ollama_event_sink(lab.root), run_id=context.ollama_runtime["run_id"])
        provider.generate(LLMProviderRequest("x", "x", [], {}, "test-parent-failure"))
        raise AssertionError("a failed provider must not return")

    monkeypatch.setattr(runner, "_execute_config", failed_config)
    with pytest.raises(ollama.OllamaProviderError):
        runner.run_holdout_evaluation(lab.request, repo_root=lab.repo, benchmark_root=lab.benchmark)
    artifact = json.loads((lab.root / "ollama-runtime.json").read_bytes())
    assert artifact["requests"]["test-parent-failure"]["attempt_count"] == 3
    assert artifact["requests"]["test-parent-failure"]["attempt_trace"][-1]["outcome"] == "terminal_failure"
    assert (lab.root / "start-receipt.json").exists()
    assert not (lab.root / "runs").exists()


def test_holdout_cli_omission_binds_provider_after_verified_authorization(lab):
    args = runner.build_parser().parse_args([
        "--holdout-authorization", str(lab.auth_path), "--all-configs", "--output-root", str(lab.root),
        "--frozen-config", str(lab.freeze_path), "--frozen-config-sha256", lab.request.frozen_config_sha256,
    ])
    request = runner._holdout_request_from_args(args)
    assert request.provider_id is None
    context = runner.holdout_preflight(request, repo_root=lab.repo, benchmark_root=lab.benchmark)
    assert context.provider.provider_id == "ollama"


def test_reordered_configs_are_rejected_before_claim(lab):
    lab.auth["config_ids"].reverse()
    _rewrite_authorization(lab)
    with pytest.raises(runner.IntegrityError):
        _preflight(lab)
    assert not lab.root.exists() and "benchmark" not in lab.calls


def test_explicit_null_freeze_value_is_not_treated_as_missing(lab):
    lab.freeze["repeat_count"] = None
    _write_json(lab.freeze_path, lab.freeze)
    with pytest.raises(runner.IntegrityError, match="repeat_count"):
        _preflight(lab, frozen_config_sha256=runner._sha256_file(lab.freeze_path))
    assert not lab.root.exists()



def test_request_ids_are_unique_across_config_and_repetition():
    case_id = "synthetic-case"
    first = runner._scope_request_id("C0_all_on", case_id, 0)
    second = runner._scope_request_id("C0_all_on", case_id, 1)
    other_config = runner._scope_request_id("C1_no_input", case_id, 0)
    assert first != second != other_config != first
    assert first == runner._scope_request_id("C0_all_on", case_id, 0)
    assert len({first, second, other_config}) == 3
    assert all(len(value) == 32 and set(value) <= set("0123456789abcdef") for value in (first, second, other_config))


def test_ollama_holdout_artifact_publish_accepts_provider_and_loopback_network(lab, monkeypatch):
    context = _preflight(lab)
    case = {**context.benchmark.cases[0], "scenario_family": "synthetic-family"}
    label = {"category": "synthetic", "allowed_final_decisions": ["ALLOW"],
             "allowed_stop_reasons": ["synthetic"], "expected_provider_called": True}
    context = dataclasses.replace(context, benchmark=runner.LoadedBenchmark((), (case,), {case["case_id"]: label}))

    class RetrieverDouble:
        def __init__(self, config):
            self.config = config

        def initialize(self):
            Path(self.config.db_path).write_bytes(b"synthetic database")

    class WorkerDouble:
        def __init__(self, **kwargs):
            assert kwargs["init_payload"]["provider_id"] == "ollama"

        def execute(self, task, timeout_seconds):
            return {"kind": "case_error", "error_category": "case_execution_error", "state_trustworthy": True}

        def close(self):
            pass

    monkeypatch.setattr(runner, "SqliteBM25Retriever", RetrieverDouble)
    monkeypatch.setattr(runner, "_SpawnCaseWorker", WorkerDouble)
    monkeypatch.setattr(runner, "_ingest_corpus", lambda *args: {})
    artifact = runner._execute_config(context, runner.CONFIG_REGISTRY["C0_all_on"], repo_root=lab.repo,
                                     hooks=runner.RunnerHooks(), run_id="test-only-publish-run")
    assert artifact["provider_id"] == "ollama"
    assert artifact["safety_limits"]["network_disabled"] is False
    augmented = runner._augment_holdout_artifact(artifact, context.holdout_capability)
    assert augmented["provider_id"] == "ollama"
    assert augmented["safety_limits"]["network_disabled"] is False
    assert augmented["schema_version"] == runner.HOLDOUT_RESULT_SCHEMA_VERSION
    assert augmented["environment"]["result_schema_version"] == runner.HOLDOUT_RESULT_SCHEMA_VERSION
    written = runner._publish_holdout_artifact(lab.root, augmented, context.holdout_capability)
    published = json.loads(written.result_path.read_text(encoding="utf-8"))
    manifest = json.loads(written.manifest_path.read_text(encoding="utf-8"))
    assert published["provider_id"] == "ollama"
    assert published["safety_limits"]["network_disabled"] is False
    assert manifest["provider_id"] == "ollama"
    assert manifest["result_schema_version"] == runner.HOLDOUT_RESULT_SCHEMA_VERSION
