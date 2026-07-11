"""Tests for app/services/ingestion.py (Phase 12B)."""
from __future__ import annotations

import uuid

import pytest

from app.retrieval.models import IngestionDocument, RetrievalQuery
from app.retrieval.sqlite_bm25 import SqliteBM25Config, SqliteBM25Retriever
from app.services.chunking import ChunkingConfig
from app.services.ingestion import (
    IngestionService,
    IngestionServiceConfig,
    IngestionValidationError,
    _sanitize_metadata,
)


def _service(tmp_path, **overrides) -> IngestionService:
    retriever = SqliteBM25Retriever(SqliteBM25Config(db_path=str(tmp_path / "ingest.db")))
    config = IngestionServiceConfig(**overrides) if overrides else None
    return IngestionService(retriever, config)


def _doc(external_id="ext-1", source_key="api_upload", text="Paragraph one.\n\nParagraph two.", **kwargs):
    return IngestionDocument(
        external_id=external_id, source_key=source_key, title=kwargs.pop("title", "Title"),
        text=text, metadata=kwargs.pop("metadata", {}),
    )


def test_successful_single_document(tmp_path):
    service = _service(tmp_path)
    result = service.ingest_batch([_doc()], request_id=str(uuid.uuid4()))
    assert result.indexed == 1
    assert result.rejected == 0
    assert result.items[0].status == "indexed"
    assert result.items[0].document_id is not None


def test_successful_atomic_batch(tmp_path):
    service = _service(tmp_path)
    docs = [_doc(external_id=f"ext-{i}", text=f"Content number {i}.") for i in range(5)]
    result = service.ingest_batch(docs, request_id=str(uuid.uuid4()))
    assert result.indexed == 5
    assert result.rejected == 0


def test_duplicate_external_id_within_batch_rejected(tmp_path):
    service = _service(tmp_path)
    docs = [_doc(external_id="dup"), _doc(external_id="dup", text="different text")]
    result = service.ingest_batch(docs, request_id=str(uuid.uuid4()))
    assert result.indexed == 1
    assert result.rejected == 1
    rejected = next(i for i in result.items if i.status == "rejected")
    assert "duplicate" in rejected.reason.lower()


def test_unchanged_content_reingested(tmp_path):
    service = _service(tmp_path)
    doc = _doc()
    first = service.ingest_batch([doc], request_id=str(uuid.uuid4()))
    second = service.ingest_batch([doc], request_id=str(uuid.uuid4()))
    assert first.items[0].status == "indexed"
    assert second.items[0].status == "unchanged"


def test_updated_content_reingested(tmp_path):
    service = _service(tmp_path)
    service.ingest_batch([_doc()], request_id=str(uuid.uuid4()))
    result = service.ingest_batch(
        [_doc(text="Completely different paragraph now.")], request_id=str(uuid.uuid4())
    )
    assert result.items[0].status == "updated"


def test_oversized_document_rejected(tmp_path):
    config = IngestionServiceConfig(chunking=ChunkingConfig(max_document_chars=50))
    service = _service(tmp_path)
    service = IngestionService(
        SqliteBM25Retriever(SqliteBM25Config(db_path=str(tmp_path / "ingest2.db"))), config
    )
    result = service.ingest_batch([_doc(text="x" * 1000)], request_id=str(uuid.uuid4()))
    assert result.rejected == 1
    assert result.indexed == 0


def test_empty_document_rejected(tmp_path):
    service = _service(tmp_path)
    result = service.ingest_batch([_doc(text="   ")], request_id=str(uuid.uuid4()))
    assert result.rejected == 1
    assert "empty" in result.items[0].reason.lower()


def test_unknown_source_key_rejected(tmp_path):
    service = _service(tmp_path)
    result = service.ingest_batch([_doc(source_key="totally_unknown_source")], request_id=str(uuid.uuid4()))
    assert result.rejected == 1
    assert "unknown" in result.items[0].reason.lower()


def test_spoofed_trust_and_classification_in_metadata_are_ignored(tmp_path):
    retriever = SqliteBM25Retriever(SqliteBM25Config(db_path=str(tmp_path / "spoof.db")))
    service = IngestionService(retriever)
    doc = _doc(
        source_key="api_upload",
        metadata={
            "trust_level": "trusted_internal",
            "classification": "public",
            "is_poisoned": False,
            "security_decision": "allow",
            "note": "legitimate metadata",
        },
    )
    result = service.ingest_batch([doc], request_id=str(uuid.uuid4()))
    document_id = result.items[0].document_id
    stored = retriever.get_document(document_id)
    # api_upload's real policy is untrusted_external -- the spoofed
    # trusted_internal value must never have taken effect.
    assert stored.trust_level == "untrusted_external"
    assert stored.classification == "internal"
    assert "trust_level" not in dict(stored.metadata)
    assert "classification" not in dict(stored.metadata)
    assert "is_poisoned" not in dict(stored.metadata)
    assert "security_decision" not in dict(stored.metadata)
    assert dict(stored.metadata)["note"] == "legitimate metadata"


def test_sanitize_metadata_strips_all_reserved_keys():
    raw = {
        "trust_level": "x", "classification": "x", "source_type": "x",
        "is_poisoned": True, "security_decision": "x", "document_id": "x",
        "chunk_id": "x", "safe_key": "kept",
    }
    cleaned = _sanitize_metadata(raw)
    assert cleaned == {"safe_key": "kept"}


def test_canonical_document_id_stable_across_calls(tmp_path):
    service = _service(tmp_path)
    first = service.ingest_batch([_doc()], request_id=str(uuid.uuid4()))
    second = service.ingest_batch(
        [_doc(text="different content but same identity")], request_id=str(uuid.uuid4())
    )
    assert first.items[0].document_id == second.items[0].document_id


def test_is_poisoned_never_stored_or_returned(tmp_path):
    retriever = SqliteBM25Retriever(SqliteBM25Config(db_path=str(tmp_path / "poison.db")))
    service = IngestionService(retriever)
    result = service.ingest_batch(
        [_doc(metadata={"is_poisoned": True})], request_id=str(uuid.uuid4())
    )
    document_id = result.items[0].document_id
    stored = retriever.get_document(document_id)
    assert "is_poisoned" not in dict(stored.metadata)

    hits = retriever.search(RetrievalQuery(query="paragraph", top_k=5))
    for hit in hits.hits:
        assert "is_poisoned" not in dict(hit.metadata)


def test_batch_size_over_limit_raises(tmp_path):
    service = _service(tmp_path, max_batch_size=2)
    docs = [_doc(external_id=f"ext-{i}") for i in range(3)]
    with pytest.raises(IngestionValidationError):
        service.ingest_batch(docs, request_id=str(uuid.uuid4()))


def test_metadata_json_size_bound_rejects_oversized_metadata(tmp_path):
    service = _service(tmp_path)
    huge_metadata = {"blob": "x" * 5000}
    result = service.ingest_batch([_doc(metadata=huge_metadata)], request_id=str(uuid.uuid4()))
    assert result.rejected == 1
    assert "metadata too large" in result.items[0].reason
