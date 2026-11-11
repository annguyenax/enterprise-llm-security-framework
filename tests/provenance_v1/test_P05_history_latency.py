"""P05: immutable history and strict latency; all data/results mock/in-sample."""
import hashlib
import json
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal

import pytest

from app.provenance import (
    TIMING_FIELDS, UNKNOWN, make_timing, normalize_source, read_artifact,
    read_history, summarize_latency, unknown_slot, validate_artifact, validate_timing,
)
from .fixtures import (
    EXECUTION_REF, FIXTURES, TIMING_REF, attest, clone, mock_timed_case,
)


def test_P05_history_latency_in_sample_history_keeps_bytes_hash_and_numbers():
    original = (FIXTURES / "mock_in_sample_history.json").read_bytes()
    original_hash = hashlib.sha256(original).hexdigest()
    view = read_history(original)
    assert view.original_bytes == original
    assert view.sha256 == original_hash
    assert view.document["p50_ms"] == Decimal("12.345678901234567890123456789")
    assert view.document["p95_ms"] == Decimal("98.765432109876543210987654321")
    assert str(view.document["samples"][1]) == "2.500"
    assert view.status == "versionless" and not view.valid_new_artifact
    assert not view.latency_reportable
    for path, field in view.fields.items():
        assert field.value is None and field.display == UNKNOWN and field.reason, path
    with pytest.raises(TypeError):
        view.document["run_id"] = "mock-in-sample-invented"
    with pytest.raises(TypeError):
        view.document["samples"][0] = 9
    with pytest.raises(TypeError):
        view.fields["run_id"] = None
    with pytest.raises(FrozenInstanceError):
        view.fields["run_id"].value = "mock-in-sample-invented"
    with pytest.raises(FrozenInstanceError):
        view.original_bytes = b"{}"
    assert (FIXTURES / "mock_in_sample_history.json").read_bytes() == original
    assert summarize_latency([json.loads(original)]) == ()


@pytest.mark.parametrize("version", [None, "provenance-v0", "provenance-v99", 1, False, {}])
def test_P05_history_latency_in_sample_explicit_version_modes(version):
    document = {
        "fixture_label": "mock/in-sample", "schema_version": version,
        "p50_ms": 17, "p95_ms": 23,
        "directory": "mock-in-sample/provenance-v1/ollama",
    }
    original = json.dumps(document).encode()
    view = read_history(original)
    assert view.status == ("versionless" if version is None else "unsupported")
    assert not view.valid_new_artifact and not view.latency_reportable
    assert view.document["p50_ms"] == 17 and view.document["p95_ms"] == 23
    assert view.original_bytes == original
    new_view = read_artifact(original, mode="new")
    assert not new_view.valid_new_artifact
    assert summarize_latency([document]) == ()


def test_P05_history_latency_in_sample_unsupported_version_never_interprets_metrics():
    artifact, sources = mock_timed_case()
    artifact["schema_version"] = "provenance-v99"
    calls = []

    def mock_resolver(reference, run_id):
        calls.append((reference, run_id))
        return sources.get(reference)

    original = json.dumps(artifact).encode()
    view = read_history(original, evidence=mock_resolver)
    assert view.status == "unsupported"
    assert not view.latency_reportable and not view.valid_new_artifact
    assert view.original_bytes == original
    assert all(field.display == UNKNOWN and field.reason for field in view.fields.values())
    assert summarize_latency([artifact], evidence=mock_resolver) == ()
    assert calls == []


def test_P05_history_latency_in_sample_unbacked_metadata_never_becomes_facts():
    original = json.dumps({
        "fixture_label": "mock/in-sample", "run_id": None, "commit_sha": "a" * 40,
        "provider": {"effective": {"value": "ollama", "evidence": None, "reason": None}},
        "is_mock": False, "p50_ms": 9,
    }).encode()
    view = read_history(original)
    assert view.fields["run_id"].display == UNKNOWN
    assert view.fields["commit_sha"].display == UNKNOWN
    assert view.fields["provider.effective"].display == UNKNOWN
    assert view.fields["is_mock"].display == UNKNOWN
    assert view.document["p50_ms"] == 9
    assert view.original_bytes == original


