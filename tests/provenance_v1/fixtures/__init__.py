"""All generated data here is mock/in-sample, including verification doubles."""
from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

from app.provenance import EvidenceSource, SUCCESS_SCOPE, unknown_slot

FIXTURES = Path(__file__).parent
REQUEST_REF = "fixture:mock-in-sample#request"
EXECUTION_REF = "fixture:mock-in-sample#execution"
TIMING_REF = "fixture:mock-in-sample#timing"


def mock_case() -> tuple[dict[str, object], dict[str, EvidenceSource]]:
    fixture = json.loads((FIXTURES / "mock_in_sample.json").read_bytes())
    assert "mock/in-sample" in fixture["fixture_label"]
    return fixture["artifact"], {
        reference: EvidenceSource(**source)
        for reference, source in fixture["evidence"].items()
    }


def mock_slot(value: object, reference: str = EXECUTION_REF, reason: str | None = None):
    return {"value": value, "evidence": reference, "reason": reason}


def get_slot(artifact, path):
    if "." in path:
        parent, child = path.split(".")
        return artifact[parent][child]
    return artifact[path]


def put_slot(artifact, path, slot):
    if "." in path:
        parent, child = path.split(".")
        artifact[parent][child] = slot
    else:
        artifact[path] = slot


def attest(artifact, sources, path, value, *, reference=None, reason=None):
    """Change a mock/in-sample value and its corresponding source together."""
    ref = reference or get_slot(artifact, path).get("evidence") or EXECUTION_REF
    put_slot(artifact, path, mock_slot(value, ref, reason))
    source = sources[ref]
    sources[ref] = replace(source, claims={**source.claims, path: value})


def mock_timed_case(flag: bool | None = True):
    artifact, sources = mock_case()
    if flag is None:
        artifact["latency_reportable"] = unknown_slot("Mock/in-sample reportability unknown")
    else:
        attest(
            artifact, sources, "latency_reportable", flag,
            reason=None if flag else "Mock/in-sample raw timing excluded",
        )
    artifact["timing"] = {
        "source_ref": TIMING_REF, "run_id": artifact["run_id"],
        "clock_id": "mock-in-sample-monotonic-clock", "start": 100, "end": 125.5,
        "unit": "ms", "scope": SUCCESS_SCOPE,
    }
    sources[TIMING_REF] = EvidenceSource(
        kind="fixture", run_id=artifact["run_id"], execution=True,
        clock_id="mock-in-sample-monotonic-clock", monotonic=True, same_process=True,
        scope=SUCCESS_SCOPE, outcome="success",
    )
    return artifact, sources


def mock_verification_candidate():
    """Artificial positive attestation; never evidence of an actual response."""
    artifact, sources = mock_case()
    artifact["provider"]["effective"] = unknown_slot("Mock/in-sample provider unknown")
    attest(artifact, sources, "is_mock", False)
    attest(artifact, sources, "llm_verified", True)
    sources[EXECUTION_REF] = replace(sources[EXECUTION_REF], real_llm_response=True)
    return artifact, sources


def clone(value):
    return deepcopy(value)
