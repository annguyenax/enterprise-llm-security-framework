"""Phase 12E.4 holdout authorization gate tests.

Every fixture in this module is synthetic. No test opens, parses or enumerates
the real frozen holdout case or label files, and no test executes holdout,
validation or development evaluation.

Plan: docs/ai-collaboration/07_PHASE_12E4_HOLDOUT_PLAN.md
"""
from __future__ import annotations

import importlib.util
import json
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"


def _load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def runner():
    return _load_module("v2_holdout_runner_mod", "run_v2_evaluation.py")


@pytest.fixture()
def authorization_payload(runner):
    """A structurally valid synthetic authorization payload."""
    return {
        "schema_version": 1,
        "authorization_id": "0f9a1c2d-3e4b-4a5c-8d6e-7f8091a2b3c4",
        "issued_at_utc": "2026-07-19T10:00:00Z",
        "issued_by": runner.HOLDOUT_AUTHORIZATION_ISSUER,
        "purpose": runner.HOLDOUT_AUTHORIZATION_PURPOSE,
        "execution_branch": "phase-12e-4-holdout-gate",
        "execution_commit": "0" * 40,
        "benchmark_manifest_sha256": "a" * 64,
        "provider_id": "mock",
        "config_ids": list(runner.CONFIG_REGISTRY),
        "config_hashes": {
            config_id: config.config_hash
            for config_id, config in runner.CONFIG_REGISTRY.items()
        },
        "result_schema_version": runner.HOLDOUT_RESULT_SCHEMA_VERSION,
        "result_manifest_schema_version": runner.HOLDOUT_RESULT_MANIFEST_SCHEMA_VERSION,
        "analysis_schema_version": 1,
        "analysis_manifest_schema_version": 1,
        "analysis_contract_sha256": "b" * 64,
        "mapping_sha256": "c" * 64,
        "output_root": "/tmp/p12e4-attempt-1",
        "attempt": 1,
        "supersedes_authorization_sha256": None,
        "holdout_authorized": True,
    }


def _repo_state(runner, parsed):
    return runner.RepositoryState(
        branch=parsed.execution_branch, commit=parsed.execution_commit, dirty=False
    )


def _manifest_identity(runner, parsed):
    return runner.ManifestIdentity(
        sha256=parsed.benchmark_manifest_sha256, status="final", file_count=9
    )


def _write_canonical(path: Path, payload: dict) -> Path:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    path.write_bytes(text.encode("utf-8") + b"\n")
    return path


@pytest.fixture()
def authorization_file(tmp_path, authorization_payload):
    return _write_canonical(tmp_path / "authorization.json", authorization_payload)


# ---------------------------------------------------------------------------
# Split safety: holdout is never an ordinary split
# ---------------------------------------------------------------------------


def test_supported_splits_exactly_development_and_validation(runner):
    assert runner.SUPPORTED_SPLITS == ("development", "validation")


def test_holdout_never_in_supported_splits(runner):
    assert runner.HOLDOUT_SPLIT not in runner.SUPPORTED_SPLITS


def test_ordinary_loader_rejects_holdout(runner, tmp_path):
    with pytest.raises(runner.IntegrityError, match="development or validation"):
        runner.load_split_benchmark(tmp_path, "holdout")


def test_load_split_benchmark_has_no_authorized_parameter(runner):
    import inspect

    parameters = inspect.signature(runner.load_split_benchmark).parameters
    assert "authorized" not in parameters
    assert set(parameters) == {"benchmark_root", "requested_split"}


def test_holdout_run_request_has_no_split(runner):
    request = runner.HoldoutRunRequest(
        authorization_path=Path("a.json"), output_root=Path("/tmp/x"),
        analysis_contract_sha256="a" * 64, mapping_sha256="b" * 64,
    )
    assert not hasattr(runner.RunRequest, "authorization_path")
    with pytest.raises(AttributeError):
        _ = request.split


# ---------------------------------------------------------------------------
# Canonical authorization parsing
# ---------------------------------------------------------------------------


def test_valid_canonical_authorization_parses(runner, authorization_file, authorization_payload):
    parsed = runner.parse_holdout_authorization(authorization_file)
    assert parsed.authorization_id == authorization_payload["authorization_id"]
    assert parsed.attempt == 1
    assert parsed.supersedes_authorization_sha256 is None
    assert parsed.holdout_authorized is True
    assert len(parsed.authorization_sha256) == 64
    assert parsed.config_ids == tuple(runner.CONFIG_REGISTRY)


def test_authorization_sha256_covers_trailing_newline(runner, authorization_file):
    import hashlib

    parsed = runner.parse_holdout_authorization(authorization_file)
    raw = authorization_file.read_bytes()
    assert raw.endswith(b"\n")
    assert parsed.authorization_sha256 == hashlib.sha256(raw).hexdigest()


def test_missing_authorization_file_rejected(runner, tmp_path):
    with pytest.raises(runner.HoldoutAuthorizationError, match="could not be read"):
        runner.parse_holdout_authorization(tmp_path / "absent.json")


def test_malformed_json_rejected(runner, tmp_path):
    path = tmp_path / "bad.json"
    path.write_bytes(b'{"schema_version": 1\n')
    with pytest.raises(runner.HoldoutAuthorizationError, match="not valid JSON"):
        runner.parse_holdout_authorization(path)


def test_bom_rejected(runner, tmp_path, authorization_payload):
    text = json.dumps(authorization_payload, sort_keys=True, separators=(",", ":"))
    path = tmp_path / "bom.json"
    path.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8") + b"\n")
    with pytest.raises(runner.HoldoutAuthorizationError, match="BOM"):
        runner.parse_holdout_authorization(path)


def test_crlf_rejected(runner, tmp_path, authorization_payload):
    text = json.dumps(authorization_payload, sort_keys=True, separators=(",", ":"))
    path = tmp_path / "crlf.json"
    path.write_bytes(text.encode("utf-8") + b"\r\n")
    with pytest.raises(runner.HoldoutAuthorizationError, match="CR"):
        runner.parse_holdout_authorization(path)


def test_missing_final_newline_rejected(runner, tmp_path, authorization_payload):
    text = json.dumps(authorization_payload, sort_keys=True, separators=(",", ":"))
    path = tmp_path / "nolf.json"
    path.write_bytes(text.encode("utf-8"))
    with pytest.raises(runner.HoldoutAuthorizationError, match="exactly one LF"):
        runner.parse_holdout_authorization(path)


def test_duplicate_trailing_newline_rejected(runner, tmp_path, authorization_payload):
    text = json.dumps(authorization_payload, sort_keys=True, separators=(",", ":"))
    path = tmp_path / "twolf.json"
    path.write_bytes(text.encode("utf-8") + b"\n\n")
    with pytest.raises(runner.HoldoutAuthorizationError, match="exactly one LF"):
        runner.parse_holdout_authorization(path)


def test_extra_whitespace_rejected(runner, tmp_path, authorization_payload):
    text = json.dumps(authorization_payload, sort_keys=True, indent=2)
    path = tmp_path / "indented.json"
    path.write_bytes(text.encode("utf-8") + b"\n")
    with pytest.raises(runner.HoldoutAuthorizationError, match="canonical"):
        runner.parse_holdout_authorization(path)


def test_unsorted_keys_rejected(runner, tmp_path, authorization_payload):
    text = json.dumps(authorization_payload, sort_keys=False, separators=(",", ":"))
    path = tmp_path / "unsorted.json"
    path.write_bytes(text.encode("utf-8") + b"\n")
    if text == json.dumps(authorization_payload, sort_keys=True, separators=(",", ":")):
        pytest.skip("payload happened to already be in sorted order")
    with pytest.raises(runner.HoldoutAuthorizationError, match="canonical"):
        runner.parse_holdout_authorization(path)


def test_non_object_authorization_rejected(runner, tmp_path):
    path = tmp_path / "list.json"
    path.write_bytes(b"[]\n")
    with pytest.raises(runner.HoldoutAuthorizationError, match="JSON object"):
        runner.parse_holdout_authorization(path)


@pytest.mark.parametrize("missing_key", sorted({"authorization_id", "attempt", "holdout_authorized"}))
def test_missing_key_rejected(runner, tmp_path, authorization_payload, missing_key):
    del authorization_payload[missing_key]
    path = _write_canonical(tmp_path / "missing.json", authorization_payload)
    with pytest.raises(runner.HoldoutAuthorizationError, match="missing keys"):
        runner.parse_holdout_authorization(path)


def test_extra_key_rejected(runner, tmp_path, authorization_payload):
    authorization_payload["unexpected_field"] = "x"
    path = _write_canonical(tmp_path / "extra.json", authorization_payload)
    with pytest.raises(runner.HoldoutAuthorizationError, match="unexpected keys"):
        runner.parse_holdout_authorization(path)


@pytest.mark.parametrize("bad_schema", [0, 2, "1", True])
def test_wrong_schema_version_rejected(runner, tmp_path, authorization_payload, bad_schema):
    authorization_payload["schema_version"] = bad_schema
    path = _write_canonical(tmp_path / "schema.json", authorization_payload)
    with pytest.raises(runner.HoldoutAuthorizationError):
        runner.parse_holdout_authorization(path)


@pytest.mark.parametrize(
    "bad_uuid",
    ["not-a-uuid", "0F9A1C2D-3E4B-4A5C-8D6E-7F8091A2B3C4", "0f9a1c2d3e4b4a5c8d6e7f8091a2b3c4", ""],
)
def test_invalid_authorization_id_rejected(runner, tmp_path, authorization_payload, bad_uuid):
    authorization_payload["authorization_id"] = bad_uuid
    path = _write_canonical(tmp_path / "uuid.json", authorization_payload)
    with pytest.raises(runner.HoldoutAuthorizationError, match="authorization_id"):
        runner.parse_holdout_authorization(path)


@pytest.mark.parametrize(
    "bad_time",
    ["2026-07-19T10:00:00", "2026-07-19 10:00:00Z", "not-a-time", "2026-07-19T10:00:00+07:00"],
)
def test_invalid_utc_timestamp_rejected(runner, tmp_path, authorization_payload, bad_time):
    authorization_payload["issued_at_utc"] = bad_time
    path = _write_canonical(tmp_path / "time.json", authorization_payload)
    with pytest.raises(runner.HoldoutAuthorizationError, match="issued_at_utc"):
        runner.parse_holdout_authorization(path)


def test_wrong_issued_by_rejected(runner, tmp_path, authorization_payload):
    authorization_payload["issued_by"] = "maintainer:someone-else"
    path = _write_canonical(tmp_path / "issuer.json", authorization_payload)
    with pytest.raises(runner.HoldoutAuthorizationError, match="issued_by"):
        runner.parse_holdout_authorization(path)


def test_wrong_purpose_rejected(runner, tmp_path, authorization_payload):
    authorization_payload["purpose"] = "some_other_purpose"
    path = _write_canonical(tmp_path / "purpose.json", authorization_payload)
    with pytest.raises(runner.HoldoutAuthorizationError, match="purpose"):
        runner.parse_holdout_authorization(path)


@pytest.mark.parametrize("bad_commit", ["A" * 40, "0" * 39, "0" * 41, "z" * 40, ""])
def test_invalid_execution_commit_rejected(runner, tmp_path, authorization_payload, bad_commit):
    authorization_payload["execution_commit"] = bad_commit
    path = _write_canonical(tmp_path / "commit.json", authorization_payload)
    with pytest.raises(runner.HoldoutAuthorizationError, match="execution_commit"):
        runner.parse_holdout_authorization(path)


@pytest.mark.parametrize("bad_provider", ["openai", "scripted_double", "", "MOCK"])
def test_non_mock_provider_rejected(runner, tmp_path, authorization_payload, bad_provider):
    authorization_payload["provider_id"] = bad_provider
    path = _write_canonical(tmp_path / "provider.json", authorization_payload)
    with pytest.raises(runner.HoldoutAuthorizationError, match="provider_id"):
        runner.parse_holdout_authorization(path)


def test_missing_config_rejected(runner, tmp_path, authorization_payload):
    authorization_payload["config_ids"] = list(runner.CONFIG_REGISTRY)[:-1]
    path = _write_canonical(tmp_path / "cfg.json", authorization_payload)
    with pytest.raises(runner.HoldoutAuthorizationError, match="config_ids"):
        runner.parse_holdout_authorization(path)


def test_duplicate_config_rejected(runner, tmp_path, authorization_payload):
    ids = list(runner.CONFIG_REGISTRY)
    authorization_payload["config_ids"] = ids[:-1] + [ids[0]]
    path = _write_canonical(tmp_path / "dup.json", authorization_payload)
    with pytest.raises(runner.HoldoutAuthorizationError, match="config_ids"):
        runner.parse_holdout_authorization(path)


def test_unknown_config_rejected(runner, tmp_path, authorization_payload):
    authorization_payload["config_ids"] = list(runner.CONFIG_REGISTRY)[:-1] + ["C8_unknown"]
    path = _write_canonical(tmp_path / "unknown.json", authorization_payload)
    with pytest.raises(runner.HoldoutAuthorizationError, match="config_ids"):
        runner.parse_holdout_authorization(path)


def test_reordered_config_rejected(runner, tmp_path, authorization_payload):
    authorization_payload["config_ids"] = list(reversed(list(runner.CONFIG_REGISTRY)))
    path = _write_canonical(tmp_path / "order.json", authorization_payload)
    with pytest.raises(runner.HoldoutAuthorizationError, match="in order"):
        runner.parse_holdout_authorization(path)