def test_P05_history_latency_in_sample_supported_new_and_history_are_strict():
    artifact, sources = mock_timed_case()
    original = json.dumps(artifact).encode()
    for mode in ("new", "history"):
        view = read_artifact(original, mode=mode, evidence=sources)
        assert view.status == "valid" and view.valid_new_artifact
        assert view.fields["is_mock"].value is True
        assert view.latency_reportable
        assert view.original_bytes == original
    del artifact["storage_backend"]
    view = read_history(json.dumps(artifact).encode(), evidence=sources)
    assert view.status == "invalid" and not view.valid_new_artifact
    assert view.fields["storage_backend"].display == UNKNOWN


@pytest.mark.parametrize("original", [b"{", b"null", b"[]", b"NaN", b'{"start": Infinity}', b"\xff"])
def test_P05_history_latency_in_sample_invalid_json_retains_bytes(original):
    view = read_history(original)
    assert view.status == "invalid" and view.original_bytes == original
    assert not view.valid_new_artifact


def test_P05_history_latency_in_sample_reader_requires_explicit_valid_mode():
    with pytest.raises(TypeError):
        read_artifact(b"{}")
    with pytest.raises(ValueError):
        read_artifact(b"{}", mode="mock-in-sample-guess")
    with pytest.raises(TypeError):
        read_history("{}")


@pytest.mark.parametrize("flag", [True, False, None], ids=["true", "false", "unknown"])
@pytest.mark.parametrize("timing", [[], "mock/in-sample", 0, True, False])
def test_P05_history_latency_in_sample_timing_wrong_object_type(flag, timing):
    artifact, sources = mock_timed_case(flag)
    artifact["timing"] = timing
    assert not validate_artifact(artifact, evidence=sources).valid


@pytest.mark.parametrize("flag", [True, False, None], ids=["true", "false", "unknown"])
@pytest.mark.parametrize("field", TIMING_FIELDS)
@pytest.mark.parametrize("fault", ["missing", "null", "wrong_type"])
def test_P05_history_latency_in_sample_each_timing_field_all_flags(flag, field, fault):
    artifact, sources = mock_timed_case(flag)
    if fault == "missing":
        del artifact["timing"][field]
    elif fault == "null":
        artifact["timing"][field] = None
    else:
        artifact["timing"][field] = "125" if field in {"start", "end"} else 123
    result = validate_artifact(artifact, evidence=sources)
    assert not result.valid
    assert any(issue.path == f"timing.{field}" for issue in result.errors)
    assert summarize_latency([artifact], evidence=sources) == ()


@pytest.mark.parametrize("flag", [True, False, None], ids=["true", "false", "unknown"])
@pytest.mark.parametrize("field", ["start", "end"])
@pytest.mark.parametrize("value", ["100", True, False, float("nan"), float("inf"), float("-inf"), [], {}], ids=["string", "bool_true", "bool_false", "nan", "inf", "negative_inf", "list", "object"])
def test_P05_history_latency_in_sample_marks_no_coercion(flag, field, value):
    artifact, sources = mock_timed_case(flag)
    artifact["timing"][field] = value
    assert not validate_artifact(artifact, evidence=sources).valid


@pytest.mark.parametrize("flag", [True, False, None], ids=["true", "false", "unknown"])
@pytest.mark.parametrize("field", ["source_ref", "run_id", "clock_id", "unit", "scope"])
@pytest.mark.parametrize("value", ["", "  ", True, [], {}])
def test_P05_history_latency_in_sample_timing_string_types(flag, field, value):
    artifact, sources = mock_timed_case(flag)
    artifact["timing"][field] = value
    assert not validate_artifact(artifact, evidence=sources).valid


@pytest.mark.parametrize("flag", [True, False, None], ids=["true", "false", "unknown"])
@pytest.mark.parametrize("unit", ["s", "MS", "milliseconds"])
def test_P05_history_latency_in_sample_wrong_unit_all_flags(flag, unit):
    artifact, sources = mock_timed_case(flag)
    artifact["timing"]["unit"] = unit
    assert not validate_artifact(artifact, evidence=sources).valid


