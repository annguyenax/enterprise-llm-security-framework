"""W13 synthetic fixtures only. No official dataset or holdout contents are read."""
from __future__ import annotations

import builtins
import dataclasses
import hashlib
import io
import json
from pathlib import Path

import pytest

from scripts import derive_v2_dev_val_manifest as derive
from scripts import run_v2_evaluation as runner


EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


@pytest.fixture(autouse=True)
def offline_and_no_protected_reads(monkeypatch):
    """Guard binary and text reads, including hashing; allow no official data."""
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    for name in runner.PRODUCTION_CREDENTIAL_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    official_root = runner.ROOT / "datasets" / "v2"

    def wrap(original):
        def guarded(file, mode="r", *args, **kwargs):
            if isinstance(file, (str, bytes, Path)):
                path = Path(file).absolute()
                reading = "r" in mode or "+" in mode
                if reading and (path.is_relative_to(official_root)
                                or "holdout" in path.name.casefold()
                                or path.name == "result.json"):
                    pytest.fail("protected artifact read attempted")
            return original(file, mode, *args, **kwargs)
        return guarded

    monkeypatch.setattr(builtins, "open", wrap(builtins.open))
    monkeypatch.setattr(io, "open", wrap(io.open))

    def no_network(*_args, **_kwargs):
        pytest.fail("network access attempted")

    monkeypatch.setattr(runner.socket.socket, "connect", no_network)
    monkeypatch.setattr(runner.socket.socket, "connect_ex", no_network)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(item) + "\n" for item in records), encoding="utf-8")


@pytest.fixture
def working_set(tmp_path):
    root = tmp_path / "working-set"
    write_jsonl(root / "corpus/documents.jsonl", [{
        "document_id": "synthetic-doc", "external_id": "synthetic-external",
        "source_key": "api_upload", "title": "Synthetic policy",
        "content": "Synthetic policy allows ordinary document lookups.",
        "scenario_family": "synthetic", "ingestion_mode": "public", "metadata": {},
    }])
    for split in runner.SUPPORTED_SPLITS:
        scopes = [scope for scope, count in runner.EXPECTED_SCOPE_COUNTS_BY_SPLIT[split].items()
                  for _ in range(count)]
        cases, labels = [], []
        for index, scope in enumerate(scopes):
            case_id = f"synthetic-{split}-{index:02d}"
            cases.append({
                "case_id": case_id, "split": split, "scenario_family": "synthetic",
                "query": "Synthetic policy", "evaluation_scope": scope, "top_k": 1,
                "relevant_document_ids": ["synthetic-doc"],
            })
            labels.append({
                "case_id": case_id, "scenario_family": "synthetic", "category": "benign",
                "allowed_final_decisions": ["allow"], "allowed_stop_reasons": ["allowed"],
                "expected_provider_called": True,
            })
        write_jsonl(root / f"cases/{split}.jsonl", reversed(cases))
        write_jsonl(root / f"labels/{split}.jsonl", labels)
    write_json(root / "contamination-exemptions.json", {"exemptions": []})
    return root


@pytest.fixture
def source_manifest(tmp_path, working_set, monkeypatch):
    """Inject official nine-file metadata without any official artifacts."""
    entries = []
    for relative in runner.REQUIRED_FROZEN_PATHS:
        if relative in runner.DEV_VAL_FROZEN_PATHS:
            raw = (working_set / relative).read_bytes()
            digest, size = hashlib.sha256(raw).hexdigest(), len(raw)
        else:
            digest, size = EMPTY_SHA256, 0
        entries.append({"path": relative, "sha256": digest, "size_bytes": size})
    path = tmp_path / "metadata-source/manifests/benchmark-v2-manifest.json"
    write_json(path, {
        "manifest_version": 1, "benchmark_version": "v2", "manifest_status": "final",
        "file_count": 9, "files": entries,
    })
    monkeypatch.setattr(runner, "OFFICIAL_V2_MANIFEST_PATH", path)
    return path


@pytest.fixture
def derived(working_set, source_manifest):
    runner.derive_dev_val_manifest(source_manifest, working_set)
    return working_set