def test_wrong_config_hash_rejected(runner, tmp_path, authorization_payload):
    first = list(runner.CONFIG_REGISTRY)[0]
    authorization_payload["config_hashes"][first] = "d" * 64
    path = _write_canonical(tmp_path / "hash.json", authorization_payload)
    with pytest.raises(runner.HoldoutAuthorizationError, match="config_hash mismatch"):
        runner.parse_holdout_authorization(path)


def test_config_hashes_wrong_key_set_rejected(runner, tmp_path, authorization_payload):
    authorization_payload["config_hashes"].pop(list(runner.CONFIG_REGISTRY)[0])
    path = _write_canonical(tmp_path / "hashkeys.json", authorization_payload)
    with pytest.raises(runner.HoldoutAuthorizationError, match="eight approved configs"):
        runner.parse_holdout_authorization(path)


@pytest.mark.parametrize("bad_attempt", [0, -1, True, 1.0, "1", None])
def test_invalid_attempt_type_rejected(runner, tmp_path, authorization_payload, bad_attempt):
    authorization_payload["attempt"] = bad_attempt
    path = _write_canonical(tmp_path / "attempt.json", authorization_payload)
    with pytest.raises(runner.HoldoutAuthorizationError, match="attempt"):
        runner.parse_holdout_authorization(path)


def test_attempt_one_with_supersedes_rejected(runner, tmp_path, authorization_payload):
    authorization_payload["supersedes_authorization_sha256"] = "e" * 64
    path = _write_canonical(tmp_path / "sup1.json", authorization_payload)
    with pytest.raises(runner.HoldoutAuthorizationError, match="must not supersede"):
        runner.parse_holdout_authorization(path)


def test_retry_without_supersedes_rejected(runner, tmp_path, authorization_payload):
    authorization_payload["attempt"] = 2
    authorization_payload["supersedes_authorization_sha256"] = None
    path = _write_canonical(tmp_path / "sup2.json", authorization_payload)
    with pytest.raises(runner.HoldoutAuthorizationError, match="superseded authorization"):
        runner.parse_holdout_authorization(path)


def test_retry_with_valid_supersedes_lineage_parses(runner, tmp_path, authorization_payload):
    authorization_payload["attempt"] = 3
    authorization_payload["supersedes_authorization_sha256"] = "f" * 64
    path = _write_canonical(tmp_path / "sup3.json", authorization_payload)
    parsed = runner.parse_holdout_authorization(path)
    assert parsed.attempt == 3
    assert parsed.supersedes_authorization_sha256 == "f" * 64


@pytest.mark.parametrize("bad_flag", [False, "true", 1, None])
def test_holdout_authorized_must_be_boolean_true(runner, tmp_path, authorization_payload, bad_flag):
    authorization_payload["holdout_authorized"] = bad_flag
    path = _write_canonical(tmp_path / "flag.json", authorization_payload)
    with pytest.raises(runner.HoldoutAuthorizationError, match="holdout_authorized"):
        runner.parse_holdout_authorization(path)


def test_wrong_holdout_result_schema_version_rejected(runner, tmp_path, authorization_payload):
    authorization_payload["result_schema_version"] = 2
    path = _write_canonical(tmp_path / "rsv.json", authorization_payload)
    with pytest.raises(runner.HoldoutAuthorizationError, match="result_schema_version"):
        runner.parse_holdout_authorization(path)


# ---------------------------------------------------------------------------
# Capability: the authorized loader cannot be unlocked by anything else
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("impostor", [True, 1, "verified", object(), None, {}])
def test_authorized_loader_rejects_non_capability(runner, impostor):
    with pytest.raises(runner.IntegrityError, match="verified capability"):
        runner.load_authorized_holdout_benchmark(impostor)


def test_authorized_loader_rejects_bare_parsed_authorization(runner, authorization_file):
    parsed = runner.parse_holdout_authorization(authorization_file)
    with pytest.raises(runner.IntegrityError, match="verified capability"):
        runner.load_authorized_holdout_benchmark(parsed)


def test_authorized_loader_rejects_direct_construction(runner, authorization_file, tmp_path):
    """Codex finding: direct construction must not unlock the loader."""
    parsed = runner.parse_holdout_authorization(authorization_file)
    forged = runner.VerifiedHoldoutAuthorization(
        authorization=parsed,
        repository=_repo_state(runner, parsed),
        manifest=_manifest_identity(runner, parsed),
        benchmark_root=tmp_path / "bench",
        attempt_root=tmp_path / "forged",
    )
    assert forged.is_valid() is False
    with pytest.raises(runner.IntegrityError, match="failed verification"):
        runner.load_authorized_holdout_benchmark(forged)


def test_no_module_attribute_can_mint_a_capability(runner):
    """Executable probe: no reachable module attribute mints/registers/signs.

    Codex finding: `_register_holdout_capability` used to be a module attribute,
    so an ordinary importer could pass a builder callback and receive a
    registered capability. This checks the actual module surface, not source
    text.
    """
    suspicious = [
        name
        for name in dir(runner)
        if any(k in name.lower() for k in ("register", "mint", "token", "salt", "sign", "issue"))
        and callable(getattr(runner, name, None))
        and not isinstance(getattr(runner, name), type)
    ]
    assert suspicious == [], f"module exposes possible minting surface: {suspicious}"
    for removed in (
        "_register_holdout_capability",
        "_build_holdout_capability_registry",
        "_holdout_capability_fingerprint",
        "_hmac_verification_token",
        "_HOLDOUT_CAPABILITY_SALT",
    ):
        assert not hasattr(runner, removed), f"{removed} must not be reachable"


def test_ordinary_importer_cannot_mint_via_any_public_callable(runner, authorization_file, tmp_path):
    """Try every module-level callable with a capability-shaped argument and
    prove none of them returns a valid capability."""
    parsed = runner.parse_holdout_authorization(authorization_file)
    candidate = runner.VerifiedHoldoutAuthorization(
        authorization=parsed,
        repository=_repo_state(runner, parsed),
        manifest=_manifest_identity(runner, parsed),
        benchmark_root=tmp_path / "bench",
        attempt_root=tmp_path / "attempt",
    )
    minted = []
    for name in dir(runner):
        if name.startswith("__"):
            continue
        attribute = getattr(runner, name, None)
        if not callable(attribute) or isinstance(attribute, type):
            continue
        for argument in (candidate, lambda _s: candidate, parsed):
            try:
                produced = attribute(argument)
            except Exception:
                continue
            if isinstance(produced, runner.VerifiedHoldoutAuthorization) and produced.is_valid():
                minted.append(name)
    assert minted == [], f"these callables minted a valid capability: {minted}"


def test_capability_registered_by_verifier_is_valid(runner, tmp_path, authorization_payload, monkeypatch):
    attempt_root = tmp_path / "ok-attempt"
    authorization_payload["output_root"] = str(attempt_root)
    parsed = runner.parse_holdout_authorization(
        _write_canonical(tmp_path / "auth.json", authorization_payload)
    )
    monkeypatch.setattr(
        runner, "verify_frozen_manifest", lambda *a, **k: _manifest_identity(runner, parsed)
    )
    hooks = runner.RunnerHooks(repository_state_loader=lambda root: _repo_state(runner, parsed))
    capability = runner.verify_holdout_authorization(
        parsed,
        repo_root=ROOT,
        benchmark_root=tmp_path / "bench-absent",
        hooks=hooks,
        analysis_contract_sha256=parsed.analysis_contract_sha256,
        mapping_sha256=parsed.mapping_sha256,
        case_timeout_seconds=30.0,
    )
    assert capability.is_valid() is True
    assert (attempt_root / "start-receipt.json").is_file()


@pytest.mark.parametrize(
    "field,value",
    [
        ("attempt_root", Path("/tmp/somewhere-else")),
        ("benchmark_root", Path("/tmp/other-bench")),
    ],
)
def test_dataclasses_replace_of_bound_field_invalidates_capability(
    runner, tmp_path, authorization_payload, monkeypatch, field, value
):
    """Codex finding: replace() used to preserve validity. It must not."""
    import dataclasses

    attempt_root = tmp_path / f"replace-{field}"
    authorization_payload["output_root"] = str(attempt_root)
    parsed = runner.parse_holdout_authorization(
        _write_canonical(tmp_path / f"auth-{field}.json", authorization_payload)
    )
    monkeypatch.setattr(
        runner, "verify_frozen_manifest", lambda *a, **k: _manifest_identity(runner, parsed)
    )
    hooks = runner.RunnerHooks(repository_state_loader=lambda root: _repo_state(runner, parsed))
    capability = runner.verify_holdout_authorization(
        parsed, repo_root=ROOT, benchmark_root=tmp_path / "bench-absent", hooks=hooks,
        analysis_contract_sha256=parsed.analysis_contract_sha256,
        mapping_sha256=parsed.mapping_sha256, case_timeout_seconds=30.0,
    )
    assert capability.is_valid() is True

    mutated = dataclasses.replace(capability, **{field: value})
    assert mutated.is_valid() is False
    with pytest.raises(runner.IntegrityError, match="failed verification"):
        runner.load_authorized_holdout_benchmark(mutated)


def test_replacing_repository_or_manifest_invalidates_capability(
    runner, tmp_path, authorization_payload, monkeypatch
):
    import dataclasses

    attempt_root = tmp_path / "replace-identity"
    authorization_payload["output_root"] = str(attempt_root)
    parsed = runner.parse_holdout_authorization(
        _write_canonical(tmp_path / "auth-id.json", authorization_payload)
    )
    monkeypatch.setattr(
        runner, "verify_frozen_manifest", lambda *a, **k: _manifest_identity(runner, parsed)
    )
    hooks = runner.RunnerHooks(repository_state_loader=lambda root: _repo_state(runner, parsed))
    capability = runner.verify_holdout_authorization(
        parsed, repo_root=ROOT, benchmark_root=tmp_path / "bench-absent", hooks=hooks,
        analysis_contract_sha256=parsed.analysis_contract_sha256,
        mapping_sha256=parsed.mapping_sha256, case_timeout_seconds=30.0,
    )
    evil_repo = runner.RepositoryState(branch="evil", commit="1" * 40, dirty=False)
    evil_manifest = runner.ManifestIdentity(sha256="9" * 64, status="final", file_count=9)
    assert dataclasses.replace(capability, repository=evil_repo).is_valid() is False
    assert dataclasses.replace(capability, manifest=evil_manifest).is_valid() is False


def test_copied_capability_object_fails(runner, tmp_path, authorization_payload, monkeypatch):
    """A copy carries the same sentinel but is still re-fingerprinted; an
    identical copy stays valid, a copy with any changed field does not."""
    import copy as copy_module
    import dataclasses

    attempt_root = tmp_path / "copy-attempt"
    authorization_payload["output_root"] = str(attempt_root)
    parsed = runner.parse_holdout_authorization(
        _write_canonical(tmp_path / "auth-copy.json", authorization_payload)
    )
    monkeypatch.setattr(
        runner, "verify_frozen_manifest", lambda *a, **k: _manifest_identity(runner, parsed)
    )
    hooks = runner.RunnerHooks(repository_state_loader=lambda root: _repo_state(runner, parsed))
    capability = runner.verify_holdout_authorization(
        parsed, repo_root=ROOT, benchmark_root=tmp_path / "bench-absent", hooks=hooks,
        analysis_contract_sha256=parsed.analysis_contract_sha256,
        mapping_sha256=parsed.mapping_sha256, case_timeout_seconds=30.0,
    )
    deep = copy_module.deepcopy(capability)
    # deepcopy clones the sentinel, so provenance identity is lost
    assert deep.is_valid() is False
    assert dataclasses.replace(capability, attempt_root=tmp_path / "x").is_valid() is False



# ---------------------------------------------------------------------------
# Attempt root contract
# ---------------------------------------------------------------------------


def _authorization_with_root(runner, tmp_path, payload, root: Path):
    payload = dict(payload)
    payload["output_root"] = str(root)
    return runner.parse_holdout_authorization(
        _write_canonical(tmp_path / f"auth-{abs(hash(str(root))) % 10**8}.json", payload)
    )


def test_relative_output_root_rejected(runner, tmp_path, authorization_payload):
    authorization_payload["output_root"] = "relative/attempt"
    parsed = runner.parse_holdout_authorization(
        _write_canonical(tmp_path / "rel.json", authorization_payload)
    )
    with pytest.raises(runner.IntegrityError, match="absolute path"):
        runner.validate_holdout_attempt_root(
            parsed, repo_root=ROOT, benchmark_root=ROOT / "datasets" / "v2"
        )


def test_repository_local_attempt_root_rejected(runner, tmp_path, authorization_payload):
    parsed = _authorization_with_root(runner, tmp_path, authorization_payload, ROOT / "p12e4-inside")
    with pytest.raises(runner.IntegrityError, match="outside the repository"):
        runner.validate_holdout_attempt_root(
            parsed, repo_root=ROOT, benchmark_root=ROOT / "datasets" / "v2"
        )


def test_existing_attempt_root_rejected(runner, tmp_path, authorization_payload):
    existing = tmp_path / "already"
    existing.mkdir()
    parsed = _authorization_with_root(runner, tmp_path, authorization_payload, existing)
    with pytest.raises(runner.IntegrityError, match="already exists"):
        runner.validate_holdout_attempt_root(
            parsed, repo_root=ROOT, benchmark_root=ROOT / "datasets" / "v2"
        )


