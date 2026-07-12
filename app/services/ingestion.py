"""Document ingestion service (Phase 12B).

Orchestrates validation, server-controlled source-policy resolution,
deterministic chunking, content hashing, and atomic persistence via a
`Retriever`. This is the only layer that is allowed to construct a
`DocumentRecord`/`ChunkRecord` (i.e. to assign `trust_level`,
`classification`, `source_type`, and canonical `document_id`/`chunk_id`
values) -- see `app/core/source_policy.py` and
`docs/modernization-v2-architecture.md` §4.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.source_policy import UnknownSourceKeyError, resolve_source_policy
from app.retrieval.base import Retriever
from app.retrieval.models import (
    ChunkRecord,
    DocumentRecord,
    IngestionBatchResult,
    IngestionDocument,
    IngestionItemResult,
)
from app.services.chunking import (
    ChunkingConfig,
    DocumentTooLongError,
    EmptyDocumentError,
    chunk_text,
)
from app.core.decisions import Decision
from app.services.audit_logger import log_event

# Metadata keys that could otherwise be used to smuggle a security
# decision through the free-form `metadata` field. These are always
# stripped -- at any nesting depth, regardless of case/whitespace variant
# -- before a DocumentRecord/ChunkRecord is constructed, regardless of
# what a caller sent -- trust/classification/source_type only ever come
# from app/core/source_policy.py, and IDs are only ever derived here.
# Extended per the Phase 12B Codex audit (Major #2) with expected_decision
# and policy_result, and made recursive/normalized -- see
# `_sanitize_metadata` below.
_RESERVED_METADATA_KEYS = frozenset(
    {
        "trust_level",
        "classification",
        "source_type",
        "is_poisoned",
        "expected_decision",
        "security_decision",
        "policy_result",
        "document_id",
        "chunk_id",
    }
)

MAX_METADATA_JSON_CHARS = 2000
MAX_METADATA_DEPTH = 4


class IngestionValidationError(ValueError):
    """Raised for a batch-level validation failure (e.g. batch too large),
    as opposed to a per-document rejection, which is reported in the
    returned IngestionBatchResult instead of raised."""


def _normalize_metadata_key(key: object) -> str:
    """Fold a metadata key to a canonical form for reserved-key matching:
    lowercase, with runs of whitespace/underscore/hyphen collapsed to a
    single underscore, so "Trust_Level", "TRUST-LEVEL", and " trust level "
    are all recognized as the reserved key `trust_level` (Phase 12B Codex
    audit, Major #2 -- the original implementation matched only the exact
    lowercase key)."""
    if not isinstance(key, str):
        return ""
    return re.sub(r"[\s_\-]+", "_", key.strip().lower())


def _metadata_depth(value: object, current: int = 0) -> int:
    """Compute the maximum nesting depth of a caller-supplied metadata
    value, so ingestion can reject unreasonably deep structures before
    attempting to sanitize/store them (Phase 12B Codex audit, Major #2:
    "bound metadata depth")."""
    if isinstance(value, dict):
        if not value:
            return current
        return max(_metadata_depth(v, current + 1) for v in value.values())
    if isinstance(value, list):
        if not value:
            return current
        return max((_metadata_depth(v, current) for v in value), default=current)
    return current


def _sanitize_metadata(raw: dict, *, _depth: int = 0) -> tuple[dict, int]:
    """Recursively strip reserved keys from `raw` at any nesting depth,
    matching case/whitespace variants of the reserved-key names (Phase
    12B Codex audit, Major #2: the original implementation only removed
    exact top-level keys, so `{"nested": {"trust_level": "..."}}` or
    `{"Trust_Level": "..."}` both passed through unmodified).

    Returns `(clean_metadata, stripped_count)` so a caller can record how
    many reserved keys were removed (for an auditable "a spoofing attempt
    occurred" signal) without ever persisting or logging the stripped
    value itself. `_depth` is an internal safety bound in addition to the
    caller-facing `_metadata_depth` pre-check -- deeper structures are
    dropped rather than recursed into indefinitely.
    """
    if _depth > MAX_METADATA_DEPTH:
        return {}, 0

    clean: dict = {}
    stripped = 0
    for key, value in raw.items():
        if _normalize_metadata_key(key) in _RESERVED_METADATA_KEYS:
            stripped += 1
            continue
        if isinstance(value, dict):
            nested_clean, nested_stripped = _sanitize_metadata(value, _depth=_depth + 1)
            clean[key] = nested_clean
            stripped += nested_stripped
        elif isinstance(value, list):
            nested_list: list = []
            for item in value:
                if isinstance(item, dict):
                    nested_clean, nested_stripped = _sanitize_metadata(item, _depth=_depth + 1)
                    nested_list.append(nested_clean)
                    stripped += nested_stripped
                else:
                    nested_list.append(item)
            clean[key] = nested_list
        else:
            clean[key] = value
    return clean, stripped


def _derive_document_id(source_key: str, external_id: str) -> str:
    digest = hashlib.sha256(f"{source_key}:{external_id}".encode("utf-8")).hexdigest()
    return f"doc_{digest[:24]}"


def _derive_chunk_id(document_id: str, chunk_index: int) -> str:
    return f"{document_id}_c{chunk_index:04d}"


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class IngestionServiceConfig:
    max_batch_size: int = 20
    chunking: ChunkingConfig = ChunkingConfig()


class IngestionService:
    def __init__(self, retriever: Retriever, config: IngestionServiceConfig | None = None) -> None:
        self._retriever = retriever
        self._config = config or IngestionServiceConfig()

    def ingest_batch(
        self, documents: list[IngestionDocument], *, request_id: str
    ) -> IngestionBatchResult:
        """Validate, resolve policy, chunk, and persist a batch of
        documents. Per-document problems (unknown source, oversized text,
        duplicate external_id within the batch) are reported as rejected
        items in the returned result, not raised. An unexpected database
        failure during the write phase raises
        `app.retrieval.sqlite_bm25.IngestionBatchError` and rolls back the
        entire write transaction -- see `Retriever.upsert_documents`.

        Writes one audit log event per batch call (not per document)
        recording only safe fields: canonical document ID, source key,
        assigned source type/classification/trust level, a content-hash
        prefix, and the result status for every item -- never full
        document text or raw secrets. This is how the source-policy
        assignment decision (`app/core/source_policy.py`) becomes
        auditable, per docs/modernization-v2-architecture.md §4 and the
        Phase 12A audit resolution (Grok, Major finding on auditability).
        """
        if len(documents) > self._config.max_batch_size:
            raise IngestionValidationError(
                f"Batch size {len(documents)} exceeds maximum {self._config.max_batch_size}."
            )

        prepared: list[tuple[DocumentRecord, list[ChunkRecord]]] = []
        rejected_items: list[IngestionItemResult] = []
        seen_keys: set[tuple[str, str]] = set()
        _stripped_counts_by_document_id: dict[str, int] = {}

        for document in documents:
            # Phase 12B Codex audit fix (Minor #3, "canonical identity not
            # normalized"): strip incidental whitespace from both fields,
            # and fold source_key's case (a small, server-defined
            # vocabulary, safe to normalize). external_id case is
            # deliberately left as-is after stripping -- external systems
            # may use case-sensitive identifiers, and force-lowercasing
            # them risks silently merging genuinely distinct documents,
            # which is a worse failure mode than the one being fixed.
            normalized_source_key = document.source_key.strip().lower()
            normalized_external_id = document.external_id.strip()

            key = (normalized_source_key, normalized_external_id)
            if key in seen_keys:
                rejected_items.append(
                    IngestionItemResult(
                        external_id=document.external_id,
                        source_key=document.source_key,
                        document_id=None,
                        status="rejected",
                        reason="duplicate external_id within batch",
                    )
                )
                continue
            seen_keys.add(key)

            try:
                policy = resolve_source_policy(normalized_source_key)
            except UnknownSourceKeyError as exc:
                rejected_items.append(
                    IngestionItemResult(
                        external_id=document.external_id,
                        source_key=document.source_key,
                        document_id=None,
                        status="rejected",
                        reason=str(exc),
                    )
                )
                continue

            raw_metadata = dict(document.metadata)
            if _metadata_depth(raw_metadata) > MAX_METADATA_DEPTH:
                rejected_items.append(
                    IngestionItemResult(
                        external_id=document.external_id,
                        source_key=document.source_key,
                        document_id=None,
                        status="rejected",
                        reason=f"metadata nesting exceeds maximum depth {MAX_METADATA_DEPTH}",
                    )
                )
                continue

            safe_metadata, metadata_keys_stripped = _sanitize_metadata(raw_metadata)
            metadata_json_size = len(json.dumps(safe_metadata, ensure_ascii=False))
            if metadata_json_size > MAX_METADATA_JSON_CHARS:
                rejected_items.append(
                    IngestionItemResult(
                        external_id=document.external_id,
                        source_key=document.source_key,
                        document_id=None,
                        status="rejected",
                        reason=(
                            f"metadata too large ({metadata_json_size} chars, "
                            f"max {MAX_METADATA_JSON_CHARS})"
                        ),
                    )
                )
                continue

            try:
                text_chunks = chunk_text(document.text, self._config.chunking)
            except (EmptyDocumentError, DocumentTooLongError) as exc:
                rejected_items.append(
                    IngestionItemResult(
                        external_id=document.external_id,
                        source_key=document.source_key,
                        document_id=None,
                        status="rejected",
                        reason=str(exc),
                    )
                )
                continue

            document_id = _derive_document_id(normalized_source_key, normalized_external_id)
            now = datetime.now(timezone.utc).isoformat()

            document_record = DocumentRecord(
                document_id=document_id,
                external_id=normalized_external_id,
                source_key=normalized_source_key,
                source_id=normalized_source_key,
                source_type=policy.source_type,
                classification=policy.classification,
                trust_level=policy.trust_level,
                title=document.title,
                content_hash=_content_hash(document.text),
                created_at=now,
                updated_at=now,
                metadata=safe_metadata,
            )
            chunk_records = [
                ChunkRecord(
                    chunk_id=_derive_chunk_id(document_id, chunk.chunk_index),
                    document_id=document_id,
                    chunk_index=chunk.chunk_index,
                    text=chunk.text,
                    content_hash=_content_hash(chunk.text),
                    metadata=safe_metadata,
                )
                for chunk in text_chunks
            ]
            prepared.append((document_record, chunk_records))
            # metadata_keys_stripped is folded into the post-persistence
            # item result below (after upsert_documents assigns the final
            # status), via _stripped_counts_by_document_id.
            _stripped_counts_by_document_id[document_id] = metadata_keys_stripped

        db_result = self._retriever.upsert_documents(prepared)

        # Attach each successfully-persisted item's metadata_keys_stripped
        # count (Major #2 auditability) -- IngestionItemResult is frozen,
        # so this reconstructs each item rather than mutating it in place.
        persisted_items = tuple(
            dataclasses.replace(
                item,
                metadata_keys_stripped=_stripped_counts_by_document_id.get(item.document_id, 0)
                if item.document_id
                else 0,
            )
            for item in db_result.items
        )

        combined_items = tuple(rejected_items) + persisted_items
        result = IngestionBatchResult(
            indexed=db_result.indexed,
            updated=db_result.updated,
            unchanged=db_result.unchanged,
            rejected=db_result.rejected + len(rejected_items),
            items=combined_items,
        )
        self._log_ingestion_event(request_id=request_id, prepared=prepared, result=result)
        return result

    def _log_ingestion_event(
        self,
        *,
        request_id: str,
        prepared: list[tuple[DocumentRecord, list[ChunkRecord]]],
        result: IngestionBatchResult,
    ) -> None:
        records_by_id = {document.document_id: document for document, _ in prepared}
        safe_items = []
        for item in result.items:
            document = records_by_id.get(item.document_id) if item.document_id else None
            safe_items.append(
                {
                    "document_id": item.document_id,
                    "source_key": item.source_key,
                    "status": item.status,
                    "source_type": document.source_type if document else None,
                    "classification": document.classification if document else None,
                    "trust_level": document.trust_level if document else None,
                    "content_hash_prefix": document.content_hash[:12] if document else None,
                    "reason": item.reason,
                    # Count only -- never the stripped key names or values
                    # (Phase 12B Codex audit, Major #2: "auditable result
                    # without persisting unsafe values").
                    "metadata_keys_stripped": item.metadata_keys_stripped,
                }
            )
        log_event(
            endpoint="/v1/documents/ingest",
            request_id=request_id,
            input_preview=f"ingest_batch: {len(result.items)} item(s)",
            final_decision=Decision.LOG_ONLY,
            reasons=[
                f"indexed={result.indexed} updated={result.updated} "
                f"unchanged={result.unchanged} rejected={result.rejected}"
            ],
            metadata={"items": safe_items},
        )