@pytest.mark.parametrize("flag", [True, False, None], ids=["true", "false", "unknown"])
def test_P05_history_latency_NEW_03_in_sample_run_mismatch_always_invalid(flag):
    artifact, sources = mock_timed_case(flag)
    artifact["timing"]["run_id"] = "mock-in-sample-other-run"
    assert not validate_artifact(artifact, evidence=sources).valid
    assert summarize_latency([artifact], evidence=sources) == ()


@pytest.mark.parametrize("flag", [True, False, None], ids=["true", "false", "unknown"])
def test_P05_history_latency_NEW_03_in_sample_reversed_marks_always_invalid(flag):
    artifact, sources = mock_timed_case(flag)
    artifact["timing"]["end"] = artifact["timing"]["start"] - 1
    assert not validate_artifact(artifact, evidence=sources).valid


@pytest.mark.parametrize("flag", [True, False, None], ids=["true", "false", "unknown"])
def test_P05_history_latency_in_sample_null_timing_only_nonreportable(flag):
    artifact, sources = mock_timed_case(flag)
    artifact["timing"] = None
    assert validate_artifact(artifact, evidence=sources).valid is (flag is not True)
    assert summarize_latency([artifact], evidence=sources) == ()


@pytest.mark.parametrize("changes", [
    {"clock_id": "mock-in-sample-different-clock"}, {"clock_id": None},
    {"monotonic": False}, {"same_process": False},
    {"monotonic": 1}, {"same_process": 1},
], ids=["wrong_clock", "missing_clock", "nonmonotonic", "different_process", "monotonic_not_bool", "same_process_not_bool"])
def test_P05_history_latency_NEW_02_in_sample_clock_evidence_resolved_via_source_ref(changes):
    artifact, sources = mock_timed_case()
    sources[TIMING_REF] = replace(sources[TIMING_REF], **changes)
    # Extra artifact keys cannot substitute for source attestations.
    artifact["timing"]["monotonic"] = True
    artifact["timing"]["same_process"] = True
    assert not validate_artifact(artifact, evidence=sources).valid
    assert summarize_latency([artifact], evidence=sources) == ()


@pytest.mark.parametrize("changes", [
    {"run_id": "mock-in-sample-other-run"}, {"execution": False},
    {"scope": "mock-in-sample-partial"}, {"outcome": "timeout"},
    {"outcome": "error"}, {"outcome": None},
], ids=["wrong_run", "not_execution", "wrong_scope", "timeout", "error", "unknown_outcome"])
def test_P05_history_latency_in_sample_reportable_requires_success_source(changes):
    artifact, sources = mock_timed_case()
    sources[TIMING_REF] = replace(sources[TIMING_REF], **changes)
    assert not validate_artifact(artifact, evidence=sources).valid
    assert summarize_latency([artifact], evidence=sources) == ()


@pytest.mark.parametrize("flag", [True, False, None], ids=["true", "false", "unknown"])
def test_P05_history_latency_in_sample_source_must_be_locatable(flag):
    artifact, sources = mock_timed_case(flag)
    del sources[TIMING_REF]
    assert not validate_artifact(artifact, evidence=sources).valid


@pytest.mark.parametrize("scope", ["timeout", "error", "retrieval_only", "dispatch_to_first_token"])
def test_P05_history_latency_in_sample_wrong_success_scope(scope):
    artifact, sources = mock_timed_case()
    artifact["timing"]["scope"] = scope
    assert not validate_artifact(artifact, evidence=sources).valid
    assert summarize_latency([artifact], evidence=sources) == ()


@pytest.mark.parametrize("flag", [False, None], ids=["false", "unknown"])
def test_P05_history_latency_in_sample_raw_marks_publish_no_percentiles(flag):
    artifact, sources = mock_timed_case(flag)
    artifact["timing"]["scope"] = "mock-in-sample-timeout"
    sources[TIMING_REF] = replace(
        sources[TIMING_REF], monotonic=False, same_process=False, outcome="timeout",
    )
    before = clone(artifact)
    assert validate_artifact(artifact, evidence=sources).valid
    assert summarize_latency([artifact], evidence=sources) == ()
    assert artifact == before


@pytest.mark.parametrize("reason", [None, "", "  ", True])
def test_P05_history_latency_in_sample_false_flag_requires_reason(reason):
    artifact, sources = mock_timed_case(False)
    artifact["latency_reportable"]["reason"] = reason
    assert not validate_artifact(artifact, evidence=sources).valid