def test_attempt_root_that_is_a_file_rejected(runner, tmp_path, authorization_payload):
    target = tmp_path / "afile"
    target.write_text("x", encoding="utf-8")
    parsed = _authorization_with_root(runner, tmp_path, authorization_payload, target)
    with pytest.raises(runner.IntegrityError, match="already exists"):
        runner.validate_holdout_attempt_root(
            parsed, repo_root=ROOT, benchmark_root=ROOT / "datasets" / "v2"
        )


def test_missing_parent_rejected(runner, tmp_path, authorization_payload):
    parsed = _authorization_with_root(
        runner, tmp_path, authorization_payload, tmp_path / "absent" / "attempt"
    )
    with pytest.raises(runner.IntegrityError, match="parent directory must already exist"):
        runner.validate_holdout_attempt_root(
            parsed, repo_root=ROOT, benchmark_root=ROOT / "datasets" / "v2"
        )


def test_cli_output_root_mismatch_rejected(runner, tmp_path, authorization_payload):
    parsed = _authorization_with_root(runner, tmp_path, authorization_payload, tmp_path / "attempt")
    with pytest.raises(runner.IntegrityError, match="does not match the authorized attempt root"):
        runner.validate_holdout_attempt_root(
            parsed,
            repo_root=ROOT,
            benchmark_root=ROOT / "datasets" / "v2",
            cli_output_root=tmp_path / "different",
        )


def test_matching_cli_output_root_accepted(runner, tmp_path, authorization_payload):
    target = tmp_path / "attempt"
    parsed = _authorization_with_root(runner, tmp_path, authorization_payload, target)
    resolved = runner.validate_holdout_attempt_root(
        parsed,
        repo_root=ROOT,
        benchmark_root=ROOT / "datasets" / "v2",
        cli_output_root=target,
    )
    assert resolved == target.resolve()
    assert not resolved.exists()