def request_and_hooks(tmp_path):
    request = runner.RunRequest(
        split="development", config_ids=("C6_none",), output_root=tmp_path / "output",
        expected_branch="synthetic-branch", expected_commit="a" * 40, benchmark_mode="dev-val",
    )
    hooks = runner.RunnerHooks(
        repository_state_loader=lambda _root: runner.RepositoryState("synthetic-branch", "a" * 40, False),
        temp_parent=tmp_path / "runtime",
    )
    return request, hooks


def test_derivation_has_six_sorted_paths_and_own_identity(derived, source_manifest):
    raw = (derived / runner.DEV_VAL_MANIFEST_PATH).read_bytes()
    manifest = json.loads(raw)
    identity = runner.verify_dev_val_manifest(derived)
    assert tuple(item["path"] for item in manifest["files"]) == runner.DEV_VAL_FROZEN_PATHS
    assert manifest["file_count"] == identity.file_count == len(manifest["files"]) == 6
    assert identity.sha256 == hashlib.sha256(raw).hexdigest()
    assert identity.sha256 != manifest["source_manifest_sha256"]
    assert manifest["source_manifest_sha256"] == hashlib.sha256(source_manifest.read_bytes()).hexdigest()
    assert identity.status == runner.DEV_VAL_MANIFEST_STATUS


def test_derivation_is_deterministic_and_refuses_overwrite(derived, source_manifest, tmp_path):
    import shutil

    other = tmp_path / "other"
    for relative in runner.DEV_VAL_FROZEN_PATHS:
        target = other / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(derived / relative, target)
    first = (derived / runner.DEV_VAL_MANIFEST_PATH).read_bytes()
    runner.derive_dev_val_manifest(source_manifest, other)
    assert (other / runner.DEV_VAL_MANIFEST_PATH).read_bytes() == first
    with pytest.raises(runner.IntegrityError, match="overwrite is prohibited"):
        runner.derive_dev_val_manifest(source_manifest, derived)
    assert (derived / runner.DEV_VAL_MANIFEST_PATH).read_bytes() == first


@pytest.mark.parametrize("split", runner.SUPPORTED_SPLITS)
def test_split_loader_uses_derived_verifier_without_official_artifacts(derived, split, monkeypatch):
    def no_official(*_args, **_kwargs):
        pytest.fail("official nine-file verifier reached")

    monkeypatch.setattr(runner, "verify_frozen_manifest", no_official)
    benchmark = runner.load_split_benchmark(derived, split, benchmark_mode="dev-val")
    assert len(benchmark.cases) == 30
    assert all(case["split"] == split for case in benchmark.cases)
    assert [case["case_id"] for case in benchmark.cases] == sorted(benchmark.labels_by_id)


def test_development_runner_executes_synthetic_working_set(derived, tmp_path):
    request, hooks = request_and_hooks(tmp_path)
    context = runner.preflight(request, benchmark_root=derived, hooks=hooks)
    artifact = runner._execute_config(  # noqa: SLF001
        context, runner.CONFIG_REGISTRY["C6_none"], repo_root=runner.ROOT,
        hooks=hooks, run_id="synthetic-run",
    )
    assert artifact["run_status"] == "complete"
    assert artifact["completed_case_count"] == 26
    assert artifact["error_case_count"] == artifact["timeout_case_count"] == 0
    assert artifact["environment"]["benchmark_manifest_sha256"] == context.manifest.sha256
    assert artifact["environment"]["benchmark_manifest_status"] == runner.DEV_VAL_MANIFEST_STATUS


@pytest.mark.parametrize("relative", [
    "cases/holdout.jsonl", "labels/holdout.jsonl", "archive/holdout/result.json",
    "archive/P3-HOLDOUT.log", "holdout-empty-directory", "archive/result.json", "logs/ollama.log",
])
def test_working_set_holdout_names_rejected_before_any_open(derived, relative, monkeypatch):
    path = derived / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if relative == "holdout-empty-directory":
        path.mkdir()
    else:
        path.touch()  # Empty synthetic sentinel; never read or hashed.

    def no_open(*_args, **_kwargs):
        pytest.fail("file opened before working-set rejection")

    monkeypatch.setattr(Path, "open", no_open)
    with pytest.raises(runner.IntegrityError, match="holdout path"):
        runner.verify_dev_val_manifest(derived)


