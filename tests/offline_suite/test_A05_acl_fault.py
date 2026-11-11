"""A05: retrieval/embedding/ACL faults fail closed (mock/in-sample doubles).

Each fault injected separately. Never return unauthorized chunks --
including partial or cached output. Undefined authorization fails closed;
the pipeline never continues as if granted.
"""

from __future__ import annotations

import pytest

from ._doubles import (
    ACLDouble, Chunk, ChunkCacheDouble, EmbeddingDouble, RetrievalDouble,
    sample_chunks, secure_retrieve,
)

REQUIRED_BRANCHES = [
    "retrieval_fault_closed",
    "embedding_fault_closed",
    "acl_fault_closed",
    "undefined_denied",
    "cache_no_bypass",
    "partial_dropped",
    "explicit_deny",
]

GRANTS = {("alice", "c1"): True, ("alice", "c2"): True}


def _pipeline(retrieval=None, embedding=None, acl=None, cache=None):
    return (retrieval or RetrievalDouble(sample_chunks()),
            embedding or EmbeddingDouble(),
            acl or ACLDouble(dict(GRANTS)),
            cache or ChunkCacheDouble())


def test_A05_acl_fault_retrieval_fault_closed_zero_chunks():
    retrieval, embedding, acl, cache = _pipeline()
    retrieval.inject("fault")
    result = secure_retrieve(retrieval, embedding, acl, cache,
                             query="q", user="alice")
    assert result.ok is False
    assert result.status == "BLOCKED"
    assert result.reason
    assert result.chunks == ()


def test_A05_acl_fault_embedding_fault_closed_drops_retrieved():
    retrieval, embedding, acl, cache = _pipeline()
    embedding.inject_fault()
    result = secure_retrieve(retrieval, embedding, acl, cache,
                             query="q", user="alice")
    assert result.ok is False
    assert result.status == "BLOCKED"
    assert result.chunks == (), "retrieved candidates must be dropped"
    assert embedding.calls, "embedding stage must actually have run"


def test_A05_acl_fault_acl_fault_closed_zero_chunks():
    retrieval, embedding, acl, cache = _pipeline()
    acl.inject_fault()
    result = secure_retrieve(retrieval, embedding, acl, cache,
                             query="q", user="alice")
    assert result.ok is False
    assert result.status == "BLOCKED"
    assert result.reason
    assert result.chunks == ()


def test_A05_acl_fault_undefined_denied_fail_closed():
    retrieval, embedding, _, cache = _pipeline()
    acl = ACLDouble({("alice", "c1"): True})  # c2 verdict undefined.
    result = secure_retrieve(retrieval, embedding, acl, cache,
                             query="q", user="alice")
    assert result.ok is False
    assert result.status == "BLOCKED"
    assert "c2" in result.reason
    assert result.chunks == (), "undefined verdict must not continue as granted"


def test_A05_acl_fault_cache_no_bypass_for_deny_or_fault():
    stolen = (Chunk("c9", "bob-only chunk", "bob"),)
    # Cache hit re-checked: unauthorized cached chunk is denied.
    retrieval, embedding, acl, cache = _pipeline()
    cache.put("q", stolen)
    result = secure_retrieve(retrieval, embedding, acl, cache,
                             query="q", user="alice")
    assert result.chunks == ()
    assert all(c.owner != "bob" or c.id not in ("c9",) for c in result.chunks)
    # Cache hit + ACL fault: fail closed, cache serves nothing.
    retrieval, embedding, _, _ = _pipeline()
    cache = ChunkCacheDouble()
    cache.put("q", sample_chunks())  # Even fully authorized cached chunks...
    acl = ACLDouble(dict(GRANTS))
    acl.inject_fault()
    result = secure_retrieve(retrieval, embedding, acl, cache,
                             query="q", user="alice")
    assert result.ok is False
    assert result.chunks == ()


def test_A05_acl_fault_partial_dropped_on_midway_fault():
    retrieval, embedding, _, cache = _pipeline()
    acl = ACLDouble(script=["grant", "fault"])  # c1 granted, then fault.
    result = secure_retrieve(retrieval, embedding, acl, cache,
                             query="q", user="alice")
    assert result.ok is False
    assert result.status == "BLOCKED"
    assert result.chunks == (), "partial grants must be dropped on fault"


def test_A05_acl_fault_explicit_deny_leaks_nothing():
    retrieval, embedding, _, cache = _pipeline()
    acl = ACLDouble({("alice", "c1"): False, ("alice", "c2"): False})
    result = secure_retrieve(retrieval, embedding, acl, cache,
                             query="q", user="alice")
    assert result.chunks == ()
    assert all(c.owner == "alice" for c in result.chunks)