def test_symlink_parent_escape_into_repository_rejected(runner, tmp_path, authorization_payload):
    link = tmp_path / "link-to-repo"
    try:
        link.symlink_to(ROOT, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is not permitted in this environment")
    parsed = _authorization_with_root(runner, tmp_path, authorization_payload, link / "attempt")
    with pytest.raises(runner.IntegrityError, match="repository"):
        runner.validate_holdout_attempt_root(
            parsed, repo_root=ROOT, benchmark_root=ROOT / "datasets" / "v2"
        )


def test_atomic_claim_succeeds_once_and_second_claim_fails(runner, tmp_path):
    target = tmp_path / "attempt"
    assert runner.claim_holdout_attempt_root(target) == target
    assert target.is_dir()
    with pytest.raises(runner.IntegrityError, match="claimed concurrently"):
        runner.claim_holdout_attempt_root(target)


# ---------------------------------------------------------------------------
# Start receipt
# ---------------------------------------------------------------------------


def test_start_receipt_has_exact_approved_key_set(runner, authorization_file):
    parsed = runner.parse_holdout_authorization(authorization_file)
    receipt = runner.build_start_receipt(
        parsed, repository=_repo_state(runner, parsed), manifest=_manifest_identity(runner, parsed),
        started_at_utc="2026-07-19T10:05:00Z",
    )
    assert set(receipt) == runner.HOLDOUT_START_RECEIPT_KEYS
    assert receipt["status"] == "claimed"
    assert receipt["schema_version"] == runner.HOLDOUT_START_RECEIPT_SCHEMA


def test_start_receipt_contains_no_forbidden_identifier_or_path(runner, authorization_file):
    parsed = runner.parse_holdout_authorization(authorization_file)
    receipt = runner.build_start_receipt(
        parsed, repository=_repo_state(runner, parsed), manifest=_manifest_identity(runner, parsed),
        started_at_utc="2026-07-19T10:05:00Z",
    )
    serialized = json.dumps(receipt)
    for forbidden in ("output_root", "authorization_path", "query", "answer", "retrieved"):
        assert forbidden not in serialized
    assert parsed.output_root not in serialized
    assert str(ROOT) not in serialized
    runner.scan_forbidden_artifact_content(receipt)


def test_start_receipt_written_durably_and_refuses_overwrite(runner, tmp_path, authorization_file):
    parsed = runner.parse_holdout_authorization(authorization_file)
    receipt = runner.build_start_receipt(
        parsed, repository=_repo_state(runner, parsed), manifest=_manifest_identity(runner, parsed),
        started_at_utc="2026-07-19T10:05:00Z",
    )
    attempt_root = runner.claim_holdout_attempt_root(tmp_path / "attempt")
    written = runner.write_start_receipt(attempt_root, receipt)
    assert written.is_file()
    assert json.loads(written.read_text(encoding="utf-8")) == receipt
    with pytest.raises(FileExistsError):
        runner.write_start_receipt(attempt_root, receipt)


# ---------------------------------------------------------------------------
# CLI contract
# ---------------------------------------------------------------------------


def test_cli_rejects_split_holdout(runner):
    with pytest.raises(SystemExit):
        runner.build_parser().parse_args(
            ["--split", "holdout", "--all-configs", "--output-root", "/tmp/x",
             "--expected-branch", "b", "--expected-commit", "0" * 40]
        )


def test_cli_has_no_force_or_overwrite_flag(runner):
    actions = {option for action in runner.build_parser()._actions for option in action.option_strings}
    for forbidden in ("--force", "--overwrite", "--allow-overwrite", "--yes"):
        assert forbidden not in actions


def test_cli_holdout_mode_rejects_split(runner, tmp_path):
    args = runner.build_parser().parse_args(
        ["--holdout-authorization", str(tmp_path / "a.json"),
         "--split", "development", "--all-configs", "--output-root", str(tmp_path / "out")]
    )
    with pytest.raises(runner.IntegrityError, match="must not be combined"):
        runner._holdout_request_from_args(args)  # noqa: SLF001


def test_cli_holdout_mode_requires_all_configs(runner, tmp_path):
    args = runner.build_parser().parse_args(
        ["--holdout-authorization", str(tmp_path / "a.json"),
         "--config", "C0_all_on", "--output-root", str(tmp_path / "out")]
    )
    with pytest.raises(runner.IntegrityError, match="--all-configs"):
        runner._holdout_request_from_args(args)  # noqa: SLF001


def test_cli_holdout_mode_rejects_partial_config_selection(runner, tmp_path):
    args = runner.build_parser().parse_args(
        ["--holdout-authorization", str(tmp_path / "a.json"),
         "--output-root", str(tmp_path / "out")]
    )
    with pytest.raises(runner.IntegrityError, match="--all-configs"):
        runner._holdout_request_from_args(args)  # noqa: SLF001


def test_cli_holdout_mode_rejects_explicit_identity_flags(runner, tmp_path):
    args = runner.build_parser().parse_args(
        ["--holdout-authorization", str(tmp_path / "a.json"), "--all-configs",
         "--output-root", str(tmp_path / "out"), "--expected-commit", "0" * 40]
    )
    with pytest.raises(runner.IntegrityError, match="comes from the authorization"):
        runner._holdout_request_from_args(args)  # noqa: SLF001


def test_cli_holdout_mode_builds_request_without_split(runner, tmp_path):
    args = runner.build_parser().parse_args(
        ["--holdout-authorization", str(tmp_path / "a.json"), "--all-configs",
         "--output-root", str(tmp_path / "out")]
    )
    request = runner._holdout_request_from_args(  # noqa: SLF001
        args, analysis_contract_sha256="a" * 64, mapping_sha256="b" * 64
    )
    assert isinstance(request, runner.HoldoutRunRequest)
    assert not isinstance(request, runner.RunRequest)


# ---------------------------------------------------------------------------
# Fail-closed ordering: nothing is read or written before verification
# ---------------------------------------------------------------------------


def test_invalid_authorization_fails_before_root_creation_and_record_read(
    runner, tmp_path, authorization_payload, monkeypatch
):
    """A bad authorization must fail before the attempt root exists and before
    the authorized loader is ever reached."""
    attempt_root = tmp_path / "attempt"
    authorization_payload["issued_by"] = "maintainer:not-approved"
    authorization_payload["output_root"] = str(attempt_root)
    path = _write_canonical(tmp_path / "bad.json", authorization_payload)

    loader_calls: list[object] = []
    monkeypatch.setattr(
        runner,
        "load_authorized_holdout_benchmark",
        lambda *a, **k: loader_calls.append(a) or pytest.fail("holdout was loaded"),
    )
    manifest_calls: list[object] = []
    monkeypatch.setattr(
        runner,
        "verify_frozen_manifest",
        lambda *a, **k: manifest_calls.append(a) or pytest.fail("manifest verified too early"),
    )

    request = runner.HoldoutRunRequest(
        authorization_path=path, output_root=attempt_root,
        analysis_contract_sha256="a" * 64, mapping_sha256="b" * 64,
    )
    with pytest.raises(runner.HoldoutAuthorizationError):
        runner.holdout_preflight(request, repo_root=ROOT)

    assert not attempt_root.exists()
    assert loader_calls == []
    assert manifest_calls == []


def test_branch_mismatch_fails_before_root_creation(
    runner, tmp_path, authorization_payload, monkeypatch
):
    attempt_root = tmp_path / "attempt"
    authorization_payload["output_root"] = str(attempt_root)
    authorization_payload["execution_branch"] = "some-other-branch"
    path = _write_canonical(tmp_path / "branch.json", authorization_payload)
    parsed = runner.parse_holdout_authorization(path)

    monkeypatch.setattr(
        runner,
        "load_authorized_holdout_benchmark",
        lambda *a, **k: pytest.fail("holdout was loaded"),
    )
    hooks = runner.RunnerHooks(
        repository_state_loader=lambda root: runner.RepositoryState(
            branch="actual-branch", commit="0" * 40, dirty=False
        )
    )
    with pytest.raises(runner.IntegrityError, match="branch"):
        runner.verify_holdout_authorization(
            parsed, repo_root=ROOT, hooks=hooks,
            analysis_contract_sha256=parsed.analysis_contract_sha256,
            mapping_sha256=parsed.mapping_sha256,
        )
    assert not attempt_root.exists()


def test_dirty_tree_fails_before_root_creation(runner, tmp_path, authorization_payload):
    attempt_root = tmp_path / "attempt"
    authorization_payload["output_root"] = str(attempt_root)
    parsed = runner.parse_holdout_authorization(_write_canonical(tmp_path / "d.json", authorization_payload))
    hooks = runner.RunnerHooks(
        repository_state_loader=lambda root: runner.RepositoryState(
            branch=parsed.execution_branch, commit=parsed.execution_commit, dirty=True
        )
    )
    with pytest.raises(runner.IntegrityError, match="clean"):
        runner.verify_holdout_authorization(
            parsed, repo_root=ROOT, hooks=hooks,
            analysis_contract_sha256=parsed.analysis_contract_sha256,
            mapping_sha256=parsed.mapping_sha256,
        )
    assert not attempt_root.exists()


# ---------------------------------------------------------------------------
# Phase 12E.3 policy regression
# ---------------------------------------------------------------------------


def test_development_validation_schema_versions_unchanged(runner):
    assert runner.RESULT_SCHEMA_VERSION == 2
    assert runner.RESULT_MANIFEST_SCHEMA_VERSION == 1


def test_holdout_schema_versions_are_separate(runner):
    assert runner.HOLDOUT_RESULT_SCHEMA_VERSION == 1
    assert runner.HOLDOUT_RESULT_MANIFEST_SCHEMA_VERSION == 1


def test_determinism_still_uses_exactly_two_repetitions(runner):
    source = (SCRIPTS_DIR / "run_v2_evaluation.py").read_text(encoding="utf-8")
    assert '"repetitions": 2' in source
    assert '"warmup": 0' in source


def test_holdout_scope_counts_sum_to_documented_split_size(runner):
    assert sum(runner.EXPECTED_HOLDOUT_SCOPE_COUNTS.values()) == runner.HOLDOUT_CASE_COUNT == 60


def test_no_reportable_latency_field_added_to_holdout_schema(runner):
    assert "p50" not in runner.HOLDOUT_START_RECEIPT_KEYS
    assert "p95" not in runner.HOLDOUT_START_RECEIPT_KEYS
    assert not any("latency" in key for key in runner.HOLDOUT_AUTHORIZATION_KEYS)


# ===========================================================================
# Analyzer holdout path
#
# Every fixture below is synthetic. No test opens a real holdout case or label
# file, and none executes holdout, validation or development evaluation.
# ===========================================================================


@pytest.fixture(scope="module")
def analyzer():
    return _load_module("v2_holdout_analyzer_mod", "analyze_v2_results.py")


def _clean_repo_hooks(analyzer, branch: str, commit: str, *, dirty: bool = False):
    module_runner = sys.modules["v2_holdout_runner_mod"]
    return analyzer.AnalyzerHooks(
        repository_state_loader=lambda root: module_runner.RepositoryState(
            branch=branch, commit=commit, dirty=dirty
        )
    )


@pytest.fixture()
def attempt_root(tmp_path, runner, authorization_payload):
    """A synthetic claimed attempt root with a valid start receipt."""
    root = tmp_path / "attempt-1"
    authorization_payload["output_root"] = str(root)
    auth_path = _write_canonical(tmp_path / "auth.json", authorization_payload)
    parsed = runner.parse_holdout_authorization(auth_path)
    runner.claim_holdout_attempt_root(root)
    receipt = runner.build_start_receipt(
        parsed, repository=_repo_state(runner, parsed), manifest=_manifest_identity(runner, parsed),
        started_at_utc="2026-07-19T10:05:00Z",
    )
    runner.write_start_receipt(root, receipt)
    return root, auth_path, parsed


# --- ordinary path stays closed -------------------------------------------


def test_ordinary_analyzer_still_rejects_split_holdout(analyzer):
    with pytest.raises(SystemExit):
        analyzer.build_parser().parse_args(
            ["--split", "holdout", "--result-manifest", "m.json"]
        )


def test_ordinary_analyzer_request_path_rejects_holdout(analyzer):
    request = analyzer.AnalysisRequest(
        split="holdout",
        expected_branch="b",
        expected_commit="0" * 40,
        output_root=Path("/tmp/x"),
        result_manifests=tuple(Path(f"m{i}.json") for i in range(8)),
    )
    with pytest.raises(analyzer.AnalysisError, match="holdout is prohibited"):
        analyzer._validate_request(request)  # noqa: SLF001


def test_holdout_analysis_request_has_no_split(analyzer):
    request = analyzer.HoldoutAnalysisRequest(
        authorization_path=Path("a.json"), result_manifests=()
    )
    with pytest.raises(AttributeError):
        _ = request.split


def test_analyzer_holdout_schema_constants_are_separate(analyzer):
    assert analyzer.ANALYSIS_SCHEMA_VERSION == 1
    assert analyzer.ANALYSIS_MANIFEST_SCHEMA_VERSION == 1
    assert analyzer.CSV_SCHEMA_VERSION == 1
    assert analyzer.HOLDOUT_ANALYSIS_SCHEMA_VERSION == 1
    assert analyzer.HOLDOUT_ANALYSIS_MANIFEST_SCHEMA_VERSION == 1


# --- analyzer CLI ----------------------------------------------------------


def test_analyzer_holdout_mode_rejects_split(analyzer, tmp_path):
    args = analyzer.build_parser().parse_args(
        ["--holdout-authorization", str(tmp_path / "a.json"), "--split", "validation",
         "--result-manifest", "m.json"]
    )
    with pytest.raises(analyzer.AnalysisError, match="must not be combined"):
        analyzer._holdout_analysis_request_from_args(args)  # noqa: SLF001


def test_analyzer_holdout_mode_rejects_output_root(analyzer, tmp_path):
    args = analyzer.build_parser().parse_args(
        ["--holdout-authorization", str(tmp_path / "a.json"),
         "--output-root", str(tmp_path / "out"), "--result-manifest", "m.json"]
    )
    with pytest.raises(analyzer.AnalysisError, match="--output-root is prohibited"):
        analyzer._holdout_analysis_request_from_args(args)  # noqa: SLF001


def test_analyzer_holdout_mode_rejects_explicit_identity(analyzer, tmp_path):
    args = analyzer.build_parser().parse_args(
        ["--holdout-authorization", str(tmp_path / "a.json"),
         "--expected-commit", "0" * 40, "--result-manifest", "m.json"]
    )
    with pytest.raises(analyzer.AnalysisError, match="comes from the authorization"):
        analyzer._holdout_analysis_request_from_args(args)  # noqa: SLF001


def test_analyzer_cli_has_no_force_flag(analyzer):
    actions = {opt for action in analyzer.build_parser()._actions for opt in action.option_strings}
    for forbidden in ("--force", "--overwrite", "--allow-overwrite"):
        assert forbidden not in actions


# --- authorization verification -------------------------------------------


def test_analyzer_requires_exactly_eight_manifests(analyzer, tmp_path, attempt_root):
    _, auth_path, _ = attempt_root
    request = analyzer.HoldoutAnalysisRequest(
        authorization_path=auth_path,
        result_manifests=(tmp_path / "one.json",),
    )
    with pytest.raises(analyzer.AnalysisError, match="exactly eight"):
        analyzer.analyze_holdout_results(request, repo_root=ROOT)


def test_analyzer_rejects_duplicate_manifest_arguments(analyzer, tmp_path, attempt_root):
    _, auth_path, _ = attempt_root
    same = tmp_path / "same.json"
    request = analyzer.HoldoutAnalysisRequest(
        authorization_path=auth_path, result_manifests=tuple([same] * 8)
    )
    with pytest.raises(analyzer.AnalysisError, match="duplicate result manifest"):
        analyzer.analyze_holdout_results(request, repo_root=ROOT)


def test_analyzer_rejects_missing_authorization_file(analyzer, tmp_path, runner):
    request = analyzer.HoldoutAnalysisRequest(
        authorization_path=tmp_path / "absent.json",
        result_manifests=tuple(tmp_path / f"m{i}.json" for i in range(8)),
    )
    with pytest.raises(analyzer.runner.HoldoutAuthorizationError, match="could not be read"):
        analyzer.analyze_holdout_results(request, repo_root=ROOT)


def test_analyzer_rejects_non_canonical_authorization(analyzer, tmp_path, runner, authorization_payload):
    path = tmp_path / "indented.json"
    path.write_bytes(json.dumps(authorization_payload, sort_keys=True, indent=2).encode("utf-8") + b"\n")
    request = analyzer.HoldoutAnalysisRequest(
        authorization_path=path,
        result_manifests=tuple(tmp_path / f"m{i}.json" for i in range(8)),
    )
    with pytest.raises(analyzer.runner.HoldoutAuthorizationError, match="canonical"):
        analyzer.analyze_holdout_results(request, repo_root=ROOT)


def test_analyzer_rejects_wrong_branch(analyzer, tmp_path, attempt_root):
    root, auth_path, parsed = attempt_root
    request = analyzer.HoldoutAnalysisRequest(
        authorization_path=auth_path,
        result_manifests=tuple(root / f"m{i}.json" for i in range(8)),
    )
    hooks = _clean_repo_hooks(analyzer, "other-branch", parsed.execution_commit)
    with pytest.raises(analyzer.AnalysisError, match="branch"):
        analyzer.analyze_holdout_results(request, repo_root=ROOT, hooks=hooks)


def test_analyzer_rejects_wrong_commit(analyzer, tmp_path, attempt_root):
    root, auth_path, parsed = attempt_root
    request = analyzer.HoldoutAnalysisRequest(
        authorization_path=auth_path,
        result_manifests=tuple(root / f"m{i}.json" for i in range(8)),
    )
    hooks = _clean_repo_hooks(analyzer, parsed.execution_branch, "1" * 40)
    with pytest.raises(analyzer.AnalysisError, match="commit"):
        analyzer.analyze_holdout_results(request, repo_root=ROOT, hooks=hooks)


def test_analyzer_rejects_dirty_tree(analyzer, tmp_path, attempt_root):
    root, auth_path, parsed = attempt_root
    request = analyzer.HoldoutAnalysisRequest(
        authorization_path=auth_path,
        result_manifests=tuple(root / f"m{i}.json" for i in range(8)),
    )
    hooks = _clean_repo_hooks(analyzer, parsed.execution_branch, parsed.execution_commit, dirty=True)
    with pytest.raises(analyzer.AnalysisError, match="clean"):
        analyzer.analyze_holdout_results(request, repo_root=ROOT, hooks=hooks)


def test_analyzer_rejects_missing_start_receipt(analyzer, tmp_path, runner, authorization_payload, monkeypatch):
    root = tmp_path / "no-receipt"
    authorization_payload["output_root"] = str(root)
    authorization_payload["analysis_contract_sha256"] = analyzer.ANALYSIS_CONTRACT_SHA256
    authorization_payload["mapping_sha256"] = analyzer.MAPPING_SHA256
    auth_path = _write_canonical(tmp_path / "auth.json", authorization_payload)
    parsed = runner.parse_holdout_authorization(auth_path)
    root.mkdir()
    request = analyzer.HoldoutAnalysisRequest(
        authorization_path=auth_path,
        result_manifests=tuple(root / f"m{i}.json" for i in range(8)),
    )
    monkeypatch.setattr(
        analyzer.runner, "verify_frozen_manifest",
        lambda *a, **k: analyzer.runner.ManifestIdentity(
            sha256=parsed.benchmark_manifest_sha256, status="final", file_count=9
        ),
    )
    hooks = _clean_repo_hooks(analyzer, parsed.execution_branch, parsed.execution_commit)
    with pytest.raises(analyzer.AnalysisError, match="start receipt"):
        analyzer.analyze_holdout_results(request, repo_root=ROOT, hooks=hooks)


def test_analyzer_rejects_receipt_from_a_different_authorization(
    analyzer, tmp_path, runner, authorization_payload, monkeypatch
):
    root = tmp_path / "mismatch"
    authorization_payload["output_root"] = str(root)
    authorization_payload["analysis_contract_sha256"] = analyzer.ANALYSIS_CONTRACT_SHA256
    authorization_payload["mapping_sha256"] = analyzer.MAPPING_SHA256
    auth_path = _write_canonical(tmp_path / "auth.json", authorization_payload)
    parsed = runner.parse_holdout_authorization(auth_path)
    runner.claim_holdout_attempt_root(root)

    other = dict(authorization_payload)
    other["authorization_id"] = "11111111-2222-4333-8444-555555555555"
    other_path = _write_canonical(tmp_path / "other.json", other)
    other_parsed = runner.parse_holdout_authorization(other_path)
    runner.write_start_receipt(
        root, runner.build_start_receipt(
            other_parsed, repository=_repo_state(runner, other_parsed),
            manifest=_manifest_identity(runner, other_parsed),
            started_at_utc="2026-07-19T10:05:00Z",
        )
    )

    request = analyzer.HoldoutAnalysisRequest(
        authorization_path=auth_path,
        result_manifests=tuple(root / f"m{i}.json" for i in range(8)),
    )
    monkeypatch.setattr(
        analyzer.runner, "verify_frozen_manifest",
        lambda *a, **k: analyzer.runner.ManifestIdentity(
            sha256=parsed.benchmark_manifest_sha256, status="final", file_count=9
        ),
    )
    hooks = _clean_repo_hooks(analyzer, parsed.execution_branch, parsed.execution_commit)
    with pytest.raises(analyzer.AnalysisError, match="start receipt authorization_id"):
        analyzer.analyze_holdout_results(request, repo_root=ROOT, hooks=hooks)


def test_analyzer_rejects_existing_analysis_directory(analyzer, tmp_path, attempt_root, monkeypatch, runner):
    root, auth_path, parsed = attempt_root
    (root / "analysis").mkdir()
    request = analyzer.HoldoutAnalysisRequest(
        authorization_path=auth_path,
        result_manifests=tuple(root / f"m{i}.json" for i in range(8)),
    )
    hooks = _clean_repo_hooks(analyzer, parsed.execution_branch, parsed.execution_commit)
    monkeypatch.setattr(
        runner, "verify_frozen_manifest",
        lambda *a, **k: runner.ManifestIdentity(
            sha256=parsed.benchmark_manifest_sha256, status="final", file_count=9
        ),
    )
    monkeypatch.setattr(analyzer, "MAPPING_SHA256", parsed.mapping_sha256)
    monkeypatch.setattr(analyzer, "ANALYSIS_CONTRACT_SHA256", parsed.analysis_contract_sha256)
    with pytest.raises(analyzer.AnalysisError):
        analyzer.analyze_holdout_results(request, repo_root=ROOT, hooks=hooks)


# --- fail-closed ordering: no holdout record read on an invalid request ----


def test_invalid_authorization_fails_before_holdout_loader(
    analyzer, tmp_path, runner, authorization_payload, monkeypatch
):
    authorization_payload["issued_by"] = "maintainer:not-approved"
    path = _write_canonical(tmp_path / "bad.json", authorization_payload)
    monkeypatch.setattr(
        runner,
        "load_authorized_holdout_benchmark",
        lambda *a, **k: pytest.fail("holdout records were loaded"),
    )
    request = analyzer.HoldoutAnalysisRequest(
        authorization_path=path,
        result_manifests=tuple(tmp_path / f"m{i}.json" for i in range(8)),
    )
    with pytest.raises(analyzer.runner.HoldoutAuthorizationError):
        analyzer.analyze_holdout_results(request, repo_root=ROOT)


def test_invalid_matrix_fails_before_holdout_loader(
    analyzer, tmp_path, attempt_root, runner, monkeypatch
):
    root, auth_path, parsed = attempt_root
    monkeypatch.setattr(
        runner,
        "load_authorized_holdout_benchmark",
        lambda *a, **k: pytest.fail("holdout records were loaded"),
    )
    request = analyzer.HoldoutAnalysisRequest(
        authorization_path=auth_path,
        result_manifests=tuple(root / f"absent-{i}.json" for i in range(8)),
    )
    hooks = _clean_repo_hooks(analyzer, parsed.execution_branch, parsed.execution_commit)
    with pytest.raises((analyzer.AnalysisError, analyzer.runner.RunnerError)):
        analyzer.analyze_holdout_results(request, repo_root=ROOT, hooks=hooks)


# --- matrix cross-validation (pure, no benchmark needed) ------------------


def _fake_input(analyzer, runner, registry_config_id, parsed, **overrides):
    manifest = {
        "config_id": registry_config_id,
        "config_hash": runner.CONFIG_REGISTRY[registry_config_id].config_hash,
        "run_status": "complete",
        "authorization_id": parsed.authorization_id,
        "holdout_authorization_sha256": parsed.authorization_sha256,
        "attempt": parsed.attempt,
        "supersedes_authorization_sha256": parsed.supersedes_authorization_sha256,
        "git_commit": parsed.execution_commit,
        "provider_id": "mock",
        "provider_behavior_hash": "9" * 64,
        "benchmark_manifest_sha256": parsed.benchmark_manifest_sha256,
        "experiment_id": "8" * 64,
        # C0 covers four scopes; C1-C7 share one ablated end_to_end case set.
        "expected_case_set_sha256": (
            "c" * 64 if registry_config_id == list(runner.CONFIG_REGISTRY)[0] else "a" * 64
        ),
    }
    manifest.update(overrides)
    return analyzer.VerifiedInput(
        manifest_path=Path(f"/tmp/{registry_config_id}/result-manifest.json"),
        manifest_sha256="2" * 64,
        manifest=manifest,
        result_sha256="1" * 64,
        result_size_bytes=2,
        result={"run_status": manifest["run_status"]},
    )


def _full_matrix(analyzer, runner, parsed):
    return [_fake_input(analyzer, runner, cid, parsed) for cid in runner.CONFIG_REGISTRY]


def test_matrix_accepts_complete_authorized_c0_c7(analyzer, runner, attempt_root):
    _, _, parsed = attempt_root
    ordered = analyzer._validate_holdout_matrix(  # noqa: SLF001
        _full_matrix(analyzer, runner, parsed), authorization=parsed
    )
    assert [item.manifest["config_id"] for item in ordered] == list(runner.CONFIG_REGISTRY)


def test_matrix_normalizes_reordered_input_to_canonical_order(analyzer, runner, attempt_root):
    _, _, parsed = attempt_root
    shuffled = list(reversed(_full_matrix(analyzer, runner, parsed)))
    ordered = analyzer._validate_holdout_matrix(shuffled, authorization=parsed)  # noqa: SLF001
    assert [item.manifest["config_id"] for item in ordered] == list(runner.CONFIG_REGISTRY)


def test_matrix_rejects_ninth_manifest(analyzer, runner, attempt_root):
    _, _, parsed = attempt_root
    matrix = _full_matrix(analyzer, runner, parsed)
    matrix.append(_fake_input(analyzer, runner, "C0_all_on", parsed))
    with pytest.raises(analyzer.AnalysisError, match="exactly eight"):
        analyzer._validate_holdout_matrix(matrix, authorization=parsed)  # noqa: SLF001


def test_matrix_rejects_duplicate_config(analyzer, runner, attempt_root):
    _, _, parsed = attempt_root
    matrix = _full_matrix(analyzer, runner, parsed)
    matrix[1] = _fake_input(analyzer, runner, "C0_all_on", parsed)
    with pytest.raises(analyzer.AnalysisError, match="duplicate configuration"):
        analyzer._validate_holdout_matrix(matrix, authorization=parsed)  # noqa: SLF001


def test_matrix_rejects_unknown_config(analyzer, runner, attempt_root):
    _, _, parsed = attempt_root
    matrix = _full_matrix(analyzer, runner, parsed)
    matrix[0] = _fake_input(analyzer, runner, "C0_all_on", parsed, config_id="C9_unknown")
    with pytest.raises(analyzer.AnalysisError, match="unknown configuration"):
        analyzer._validate_holdout_matrix(matrix, authorization=parsed)  # noqa: SLF001


def test_matrix_rejects_partial_run(analyzer, runner, attempt_root):
    _, _, parsed = attempt_root
    matrix = _full_matrix(analyzer, runner, parsed)
    matrix[3] = _fake_input(analyzer, runner, "C3_no_context", parsed, run_status="partial")
    with pytest.raises(analyzer.AnalysisError, match="partial matrices are rejected"):
        analyzer._validate_holdout_matrix(matrix, authorization=parsed)  # noqa: SLF001


def test_matrix_rejects_mixed_attempts(analyzer, runner, attempt_root):
    _, _, parsed = attempt_root
    matrix = _full_matrix(analyzer, runner, parsed)
    matrix[2] = _fake_input(analyzer, runner, "C2_no_provenance", parsed, attempt=2)
    with pytest.raises(analyzer.AnalysisError, match="mixes attempts"):
        analyzer._validate_holdout_matrix(matrix, authorization=parsed)  # noqa: SLF001


def test_matrix_rejects_mixed_authorization_id(analyzer, runner, attempt_root):
    _, _, parsed = attempt_root
    matrix = _full_matrix(analyzer, runner, parsed)
    matrix[4] = _fake_input(
        analyzer, runner, "C4_no_dlp", parsed,
        authorization_id="99999999-8888-4777-8666-555555555555",
    )
    with pytest.raises(analyzer.AnalysisError, match="mixes authorization identities"):
        analyzer._validate_holdout_matrix(matrix, authorization=parsed)  # noqa: SLF001


def test_matrix_rejects_mixed_authorization_hash(analyzer, runner, attempt_root):
    _, _, parsed = attempt_root
    matrix = _full_matrix(analyzer, runner, parsed)
    matrix[5] = _fake_input(
        analyzer, runner, "C5_no_output", parsed, holdout_authorization_sha256="e" * 64
    )
    with pytest.raises(analyzer.AnalysisError, match="mixes authorization hashes"):
        analyzer._validate_holdout_matrix(matrix, authorization=parsed)  # noqa: SLF001


def test_matrix_rejects_mixed_commit(analyzer, runner, attempt_root):
    _, _, parsed = attempt_root
    matrix = _full_matrix(analyzer, runner, parsed)
    matrix[6] = _fake_input(analyzer, runner, "C6_none", parsed, git_commit="1" * 40)
    with pytest.raises(analyzer.AnalysisError, match="mixes implementation commits"):
        analyzer._validate_holdout_matrix(matrix, authorization=parsed)  # noqa: SLF001


def test_matrix_rejects_non_mock_provider(analyzer, runner, attempt_root):
    _, _, parsed = attempt_root
    matrix = _full_matrix(analyzer, runner, parsed)
    matrix[0] = _fake_input(analyzer, runner, "C0_all_on", parsed, provider_id="openai")
    with pytest.raises(analyzer.AnalysisError, match="non-mock provider"):
        analyzer._validate_holdout_matrix(matrix, authorization=parsed)  # noqa: SLF001


def test_matrix_rejects_mixed_provider_behavior(analyzer, runner, attempt_root):
    _, _, parsed = attempt_root
    matrix = _full_matrix(analyzer, runner, parsed)
    matrix[1] = _fake_input(
        analyzer, runner, "C1_no_input", parsed, provider_behavior_hash="7" * 64
    )
    with pytest.raises(analyzer.AnalysisError, match="provider behavior identities"):
        analyzer._validate_holdout_matrix(matrix, authorization=parsed)  # noqa: SLF001


def test_matrix_rejects_wrong_benchmark_manifest(analyzer, runner, attempt_root):
    _, _, parsed = attempt_root
    matrix = _full_matrix(analyzer, runner, parsed)
    matrix[2] = _fake_input(
        analyzer, runner, "C2_no_provenance", parsed, benchmark_manifest_sha256="5" * 64
    )
    with pytest.raises(analyzer.AnalysisError, match="mixes benchmark identities"):
        analyzer._validate_holdout_matrix(matrix, authorization=parsed)  # noqa: SLF001


def test_matrix_rejects_wrong_config_hash(analyzer, runner, attempt_root):
    _, _, parsed = attempt_root
    matrix = _full_matrix(analyzer, runner, parsed)
    matrix[3] = _fake_input(analyzer, runner, "C3_no_context", parsed, config_hash="4" * 64)
    with pytest.raises(analyzer.AnalysisError, match="config hash"):
        analyzer._validate_holdout_matrix(matrix, authorization=parsed)  # noqa: SLF001


def test_matrix_rejects_mixed_experiment_identity(analyzer, runner, attempt_root):
    _, _, parsed = attempt_root
    matrix = _full_matrix(analyzer, runner, parsed)
    matrix[7] = _fake_input(
        analyzer, runner, "C7_no_context_no_output", parsed, experiment_id="3" * 64
    )
    with pytest.raises(analyzer.AnalysisError, match="experiment identities"):
        analyzer._validate_holdout_matrix(matrix, authorization=parsed)  # noqa: SLF001


# --- holdout identity field validation ------------------------------------


def test_holdout_identity_rejects_attempt_one_with_supersedes(analyzer):
    payload = {
        "authorization_id": "0f9a1c2d-3e4b-4a5c-8d6e-7f8091a2b3c4",
        "holdout_authorization_sha256": "a" * 64,
        "attempt": 1,
        "supersedes_authorization_sha256": "b" * 64,
        "holdout_authorized": True,
    }
    with pytest.raises(analyzer.AnalysisError, match="must not supersede"):
        analyzer._validate_holdout_identity_fields(payload, "manifest")  # noqa: SLF001


def test_holdout_identity_rejects_false_authorized_flag(analyzer):
    payload = {
        "authorization_id": "0f9a1c2d-3e4b-4a5c-8d6e-7f8091a2b3c4",
        "holdout_authorization_sha256": "a" * 64,
        "attempt": 1,
        "supersedes_authorization_sha256": None,
        "holdout_authorized": False,
    }
    with pytest.raises(analyzer.AnalysisError, match="boolean true"):
        analyzer._validate_holdout_identity_fields(payload, "manifest")  # noqa: SLF001


def test_holdout_identity_rejects_bool_attempt(analyzer):
    payload = {
        "authorization_id": "0f9a1c2d-3e4b-4a5c-8d6e-7f8091a2b3c4",
        "holdout_authorization_sha256": "a" * 64,
        "attempt": True,
        "supersedes_authorization_sha256": None,
        "holdout_authorized": True,
    }
    with pytest.raises(analyzer.AnalysisError, match="attempt must be an integer"):
        analyzer._validate_holdout_identity_fields(payload, "manifest")  # noqa: SLF001


# --- disclosure suppression ------------------------------------------------


def test_analysis_disclosure_guard_rejects_absolute_attempt_root(analyzer, attempt_root):
    root, _, parsed = attempt_root
    payload = {"note": str(root)}
    with pytest.raises(analyzer.AnalysisError, match="absolute attempt root"):
        analyzer._assert_no_authorization_disclosure(payload, parsed, root)  # noqa: SLF001


def test_analysis_disclosure_guard_accepts_safe_identity_only(analyzer, attempt_root):
    _, _, parsed = attempt_root
    payload = {
        "authorization_id": parsed.authorization_id,
        "holdout_authorization_sha256": parsed.authorization_sha256,
        "attempt": parsed.attempt,
        "holdout_authorized": True,
    }
    analyzer._assert_no_authorization_disclosure(  # noqa: SLF001
        payload, parsed, Path(parsed.output_root)
    )


# --- Phase 12E.3 metric policy regression ---------------------------------


def test_phase_12e3_metric_policy_constants_unchanged(analyzer):
    assert analyzer.RATE_REPORTING_MIN_N == 10
    assert analyzer.WILSON_CONFIDENCE_LEVEL == 0.95
    defaults = analyzer.ANALYSIS_CONTRACT
    assert defaults["abr_enabled"] is False
    assert defaults["macro_metrics_enabled"] is False
    assert defaults["latency_reportable"] is False
    assert defaults["wilson_continuity_correction"] is False
    assert defaults["rate_reporting_min_n"] == 10


def test_holdout_identity_keys_introduce_no_metric(analyzer):
    for key in analyzer.HOLDOUT_IDENTITY_KEYS:
        assert not any(token in key for token in ("aomr", "fpr", "abr", "macro", "f1", "latency", "p50", "p95"))


# ===========================================================================
# Synthetic end-to-end: analyze_holdout_results -> _build_analysis -> publish
#
# The frozen holdout case/label files are NEVER opened. The synthetic
# benchmark content is the DEVELOPMENT split (safe to read), returned by a
# monkeypatched `load_authorized_holdout_benchmark`, while the artifacts are
# labelled with the holdout split and holdout schemas. This exercises the real
# analysis builder and the real atomic publication path without any holdout
# record ever being read.
# ===========================================================================


def _synthetic_holdout_matrix(runner, analyzer, attempt_root, parsed, benchmark, manifest, repository):
    """Build eight complete C0-C7 holdout artifacts with real hashes/sizes."""
    import hashlib

    settings = runner.load_settings()
    provider = runner.default_provider_spec(runner.SUPPORTED_PROVIDER_ID, settings)
    safety_limits = runner._settings_safety_limits(settings, 30.0)  # noqa: SLF001
    dependencies = ["phase12e4-test-fixture==1"]
    dependencies_sha256 = runner._sha256_bytes(  # noqa: SLF001
        runner._canonical_json_bytes(dependencies)  # noqa: SLF001
    )
    experiment_id = runner._experiment_id(  # noqa: SLF001
        repository, manifest, provider, safety_limits, dependencies_sha256, runner.HOLDOUT_SPLIT
    )
    expected_by_config, scopes_by_config = runner._expected_case_sets(  # noqa: SLF001
        benchmark, tuple(runner.CONFIG_REGISTRY)
    )
    cases_by_id = {case["case_id"]: case for case in benchmark.cases}
    runs_root = attempt_root / "runs"
    manifest_paths: list[Path] = []

    for config_id, config in runner.CONFIG_REGISTRY.items():
        expected_ids = expected_by_config[config_id]
        records = []
        for ordinal, case_id in enumerate(expected_ids):
            case = cases_by_id[case_id]
            label = benchmark.labels_by_id[case_id]
            outcome = runner.ScopeOutcome(
                final_decision=label["allowed_final_decisions"][0],
                stop_reason=label["allowed_stop_reasons"][0],
                provider_called=bool(label["expected_provider_called"]),
                retrieved_count=0,
                accepted_context_count=0,
                rejected_context_count=0,
                redaction_count=0,
                dlp_finding_categories={},
                stage_results=(),
                pipeline_pre_audit_ms=1.0,
                end_to_end_with_audit_ms=2.0,
            )
            first = runner._case_completed_record(  # noqa: SLF001
                case=case,
                label=label,
                config=config,
                ordinal=ordinal,
                repository=repository,
                manifest=manifest,
                split=runner.HOLDOUT_SPLIT,
                outcome=outcome,
            )
            records.append(runner._merge_repetition_latency(first, first))  # noqa: SLF001

        scope_sets = {
            scope: {"count": len(ids), "sha256": runner._case_set_hash(ids)}  # noqa: SLF001
            for scope, ids in scopes_by_config[config_id].items()
        }
        artifact = {
            "schema_version": runner.HOLDOUT_RESULT_SCHEMA_VERSION,
            "experiment_id": experiment_id,
            "run_id": f"{config_id}-synthetic-holdout-run",
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
                "result_schema_version": runner.HOLDOUT_RESULT_SCHEMA_VERSION,
            },
            "split": runner.HOLDOUT_SPLIT,
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
                "n_end_to_end": sum(r["evaluation_scope"] == "end_to_end" for r in records),
                "aomr": None,
                "fpr": None,
                "fnr": None,
                "marginal_contribution": None,
                "metrics_computed": False,
                "note": "computed by the analysis step, not the runner",
            },
            "authorization_id": parsed.authorization_id,
            "holdout_authorization_sha256": parsed.authorization_sha256,
            "attempt": parsed.attempt,
            "supersedes_authorization_sha256": parsed.supersedes_authorization_sha256,
            "holdout_authorized": True,
        }
        result_bytes = runner._canonical_json_bytes(artifact)  # noqa: SLF001
        result_manifest = {
            "schema_version": runner.HOLDOUT_RESULT_MANIFEST_SCHEMA_VERSION,
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
            "benchmark_manifest_sha256": artifact["environment"]["benchmark_manifest_sha256"],
            "expected_case_set_sha256": artifact["expected_case_set_sha256"],
            "authorization_id": parsed.authorization_id,
            "holdout_authorization_sha256": parsed.authorization_sha256,
            "attempt": parsed.attempt,
            "supersedes_authorization_sha256": parsed.supersedes_authorization_sha256,
            "holdout_authorized": True,
        }
        directory = runs_root / experiment_id / config_id / artifact["run_id"]
        directory.mkdir(parents=True)
        (directory / "result.json").write_bytes(result_bytes)
        manifest_path = directory / "result-manifest.json"
        manifest_path.write_bytes(runner._canonical_json_bytes(result_manifest))  # noqa: SLF001
        manifest_paths.append(manifest_path)
    return tuple(manifest_paths)