def test_derivation_rejects_holdout_before_reading_source(working_set, source_manifest, monkeypatch):
    (working_set / "cases/holdout.jsonl").touch()
    monkeypatch.setattr(Path, "open", lambda *_a, **_k: pytest.fail("file opened"))
    with pytest.raises(runner.IntegrityError, match="holdout path"):
        runner.derive_dev_val_manifest(source_manifest, working_set)


@pytest.mark.parametrize("mutation", ["candidate", "missing", "order", "extra", "digest", "size"])
def test_derivation_validates_source_metadata_before_artifact_reads(
    working_set, source_manifest, mutation, monkeypatch,
):
    manifest = json.loads(source_manifest.read_bytes())
    if mutation == "candidate":
        manifest["manifest_status"] = "candidate"
    elif mutation == "missing":
        manifest["files"].pop()
        manifest["file_count"] -= 1
    elif mutation == "order":
        manifest["files"].reverse()
    elif mutation == "extra":
        manifest["files"][0]["path"] = "cases/unapproved.jsonl"
    elif mutation == "digest":
        manifest["files"][0]["sha256"] = "invalid"
    else:
        manifest["files"][0]["size_bytes"] = False
    write_json(source_manifest, manifest)
    monkeypatch.setattr(runner, "_sha256_file", lambda *_a: pytest.fail("artifact hashed"))
    with pytest.raises(runner.IntegrityError):
        runner.derive_dev_val_manifest(source_manifest, working_set)
    assert not (working_set / runner.DEV_VAL_MANIFEST_PATH).exists()


def test_derivation_refuses_working_set_mismatch(working_set, source_manifest):
    with (working_set / "cases/development.jsonl").open("ab") as handle:
        handle.write(b"\n")
    with pytest.raises(runner.IntegrityError, match="artifact mismatch"):
        runner.derive_dev_val_manifest(source_manifest, working_set)
    assert not (working_set / runner.DEV_VAL_MANIFEST_PATH).exists()


@pytest.mark.parametrize("relative", [
    "cases/holdout.jsonl", "labels/holdout.jsonl", "../holdout.jsonl",
    "/tmp/holdout.jsonl", "cases\\holdout.jsonl",
])
def test_manifest_holdout_paths_rejected_before_artifact_reads(derived, relative, monkeypatch):
    path = derived / runner.DEV_VAL_MANIFEST_PATH
    manifest = json.loads(path.read_bytes())
    manifest["files"].append({"path": relative, "sha256": EMPTY_SHA256, "size_bytes": 0})
    manifest["file_count"] += 1
    write_json(path, manifest)
    monkeypatch.setattr(runner, "_sha256_file", lambda *_a: pytest.fail("artifact hashed"))
    with pytest.raises(runner.IntegrityError, match="holdout path"):
        runner.load_split_benchmark(derived, "development", benchmark_mode="dev-val")


@pytest.mark.parametrize("mutation", [
    "count", "order", "duplicate", "missing", "digest", "size", "traversal", "source", "mode", "status",
])
def test_malformed_derived_manifest_fails_closed(derived, mutation):
    path = derived / runner.DEV_VAL_MANIFEST_PATH
    manifest = json.loads(path.read_bytes())
    if mutation == "count":
        manifest["file_count"] = 9
    elif mutation == "order":
        manifest["files"].reverse()
    elif mutation == "duplicate":
        manifest["files"][1] = manifest["files"][0]
    elif mutation == "missing":
        manifest["files"].pop()
        manifest["file_count"] -= 1
    elif mutation == "digest":
        manifest["files"][0]["sha256"] = "invalid"
    elif mutation == "size":
        manifest["files"][0]["size_bytes"] = True
    elif mutation == "traversal":
        manifest["files"][0]["path"] = "../development.jsonl"
    elif mutation == "source":
        manifest["source_manifest_sha256"] = None
    elif mutation == "mode":
        manifest["benchmark_mode"] = "official"
    else:
        manifest["manifest_status"] = "final"
    write_json(path, manifest)
    with pytest.raises(runner.IntegrityError):
        runner.verify_dev_val_manifest(derived)


