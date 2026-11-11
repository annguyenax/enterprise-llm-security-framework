"""A04: provider-double timeout fails closed (mock/in-sample doubles only).

Provider double timeout -> ERROR/BLOCK record with a reason; no
real-response, not counted as guard-success, never used as success
latency. A double's error proves nothing about real provider availability.
"""

from __future__ import annotations

import pytest

from ._doubles import (
    GuardOutcomeRecorder, LatencyRecorder, ProviderDouble, ProviderErrorRecord,
    guarded_generate,
)

REQUIRED_BRANCHES = [
    "provider_timeout_error",
    "not_counted_success",
    "no_latency_sample",
    "no_availability_claim",
    "success_control",
]


def _timed_out():
    provider = ProviderDouble()
    provider.inject_timeout()
    outcomes = GuardOutcomeRecorder()
    latency = LatencyRecorder()
    record = guarded_generate(provider, "in-sample prompt",
                              outcomes=outcomes, latency=latency)
    assert isinstance(record, ProviderErrorRecord)
    return record, outcomes, latency


def test_A04_provider_timeout_error_with_reason_no_response():
    record, _, _ = _timed_out()
    assert record.ok is False
    assert record.status == "ERROR"
    assert record.reason, "error record must carry a reason"
    assert record.has_response is False
    assert record.label == "mock/in-sample"


def test_A04_provider_timeout_not_counted_success():
    _, outcomes, _ = _timed_out()
    assert outcomes.outcomes == ["BLOCK"]
    assert outcomes.guard_successes == 0


def test_A04_provider_timeout_no_latency_sample():
    _, _, latency = _timed_out()
    assert latency.samples == [], (
        "timeout must not feed the success-latency distribution")


def test_A04_provider_timeout_no_availability_claim():
    record, _, _ = _timed_out()
    assert record.counted_as_success is False
    assert record.latency_sample is None
    assert "unknown" in record.availability
    assert "double" in record.availability


def test_A04_provider_timeout_success_control_proves_harness():
    provider = ProviderDouble()
    outcomes = GuardOutcomeRecorder()
    latency = LatencyRecorder()
    result = guarded_generate(provider, "in-sample prompt",
                              outcomes=outcomes, latency=latency)
    assert result["ok"] is True
    assert result["response"]["is_real"] is False
    assert outcomes.guard_successes == 1
    assert len(latency.samples) == 1