@pytest.fixture()
def synthetic_holdout_attempt(tmp_path, runner, analyzer, authorization_payload):
    """A complete synthetic authorized holdout attempt, ready to analyze."""
    benchmark_root = runner.ROOT / "datasets" / "v2"
    real_manifest = runner.verify_frozen_manifest(benchmark_root)
    # Synthetic benchmark CONTENT is the development split; the holdout files
    # are never opened.
    benchmark = runner.load_split_benchmark(benchmark_root, "development")

    attempt_root = tmp_path / "p12e4-attempt-1"
    authorization_payload["output_root"] = str(attempt_root)
    authorization_payload["benchmark_manifest_sha256"] = real_manifest.sha256
    authorization_payload["analysis_contract_sha256"] = analyzer.ANALYSIS_CONTRACT_SHA256
    authorization_payload["mapping_sha256"] = analyzer.MAPPING_SHA256
    auth_path = _write_canonical(tmp_path / "authorization.json", authorization_payload)
    parsed = runner.parse_holdout_authorization(auth_path)

    repository = runner.RepositoryState(
        branch=parsed.execution_branch, commit=parsed.execution_commit, dirty=False
    )
    runner.claim_holdout_attempt_root(attempt_root)
    runner.write_start_receipt(
        attempt_root,
        runner.build_start_receipt(
            parsed, repository=_repo_state(runner, parsed),
            manifest=_manifest_identity(runner, parsed),
            started_at_utc="2026-07-19T10:05:00Z",
        ),
    )
    manifests = _synthetic_holdout_matrix(
        runner, analyzer, attempt_root, parsed, benchmark, real_manifest, repository
    )
    return attempt_root, auth_path, parsed, manifests, benchmark, repository


