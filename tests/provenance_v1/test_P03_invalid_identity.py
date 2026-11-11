"""P03: closed provider enum, open model strings; mock/in-sample only."""
import pytest

from app.provenance import normalize_source, unknown_slot, validate_artifact
from .fixtures import attest, mock_case


@pytest.mark.parametrize("path", ["provider.requested", "provider.effective"])
@pytest.mark.parametrize("value", ["mock", "ollama"])
def test_P03_invalid_identity_in_sample_each_supported_provider(path, value):
    artifact, sources = mock_case()
    attest(artifact, sources, path, value)
    assert validate_artifact(artifact, evidence=sources).valid


@pytest.mark.parametrize("path", ["provider.requested", "provider.effective"])
@pytest.mark.parametrize("value", ["unsupported-in-sample", "UNKNOWN", "", "Mock", 1, True, [], {}])
def test_P03_invalid_identity_in_sample_unsupported_provider(path, value):
    artifact, sources = mock_case()
    attest(artifact, sources, path, value)
    assert not validate_artifact(artifact, evidence=sources).valid


@pytest.mark.parametrize("path", ["model.requested", "model.effective"])
@pytest.mark.parametrize("value", ["mock-in-sample-arbitrary-model:42", "mock", "ollama"])
def test_P03_invalid_identity_in_sample_model_not_provider_enum(path, value):
    artifact, sources = mock_case()
    attest(artifact, sources, path, value)
    assert validate_artifact(artifact, evidence=sources).valid


@pytest.mark.parametrize("path", ["model.requested", "model.effective"])
@pytest.mark.parametrize("value", ["", "  ", True, False, 1, 1.5, [], {}])
def test_P03_invalid_identity_in_sample_invalid_model_type(path, value):
    artifact, sources = mock_case()
    attest(artifact, sources, path, value)
    assert not validate_artifact(artifact, evidence=sources).valid


@pytest.mark.parametrize("path", ["provider.requested", "provider.effective", "model.requested", "model.effective"])
def test_P03_invalid_identity_in_sample_null_is_unknown(path):
    artifact, sources = mock_case()
    parent, child = path.split(".")
    artifact[parent][child] = unknown_slot("Mock/in-sample identity unavailable")
    assert validate_artifact(artifact, evidence=sources).valid


def test_P03_invalid_identity_in_sample_no_provider_or_path_inferred_from_model():
    artifact, sources = mock_case()
    for model_name in ("ollama", "rag", "gateway", "mock-in-sample-other-model"):
        attest(artifact, sources, "model.requested", model_name)
        source = {"model": {"requested": artifact["model"]["requested"]}}
        normalized = normalize_source(source, run_id=artifact["run_id"], evidence=sources)
        assert normalized["model"]["requested"]["value"] == model_name
        assert normalized["model"]["effective"]["value"] is None
        assert normalized["provider"]["requested"]["value"] is None
        assert normalized["provider"]["effective"]["value"] is None
        assert normalized["execution_path"]["value"] is None
        assert validate_artifact(normalized, evidence=sources).valid
