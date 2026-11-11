"""P01: strict NEW artifacts; every fixture/result is mock/in-sample."""
from dataclasses import replace
from types import MappingProxyType

import pytest

from app.provenance import (
    BOOLEAN_SLOTS, REQUIRED_KEYS, SLOT_KEYS, SLOT_PATHS, normalize_source,
    unknown_slot, validate_artifact,
)
from .fixtures import (
    EXECUTION_REF, attest, clone, get_slot, mock_case, mock_slot,
    mock_verification_candidate, put_slot,
)


def test_P01_metadata_missing_in_sample_valid_baseline_and_no_mutation():
    artifact, sources = mock_case()
    before = clone(artifact)
    assert validate_artifact(artifact, evidence=sources).valid
    assert artifact == before
    assert not validate_artifact(artifact).valid  # References alone are not evidence.


@pytest.mark.parametrize("key", REQUIRED_KEYS)
def test_P01_metadata_missing_in_sample_each_required_key(key):
    artifact, sources = mock_case()
    del artifact[key]
    result = validate_artifact(artifact, evidence=sources)
    assert not result.valid
    assert any(issue.path == key for issue in result.errors)
    assert key not in artifact  # Reader did not repair the emitted structure.


@pytest.mark.parametrize("version", [None, "", "provenance-v0", "provenance-v2", 1, True, [], {}])
def test_P01_metadata_missing_in_sample_invalid_version(version):
    artifact, sources = mock_case()
    artifact["schema_version"] = version
    assert not validate_artifact(artifact, evidence=sources)


@pytest.mark.parametrize("run_id", [None, "", "  ", 0, True, [], {}])
def test_P01_metadata_missing_in_sample_invalid_run_id(run_id):
    artifact, sources = mock_case()
    artifact["run_id"] = run_id
    assert not validate_artifact(artifact, evidence=sources).valid


@pytest.mark.parametrize("path", SLOT_PATHS)
@pytest.mark.parametrize("key", SLOT_KEYS)
def test_P01_metadata_missing_in_sample_each_slot_key(path, key):
    artifact, sources = mock_case()
    del get_slot(artifact, path)[key]
    assert not validate_artifact(artifact, evidence=sources).valid


@pytest.mark.parametrize("path", SLOT_PATHS)
@pytest.mark.parametrize("bad_slot", [None, True, "mock/in-sample", 7, [], {"value": None}])
def test_P01_metadata_missing_in_sample_wrong_slot_type(path, bad_slot):
    artifact, sources = mock_case()
    put_slot(artifact, path, bad_slot)
    assert not validate_artifact(artifact, evidence=sources).valid


@pytest.mark.parametrize("path", SLOT_PATHS)
def test_P01_metadata_missing_in_sample_slot_extra_key(path):
    artifact, sources = mock_case()
    get_slot(artifact, path)["extra"] = "mock/in-sample"
    assert not validate_artifact(artifact, evidence=sources).valid


@pytest.mark.parametrize("path", SLOT_PATHS)
@pytest.mark.parametrize("reference", [None, "", "fixture:mock-in-sample#absent", True, {}, []])
def test_P01_metadata_missing_in_sample_claim_without_evidence(path, reference):
    artifact, sources = mock_case()
    if path == "commit_sha":
        attest(artifact, sources, path, "a" * 40)
    get_slot(artifact, path)["evidence"] = reference
    assert not validate_artifact(artifact, evidence=sources).valid


@pytest.mark.parametrize("reason", [None, "", "  ", True, 1, [], {}])
@pytest.mark.parametrize("path", SLOT_PATHS)
def test_P01_metadata_missing_in_sample_null_requires_reason(path, reason):
    artifact, sources = mock_case()
    put_slot(artifact, path, {"value": None, "evidence": None, "reason": reason})
    assert not validate_artifact(artifact, evidence=sources).valid


@pytest.mark.parametrize("path", SLOT_PATHS)
def test_P01_metadata_missing_in_sample_null_requires_null_evidence(path):
    artifact, sources = mock_case()
    put_slot(artifact, path, mock_slot(None, reason="Mock/in-sample unknown"))
    assert not validate_artifact(artifact, evidence=sources).valid


@pytest.mark.parametrize("sha", ["a" * 40, "0123456789abcdef" * 4])
def test_P01_metadata_missing_in_sample_valid_commit_formats(sha):
    artifact, sources = mock_case()
    attest(artifact, sources, "commit_sha", sha)
    assert validate_artifact(artifact, evidence=sources).valid


@pytest.mark.parametrize("sha", ["", "a" * 39, "a" * 41, "a" * 63, "a" * 65, "A" * 40, "g" * 40, " a" * 20, 40, True])
def test_P01_metadata_missing_in_sample_invalid_commit_format(sha):
    artifact, sources = mock_case()
    attest(artifact, sources, "commit_sha", sha)
    assert not validate_artifact(artifact, evidence=sources).valid


def test_P01_metadata_missing_in_sample_null_commit_no_claim():
    artifact, sources = mock_case()
    assert artifact["commit_sha"]["value"] is None
    assert artifact["commit_sha"]["evidence"] is None
    assert validate_artifact(artifact, evidence=sources).valid


@pytest.mark.parametrize("path", sorted(BOOLEAN_SLOTS))
@pytest.mark.parametrize("value", [0, 1, "true", "false", "UNKNOWN", [], {}])
def test_P01_metadata_missing_in_sample_boolean_types(path, value):
    artifact, sources = mock_case()
    attest(artifact, sources, path, value)
    assert not validate_artifact(artifact, evidence=sources).valid