def _holdout_hooks(analyzer, repository):
    return analyzer.AnalyzerHooks(repository_state_loader=lambda root: repository)


def test_synthetic_holdout_attempt_reaches_analysis_construction_and_publication(
    analyzer, runner, synthetic_holdout_attempt, monkeypatch
):
    """The required acceptance path: a valid synthetic authorized attempt runs
    through analyze_holdout_results() to atomic publication."""
    attempt_root, auth_path, parsed, manifests, benchmark, repository = synthetic_holdout_attempt

    loaded: list[str] = []

    def _synthetic_loader(capability, **_kwargs):
        assert isinstance(capability, analyzer.runner.VerifiedHoldoutAuthorization)
        assert capability.is_valid()
        loaded.append(capability.authorization.authorization_id)
        return benchmark

    monkeypatch.setattr(analyzer.runner, "load_authorized_holdout_benchmark", _synthetic_loader)

    request = analyzer.HoldoutAnalysisRequest(
        authorization_path=auth_path, result_manifests=manifests
    )
    written = analyzer.analyze_holdout_results(
        request, repo_root=runner.ROOT, hooks=_holdout_hooks(analyzer, repository)
    )

    # Reached the authorized loader, then the builder, then publication.
    assert loaded == [parsed.authorization_id]
    assert isinstance(written, analyzer.WrittenAnalysis)
    analysis_dir = attempt_root / "analysis"
    assert written.output_directory == analysis_dir
    assert analysis_dir.is_dir()

    produced = sorted(path.name for path in analysis_dir.iterdir())
    assert produced == ["analysis-manifest.json", "analysis-table.csv", "analysis.json"]
    assert len(produced) == 3


def test_published_holdout_analysis_carries_holdout_schema_and_identity(
    analyzer, runner, synthetic_holdout_attempt, monkeypatch
):
    attempt_root, auth_path, parsed, manifests, benchmark, repository = synthetic_holdout_attempt
    monkeypatch.setattr(
        analyzer.runner, "load_authorized_holdout_benchmark", lambda c, **k: benchmark
    )
    analyzer.analyze_holdout_results(
        analyzer.HoldoutAnalysisRequest(authorization_path=auth_path, result_manifests=manifests),
        repo_root=runner.ROOT,
        hooks=_holdout_hooks(analyzer, repository),
    )
    analysis_dir = attempt_root / "analysis"
    analysis = json.loads((analysis_dir / "analysis.json").read_text(encoding="utf-8"))
    manifest = json.loads((analysis_dir / "analysis-manifest.json").read_text(encoding="utf-8"))

    assert analysis["schema_version"] == analyzer.HOLDOUT_ANALYSIS_SCHEMA_VERSION
    assert manifest["schema_version"] == analyzer.HOLDOUT_ANALYSIS_MANIFEST_SCHEMA_VERSION
    assert manifest["analysis_schema_version"] == analyzer.HOLDOUT_ANALYSIS_SCHEMA_VERSION
    assert analysis["split"] == runner.HOLDOUT_SPLIT

    for payload in (analysis, manifest):
        assert payload["authorization_id"] == parsed.authorization_id
        assert payload["holdout_authorization_sha256"] == parsed.authorization_sha256
        assert payload["attempt"] == parsed.attempt
        assert payload["supersedes_authorization_sha256"] is None
        assert payload["holdout_authorized"] is True


def test_published_holdout_analysis_covers_all_eight_configs_in_canonical_order(
    analyzer, runner, synthetic_holdout_attempt, monkeypatch
):
    attempt_root, auth_path, _, manifests, benchmark, repository = synthetic_holdout_attempt
    monkeypatch.setattr(
        analyzer.runner, "load_authorized_holdout_benchmark", lambda c, **k: benchmark
    )
    # Deliberately pass the manifests reversed: the analyzer must normalize.
    analyzer.analyze_holdout_results(
        analyzer.HoldoutAnalysisRequest(
            authorization_path=auth_path, result_manifests=tuple(reversed(manifests))
        ),
        repo_root=runner.ROOT,
        hooks=_holdout_hooks(analyzer, repository),
    )
    analysis = json.loads(
        (attempt_root / "analysis" / "analysis.json").read_text(encoding="utf-8")
    )
    configs = analysis["configs"]
    observed = (
        [entry["config_id"] for entry in configs]
        if isinstance(configs, list)
        else list(configs)
    )
    assert observed == list(runner.CONFIG_REGISTRY)


def test_published_holdout_analysis_preserves_phase_12e3_metric_policy(
    analyzer, runner, synthetic_holdout_attempt, monkeypatch
):
    attempt_root, auth_path, _, manifests, benchmark, repository = synthetic_holdout_attempt
    monkeypatch.setattr(
        analyzer.runner, "load_authorized_holdout_benchmark", lambda c, **k: benchmark
    )
    analyzer.analyze_holdout_results(
        analyzer.HoldoutAnalysisRequest(authorization_path=auth_path, result_manifests=manifests),
        repo_root=runner.ROOT,
        hooks=_holdout_hooks(analyzer, repository),
    )
    analysis_dir = attempt_root / "analysis"
    analysis = json.loads((analysis_dir / "analysis.json").read_text(encoding="utf-8"))
    raw_json = (analysis_dir / "analysis.json").read_text(encoding="utf-8")
    raw_csv = (analysis_dir / "analysis-table.csv").read_text(encoding="utf-8")

    assert analysis["latency"]["reportable"] is False
    assert analysis["latency"]["p50"] is None
    assert analysis["latency"]["p95"] is None
    contract = analysis["claims_control"]
    assert contract["abr_enabled"] is False
    assert contract["macro_enabled"] is False
    assert contract["family_rates_enabled"] is False
    assert contract["no_p_values"] is True
    assert contract["no_family_percentages"] is True
    assert analyzer.RATE_REPORTING_MIN_N == 10

    for forbidden in ('"abr"', "Attack Block Rate", '"macro"', '"f1"', '"p_value"'):
        assert forbidden not in raw_json
    for forbidden in ("abr", "macro", "f1", "p_value"):
        assert f",{forbidden}," not in raw_csv


def test_published_holdout_analysis_discloses_no_authorization_path_or_absolute_root(
    analyzer, runner, synthetic_holdout_attempt, monkeypatch
):
    attempt_root, auth_path, parsed, manifests, benchmark, repository = synthetic_holdout_attempt
    monkeypatch.setattr(
        analyzer.runner, "load_authorized_holdout_benchmark", lambda c, **k: benchmark
    )
    analyzer.analyze_holdout_results(
        analyzer.HoldoutAnalysisRequest(authorization_path=auth_path, result_manifests=manifests),
        repo_root=runner.ROOT,
        hooks=_holdout_hooks(analyzer, repository),
    )
    analysis_dir = attempt_root / "analysis"
    for name in ("analysis.json", "analysis-table.csv", "analysis-manifest.json"):
        text = (analysis_dir / name).read_text(encoding="utf-8")
        for secret in (str(auth_path), str(attempt_root), parsed.output_root, str(runner.ROOT)):
            assert secret not in text
            assert json.dumps(secret, ensure_ascii=False)[1:-1] not in text
        assert "authorization.json" not in text

    for name in ("analysis.json", "analysis-manifest.json"):
        payload = json.loads((analysis_dir / name).read_text(encoding="utf-8"))
        runner.scan_forbidden_artifact_content(payload)
        runner._assert_no_absolute_path(payload)  # noqa: SLF001


def test_published_holdout_analysis_manifest_references_are_valid(
    analyzer, runner, synthetic_holdout_attempt, monkeypatch
):
    import hashlib

    attempt_root, auth_path, _, manifests, benchmark, repository = synthetic_holdout_attempt
    monkeypatch.setattr(
        analyzer.runner, "load_authorized_holdout_benchmark", lambda c, **k: benchmark
    )
    analyzer.analyze_holdout_results(
        analyzer.HoldoutAnalysisRequest(authorization_path=auth_path, result_manifests=manifests),
        repo_root=runner.ROOT,
        hooks=_holdout_hooks(analyzer, repository),
    )
    analysis_dir = attempt_root / "analysis"
    manifest = json.loads((analysis_dir / "analysis-manifest.json").read_text(encoding="utf-8"))
    analysis_bytes = (analysis_dir / "analysis.json").read_bytes()
    table_bytes = (analysis_dir / "analysis-table.csv").read_bytes()

    assert manifest["analysis_sha256"] == hashlib.sha256(analysis_bytes).hexdigest()
    assert manifest["analysis_size_bytes"] == len(analysis_bytes)
    assert manifest["table_sha256"] == hashlib.sha256(table_bytes).hexdigest()
    assert manifest["table_size_bytes"] == len(table_bytes)
    # Every declared input result hash matches an artifact actually on disk.
    on_disk = {
        json.loads(path.read_text(encoding="utf-8"))["result_sha256"] for path in manifests
    }
    declared = {item["result_sha256"] for item in manifest["input_manifest_sha256_list"]}
    assert declared == on_disk
    assert len(manifest["input_manifest_sha256_list"]) == 8