@pytest.mark.parametrize("entrypoint", ["verify", "preflight"])
def test_valid_source_digest_must_match_official_before_artifact_reads(
    derived, tmp_path, monkeypatch, entrypoint,
):
    path = derived / runner.DEV_VAL_MANIFEST_PATH
    manifest = json.loads(path.read_bytes())
    manifest["source_manifest_sha256"] = hashlib.sha256(b"unofficial metadata").hexdigest()
    write_json(path, manifest)
    monkeypatch.setattr(runner, "_sha256_file", lambda *_a: pytest.fail("artifact hashed"))
    with pytest.raises(runner.IntegrityError, match="source digest differs from the official"):
        if entrypoint == "verify":
            runner.verify_dev_val_manifest(derived)
        else:
            request, hooks = request_and_hooks(tmp_path)
            runner.preflight(request, benchmark_root=derived, hooks=hooks)
            pytest.fail("preflight accepted an unofficial source digest")
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("relative", runner.DEV_VAL_FROZEN_PATHS)
def test_self_consistent_table_must_match_official_subset_before_artifact_reads(
    derived, relative, monkeypatch,
):
    artifact = derived / relative
    raw = artifact.read_bytes() + b"\n"
    artifact.write_bytes(raw)
    path = derived / runner.DEV_VAL_MANIFEST_PATH
    manifest = json.loads(path.read_bytes())
    entry = next(item for item in manifest["files"] if item["path"] == relative)
    entry.update(sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw))
    write_json(path, manifest)
    monkeypatch.setattr(runner, "_sha256_file", lambda *_a: pytest.fail("artifact hashed"))
    with pytest.raises(runner.IntegrityError, match="file table differs from the official V2 subset"):
        runner.verify_dev_val_manifest(derived)


@pytest.mark.parametrize("field,value", [("sha256", "f" * 64), ("size_bytes", 0)])
def test_official_subset_compares_each_hash_and_size(derived, field, value, monkeypatch):
    path = derived / runner.DEV_VAL_MANIFEST_PATH
    manifest = json.loads(path.read_bytes())
    manifest["files"][0][field] = value
    write_json(path, manifest)
    monkeypatch.setattr(runner, "_sha256_file", lambda *_a: pytest.fail("artifact hashed"))
    with pytest.raises(runner.IntegrityError, match="file table differs from the official V2 subset"):
        runner.verify_dev_val_manifest(derived)


@pytest.mark.parametrize("relative", runner.DEV_VAL_FROZEN_PATHS)
def test_each_dev_val_artifact_mismatch_fails_closed(derived, relative):
    with (derived / relative).open("ab") as handle:
        handle.write(b"\n")
    with pytest.raises(runner.IntegrityError, match="artifact mismatch"):
        runner.verify_dev_val_manifest(derived)


@pytest.mark.parametrize("relative", runner.DEV_VAL_FROZEN_PATHS)
def test_each_dev_val_artifact_is_required(derived, relative):
    path = derived / relative
    path.rename(path.with_suffix(".saved"))
    with pytest.raises(runner.IntegrityError, match="six runtime artifacts"):
        runner.verify_dev_val_manifest(derived)


@pytest.mark.parametrize("relative", ["cases/extra.jsonl", "design/authoring-provenance.jsonl"])
def test_unneeded_artifacts_rejected_by_path_without_read(derived, relative, monkeypatch):
    path = derived / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    # No case ID or case content; provenance is not a runtime input.
    path.write_text('{"split":"holdout"}\n', encoding="utf-8")
    monkeypatch.setattr(Path, "open", lambda *_a, **_k: pytest.fail("file opened"))
    with pytest.raises(runner.IntegrityError, match="six runtime artifacts"):
        runner.verify_dev_val_manifest(derived)


