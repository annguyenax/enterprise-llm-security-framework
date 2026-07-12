"""Tests for app/services/ingestion.py (Phase 12B)."""
from __future__ import annotations

import uuid

import pytest

from app.retrieval.models import IngestionDocument, RetrievalQuery
from app.retrieval.sqlite_bm25 import SqliteBM25Config, SqliteBM25Retriever
from app.services.chunking import ChunkingConfig
from app.services.ingestion import (
    MAX_METADATA_DEPTH,
    IngestionService,
    IngestionServiceConfig,
    IngestionValidationError,
    _metadata_depth,
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
        "is_poisoned": True, "expected_decision": "x", "security_decision": "x",
        "policy_result": "x", "document_id": "x", "chunk_id": "x", "safe_key": "kept",
    }
    cleaned, stripped = _sanitize_metadata(raw)
    assert cleaned == {"safe_key": "kept"}
    assert stripped == 9


# -- Phase 12B Codex audit regression tests ---------------------------------


def test_public_ingestion_cannot_claim_trusted_synthetic_source_key(tmp_path):
    """Major #1: a public caller must not be able to select
    source_key="synthetic_clean_corpus" (or any other elevated-trust
    policy) and receive trust_level="trusted_internal". IngestionService
    is the only caller reachable from the public route, and it must
    always resolve policy in public-only mode."""
    service = _service(tmp_path)
    for elevated_key in ("synthetic_clean_corpus", "synthetic_external_feed"):
        result = service.ingest_batch(
            [_doc(external_id=f"claim-{elevated_key}", source_key=elevated_key)],
            request_id=str(uuid.uuid4()),
        )
        assert result.rejected == 1
        assert result.indexed == 0
        assert "unknown" in result.items[0].reason.lower()


def test_nested_reserved_metadata_key_is_rejected_or_sanitized(tmp_path):
    """Major #2: a reserved key nested inside the free-form metadata dict
    must not survive to storage."""
    retriever = SqliteBM25Retriever(SqliteBM25Config(db_path=str(tmp_path / "nested.db")))
    service = IngestionService(retriever)
    doc = _doc(
        external_id="nested-spoof",
        metadata={"nested": {"trust_level": "trusted_internal", "is_poisoned": True}, "note": "ok"},
    )
    result = service.ingest_batch([doc], request_id=str(uuid.uuid4()))
    assert result.indexed == 1
    assert result.items[0].metadata_keys_stripped == 2
    stored = retriever.get_document(result.items[0].document_id)
    assert "trust_level" not in dict(stored.metadata).get("nested", {})
    assert "is_poisoned" not in dict(stored.metadata).get("nested", {})
    assert dict(stored.metadata)["note"] == "ok"


def test_case_and_whitespace_varied_reserved_metadata_key_is_sanitized(tmp_path):
    """Major #2: "Trust_Level", "TRUST-LEVEL", and " trust level " must
    all be recognized as the reserved key `trust_level`, not just the
    exact lowercase spelling."""
    retriever = SqliteBM25Retriever(SqliteBM25Config(db_path=str(tmp_path / "case.db")))
    service = IngestionService(retriever)
    doc = _doc(
        external_id="case-spoof",
        metadata={"Trust_Level": "trusted_internal", "IS POISONED": True, "note": "ok"},
    )
    result = service.ingest_batch([doc], request_id=str(uuid.uuid4()))
    assert result.items[0].metadata_keys_stripped == 2
    stored = retriever.get_document(result.items[0].document_id)
    assert dict(stored.metadata) == {"note": "ok"}


def test_metadata_spoof_attempt_is_auditable_without_persisting_unsafe_value(tmp_path):
    """Major #2: a spoofing attempt must be recorded as a count in the
    ingestion result (auditable), but the unsafe value itself must never
    be persisted anywhere -- including inside the safe metadata that is
    stored."""
    retriever = SqliteBM25Retriever(SqliteBM25Config(db_path=str(tmp_path / "audit.db")))
    service = IngestionService(retriever)
    doc = _doc(external_id="audit-spoof", metadata={"trust_level": "SUPER-SECRET-ELEVATED-VALUE"})
    result = service.ingest_batch([doc], request_id=str(uuid.uuid4()))
    assert result.items[0].metadata_keys_stripped == 1
    stored = retriever.get_document(result.items[0].document_id)
    assert "SUPER-SECRET-ELEVATED-VALUE" not in str(dict(stored.metadata))