def test_second_holdout_publication_refuses_overwrite_and_leaves_first_intact(
    analyzer, runner, synthetic_holdout_attempt, monkeypatch
):
    attempt_root, auth_path, _, manifests, benchmark, repository = synthetic_holdout_attempt
    monkeypatch.setattr(
        analyzer.runner, "load_authorized_holdout_benchmark", lambda c, **k: benchmark
    )
    request = analyzer.HoldoutAnalysisRequest(
        authorization_path=auth_path, result_manifests=manifests
    )
    hooks = _holdout_hooks(analyzer, repository)
    analyzer.analyze_holdout_results(request, repo_root=runner.ROOT, hooks=hooks)

    analysis_dir = attempt_root / "analysis"
    first = {
        path.name: path.read_bytes() for path in sorted(analysis_dir.iterdir()) if path.is_file()
    }
    assert set(first) == {"analysis.json", "analysis-table.csv", "analysis-manifest.json"}

    with pytest.raises(analyzer.AnalysisError, match="analysis"):
        analyzer.analyze_holdout_results(request, repo_root=runner.ROOT, hooks=hooks)

    after = {
        path.name: path.read_bytes() for path in sorted(analysis_dir.iterdir()) if path.is_file()
    }
    assert after == first


def test_repeated_holdout_analysis_is_canonically_deterministic(
    analyzer, runner, synthetic_holdout_attempt, tmp_path, monkeypatch
):
    """No fixed-time hook exists, so this verifies canonical serialization and
    internal hash consistency rather than claiming byte-identical timestamps."""
    attempt_root, auth_path, _, manifests, benchmark, repository = synthetic_holdout_attempt
    monkeypatch.setattr(
        analyzer.runner, "load_authorized_holdout_benchmark", lambda c, **k: benchmark
    )
    analyzer.analyze_holdout_results(
        analyzer.HoldoutAnalysisRequest(authorization_path=auth_path, result_manifests=manifests),
        repo_root=runner.ROOT,
        hooks=_holdout_hooks(analyzer, repository),
    )
    analysis_path = attempt_root / "analysis" / "analysis.json"
    raw = analysis_path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    assert runner._canonical_json_bytes(payload) == raw  # noqa: SLF001
    table = (attempt_root / "analysis" / "analysis-table.csv").read_bytes()
    assert b"\r\n" not in table
    assert table.decode("utf-8")


# --- shim safety -----------------------------------------------------------


def test_ordinary_analyze_results_still_rejects_holdout_split(analyzer, tmp_path):
    request = analyzer.AnalysisRequest(
        split=runner_holdout_split(analyzer),
        expected_branch="phase-12e-4-holdout-gate",
        expected_commit="0" * 40,
        output_root=tmp_path / "out",
        result_manifests=tuple(tmp_path / f"m{i}.json" for i in range(8)),
    )
    with pytest.raises(analyzer.AnalysisError, match="holdout is prohibited"):
        analyzer.analyze_results(request)


def runner_holdout_split(analyzer) -> str:
    return analyzer.runner.HOLDOUT_SPLIT


def test_holdout_shim_is_not_reachable_through_the_ordinary_request_path(analyzer, tmp_path):
    """The internal shim carries split=holdout, but it is only ever built
    inside analyze_holdout_results and never passes _validate_request."""
    import inspect

    source = inspect.getsource(analyzer.analyze_results)
    assert "_holdout_analysis_shim" not in source
    assert "_validate_request(request)" in source

    shim_source = inspect.getsource(analyzer._holdout_analysis_shim)  # noqa: SLF001
    assert "HOLDOUT_SPLIT" in shim_source
    # And the ordinary validator still rejects exactly that value.
    with pytest.raises(analyzer.AnalysisError, match="holdout is prohibited"):
        analyzer._validate_request(  # noqa: SLF001
            analyzer._holdout_analysis_shim(  # noqa: SLF001
                _dummy_authorization(analyzer), tmp_path / "analysis"
            )
        )


def _dummy_authorization(analyzer):
    return analyzer.runner.HoldoutAuthorization(
        schema_version=1,
        authorization_id="0f9a1c2d-3e4b-4a5c-8d6e-7f8091a2b3c4",
        issued_at_utc="2026-07-19T10:00:00Z",
        issued_by=analyzer.runner.HOLDOUT_AUTHORIZATION_ISSUER,
        purpose=analyzer.runner.HOLDOUT_AUTHORIZATION_PURPOSE,
        execution_branch="phase-12e-4-holdout-gate",
        execution_commit="0" * 40,
        benchmark_manifest_sha256="a" * 64,
        provider_id="mock",
        config_ids=tuple(analyzer.runner.CONFIG_REGISTRY),
        config_hashes={
            cid: c.config_hash for cid, c in analyzer.runner.CONFIG_REGISTRY.items()
        },
        result_schema_version=1,
        result_manifest_schema_version=1,
        analysis_schema_version=1,
        analysis_manifest_schema_version=1,
        analysis_contract_sha256="b" * 64,
        mapping_sha256="c" * 64,
        output_root="/tmp/x",
        attempt=1,
        supersedes_authorization_sha256=None,
        holdout_authorized=True,
        authorization_sha256="d" * 64,
    )


def test_holdout_mode_reachable_only_through_holdout_authorization_flag(analyzer):
    parser = analyzer.build_parser()
    options = {opt for action in parser._actions for opt in action.option_strings}
    assert "--holdout-authorization" in options
    split_action = next(a for a in parser._actions if "--split" in a.option_strings)
    assert list(split_action.choices) == list(analyzer.runner.SUPPORTED_SPLITS)
    assert analyzer.runner.HOLDOUT_SPLIT not in split_action.choices


# ===========================================================================
# Synthetic 60-case holdout contract (production loader, no real holdout file)
# ===========================================================================


@pytest.fixture(autouse=True)
def _guard_against_opening_real_holdout(monkeypatch):
    """Hard guard: fail any test that opens the frozen holdout case/label files."""
    real_open = Path.open
    forbidden = {
        (ROOT / "datasets" / "v2" / "cases" / "holdout.jsonl").resolve(),
        (ROOT / "datasets" / "v2" / "labels" / "holdout.jsonl").resolve(),
    }

    def guarded(self, *args, **kwargs):
        try:
            resolved = self.resolve()
        except OSError:
            resolved = self
        if resolved in forbidden:
            # Byte-hashing the frozen holdout files is legitimate and required
            # by `verify_frozen_manifest`; Phase 12E.3 closure recorded them as
            # "byte-hashed, not parsed". Anything that could READ CONTENT for
            # parsing (text mode) is what must never happen in a test.
            mode = kwargs.get("mode", args[0] if args else "r")
            if "b" not in str(mode):
                raise AssertionError(
                    "test attempted to parse a real holdout artifact (mode=%r)" % (mode,)
                )
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    yield


def _synthetic_holdout_split(root, runner, *, counts=None, mutate=None):
    """Write a fully synthetic 60-case holdout split under tmp_path."""
    counts = counts or {
        "end_to_end": 52, "component": 2, "availability_fault": 4, "residual_risk_only": 2,
    }
    families = sorted(getattr(runner, "REQUIRED_FAMILIES", None) or
                      ["clean_benign_rag", "direct_injection", "indirect_retrieved_injection"])
    (root / "cases").mkdir(parents=True, exist_ok=True)
    (root / "labels").mkdir(parents=True, exist_ok=True)
    (root / "corpus").mkdir(parents=True, exist_ok=True)

    cases, labels = [], []
    ordinal = 0
    for scope, n in counts.items():
        for _ in range(n):
            ordinal += 1
            cid = "V2-HOLD-%04d" % ordinal
            fam = families[ordinal % len(families)]
            cases.append({
                "case_id": cid, "split": "holdout", "scenario_family": fam,
                "language": "en", "query": "synthetic query %d" % ordinal, "top_k": 5,
                "relevant_document_ids": ["v2-doc-0001"], "evaluation_scope": scope,
            })
            labels.append({
                "case_id": cid, "scenario_family": fam, "language": "en",
                "template_id": fam + ":holdout:00", "semantic_group_id": "g",
                "translation_group_id": fam + ":holdout:00", "authoring_set": "holdout",
                "expected_document_ingestion_status": "indexed", "category": "benign",
                "attack_family": None, "expected_final_decision": "allow",
                "allowed_final_decisions": ["allow"], "expected_stop_reason": "allowed",
                "allowed_stop_reasons": ["allowed"], "expected_provider_called": True,
                "expected_retrieval_behavior": "hits>=1",
                "expected_context_behavior": "accepted_context_count>=1",
                "expected_dlp_action": None, "expected_redaction_categories": [],
                "expected_redaction_count": 0, "expected_security_property": "x",
                "rationale": "synthetic", "residual_risk": None,
            })
    if mutate:
        mutate(cases, labels)

    def _write(path, records):
        payload = "".join(
            json.dumps(r, ensure_ascii=False, sort_keys=True) + chr(10) for r in records
        )
        path.write_text(payload, encoding="utf-8", newline="")

    _write(root / "cases" / "holdout.jsonl", cases)
    _write(root / "labels" / "holdout.jsonl", labels)
    _write(root / "corpus" / "documents.jsonl", [{
        "document_id": "v2-doc-0001", "external_id": "v2-doc-0001",
        "source_key": "api_upload", "ingestion_mode": "public", "title": "t",
        "content": "c", "metadata": {}, "language": "en", "scenario_family": families[0],
    }])
    return root


def test_production_loader_accepts_synthetic_60_case_holdout(runner, tmp_path):
    root = _synthetic_holdout_split(tmp_path / "bench", runner)
    loaded = runner._load_frozen_split(root, runner.HOLDOUT_SPLIT)  # noqa: SLF001
    assert len(loaded.cases) == 60
    assert len(loaded.labels_by_id) == 60
    ids = [c["case_id"] for c in loaded.cases]
    assert ids == sorted(ids)
    assert len(set(ids)) == 60
    assert set(ids) == set(loaded.labels_by_id)
    for case in loaded.cases:
        assert loaded.labels_by_id[case["case_id"]]["scenario_family"] == case["scenario_family"]


def test_synthetic_holdout_expected_sets_are_60_and_52(runner, tmp_path):
    root = _synthetic_holdout_split(tmp_path / "bench", runner)
    loaded = runner._load_frozen_split(root, runner.HOLDOUT_SPLIT)  # noqa: SLF001
    overall, by_scope = runner._expected_case_sets(  # noqa: SLF001
        loaded, tuple(runner.CONFIG_REGISTRY)
    )
    assert len(overall["C0_all_on"]) == 60
    for config_id in list(runner.CONFIG_REGISTRY)[1:]:
        assert len(overall[config_id]) == 52
        assert set(by_scope[config_id]) == {"end_to_end"}


def test_synthetic_holdout_hashes_are_deterministic(runner, tmp_path):
    a = runner._load_frozen_split(  # noqa: SLF001
        _synthetic_holdout_split(tmp_path / "a", runner), runner.HOLDOUT_SPLIT
    )
    b = runner._load_frozen_split(  # noqa: SLF001
        _synthetic_holdout_split(tmp_path / "b", runner), runner.HOLDOUT_SPLIT
    )
    ha = runner._case_set_hash([c["case_id"] for c in a.cases])  # noqa: SLF001
    hb = runner._case_set_hash([c["case_id"] for c in b.cases])  # noqa: SLF001
    assert ha == hb and len(ha) == 64


@pytest.mark.parametrize("counts,label", [
    ({"end_to_end": 51, "component": 2, "availability_fault": 4, "residual_risk_only": 2}, "59"),
    ({"end_to_end": 53, "component": 2, "availability_fault": 4, "residual_risk_only": 2}, "61"),
    ({"end_to_end": 50, "component": 4, "availability_fault": 4, "residual_risk_only": 2}, "skew"),
    ({"end_to_end": 52, "component": 2, "availability_fault": 2, "residual_risk_only": 4}, "swap"),
])
def test_wrong_holdout_case_count_or_distribution_rejected(runner, tmp_path, counts, label):
    root = _synthetic_holdout_split(tmp_path / ("bad-" + label), runner, counts=counts)
    with pytest.raises(runner.IntegrityError, match="expected-case set changed"):
        runner._load_frozen_split(root, runner.HOLDOUT_SPLIT)  # noqa: SLF001


def test_duplicate_case_id_rejected(runner, tmp_path):
    def dup(cases, labels):
        cases[1]["case_id"] = cases[0]["case_id"]

    root = _synthetic_holdout_split(tmp_path / "dup-case", runner, mutate=dup)
    with pytest.raises(runner.IntegrityError, match="duplicate case identity"):
        runner._load_frozen_split(root, runner.HOLDOUT_SPLIT)  # noqa: SLF001


def test_duplicate_label_id_rejected(runner, tmp_path):
    def dup(cases, labels):
        labels[1]["case_id"] = labels[0]["case_id"]

    root = _synthetic_holdout_split(tmp_path / "dup-label", runner, mutate=dup)
    with pytest.raises(runner.IntegrityError, match="duplicate label identity"):
        runner._load_frozen_split(root, runner.HOLDOUT_SPLIT)  # noqa: SLF001


def test_missing_label_rejected(runner, tmp_path):
    root = _synthetic_holdout_split(
        tmp_path / "missing-label", runner, mutate=lambda c, l: l.pop()
    )
    with pytest.raises(runner.IntegrityError):
        runner._load_frozen_split(root, runner.HOLDOUT_SPLIT)  # noqa: SLF001