@pytest.mark.parametrize("relative", ["cases/development.jsonl", "archive"])
def test_symlinks_rejected_before_open(derived, relative, tmp_path, monkeypatch):
    path = derived / relative
    if path.exists():
        path.rename(tmp_path / "saved-development.jsonl")
    path.symlink_to(tmp_path / "absent-target")
    monkeypatch.setattr(Path, "open", lambda *_a, **_k: pytest.fail("file opened"))
    with pytest.raises(runner.IntegrityError, match="links"):
        runner.verify_dev_val_manifest(derived)


def test_direct_loader_cannot_skip_derived_verification(derived):
    (derived / runner.DEV_VAL_MANIFEST_PATH).rename(derived / "saved-manifest.json")
    with pytest.raises(runner.IntegrityError, match="manifest is unavailable"):
        runner.load_split_benchmark(derived, "validation", benchmark_mode="dev-val")
    with pytest.raises(runner.IntegrityError, match="development or validation"):
        runner.load_split_benchmark(derived, "holdout", benchmark_mode="dev-val")


def test_preflight_refuses_holdout_without_creating_output(derived, tmp_path):
    (derived / "labels/holdout.jsonl").touch()
    request, hooks = request_and_hooks(tmp_path)
    with pytest.raises(runner.IntegrityError, match="holdout path"):
        runner.preflight(request, benchmark_root=derived, hooks=hooks)
    assert not request.output_root.exists()


def test_timeout_recovery_reverifies_derived_manifest(derived, tmp_path):
    request, hooks = request_and_hooks(tmp_path)
    context = runner.preflight(request, benchmark_root=derived, hooks=hooks)
    database = tmp_path / "temporary.sqlite3"
    database.write_bytes(b"synthetic database identity")
    arguments = dict(
        case=context.benchmark.cases[0], database_path=database,
        database_sha256=runner._sha256_file(database), temp_root=tmp_path,
        context=context, repo_root=runner.ROOT, hooks=hooks,
    )
    runner._verify_timeout_recovery_state(**arguments)
    (derived / "cases/holdout.jsonl").touch()
    with pytest.raises(runner.IntegrityError, match="holdout path"):
        runner._verify_timeout_recovery_state(**arguments)


def test_official_verifier_still_requires_nine_files(working_set, source_manifest, monkeypatch):
    """Official placeholder hashes are stubbed; no holdout file is opened."""
    write_json(working_set / "manifests/benchmark-v2-manifest.json", json.loads(source_manifest.read_bytes()))
    with pytest.raises(runner.IntegrityError, match="frozen artifact missing"):
        runner.verify_frozen_manifest(working_set)
    for relative in set(runner.REQUIRED_FROZEN_PATHS) - set(runner.DEV_VAL_FROZEN_PATHS):
        path = working_set / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    original_hash = runner._sha256_file

    def synthetic_hash(path):
        if path.name == "holdout.jsonl":
            return EMPTY_SHA256
        return original_hash(path)

    monkeypatch.setattr(runner, "_sha256_file", synthetic_hash)
    identity = runner.verify_frozen_manifest(working_set)
    assert identity.file_count == 9
    assert identity.status == "final"
    with pytest.raises(runner.IntegrityError, match="holdout path"):
        runner.verify_dev_val_manifest(working_set)
    manifest_path = working_set / "manifests/benchmark-v2-manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest["files"] = [entry for entry in manifest["files"] if entry["path"] in runner.DEV_VAL_FROZEN_PATHS]
    manifest["file_count"] = 6
    write_json(manifest_path, manifest)
    with pytest.raises(runner.IntegrityError, match="exactly nine artifacts"):
        runner.verify_frozen_manifest(working_set)


def test_derived_manifest_is_not_an_official_manifest(derived):
    write_json(derived / "manifests/benchmark-v2-manifest.json",
               json.loads((derived / runner.DEV_VAL_MANIFEST_PATH).read_bytes()))
    with pytest.raises(runner.IntegrityError, match="status must be final"):
        runner.verify_frozen_manifest(derived)


@pytest.mark.parametrize("explicit_source", [False, True])
def test_cli_tool_derives_from_injected_official_metadata(
    working_set, source_manifest, capsys, explicit_source,
):
    args = ["--benchmark-root", str(working_set)]
    if explicit_source:
        args.extend(["--source-manifest", str(source_manifest)])
    assert derive.main(args) == 0
    assert "files=6; sha256=" in capsys.readouterr().out
    assert derive.main(args) == 1
    assert "manifest_write" in capsys.readouterr().err


