"""Writer-only normalization of incomplete sources; never a validating reader."""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy

from .schema import (
    SCHEMA_VERSION, SLOT_PATHS, EvidenceResolver, ProvenanceSlot, nonempty_string,
    slot_at, slot_value,
)
from .timing import validate_timing
from .validate import _slot_errors


def unknown_slot(reason: str) -> ProvenanceSlot:
    if not nonempty_string(reason):
        raise ValueError("UNKNOWN requires a non-empty reason")
    return {"value": None, "evidence": None, "reason": reason}


def normalize_source(
    source: Mapping[str, object], *, run_id: str | None = None,
    evidence: EvidenceResolver | None = None,
) -> dict[str, object]:
    """Create a full writer structure from partial provenance-slot metadata.

    Missing or unsupported claims become UNKNOWN. Raw strings and booleans
    without slots/evidence do not become claims. No IDs, SHA, effective values,
    provider, execution, ACL or non-mock state are inferred. The caller must
    supply an actual run_id; without one this result remains invalid for NEW
    emission. Validation of an emitted artifact must call validate_artifact
    directly, not this function. Unsupported versions cannot be upgraded here.
    """
    if source.get("schema_version") not in (None, SCHEMA_VERSION):
        raise ValueError("cannot normalize an unsupported schema_version")
    selected_run = run_id if run_id is not None else source.get("run_id")
    result: dict[str, object] = {
        "schema_version": SCHEMA_VERSION, "run_id": selected_run,
        "provider": {}, "model": {}, "timing": None,
    }
    for path in SLOT_PATHS:
        candidate = slot_at(source, path)
        slot = (
            deepcopy(dict(candidate))
            if not _slot_errors(path, candidate, selected_run, evidence)
            else unknown_slot(f"No usable source evidence for {path}")
        )
        if "." in path:
            parent, child = path.split(".")
            result[parent][child] = slot
        else:
            result[path] = slot

    # Mock execution can support false verification using its own evidence.
    # Never infer true from is_mock=false or copy requested onto effective.
    mock_slot = None
    for path, value in (("is_mock", True), ("provider.effective", "mock")):
        if slot_value(result, path) == value:
            mock_slot = slot_at(result, path)
            break
    if mock_slot is not None:
        original_verified = slot_at(source, "llm_verified")
        claimed_true = (
            isinstance(original_verified, Mapping)
            and original_verified.get("value") is True
        )
        if claimed_true:
            # Do not silently overwrite a claimed true into a clean false.
            result["llm_verified"] = unknown_slot(
                "NEW-01: mock evidence contradicts llm_verified=true"
            )
        elif slot_value(result, "llm_verified") is None:
            candidate = {"value": False, "evidence": mock_slot["evidence"], "reason": None}
            if not _slot_errors("llm_verified", candidate, selected_run, evidence):
                result["llm_verified"] = candidate

    timing = source.get("timing")
    if timing is not None and validate_timing(
        timing, run_id=selected_run,
        reportable=slot_value(result, "latency_reportable") is True,
        evidence=evidence,
    ).valid:
        result["timing"] = deepcopy(timing)
    elif slot_value(result, "latency_reportable") is True:
        result["latency_reportable"] = unknown_slot("No valid reportable timing evidence")
    return result