@pytest.mark.parametrize("path", ["provider", "model"])
@pytest.mark.parametrize("value", [None, [], "mock/in-sample", 1])
def test_P01_metadata_missing_in_sample_identity_object_type(path, value):
    artifact, sources = mock_case()
    artifact[path] = value
    assert not validate_artifact(artifact, evidence=sources).valid


@pytest.mark.parametrize("artifact", [None, [], True, "mock/in-sample", 1])
def test_P01_metadata_missing_in_sample_artifact_object_type(artifact):
    assert not validate_artifact(artifact).valid


def test_P01_metadata_missing_in_sample_normalize_incomplete_not_emitted():
    source = {"fixture_label": "mock/in-sample", "is_mock": False}
    before = clone(source)
    artifact = normalize_source(source, run_id="mock-in-sample-writer")
    assert source == before
    assert set(artifact) == set(REQUIRED_KEYS)
    for path in SLOT_PATHS:
        slot = get_slot(artifact, path)
        assert set(slot) == set(SLOT_KEYS)
        assert slot["value"] is None and slot["evidence"] is None and slot["reason"]
    assert artifact["timing"] is None
    assert validate_artifact(artifact).valid
    assert not validate_artifact(normalize_source({})).valid
    with pytest.raises(ValueError, match="unsupported"):
        normalize_source({"schema_version": "provenance-v99"})
    with pytest.raises(ValueError):
        unknown_slot("")


@pytest.mark.parametrize("fault", ["missing_response_attestation", "wrong_run", "not_execution", "unrelated_claim"])
def test_P01_metadata_missing_NEW_04_in_sample_unmatched_response_evidence(fault):
    # Positive-shaped fixture evidence is still only an in-sample double.
    artifact, sources = mock_verification_candidate()
    assert validate_artifact(artifact, evidence=sources).valid
    source = sources[EXECUTION_REF]
    changes = {
        "missing_response_attestation": {"real_llm_response": False},
        "wrong_run": {"run_id": "mock-in-sample-other-run"},
        "not_execution": {"execution": False},
        "unrelated_claim": {"claims": {**source.claims, "llm_verified": False}},
    }
    sources[EXECUTION_REF] = replace(source, **changes[fault])
    result = validate_artifact(artifact, evidence=sources)
    assert not result.valid
    assert any(issue.path == "llm_verified" for issue in result.errors)


def test_P01_metadata_missing_in_sample_source_failures_and_mismatched_claims():
    artifact, sources = mock_case()
    sources[EXECUTION_REF] = replace(sources[EXECUTION_REF], claims={"is_mock": 1})
    assert not validate_artifact(artifact, evidence=sources).valid

    def failing_resolver(reference, run_id):
        raise OSError("mock/in-sample source unavailable")

    assert not validate_artifact(artifact, evidence=failing_resolver).valid
    assert not validate_artifact(artifact, evidence={EXECUTION_REF: object()}).valid


@pytest.mark.parametrize("kind", ["mock-in-sample-unsupported-kind", None, [], {}])
def test_P01_metadata_missing_in_sample_invalid_evidence_source_kind(kind):
    artifact, sources = mock_case()
    sources[EXECUTION_REF] = replace(sources[EXECUTION_REF], kind=kind)
    assert not validate_artifact(artifact, evidence=sources).valid


@pytest.mark.parametrize("reason", [False, 0, [], {}, ""])
def test_P01_metadata_missing_in_sample_claim_reason_type(reason):
    artifact, sources = mock_case()
    artifact["acl_enabled"]["reason"] = reason
    assert not validate_artifact(artifact, evidence=sources).valid


def test_P01_metadata_missing_NEW_01_normalize_does_not_overwrite_verified_true():
    """Mock evidence must not silently replace an evidenced llm_verified=true
    with false; the contradiction becomes UNKNOWN."""
    artifact, sources = mock_case()
    artifact["llm_verified"] = {
        "value": True, "evidence": EXECUTION_REF, "reason": None,
    }
    # The source already attests is_mock=true; adding a verified-true claim
    # is the NEW-01 contradiction. normalize must not emit a clean false.
    normalized = normalize_source(artifact, evidence=sources)
    assert normalized["is_mock"]["value"] is True
    assert normalized["llm_verified"]["value"] is None
    assert normalized["llm_verified"]["value"] is not False
    assert normalized["llm_verified"]["reason"]
    assert "NEW-01" in normalized["llm_verified"]["reason"]
    # Writer does not invent a clean false. The contradiction remains invalid
    # for NEW emission until the caller supplies evidence-backed false.
    assert not validate_artifact(normalized, evidence=sources).valid


def test_P01_metadata_missing_NEW_01_normalize_mappingproxy_claimed_true():
    """A true claim held in a Mapping (not a plain dict) must not be
    silently overwritten to a clean false."""
    artifact, sources = mock_case()
    artifact["llm_verified"] = MappingProxyType({
        "value": True, "evidence": EXECUTION_REF, "reason": None,
    })
    normalized = normalize_source(artifact, evidence=sources)
    assert normalized["llm_verified"]["value"] is None
    assert normalized["llm_verified"]["value"] is not False
    assert "NEW-01" in (normalized["llm_verified"]["reason"] or "")
