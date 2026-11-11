"""P04: execution, storage and independent ACL evidence; mock/in-sample."""
from dataclasses import asdict, fields, replace

import pytest

from app.core.pipeline import GuardProfile
from app.provenance import normalize_source, unknown_slot, validate_artifact
from .fixtures import attest, get_slot, mock_case

GUARD_FIELDS = tuple(field.name for field in fields(GuardProfile))


@pytest.mark.parametrize("path,value", [
    ("execution_path", "gateway"), ("execution_path", "rag"),
    ("storage_backend", "none"), ("storage_backend", "memory"),
    ("storage_backend", "persistent"),
])
def test_P04_execution_acl_in_sample_each_supported_enum(path, value):
    artifact, sources = mock_case()
    attest(artifact, sources, path, value)
    assert validate_artifact(artifact, evidence=sources).valid


@pytest.mark.parametrize("path", ["execution_path", "storage_backend"])
@pytest.mark.parametrize("value", ["unsupported-in-sample", "UNKNOWN", "", True, 0, [], {}])
def test_P04_execution_acl_in_sample_unsupported_enum(path, value):
    artifact, sources = mock_case()
    attest(artifact, sources, path, value)
    assert not validate_artifact(artifact, evidence=sources).valid


@pytest.mark.parametrize("path", ["execution_path", "storage_backend", "acl_enabled"])
def test_P04_execution_acl_in_sample_missing_evidence_not_inferred(path):
    artifact, sources = mock_case()
    get_slot(artifact, path)["evidence"] = None
    assert not validate_artifact(artifact, evidence=sources).valid
    normalized = normalize_source(artifact, evidence=sources)
    slot = get_slot(normalized, path)
    assert slot["value"] is None and slot["evidence"] is None and slot["reason"]
    assert validate_artifact(normalized, evidence=sources).valid


@pytest.mark.parametrize("flag", GUARD_FIELDS)
@pytest.mark.parametrize("acl", [True, False, None])
def test_P04_execution_acl_in_sample_six_guard_flags_do_not_flip_acl(flag, acl):
    artifact, sources = mock_case()
    if acl is None:
        artifact["acl_enabled"] = unknown_slot("Mock/in-sample ACL evidence absent")
    else:
        attest(artifact, sources, "acl_enabled", acl)
    original = normalize_source(artifact, evidence=sources)
    profile = replace(GuardProfile(), **{flag: False})
    artifact["guard_profile"] = asdict(profile)
    normalized = normalize_source(artifact, evidence=sources)
    assert normalized["acl_enabled"] == original["acl_enabled"]
    assert normalized["acl_enabled"]["value"] is acl
    assert validate_artifact(normalized, evidence=sources).valid


def test_P04_execution_acl_in_sample_no_directory_metadata_inference():
    normalized = normalize_source({
        "fixture_label": "mock/in-sample", "directory": "ollama/rag/persistent",
        "path": "mock-in-sample/gateway/memory", "guard_profile": asdict(GuardProfile()),
    }, run_id="mock-in-sample-directory")
    for path in ("execution_path", "storage_backend", "acl_enabled", "is_mock"):
        assert normalized[path]["value"] is None
        assert normalized[path]["reason"]
    assert normalized["provider"]["effective"]["value"] is None
    assert validate_artifact(normalized).valid
