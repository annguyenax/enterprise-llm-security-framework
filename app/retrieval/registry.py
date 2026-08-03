"""Collaboration seam for retriever backends (see ADR-004).

New retrieval backends — e.g. an enterprise vector / knowledge-base retriever —
implement the :class:`app.retrieval.base.Retriever` ABC and register a factory
here, so the gateway/pipeline can select a backend by name via configuration
**without** editing gateway code. The default backend remains the existing
SQLite FTS5/BM25 retriever so current demos and evaluations do not change.

This module is additive and imports no concrete backend, so registering a new
retriever never forces a change to shared gateway files.
"""
from __future__ import annotations

from typing import Any, Callable

from app.retrieval.base import Retriever

RetrieverFactory = Callable[..., Retriever]

_RETRIEVER_REGISTRY: dict[str, RetrieverFactory] = {}


def register_retriever(name: str, factory: RetrieverFactory) -> None:
    """Register a retriever factory under a normalized name. Fail-closed on a
    duplicate or empty name so two workstreams cannot silently collide."""
    key = name.strip().lower()
    if not key:
        raise ValueError("retriever name must be non-empty")
    if key in _RETRIEVER_REGISTRY:
        raise ValueError(f"retriever {key!r} is already registered")
    _RETRIEVER_REGISTRY[key] = factory


def available_retrievers() -> tuple[str, ...]:
    """Return the sorted names of currently registered retrievers."""
    return tuple(sorted(_RETRIEVER_REGISTRY))


def get_retriever(name: str, *args: Any, **kwargs: Any) -> Retriever:
    """Construct a registered retriever, rejecting unknown names (fail-closed)."""
    key = name.strip().lower()
    factory = _RETRIEVER_REGISTRY.get(key)
    if factory is None:
        raise ValueError(
            f"Unsupported retriever {name!r}. Registered: {list(available_retrievers())}."
        )
    return factory(*args, **kwargs)
