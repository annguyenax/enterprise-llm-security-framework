"""P02: evidence stays with each identity; all results mock/in-sample."""
from dataclasses import replace

import pytest

from app.provenance import normalize_source, unknown_slot, validate_artifact
from .fixtures import (
    EXECUTION_REF, REQUEST_REF, attest, clone, mock_case, mock_slot,
    mock_verification_candidate,
)


def test_P02_effective_differs_in_sample_requested_effective_kept_separate():
    artifact, sources = mock_case()
    attest(artifact, sources, "provider.requested", "ollama")
    before = clone(artifact)
    assert validate_artifact(artifact, evidence=sources).valid
    normalized = normalize_source(artifact, evidence=sources)
    assert artifact == before
    assert normalized == artifact
    for name in ("provider", "model"):
        assert normalized[name]["requested"]["value"] != normalized[name]["effective"]["value"]
        assert normalized[name]["requested"]["evidence"] == REQUEST_REF
        assert normalized[name]["effective"]["evidence"] == EXECUTION_REF


@pytest.mark.parametrize("fault", ["missing_reference", "request_reference", "not_execution", "wrong_run"])
def test_P02_effective_differs_in_sample_unbacked_effective_stays_unknown(fault):
    artifact, sources = mock_case()
    for name in ("provider", "model"):
        if fault == "missing_reference":
            artifact[name]["effective"]["evidence"] = None
        elif fault == "request_reference":
            artifact[name]["effective"] = clone(artifact[name]["requested"])
    if fault == "not_execution":
        sources[EXECUTION_REF] = replace(sources[EXECUTION_REF], execution=False)
    if fault == "wrong_run":
        sources[EXECUTION_REF] = replace(sources[EXECUTION_REF], run_id="mock-in-sample-other-run")
    assert not validate_artifact(artifact, evidence=sources).valid
    normalized = normalize_source(artifact, evidence=sources)
    for name in ("provider", "model"):
        assert normalized[name]["requested"] == artifact[name]["requested"]
        slot = normalized[name]["effective"]
        assert slot["value"] is None and slot["evidence"] is None and slot["reason"]
    assert validate_artifact(normalized, evidence=sources).valid


def test_P02_effective_differs_in_sample_requested_claim_is_not_execution_evidence():
    artifact, sources = mock_case()
    # Even an effective-shaped claim in a request source is insufficient.
    request = sources[REQUEST_REF]
    sources[REQUEST_REF] = replace(request, claims={
        **request.claims, "provider.effective": "mock",
        "model.effective": "mock-in-sample-request-model",
    })
    artifact["provider"]["effective"] = mock_slot("mock", REQUEST_REF)
    artifact["model"]["effective"] = mock_slot("mock-in-sample-request-model", REQUEST_REF)
    assert not validate_artifact(artifact, evidence=sources).valid


def test_P02_effective_differs_in_sample_non_mock_does_not_infer_identity_or_verification():
    artifact, sources = mock_case()
    attest(artifact, sources, "is_mock", False)
    source = {"fixture_label": "mock/in-sample", "is_mock": artifact["is_mock"]}
    normalized = normalize_source(source, run_id=artifact["run_id"], evidence=sources)
    assert normalized["is_mock"]["value"] is False
    for name in ("provider", "model"):
        assert normalized[name]["requested"]["value"] is None
        assert normalized[name]["effective"]["value"] is None
    assert normalized["llm_verified"]["value"] is None
    assert normalized["execution_path"]["value"] is None
    assert validate_artifact(normalized, evidence=sources).valid
    normalized_without_evidence = normalize_source(source, run_id=artifact["run_id"])
    assert normalized_without_evidence["is_mock"]["value"] is None


def test_P02_effective_differs_in_sample_mock_supports_false_verification():
    artifact, sources = mock_case()
    del artifact["llm_verified"]
    assert not validate_artifact(artifact, evidence=sources).valid
    normalized = normalize_source(artifact, evidence=sources)
    assert normalized["llm_verified"] == mock_slot(False)
    assert validate_artifact(normalized, evidence=sources).valid


def test_P02_effective_differs_in_sample_evidenced_mock_state_supports_false_verification():
    artifact, sources = mock_case()
    sources[EXECUTION_REF] = replace(sources[EXECUTION_REF], execution=False, claims={"is_mock": True})
    normalized = normalize_source(
        {"is_mock": artifact["is_mock"]}, run_id=artifact["run_id"], evidence=sources,
    )
    assert normalized["is_mock"]["value"] is True
    assert normalized["llm_verified"] == mock_slot(False)
    assert validate_artifact(normalized, evidence=sources).valid


@pytest.mark.parametrize("path", ["is_mock", "provider.effective"])
def test_P02_effective_differs_in_sample_mock_requires_false_not_unknown(path):
    artifact, sources = mock_case()
    if path == "is_mock":
        artifact["provider"]["effective"] = unknown_slot("Mock/in-sample effective unknown")
    else:
        artifact["is_mock"] = unknown_slot("Mock/in-sample state unknown")
    artifact["llm_verified"] = unknown_slot("Mock/in-sample verification absent")
    assert not validate_artifact(artifact, evidence=sources).valid


def test_P02_effective_differs_NEW_01_in_sample_mock_and_verified_true_invalid():
    artifact, sources = mock_verification_candidate()
    attest(artifact, sources, "is_mock", True)
    # Both individual references resolve, including an artificial same-run
    # verification attestation. The cross-slot contradiction must still fail.
    result = validate_artifact(artifact, evidence=sources)
    assert not result.valid
    assert any("NEW-01" in issue.message for issue in result.errors)


def test_P02_effective_differs_in_sample_all_slots_require_same_nonempty_run():
    """Every slot, including execution_path and storage_backend, needs a
    nonempty matching run_id. None == None is not evidence."""
    artifact, sources = mock_case()
    # Evidence from another run cannot support execution_path.
    sources[EXECUTION_REF] = replace(sources[EXECUTION_REF], run_id="mock-in-sample-other-run")
    assert not validate_artifact(artifact, evidence=sources).valid
    # A source with a null run_id cannot support the artifact run.
    artifact, sources = mock_case()
    sources[EXECUTION_REF] = replace(sources[EXECUTION_REF], run_id=None)
    assert not validate_artifact(artifact, evidence=sources).valid
    # Two null run IDs still do not match.
    artifact, sources = mock_case()
    artifact["run_id"] = None
    sources[EXECUTION_REF] = replace(sources[EXECUTION_REF], run_id=None)
    result = validate_artifact(artifact, evidence=sources)
    assert not result.valid
