"""A03: retrieval timeout fails closed (mock/in-sample doubles only).

Injected retrieval timeout -> safe BLOCKED result with a reason, zero
unauthorized chunks, no downstream provider call. A timeout never becomes
an empty successful retrieval.
"""

from __future__ import annotations

import pytest

from ._doubles import (
    ProviderDouble, RetrievalDouble, guarded_retrieve, retrieve_then_generate,
    sample_chunks,
)

REQUIRED_BRANCHES = [
    "retrieval_timeout_blocked",
    "timeout_drops_partial",
    "no_downstream_call",
    "success_control",
]


def test_A03_retrieval_timeout_blocked_with_reason_not_empty_success():
    retrieval = RetrievalDouble(sample_chunks())
    retrieval.inject("timeout")
    result = guarded_retrieve(retrieval, "in-sample query")
    assert result.ok is False
    assert result.status == "BLOCKED"
    assert result.reason, "blocked result must carry a reason"
    assert result.chunks == ()
    assert result.status != "success"
    assert result.label == "mock/in-sample"


def test_A03_retrieval_timeout_drops_partial_staged_chunks():
    retrieval = RetrievalDouble(sample_chunks())
    retrieval.stage_partial(sample_chunks())
    retrieval.inject("timeout")
    result = guarded_retrieve(retrieval, "in-sample query")
    assert result.ok is False
    assert result.chunks == (), "staged partial chunks must not leak"


def test_A03_retrieval_timeout_no_downstream_call():
    retrieval = RetrievalDouble(sample_chunks())
    retrieval.inject("timeout")
    provider = ProviderDouble()
    result = retrieve_then_generate(retrieval, provider, "in-sample query")
    assert result.ok is False
    assert result.provider_called is False
    assert provider.calls == [], "provider must not be contacted after timeout"


def test_A03_retrieval_timeout_success_control_proves_harness():
    retrieval = RetrievalDouble(sample_chunks())
    provider = ProviderDouble()
    result = retrieve_then_generate(retrieval, provider, "in-sample query")
    assert result.ok is True
    assert result.status == "success"
    assert len(result.chunks) == 2
    assert result.provider_called is True
    assert len(provider.calls) == 1


def test_A03_retrieval_timeout_staged_chunks_included_on_success():
    """On the success path, staged chunks are in the result so a timeout
    leak would be observable if drop-on-fault were forgotten."""
    extras = sample_chunks()
    retrieval = RetrievalDouble(())
    retrieval.stage_partial(extras)
    result = guarded_retrieve(retrieval, "in-sample query")
    assert result.ok is True
    assert result.chunks == extras