def test_P05_history_latency_in_sample_valid_zero_and_numeric_timing_builder():
    artifact, sources = mock_timed_case()
    timing = artifact["timing"]
    timing["start"] = timing["end"] = 12.5
    assert validate_artifact(artifact, evidence=sources).valid
    built = make_timing(
        source_ref=TIMING_REF, run_id=artifact["run_id"], clock_id=timing["clock_id"],
        start=12.5, end=12.5, scope=timing["scope"], evidence=sources,
    )
    assert built == timing
    summary, = summarize_latency([artifact], evidence=sources)
    assert summary.group.label == "mock"
    assert summary.count == 1 and summary.p50_ms == summary.p95_ms == 0
    with pytest.raises(ValueError):
        make_timing(
            source_ref=TIMING_REF, run_id=artifact["run_id"], clock_id=timing["clock_id"],
            start="12.5", end=12.5, scope=timing["scope"], evidence=sources,
        )


def test_P05_history_latency_in_sample_normalizer_does_not_invent_timing():
    artifact, sources = mock_timed_case()
    before = clone(artifact)
    assert normalize_source(artifact, evidence=sources) == artifact
    assert artifact == before
    artifact["timing"]["end"] = -1
    normalized = normalize_source(artifact, evidence=sources)
    assert normalized["timing"] is None
    assert normalized["latency_reportable"]["value"] is None
    assert normalized["latency_reportable"]["reason"]
    assert validate_artifact(normalized, evidence=sources).valid


def test_P05_history_latency_in_sample_aggregation_shares_source_scope_and_separates_status():
    # Only synthetic fixture records, including the artificial verified-shaped
    # record. These assertions verify grouping, never actual provider quality.
    samples = []
    registry = {}
    for index, (state, duration) in enumerate([
        ("mock", 10), ("mock", 30), ("mock", 20), ("unknown", 90), ("verified_shape", 80),
    ]):
        artifact, sources = mock_timed_case()
        if state != "mock":
            artifact["provider"]["effective"] = unknown_slot("Mock/in-sample provider unknown")
            if state == "unknown":
                artifact["is_mock"] = unknown_slot("Mock/in-sample state unknown")
                artifact["llm_verified"] = unknown_slot("Mock/in-sample response unknown")
            else:
                attest(artifact, sources, "is_mock", False)
                attest(artifact, sources, "llm_verified", True)
                sources[EXECUTION_REF] = replace(sources[EXECUTION_REF], real_llm_response=True)
        run_id = f"mock-in-sample-aggregate-{index}"
        artifact["run_id"] = artifact["timing"]["run_id"] = run_id
        artifact["timing"]["end"] = artifact["timing"]["start"] + duration
        for ref, source in sources.items():
            registry[(ref, run_id)] = replace(source, run_id=run_id)
        samples.append(artifact)

    def mock_resolver(reference, run_id):
        return registry.get((reference, run_id))

    summaries = summarize_latency(samples, evidence=mock_resolver)
    assert len(summaries) == 3
    mock_summary = next(item for item in summaries if item.group.label == "mock")
    assert mock_summary.count == 3
    assert mock_summary.p50_ms == 20 and mock_summary.p95_ms == 30
    assert {item.group.is_mock for item in summaries} == {True, False, None}
    assert next(item for item in summaries if item.group.is_mock is None).group.label == UNKNOWN
    verified = next(item for item in summaries if item.group.is_mock is False)
    assert verified.group.label == "in-sample"
    assert verified.group.label != "response-verified"
    assert verified.group.evidence_kind == "fixture"