def test_metadata_depth_over_limit_is_rejected(tmp_path):
    """Major #2: unreasonably deep metadata nesting is rejected outright
    rather than silently truncated."""
    deep: dict = {"v": 1}
    for _ in range(MAX_METADATA_DEPTH + 3):
        deep = {"nested": deep}
    assert _metadata_depth(deep) > MAX_METADATA_DEPTH

    service = _service(tmp_path)
    result = service.ingest_batch([_doc(metadata=deep)], request_id=str(uuid.uuid4()))
    assert result.rejected == 1
    assert "depth" in result.items[0].reason.lower()


def test_same_text_replay_with_changed_title_and_metadata_is_updated(tmp_path):
    """Major #3: re-ingesting identical text with a changed title/metadata
    must be reported as `updated`, not `unchanged`, and the new fields
    must actually be persisted."""
    retriever = SqliteBM25Retriever(SqliteBM25Config(db_path=str(tmp_path / "refresh.db")))
    service = IngestionService(retriever)
    doc = _doc(external_id="refresh-1", title="Original Title", metadata={"note": "v1"})
    first = service.ingest_batch([doc], request_id=str(uuid.uuid4()))
    assert first.items[0].status == "indexed"

    updated_doc = _doc(external_id="refresh-1", title="Corrected Title", metadata={"note": "v2"})
    second = service.ingest_batch([updated_doc], request_id=str(uuid.uuid4()))
    assert second.items[0].status == "updated"

    stored = retriever.get_document(first.items[0].document_id)
    assert stored.title == "Corrected Title"
    assert dict(stored.metadata)["note"] == "v2"


def test_environment_configured_limits_actually_control_the_service(tmp_path):
    """Major #4 (service-level slice): IngestionServiceConfig's chunking
    limits, when actually passed to the service (as app/api/routes.py now
    does from settings), control whether a document is accepted."""
    tight_config = IngestionServiceConfig(chunking=ChunkingConfig(max_document_chars=10))
    retriever = SqliteBM25Retriever(SqliteBM25Config(db_path=str(tmp_path / "limits.db")))
    service = IngestionService(retriever, tight_config)
    result = service.ingest_batch(
        [_doc(external_id="too-long", text="this text is definitely longer than ten characters")],
        request_id=str(uuid.uuid4()),
    )
    assert result.rejected == 1
    assert "exceeds maximum" in result.items[0].reason


def test_external_id_and_source_key_whitespace_normalized_before_dedup(tmp_path):
    """Minor #3: whitespace/case variants of the same external_id/
    source_key across two separate ingestion calls must resolve to the
    same logical document (a corrected re-upload), not a second distinct
    one -- proving normalization happens before canonical ID derivation
    and duplicate detection, not just within a single batch."""
    service = _service(tmp_path)
    first = service.ingest_batch(
        [_doc(external_id="policy-1", source_key="api_upload", text="First version of the text.")],
        request_id=str(uuid.uuid4()),
    )
    second = service.ingest_batch(
        [_doc(external_id=" policy-1 ", source_key="API_UPLOAD", text="Second version of the text.")],
        request_id=str(uuid.uuid4()),
    )
    assert first.items[0].status == "indexed"
    assert second.items[0].status == "updated"
    assert first.items[0].document_id == second.items[0].document_id


def test_duplicate_within_batch_detected_across_whitespace_case_variants(tmp_path):
    """Minor #3 (batch-local variant): two items in the SAME batch that
    normalize to the same identity (whitespace around external_id, case
    variant of source_key -- external_id case itself is intentionally NOT
    folded, see ingestion.py rationale) must be treated as an in-batch
    duplicate (first wins, second rejected), not two separate documents."""
    service = _service(tmp_path)
    docs = [
        _doc(external_id="policy-2", source_key="api_upload", text="First version."),
        _doc(external_id=" policy-2 ", source_key="API_UPLOAD", text="Second version."),
    ]
    result = service.ingest_batch(docs, request_id=str(uuid.uuid4()))
    assert result.indexed == 1
    assert result.rejected == 1
    rejected = next(i for i in result.items if i.status == "rejected")
    assert "duplicate" in rejected.reason.lower()


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