@pytest.mark.parametrize("source_kind", ["metadata", "holdout-path"])
@pytest.mark.parametrize("entrypoint", ["derive", "cli"])
def test_nonofficial_source_rejected_before_any_open(
    working_set, source_manifest, tmp_path, monkeypatch, capsys, source_kind, entrypoint,
):
    if source_kind == "metadata":
        # Even an identical FINAL manifest at a different path is refused.
        source = tmp_path / "alternate/manifests/benchmark-v2-manifest.json"
        source.parent.mkdir(parents=True)
        source.write_bytes(source_manifest.read_bytes())
    else:
        source = tmp_path / "holdout.jsonl"
        source.touch()  # Name-only rejection, with no protected content.
    monkeypatch.setattr(Path, "open", lambda *_a, **_k: pytest.fail("file opened"))
    if entrypoint == "derive":
        with pytest.raises(runner.IntegrityError, match="must be the official V2 manifest"):
            runner.derive_dev_val_manifest(source, working_set)
    else:
        assert derive.main(["--benchmark-root", str(working_set), "--source-manifest", str(source)]) == 1
        assert "manifest_source" in capsys.readouterr().err
    assert not (working_set / runner.DEV_VAL_MANIFEST_PATH).exists()


def test_cli_runner_passes_dev_val_mode_and_root(derived, tmp_path, monkeypatch):
    captured = {}

    def fake_run(request, **kwargs):
        captured.update(request=request, **kwargs)
        return []

    monkeypatch.setattr(runner, "run_evaluation", fake_run)
    assert runner.main([
        "--split", "development", "--config", "C6_none", "--benchmark-mode", "dev-val",
        "--benchmark-root", str(derived), "--output-root", str(tmp_path / "output"),
        "--expected-branch", "synthetic", "--expected-commit", "a" * 40,
    ]) == 0
    assert captured["request"].benchmark_mode == "dev-val"
    assert captured["benchmark_root"] == derived


@pytest.mark.parametrize("mode", [[], ["--benchmark-mode", "official"]])
@pytest.mark.parametrize("authorized", [False, True])
def test_cli_runner_rejects_official_root_before_any_open_or_dispatch(
    tmp_path, monkeypatch, capsys, mode, authorized,
):
    args = [
        "--benchmark-root", str(tmp_path / "unofficial-benchmark"),
        "--output-root", str(tmp_path / "output"), *mode,
    ]
    if authorized:
        args.extend(["--holdout-authorization", str(tmp_path / "absent-authorization.json"), "--all-configs"])
    else:
        args.extend([
            "--split", "development", "--config", "C6_none",
            "--expected-branch", "synthetic", "--expected-commit", "a" * 40,
        ])
    monkeypatch.setattr(Path, "open", lambda *_a, **_k: pytest.fail("file opened"))
    for name in ("run_evaluation", "run_holdout_evaluation", "_holdout_request_from_args"):
        monkeypatch.setattr(runner, name, lambda *_a, **_k: pytest.fail("runner dispatched"))
    assert runner.main(args) == 1
    assert "--benchmark-root requires --benchmark-mode dev-val" in capsys.readouterr().err
    assert not (tmp_path / "output").exists()


def test_dev_val_mode_cannot_enter_authorized_holdout_path(tmp_path):
    args = runner.build_parser().parse_args([
        "--holdout-authorization", "absent-authorization.json", "--all-configs",
        "--output-root", str(tmp_path / "output"), "--benchmark-mode", "dev-val",
    ])
    with pytest.raises(runner.IntegrityError, match="overrides are prohibited"):
        runner._holdout_request_from_args(args)


def test_invalid_benchmark_mode_fails_closed(derived, tmp_path):
    request, hooks = request_and_hooks(tmp_path)
    with pytest.raises(runner.IntegrityError, match="benchmark mode"):
        runner.preflight(dataclasses.replace(request, benchmark_mode="unknown"), benchmark_root=derived, hooks=hooks)
