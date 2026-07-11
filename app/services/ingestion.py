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

import hashlib
import json
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
# stripped before a DocumentRecord/ChunkRecord is constructed, regardless
# of what a caller sent -- trust/classification/source_type only ever come
# from app/core/source_policy.py, and IDs are only ever derived here.
_RESERVED_METADATA_KEYS = frozenset(
    {
        "trust_level",
        "classification",
        "source_type",
        "is_poisoned",
        "security_decision",
        "document_id",
        "chunk_id",
    }
)

MAX_METADATA_JSON_CHARS = 2000


class IngestionValidationError(ValueError):
    """Raised for a batch-level validation failure (e.g. batch too large),
    as opposed to a per-document rejection, which is reported in the
    returned IngestionBatchResult instead of raised."""


def _sanitize_metadata(raw: dict) -> dict:
    return {key: value for key, value in raw.items() if key not in _RESERVED_METADATA_KEYS}


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

        for document in documents:
            key = (document.source_key, document.external_id)
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
                policy = resolve_source_policy(document.source_key)
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

            safe_metadata = _sanitize_metadata(dict(document.metadata))
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

            document_id = _derive_document_id(document.source_key, document.external_id)
            now = datetime.now(timezone.utc).isoformat()

            document_record = DocumentRecord(
                document_id=document_id,
                external_id=document.external_id,
                source_key=document.source_key,
                source_id=document.source_key,
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

        db_result = self._retriever.upsert_documents(prepared)

        combined_items = tuple(rejected_items) + db_result.items
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