def test_extra_label_rejected(runner, tmp_path):
    def extra(cases, labels):
        labels.append(dict(labels[0], case_id="V2-HOLD-9999"))

    root = _synthetic_holdout_split(tmp_path / "extra-label", runner, mutate=extra)
    with pytest.raises(runner.IntegrityError):
        runner._load_frozen_split(root, runner.HOLDOUT_SPLIT)  # noqa: SLF001


def test_family_mismatch_rejected(runner, tmp_path):
    def mismatch(cases, labels):
        labels[0]["scenario_family"] = "a_different_family"

    root = _synthetic_holdout_split(tmp_path / "fam", runner, mutate=mismatch)
    with pytest.raises(runner.IntegrityError, match="case-label mapping mismatch"):
        runner._load_frozen_split(root, runner.HOLDOUT_SPLIT)  # noqa: SLF001


def test_unsupported_scope_rejected(runner, tmp_path):
    def bad_scope(cases, labels):
        cases[0]["evaluation_scope"] = "not_a_scope"

    root = _synthetic_holdout_split(tmp_path / "scope", runner, mutate=bad_scope)
    with pytest.raises(runner.IntegrityError, match="evaluation_scope is invalid"):
        runner._load_frozen_split(root, runner.HOLDOUT_SPLIT)  # noqa: SLF001


def test_wrong_split_field_rejected(runner, tmp_path):
    def bad_split(cases, labels):
        cases[0]["split"] = "validation"

    root = _synthetic_holdout_split(tmp_path / "split", runner, mutate=bad_split)
    with pytest.raises(runner.IntegrityError, match="does not match the request"):
        runner._load_frozen_split(root, runner.HOLDOUT_SPLIT)  # noqa: SLF001


# ===========================================================================
# Codex Finding 2 — runtime safety must be validated BEFORE claim/receipt/loader
# ===========================================================================


def _runtime_safety_probe(runner, tmp_path, authorization_payload, monkeypatch, **overrides):
    """Run holdout_preflight with one invalid setting and report side effects."""
    import dataclasses

    attempt_root = tmp_path / "rt-attempt"
    authorization_payload["output_root"] = str(attempt_root)
    auth_path = _write_canonical(tmp_path / "rt-auth.json", authorization_payload)
    parsed = runner.parse_holdout_authorization(auth_path)

    base = runner.load_settings()
    # Some of these fields are also rejected by Settings.__post_init__, which is
    # good defence in depth but would stop the fixture from constructing the
    # broken value at all. Bypass __post_init__ so the probe proves the HOLDOUT
    # gate independently rejects each value before any claim or loader call.
    broken = dataclasses.replace(base)
    for field_name, value in overrides.items():
        object.__setattr__(broken, field_name, value)
    monkeypatch.setattr(runner, "load_settings", lambda: broken)
    monkeypatch.setattr(
        runner, "verify_frozen_manifest", lambda *a, **k: _manifest_identity(runner, parsed)
    )

    loader_calls = []
    monkeypatch.setattr(
        runner,
        "load_authorized_holdout_benchmark",
        lambda *a, **k: loader_calls.append(1),
    )

    request = runner.HoldoutRunRequest(
        authorization_path=auth_path,
        output_root=attempt_root,
        analysis_contract_sha256=parsed.analysis_contract_sha256,
        mapping_sha256=parsed.mapping_sha256,
    )
    hooks = runner.RunnerHooks(repository_state_loader=lambda root: _repo_state(runner, parsed))
    with pytest.raises(runner.IntegrityError) as excinfo:
        runner.holdout_preflight(request, repo_root=ROOT, hooks=hooks)
    return excinfo.value, attempt_root, loader_calls


@pytest.mark.parametrize(
    "overrides,label",
    [
        ({"retrieval_max_batch_size": 0}, "batch-zero"),
        ({"retrieval_max_batch_size": -1}, "batch-negative"),
        ({"retrieval_max_batch_size": True}, "batch-bool"),
        ({"retrieval_max_top_k": 0}, "topk-zero"),
        ({"retrieval_max_top_k": 10_000}, "topk-above-max"),
        ({"rag_max_top_k": 0}, "rag-topk-zero"),
        ({"rag_max_aggregate_context_chars": 0}, "aggregate-zero"),
        ({"rag_max_aggregate_context_chars": 10_000_000}, "aggregate-above-max"),
        ({"dlp_max_inspect_chars": 0}, "dlp-zero"),
        ({"dlp_max_inspect_chars": 10_000_000}, "dlp-above-max"),
        ({"retrieval_max_document_chars": 0}, "doc-zero"),
        ({"retrieval_max_query_chars": -5}, "query-negative"),
        ({"retrieval_chunk_max_chars": 0}, "chunk-zero"),
        ({"retrieval_chunk_overlap_chars": -1}, "overlap-negative"),
        ({"retrieval_busy_timeout_ms": 0}, "busy-zero"),
        ({"llm_provider_timeout_seconds": 0}, "provider-timeout-zero"),
    ],
)
def test_invalid_runtime_setting_blocks_before_root_receipt_and_loader(
    runner, tmp_path, authorization_payload, monkeypatch, overrides, label
):
    error, attempt_root, loader_calls = _runtime_safety_probe(
        runner, tmp_path, authorization_payload, monkeypatch, **overrides
    )
    assert error.code == "runtime_safety", f"{label}: unexpected code {error.code}"
    assert not attempt_root.exists(), f"{label}: attempt root was created"
    assert not (attempt_root / "start-receipt.json").exists(), f"{label}: receipt was written"
    assert loader_calls == [], f"{label}: holdout loader was called"


@pytest.mark.parametrize(
    "timeout,label",
    [
        (0, "zero"),
        (-1.0, "negative"),
        (float("nan"), "nan"),
        (float("inf"), "positive-infinity"),
        (float("-inf"), "negative-infinity"),
        (True, "bool"),
        (100_000.0, "above-maximum"),
    ],
)
def test_invalid_case_timeout_blocks_before_root_receipt_and_loader(
    runner, tmp_path, authorization_payload, monkeypatch, timeout, label
):
    attempt_root = tmp_path / "to-attempt"
    authorization_payload["output_root"] = str(attempt_root)
    auth_path = _write_canonical(tmp_path / "to-auth.json", authorization_payload)
    parsed = runner.parse_holdout_authorization(auth_path)
    monkeypatch.setattr(
        runner, "verify_frozen_manifest", lambda *a, **k: _manifest_identity(runner, parsed)
    )
    loader_calls = []
    monkeypatch.setattr(
        runner, "load_authorized_holdout_benchmark", lambda *a, **k: loader_calls.append(1)
    )
    request = runner.HoldoutRunRequest(
        authorization_path=auth_path,
        output_root=attempt_root,
        analysis_contract_sha256=parsed.analysis_contract_sha256,
        mapping_sha256=parsed.mapping_sha256,
        case_timeout_seconds=timeout,
    )
    hooks = runner.RunnerHooks(repository_state_loader=lambda root: _repo_state(runner, parsed))
    with pytest.raises(runner.IntegrityError):
        runner.holdout_preflight(request, repo_root=ROOT, hooks=hooks)
    assert not attempt_root.exists(), f"{label}: attempt root was created"
    assert loader_calls == [], f"{label}: holdout loader was called"


def test_valid_runtime_settings_pass_the_safety_gate(runner):
    runner.validate_holdout_runtime_safety(runner.load_settings(), case_timeout_seconds=30.0)


# ===========================================================================
# Codex Finding 3 — analyzer Stage A must reject before the loader runs
# ===========================================================================


def _mutated_holdout_attempt(runner, analyzer, tmp_path, authorization_payload, mutate):
    """Build a complete synthetic attempt, apply `mutate`, and re-hash so the
    artifacts stay internally consistent."""
    import hashlib

    benchmark_root = runner.ROOT / "datasets" / "v2"
    real_manifest = runner.verify_frozen_manifest(benchmark_root)
    benchmark = runner.load_split_benchmark(benchmark_root, "development")

    attempt_root = tmp_path / "mut-attempt"
    authorization_payload["output_root"] = str(attempt_root)
    authorization_payload["benchmark_manifest_sha256"] = real_manifest.sha256
    authorization_payload["analysis_contract_sha256"] = analyzer.ANALYSIS_CONTRACT_SHA256
    authorization_payload["mapping_sha256"] = analyzer.MAPPING_SHA256
    auth_path = _write_canonical(tmp_path / "mut-auth.json", authorization_payload)
    parsed = runner.parse_holdout_authorization(auth_path)
    repository = runner.RepositoryState(
        branch=parsed.execution_branch, commit=parsed.execution_commit, dirty=False
    )
    runner.claim_holdout_attempt_root(attempt_root)
    runner.write_start_receipt(
        attempt_root,
        runner.build_start_receipt(
            parsed, repository=repository, manifest=real_manifest,
            started_at_utc="2026-07-19T10:05:00Z",
        ),
    )
    manifests = _synthetic_holdout_matrix(
        runner, analyzer, attempt_root, parsed, benchmark, real_manifest, repository
    )

    for manifest_path in manifests:
        result_path = manifest_path.parent / "result.json"
        result = json.loads(result_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        mutate(result, manifest)
        result_bytes = runner._canonical_json_bytes(result)  # noqa: SLF001
        result_path.write_bytes(result_bytes)
        # Keep the manifest internally consistent with the mutated result so the
        # rejection cannot be attributed to a trivially broken hash.
        manifest["result_sha256"] = hashlib.sha256(result_bytes).hexdigest()
        manifest["result_size_bytes"] = len(result_bytes)
        manifest_path.write_bytes(runner._canonical_json_bytes(manifest))  # noqa: SLF001

    return auth_path, manifests, benchmark, repository


@pytest.mark.parametrize(
    "mutate,label",
    [
        (lambda r, m: (r.__setitem__("provider_behavior_hash", "7" * 64),
                       r["environment"].__setitem__("provider_behavior_hash", "7" * 64),
                       m.__setitem__("provider_behavior_hash", "7" * 64)),
         "provider_behavior_hash"),
        (lambda r, m: (r.__setitem__("experiment_id", "6" * 64),
                       m.__setitem__("experiment_id", "6" * 64)),
         "experiment_id"),
        (lambda r, m: (r.__setitem__("profile_id", "tampered-profile"),
                       m.__setitem__("profile_id", "tampered-profile")),
         "profile_id"),
        (lambda r, m: (r.__setitem__("expected_case_set_sha256", "5" * 64),
                       m.__setitem__("expected_case_set_sha256", "5" * 64)),
         "expected_case_set_sha256"),
        (lambda r, m: r["environment"].__setitem__("dependencies_sha256", "4" * 64),
         "dependency_identity"),
        (lambda r, m: r["environment"].__setitem__("result_schema_version", 2),
         "environment_schema"),
        (lambda r, m: (r.__setitem__("schema_version", 2), m.__setitem__("result_schema_version", 2)),
         "result_schema"),
        (lambda r, m: r.__setitem__("split", "validation"), "split"),
        (lambda r, m: (r.__setitem__("run_status", "partial"),
                       m.__setitem__("run_status", "partial")),
         "run_status"),
        (lambda r, m: (r.__setitem__("attempt", 9), m.__setitem__("attempt", 9)), "attempt"),
        (lambda r, m: (r.__setitem__("authorization_id", "11111111-2222-4333-8444-555555555555"),
                       m.__setitem__("authorization_id", "11111111-2222-4333-8444-555555555555")),
         "authorization_id"),
        (lambda r, m: (r.__setitem__("holdout_authorization_sha256", "3" * 64),
                       m.__setitem__("holdout_authorization_sha256", "3" * 64)),
         "authorization_hash"),
        (lambda r, m: (r.__setitem__("config_hash", "2" * 64), m.__setitem__("config_hash", "2" * 64)),
         "config_hash"),
        (lambda r, m: r["environment"].__setitem__("git_commit", "1" * 40), "commit"),
        (lambda r, m: r["environment"].__setitem__("benchmark_manifest_sha256", "0" * 64),
         "benchmark_identity"),
    ],
)
def test_stage_a_rejects_every_identity_mutation_before_loader(
    analyzer, runner, tmp_path, authorization_payload, monkeypatch, mutate, label
):
    """Codex finding: provider_behavior_hash and experiment_id mutations used to
    reach the loader. Every identity below must now be rejected in Stage A."""
    auth_path, manifests, benchmark, repository = _mutated_holdout_attempt(
        runner, analyzer, tmp_path, authorization_payload, mutate
    )
    loader_calls = []

    # Patch the EXACT module instance the analyzer uses.
    def _counting_loader(*args, **kwargs):
        loader_calls.append(1)
        return benchmark

    monkeypatch.setattr(analyzer.runner, "load_authorized_holdout_benchmark", _counting_loader)

    request = analyzer.HoldoutAnalysisRequest(
        authorization_path=auth_path, result_manifests=manifests
    )
    hooks = analyzer.AnalyzerHooks(repository_state_loader=lambda root: repository)
    with pytest.raises((analyzer.AnalysisError, analyzer.runner.RunnerError)):
        analyzer.analyze_holdout_results(request, repo_root=runner.ROOT, hooks=hooks)

    assert loader_calls == [], f"{label}: holdout loader ran before rejection"
    assert not (Path(str(manifests[0]).split("runs")[0]) / "analysis").exists()
