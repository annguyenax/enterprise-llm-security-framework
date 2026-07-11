"""Storage-agnostic retriever contract (Phase 12B).

The only implementation as of Phase 12B is `SqliteBM25Retriever`
(`app/retrieval/sqlite_bm25.py`), per `docs/decisions/ADR-002-retrieval-engine.md`.
A future vector or hybrid retriever (optional Phase 12F, requires its own
ADR) would implement this same contract so callers (the ingestion service,
and later the RAG Query Service in Phase 12C) do not need to change.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.retrieval.models import (
    ChunkRecord,
    DocumentRecord,
    IngestionBatchResult,
    RetrievalQuery,
    RetrievalResult,
)


class Retriever(ABC):
    @abstractmethod
    def initialize(self) -> None:
        """Run capability checks and ensure the storage schema exists.

        Must fail loudly (raise) if the storage backend cannot support the
        required retrieval capability -- see
        docs/decisions/ADR-002-retrieval-engine.md for why there is no
        silent-fallback mode for the SQLite FTS5 implementation.
        """

    @abstractmethod
    def upsert_documents(
        self, prepared: list[tuple[DocumentRecord, list[ChunkRecord]]]
    ) -> IngestionBatchResult:
        """Atomically index, update, or leave unchanged a batch of
        already-validated, already-policy-resolved documents and their
        chunks. Callers (the ingestion service) are responsible for
        validation, source-policy resolution, and chunking before calling
        this method -- this method only persists what it is given."""

    @abstractmethod
    def search(self, query: RetrievalQuery) -> RetrievalResult:
        """Return ranked retrieval hits for a query, bounded by
        `query.top_k`. Must never perform a network call and must never
        invoke a guard or an LLM provider -- this is retrieval only."""

    @abstractmethod
    def get_document(self, document_id: str) -> DocumentRecord | None:
        """Return one document's metadata, or None if not found."""

    @abstractmethod
    def delete_document(self, document_id: str) -> bool:
        """Remove a document and its chunks/index rows. Returns True if a
        document was actually deleted. Provided for test support and
        completeness; not exposed via any Phase 12B API endpoint."""