@pytest.mark.parametrize("dimension", [
    "provider.effective", "model.effective", "execution_path", "storage_backend",
    "acl_enabled", "commit_sha", "source_ref",
])
def test_P05_history_latency_in_sample_effective_provenance_groups_stay_separate(dimension):
    first, first_sources = mock_timed_case()
    second, second_sources = mock_timed_case()
    values = {
        "provider.effective": "ollama", "model.effective": "mock-in-sample-other-model",
        "execution_path": "rag", "storage_backend": "persistent", "acl_enabled": False,
        "commit_sha": "a" * 40,
    }
    if dimension == "source_ref":
        new_ref = "fixture:mock-in-sample#other-timing"
        second["timing"]["source_ref"] = new_ref
        second_sources[new_ref] = second_sources.pop(TIMING_REF)
    else:
        attest(second, second_sources, dimension, values[dimension])
    second["run_id"] = second["timing"]["run_id"] = "mock-in-sample-second-group"
    second_sources = {
        ref: replace(source, run_id=second["run_id"]) for ref, source in second_sources.items()
    }

    def mock_resolver(reference, run_id):
        return (first_sources if run_id == first["run_id"] else second_sources).get(reference)

    assert len(summarize_latency([first, second], evidence=mock_resolver)) == 2


def test_P05_history_latency_in_sample_versionless_never_promotes_or_resolves():
    """Versionless history with a string run_id and a resolvable slot must
    keep every field UNKNOWN and must not call the evidence resolver."""
    artifact, sources = mock_timed_case()
    artifact.pop("schema_version", None)
    calls = []

    def mock_resolver(reference, run_id):
        calls.append((reference, run_id))
        return sources.get(reference)

    view = read_history(json.dumps(artifact).encode(), evidence=mock_resolver)
    assert view.status == "versionless"
    assert isinstance(artifact["run_id"], str) and artifact["run_id"]
    for path, field in view.fields.items():
        assert field.value is None and field.display == UNKNOWN and field.reason, path
    assert view.fields["run_id"].value is None
    assert calls == []


def test_P05_history_latency_in_sample_invalid_does_not_interpret_fields():
    artifact, sources = mock_timed_case()
    del artifact["storage_backend"]
    calls = []

    def mock_resolver(reference, run_id):
        calls.append((reference, run_id))
        return sources.get(reference)

    view = read_history(json.dumps(artifact).encode(), evidence=mock_resolver)
    assert view.status == "invalid"
    for field in view.fields.values():
        assert field.value is None and field.display == UNKNOWN and field.reason
    # Validation may consult evidence to decide status; field promotion must not.
    assert view.fields["run_id"].value is None


def test_P05_history_latency_in_sample_mixed_evidence_kind_never_response_verified():
    """A log-backed timing source plus a fixture-backed llm_verified claim
    must stay labelled in-sample, never response-verified."""
    artifact, sources = mock_timed_case()
    artifact["provider"]["effective"] = unknown_slot("Mock/in-sample provider unknown")
    attest(artifact, sources, "is_mock", False)
    attest(artifact, sources, "llm_verified", True)
    sources[EXECUTION_REF] = replace(sources[EXECUTION_REF], real_llm_response=True)
    sources[TIMING_REF] = replace(sources[TIMING_REF], kind="log")
    summaries = summarize_latency([artifact], evidence=sources)
    assert len(summaries) == 1
    assert summaries[0].group.evidence_kind == "fixture"
    assert summaries[0].group.label == "in-sample"
    assert summaries[0].group.label != "response-verified"


def test_P05_history_latency_in_sample_log_verified_fixture_timing_is_in_sample():
    """The reverse mix (log-backed verification, fixture timing) is also
    in-sample, never response-verified."""
    artifact, sources = mock_timed_case()
    artifact["provider"]["effective"] = unknown_slot("Mock/in-sample provider unknown")
    attest(artifact, sources, "is_mock", False)
    log_ref = "log:mock-in-sample#verified"
    artifact["llm_verified"] = {"value": True, "evidence": log_ref, "reason": None}
    sources[log_ref] = replace(
        sources[EXECUTION_REF], kind="log", real_llm_response=True,
        claims={**sources[EXECUTION_REF].claims, "llm_verified": True, "is_mock": False},
    )
    sources[EXECUTION_REF] = replace(
        sources[EXECUTION_REF],
        claims={**sources[EXECUTION_REF].claims, "is_mock": False},
    )
    assert validate_artifact(artifact, evidence=sources).valid
    summaries = summarize_latency([artifact], evidence=sources)
    assert len(summaries) == 1
    assert summaries[0].group.evidence_kind == "fixture"
    assert summaries[0].group.label == "in-sample"
