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
import math
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

# Final re-audit fix: this bound is measured against the UTF-8 encoded
# byte length of the deterministically-serialized raw metadata, never a
# Python character count (`len(str)`/`len(json.dumps(...))` count
# Unicode *characters*, so a Vietnamese-text or emoji payload could be
# well over this many bytes on the wire while reporting a much smaller
# character count -- see `_metadata_byte_size` and the pipeline in
# `IngestionService.ingest_batch`).
MAX_METADATA_JSON_BYTES = 2000
# Depth counts every container crossing (dict-value and list-item descent
# both count), including the final step down to a primitive leaf value.
# Raised from 4 to 6 during the Phase 12B re-audit fix: with list nesting
# now correctly counted (see _metadata_depth), a realistic
# dict-inside-list-inside-dict-inside-list-inside-dict combination (5
# container crossings) needs a 6th unit of budget left over to reach its
# own leaf values without being truncated -- 4 left essentially no room
# for any real-world combination once list-depth-counting was fixed. 6
# still firmly rejects pathological depth (10+ levels, see
# test_metadata_depth_over_limit_is_rejected).
#
# Final re-audit fix: this bound is now enforced by an iterative,
# explicit-stack-based preflight (`_preflight_metadata`) that runs BEFORE
# any recursive traversal or `json.dumps` call, so a ~900-level-deep
# structure is rejected in a handful of stack pops instead of raising an
# unhandled RecursionError from unbounded recursion/serialization.
MAX_METADATA_DEPTH = 6


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
    "bound metadata depth").

    **Fixed per the Phase 12B re-audit:** a list now increases depth by
    one, exactly like a dict does, when descending into its elements --
    the original implementation only incremented depth for dicts, so a
    list-of-lists could nest arbitrarily deep without ever tripping this
    pre-check.
    """
    if isinstance(value, dict):
        if not value:
            return current
        return max(_metadata_depth(v, current + 1) for v in value.values())
    if isinstance(value, list):
        if not value:
            return current
        return max(_metadata_depth(v, current + 1) for v in value)
    return current


_JSON_COMPATIBLE_SCALAR_TYPES = (str, int, bool, type(None))


def _preflight_metadata(raw: object) -> str | None:
    """Iteratively (never recursively) validate that `raw` is a bounded,
    JSON-compatible, acyclic structure, BEFORE any recursive traversal or
    `json.dumps` call is attempted on it.

    Final re-audit fix: the previous pipeline ran `json.dumps(...)` and
    the recursive `_metadata_depth`/`_sanitize_metadata` helpers directly
    against caller-supplied metadata with no bound checked first. A
    sufficiently deep structure (observed: ~900 nested lists) blew the
    Python recursion limit inside `json.dumps` itself, raising an
    unhandled `RecursionError` instead of a controlled rejection. This
    function uses an explicit list-as-stack instead of function-call
    recursion, so traversal depth is bounded by loop iterations, not by
    the C-level Python call stack -- a pathologically deep structure is
    rejected after a handful of pops (as soon as one branch's depth would
    exceed `MAX_METADATA_DEPTH`), not by exhausting the stack.

    Returns `None` if `raw` is valid, else a short, safe (no submitted
    value, no internal detail) rejection reason string.

    Checks performed, in order, per popped node:
    1. Cyclic reference (direct Python object-identity re-visit of an
       ancestor container on the *current* path only -- not "has this
       object been seen anywhere before", which would misfire on
       legitimate shared/repeated sub-objects that are not cycles).
       HTTP JSON bodies can never contain a cycle (json.loads only ever
       builds a tree); this guards direct service-level Python callers
       (e.g. tests, or a future internal caller) constructing a
       self-referential dict/list by hand.
    2. Bounded depth (both dict-value and list-item descent count,
       matching `_metadata_depth`'s semantics).
    3. JSON-compatible type: dict with string keys, list, str, int, bool,
       None, or finite float. NaN/Infinity and any other object type
       (sets, tuples, custom classes, etc.) are rejected.
    """
    # Each stack entry is (value, depth-of-this-value, ancestor object
    # ids on the path taken to reach it). `ancestors` is a tuple (not a
    # shared mutable set) so sibling branches never see each other's
    # ancestry -- only true ancestor-descendant self-reference trips it.
    stack: list[tuple[object, int, tuple[int, ...]]] = [(raw, 0, ())]

    while stack:
        value, depth, ancestors = stack.pop()

        if isinstance(value, dict):
            if not value:
                continue
            value_id = id(value)
            if value_id in ancestors:
                return "metadata contains a cyclic reference"
            if depth + 1 > MAX_METADATA_DEPTH:
                return f"metadata nesting exceeds maximum depth {MAX_METADATA_DEPTH}"
            next_ancestors = ancestors + (value_id,)
            for key, sub_value in value.items():
                if not isinstance(key, str):
                    return "metadata is not JSON-compatible"
                stack.append((sub_value, depth + 1, next_ancestors))
            continue

        if isinstance(value, list):
            if not value:
                continue
            value_id = id(value)
            if value_id in ancestors:
                return "metadata contains a cyclic reference"
            if depth + 1 > MAX_METADATA_DEPTH:
                return f"metadata nesting exceeds maximum depth {MAX_METADATA_DEPTH}"
            next_ancestors = ancestors + (value_id,)
            for item in value:
                stack.append((item, depth + 1, next_ancestors))
            continue

        if isinstance(value, float):
            if math.isnan(value) or math.isinf(value):
                return "metadata is not JSON-compatible"
            continue

        if isinstance(value, _JSON_COMPATIBLE_SCALAR_TYPES):
            continue

        return "metadata is not JSON-compatible"

    return None


def _metadata_byte_size(raw: object) -> int:
    """Deterministically serialize already-preflighted `raw` metadata and
    return its UTF-8 encoded byte length.

    Final re-audit fix: the previous check measured
    `len(json.dumps(raw_metadata, ensure_ascii=False))`, which is a
    Python *character* count, not a byte count. Multi-byte UTF-8 content
    (Vietnamese text, emoji) is under-counted -- e.g. a metadata object
    serializing to 2,412 UTF-8 bytes measured as only ~1,212 characters,
    passing a nominal 2,000-byte limit it should have failed. Using
    `sort_keys=True` and fixed `separators` makes the byte count
    deterministic and reproducible for a given logical metadata value,
    independent of caller-supplied key ordering.
    """
    serialized = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return len(serialized.encode("utf-8"))


def _sanitize_metadata(value: object, *, _depth: int = 0) -> tuple[object, int]:
    """Recursively strip reserved keys from `value` at any nesting depth
    and through any combination of dicts and lists, matching case/
    whitespace variants of the reserved-key names (Phase 12B Codex audit,
    Major #2; re-audit finding: the first fix only recursed into a list
    element when that element was itself a dict, so a list-of-lists such
    as `[[{"trust_level": "..."}]]` bypassed sanitization entirely and
    was persisted unmodified with `metadata_keys_stripped=0`).

    This now recurses uniformly over every JSON-compatible container --
    dict, list, nested lists, dicts inside lists, lists inside dicts, any
    combination -- and passes primitive values (str/int/float/bool/None)
    through unchanged. Callers always pass a `dict` at the top level (a
    document's whole metadata object); the recursive calls may pass any
    JSON-compatible value.

    Returns `(clean_value, stripped_count)` so a caller can record how
    many reserved keys were removed (for an auditable "a spoofing attempt
    occurred" signal) without ever persisting or logging the stripped
    value itself. Every level constructs a **new** dict/list rather than
    mutating `value` in place, so the caller-supplied metadata object is
    never mutated. `_depth` is an internal safety bound in addition to
    the caller-facing `_metadata_depth` pre-check -- structures deeper
    than `MAX_METADATA_DEPTH` are dropped (replaced with `None`, a valid,
    safely-nestable JSON value) rather than recursed into indefinitely.
    """
    if _depth > MAX_METADATA_DEPTH:
        return None, 0

    if isinstance(value, dict):
        clean: dict = {}
        stripped = 0
        for key, sub_value in value.items():
            if _normalize_metadata_key(key) in _RESERVED_METADATA_KEYS:
                stripped += 1
                continue
            cleaned_sub, nested_stripped = _sanitize_metadata(sub_value, _depth=_depth + 1)
            clean[key] = cleaned_sub
            stripped += nested_stripped
        return clean, stripped

    if isinstance(value, list):
        clean_list: list = []
        stripped = 0
        for item in value:
            cleaned_item, nested_stripped = _sanitize_metadata(item, _depth=_depth + 1)
            clean_list.append(cleaned_item)
            stripped += nested_stripped
        return clean_list, stripped

    return value, 0


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

            # Final re-audit fix: required processing order is now (1)
            # iterative, non-recursive raw structure/cycle/type/depth
            # preflight, (2) deterministic raw JSON serialization, (3)
            # UTF-8 byte-size enforcement, (4) recursive prohibited-key
            # sanitization (safe now that (1) has already bounded
            # depth). The metadata-size limit still applies to the RAW
            # caller-submitted metadata, before prohibited keys are
            # stripped -- otherwise a caller can place an arbitrarily
            # large value under a reserved key (e.g. {"trust_level": "x"
            # * 1_000_000}) and have it evade the configured size limit
            # entirely, since sanitization would remove that key before
            # the size was ever measured.
            raw_metadata = dict(document.metadata)

            preflight_reason = _preflight_metadata(raw_metadata)
            if preflight_reason is not None:
                rejected_items.append(
                    IngestionItemResult(
                        external_id=document.external_id,
                        source_key=document.source_key,
                        document_id=None,
                        status="rejected",
                        reason=preflight_reason,
                    )
                )
                continue

            try:
                # Defensive safety net only: `_preflight_metadata` has
                # already bounded depth and validated types/cycles above,
                # so this should never actually raise. Caught anyway so a
                # gap in the preflight can never surface as an unhandled
                # 500/RecursionError -- it degrades to the same safe,
                # generic rejection instead.
                raw_metadata_byte_size = _metadata_byte_size(raw_metadata)
            except RecursionError:
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
            except (TypeError, ValueError):
                rejected_items.append(
                    IngestionItemResult(
                        external_id=document.external_id,
                        source_key=document.source_key,
                        document_id=None,
                        status="rejected",
                        reason="metadata is not JSON-compatible",
                    )
                )
                continue

            if raw_metadata_byte_size > MAX_METADATA_JSON_BYTES:
                rejected_items.append(
                    IngestionItemResult(
                        external_id=document.external_id,
                        source_key=document.source_key,
                        document_id=None,
                        status="rejected",
                        reason=(
                            f"metadata too large ({raw_metadata_byte_size} bytes, "
                            f"max {MAX_METADATA_JSON_BYTES})"
                        ),
                    )
                )
                continue

            try:
                # Defensive safety net only, matching the byte-size check
                # above: _preflight_metadata already guarantees depth <=
                # MAX_METADATA_DEPTH, so _sanitize_metadata's own
                # recursion is bounded in practice before it ever runs.
                safe_metadata, metadata_keys_stripped = _sanitize_metadata(raw_metadata)
            except RecursionError:
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
