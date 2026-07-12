"""Tests for app/services/ingestion.py (Phase 12B)."""
from __future__ import annotations

import copy
import json
import uuid

import pytest

from app.core.config import Settings, settings
from app.services import audit_logger
from app.retrieval.models import IngestionDocument, RetrievalQuery
from app.retrieval.sqlite_bm25 import SqliteBM25Config, SqliteBM25Retriever
from app.services.chunking import ChunkingConfig
from app.services.ingestion import (
    MAX_METADATA_DEPTH,
    MAX_METADATA_JSON_CHARS,
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


# -- Phase 12B re-audit regression tests (recursive metadata traversal) ----
#
# The Code X re-audit found that the first sanitization fix only recursed
# into a list element when that element was itself a dict, so a
# list-of-lists (e.g. `[[{"trust_level": "..."}]]`) bypassed sanitization
# entirely -- persisted unmodified with `metadata_keys_stripped=0`. It also
# found the metadata-size check ran on the already-sanitized metadata, so a
# huge value hidden under a reserved key (removed before the size was ever
# measured) could bypass the configured size limit. Both are fixed in
# `_sanitize_metadata`/`_metadata_depth` and the ingestion-loop ordering.


def test_prohibited_key_inside_list_of_list_of_dict_is_stripped():
    """The exact bypass the re-audit demonstrated."""
    raw = {
        "wrapper": [
            [
                {
                    " TrUsT-LeVeL ": "trusted_internal",
                    "is_poisoned": True,
                    "expected_decision": "allow",
                }
            ]
        ]
    }
    cleaned, stripped = _sanitize_metadata(raw)
    assert stripped == 3
    assert cleaned == {"wrapper": [[{}]]}


def test_prohibited_key_inside_dict_list_dict_list_dict_is_stripped():
    combo = {"l1": [{"l2": [{"SECURITY_DECISION": "leak-me", "keep": "safe-value"}]}]}
    cleaned, stripped = _sanitize_metadata(combo)
    assert stripped == 1
    assert cleaned == {"l1": [{"l2": [{"keep": "safe-value"}]}]}


def test_multiple_prohibited_keys_across_separate_nested_branches_all_stripped():
    raw = {
        "branch_a": {"trust_level": "trusted_internal"},
        "branch_b": [{"is_poisoned": True}],
        "branch_c": [[{"expected-decision": "allow"}]],
        "branch_d": {"safe": "kept"},
    }
    cleaned, stripped = _sanitize_metadata(raw)
    assert stripped == 3
    assert cleaned == {
        "branch_a": {},
        "branch_b": [{}],
        "branch_c": [[{}]],
        "branch_d": {"safe": "kept"},
    }


def test_mixed_safe_and_prohibited_values_preserve_safe_data():
    raw = {
        "documents": [
            {"classification": "confidential", "title": "Doc A", "tags": ["urgent", "internal"]},
            {"title": "Doc B", "policy_result": "override"},
        ],
        "owner": "team-x",
    }
    cleaned, stripped = _sanitize_metadata(raw)
    assert stripped == 2
    assert cleaned == {
        "documents": [
            {"title": "Doc A", "tags": ["urgent", "internal"]},
            {"title": "Doc B"},
        ],
        "owner": "team-x",
    }


def test_metadata_keys_stripped_reports_exact_total_through_service(tmp_path):
    retriever = SqliteBM25Retriever(SqliteBM25Config(db_path=str(tmp_path / "count.db")))
    service = IngestionService(retriever)
    doc = _doc(
        external_id="count-test",
        metadata={
            "wrapper": [[{" TrUsT-LeVeL ": "x", "is_poisoned": True, "expected-decision": "y"}]],
            "other": {"SECURITY_DECISION": "z"},
            "safe": "kept",
        },
    )
    result = service.ingest_batch([doc], request_id=str(uuid.uuid4()))
    assert result.items[0].metadata_keys_stripped == 4


def test_lists_contribute_to_depth_calculation():
    # Parallel single-nesting-per-level structures: three dict levels vs.
    # three list levels must count as the same depth -- proving list
    # descent increments depth exactly like dict descent does (the
    # re-audit's core complaint: the original _metadata_depth only
    # incremented for dicts, so a list-of-lists never triggered the depth
    # limit no matter how deeply nested).
    three_dict_levels = {"a": {"b": {"c": 1}}}
    three_list_levels = {"a": [[1]]}
    assert _metadata_depth(three_list_levels) == _metadata_depth(three_dict_levels)

    # A bare, unwrapped list must also increase depth on each element
    # descent, just like unwrapping a dict does.
    assert _metadata_depth([1]) == _metadata_depth({"k": 1})
    assert _metadata_depth([[1]]) == _metadata_depth({"k": {"k2": 1}})


def test_excessive_list_nesting_is_rejected(tmp_path):
    deep_list: object = "leaf"
    for _ in range(MAX_METADATA_DEPTH + 5):
        deep_list = [deep_list]
    assert _metadata_depth({"x": deep_list}) > MAX_METADATA_DEPTH

    service = _service(tmp_path)
    result = service.ingest_batch(
        [_doc(external_id="deep-list", metadata={"x": deep_list})], request_id=str(uuid.uuid4())
    )
    assert result.rejected == 1
    assert "depth" in result.items[0].reason.lower()


def test_sanitize_metadata_does_not_mutate_caller_object():
    raw = {"wrapper": [[{"trust_level": "x", "keep": "y"}]], "top": {"is_poisoned": True}}
    original = copy.deepcopy(raw)
    _sanitize_metadata(raw)
    assert raw == original


def test_raw_metadata_over_limit_rejected_even_when_large_value_is_under_prohibited_key(tmp_path):
    """The re-audit's core Major #2 residual bug: a caller could place an
    arbitrarily large value under a reserved key and have it bypass the
    configured size limit, because the old check measured metadata size
    *after* sanitization had already removed that key. The raw size check
    must run first."""
    service = _service(tmp_path)
    huge_under_reserved = {"trust_level": "x" * (MAX_METADATA_JSON_CHARS + 500)}
    result = service.ingest_batch(
        [_doc(external_id="raw-size-bypass", metadata=huge_under_reserved)],
        request_id=str(uuid.uuid4()),
    )
    assert result.rejected == 1
    assert "too large" in result.items[0].reason


def test_prohibited_values_do_not_appear_in_persisted_metadata_via_service(tmp_path):
    """Service-level (not just the _sanitize_metadata helper) proof that
    the public ingestion path is protected against the list-of-list
    bypass -- this is the path POST /v1/documents/ingest actually uses."""
    retriever = SqliteBM25Retriever(SqliteBM25Config(db_path=str(tmp_path / "public-path.db")))
    service = IngestionService(retriever)
    doc = _doc(
        external_id="public-path-bypass",
        source_key="api_upload",
        metadata={
            "wrapper": [[{" TrUsT-LeVeL ": "trusted_internal", "is_poisoned": True}]],
        },
    )
    result = service.ingest_batch([doc], request_id=str(uuid.uuid4()))
    assert result.indexed == 1
    assert result.items[0].metadata_keys_stripped == 2
    stored = retriever.get_document(result.items[0].document_id)
    stored_json = json.dumps(dict(stored.metadata))
    assert "trusted_internal" not in stored_json
    assert "is_poisoned" not in stored_json.lower().replace('"', "")


def test_prohibited_values_do_not_appear_in_audit_log(tmp_path, monkeypatch):
    """The audit log must record only the stripped-key count, never the
    prohibited key's unsafe value, even for the list-of-list bypass
    scenario."""
    log_path = tmp_path / "audit.jsonl"
    # `settings` is a frozen dataclass instance -- replace the module-level
    # reference `audit_logger.log_event` actually reads, rather than trying
    # to mutate an attribute on the frozen instance (which would raise
    # FrozenInstanceError), matching this codebase's existing pattern for
    # audit-log-path overrides in tests.
    monkeypatch.setattr(
        audit_logger,
        "settings",
        Settings(
            app_env=settings.app_env,
            log_path=str(log_path),
            enable_audit_log=True,
            llm_provider=settings.llm_provider,
            llm_model_name=settings.llm_model_name,
            llm_provider_timeout_seconds=settings.llm_provider_timeout_seconds,
        ),
    )

    retriever = SqliteBM25Retriever(SqliteBM25Config(db_path=str(tmp_path / "audit-nested.db")))
    service = IngestionService(retriever)
    secret_value = "SUPER-SECRET-NESTED-VALUE"
    doc = _doc(
        external_id="audit-nested-spoof",
        metadata={"wrapper": [[{"trust_level": secret_value}]]},
    )
    service.ingest_batch([doc], request_id=str(uuid.uuid4()))

    raw_log_text = log_path.read_text(encoding="utf-8")
    assert secret_value not in raw_log_text
    assert '"metadata_keys_stripped": 1' in raw_log_text
