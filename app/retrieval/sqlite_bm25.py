"""SQLite FTS5/BM25 retriever (Phase 12B).

Persistent, deterministic, offline lexical retrieval using only Python's
standard-library `sqlite3` module. See
`docs/decisions/ADR-002-retrieval-engine.md` for the decision record and
`docs/modernization-v2-architecture.md` §2-3 for the target design this
implements.

Key policies enforced here (all non-negotiable per ADR-002 and the Phase
12A audit resolution):

- **No fallback of any kind if FTS5 is unavailable.** `check_capability()`
  raises `FTS5UnavailableError` and every public method fails the same
  way -- there is no `LIKE`-based or otherwise degraded search path
  anywhere in this module.
- **Short-lived connections only.** No module- or instance-level shared
  `sqlite3.Connection` is ever kept open across calls; every public
  method opens its own connection and closes it before returning.
- **Query text is never concatenated raw into an FTS5 `MATCH` expression.**
  See `_build_safe_match_query` for the tokenization/escaping approach.
- **Deterministic ranking.** Results are ordered by `bm25()` ascending
  (SQLite's bm25() returns more-negative values for better matches, so
  ascending order puts the best match first) with `chunk_id` ascending as
  an explicit, stable tie-breaker.
"""
from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from app.retrieval.base import Retriever
from app.retrieval.models import (
    ChunkRecord,
    DocumentRecord,
    IngestionBatchResult,
    IngestionItemResult,
    RetrievalHit,
    RetrievalQuery,
    RetrievalResult,
)

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    document_id TEXT PRIMARY KEY,
    external_id TEXT NOT NULL,
    source_key TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    classification TEXT NOT NULL,
    trust_level TEXT NOT NULL,
    title TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (source_key, external_id)
);

CREATE TABLE IF NOT EXISTS chunks (
    rowid INTEGER PRIMARY KEY,
    chunk_id TEXT NOT NULL UNIQUE,
    document_id TEXT NOT NULL REFERENCES documents (document_id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    UNIQUE (document_id, chunk_index)
);
CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks (document_id);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text,
    content='chunks',
    content_rowid='rowid'
);
"""

_SCHEMA_VERSION = "1"

# FTS5 special characters/operators that must never reach MATCH unescaped.
# Tokenization below only ever extracts \w+ runs, which already excludes
# every character in this set -- this constant exists for documentation
# and for the explicit adversarial test suite, not as a runtime filter.
FTS5_SPECIAL_CHARACTERS = frozenset('"*:^()-')
FTS5_RESERVED_WORDS = frozenset({"AND", "OR", "NOT", "NEAR"})

_WORD_PATTERN = re.compile(r"\w+", re.UNICODE)
_CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class FTS5UnavailableError(RuntimeError):
    """Raised when SQLite FTS5 is not available in this Python build.
    There is no fallback -- see the module docstring and
    docs/decisions/ADR-002-retrieval-engine.md."""


class EmptySearchQueryError(ValueError):
    """Raised when a query contains no searchable terms after sanitization."""


class IngestionBatchError(RuntimeError):
    """Raised when an unexpected database error occurs while writing a
    batch; the whole batch's transaction is rolled back before this is
    raised, so no partial write is ever left behind."""


@dataclass(frozen=True)
class SqliteBM25Config:
    db_path: str
    busy_timeout_ms: int = 5000
    max_query_chars: int = 500
    max_query_terms: int = 12
    max_top_k: int = 50


def _connect(db_path: str, busy_timeout_ms: int) -> sqlite3.Connection:
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=busy_timeout_ms / 1000.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(f"PRAGMA busy_timeout = {int(busy_timeout_ms)}")
    return conn


def _strip_control_characters(text: str) -> str:
    return _CONTROL_CHAR_PATTERN.sub(" ", text)


def _extract_safe_terms(
    raw_query: str, max_query_chars: int, max_query_terms: int
) -> tuple[str, list[str]]:
    """Normalize and tokenize `raw_query` into a bounded list of plain
    lexical terms, safe to embed (individually quoted) in an FTS5 MATCH
    expression. Never returns raw FTS5 syntax -- only \\w+ runs survive.

    Deterministic bounds: the query is truncated to `max_query_chars`
    characters (not rejected) before tokenization, and only the first
    `max_query_terms` extracted terms (in original order) are kept.
    """
    cleaned = _strip_control_characters(raw_query)[:max_query_chars]
    normalized = unicodedata.normalize("NFKC", cleaned)
    terms = _WORD_PATTERN.findall(normalized)
    return normalized, terms[:max_query_terms]


def _quote_fts5_term(term: str) -> str:
    # FTS5 quoted-string escaping: a literal double quote inside a quoted
    # token is written as two double quotes. Wrapping every term in
    # double quotes -- including terms that happen to spell a reserved
    # word like NEAR/AND/OR/NOT -- makes FTS5 treat it as a literal term,
    # not as an operator, per FTS5 query syntax rules.
    escaped = term.replace('"', '""')
    return f'"{escaped}"'


def _build_safe_match_query(terms: list[str]) -> str:
    """Join sanitized terms into a MATCH expression.

    Documented combining behavior: terms are joined with explicit ``OR``,
    so a chunk matching *any* extracted term is a candidate hit, ranked by
    `bm25()` (which still rewards chunks matching more terms, since BM25
    sums per-term scores and down-weights very common terms via document
    frequency). **Changed from implicit AND to OR per the Phase 12B Codex
    audit (Major #5, "Implicit AND permits trivial retrieval
    suppression"):** the original AND-only behavior meant one extra,
    otherwise-irrelevant query term could silently zero out an otherwise
    matching result -- a real false-negative/evasion primitive, not just a
    ranking preference. See `docs/decisions/ADR-002-retrieval-engine.md`
    for the updated decision record.
    """
    return " OR ".join(_quote_fts5_term(term) for term in terms)


def _metadata_json(metadata: object) -> str:
    # sort_keys=True makes this a canonical representation, so two
    # semantically-identical dicts serialize identically regardless of
    # key insertion order -- required for _is_unchanged's string
    # comparison below to be meaningful rather than order-fragile.
    return json.dumps(dict(metadata), ensure_ascii=False, sort_keys=True)


def _is_unchanged(existing_row: sqlite3.Row, incoming: DocumentRecord) -> bool:
    """Decide whether a re-ingested document is truly unchanged.

    **Phase 12B Codex audit fix (Major #3, "'Unchanged' detection ignores
    mutable and security-relevant state"):** the original implementation
    compared only `content_hash`, so re-ingesting identical text with a
    corrected title, metadata, or (if the source policy configuration
    changes) classification/trust_level was wrongly reported as
    `unchanged` and those fields silently never propagated. This now
    compares every field `_replace_document` would otherwise update, so a
    change to any of them is correctly detected as `updated`.
    """
    return (
        existing_row["content_hash"] == incoming.content_hash
        and existing_row["title"] == incoming.title
        and existing_row["metadata_json"] == _metadata_json(incoming.metadata)
        and existing_row["source_type"] == incoming.source_type
        and existing_row["classification"] == incoming.classification
        and existing_row["trust_level"] == incoming.trust_level
    )


class SqliteBM25Retriever(Retriever):
    """Persistent SQLite FTS5/BM25 retriever. See module docstring for
    the non-negotiable policies this class enforces."""

    def __init__(self, config: SqliteBM25Config) -> None:
        self._config = config
        self._capability_confirmed = False

    # -- connection / schema / capability -------------------------------

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = _connect(self._config.db_path, self._config.busy_timeout_ms)
        try:
            yield conn
        finally:
            conn.close()

    def check_capability(self) -> None:
        """Explicit FTS5 capability probe. Raises FTS5UnavailableError
        with no side effects on failure; safe to call repeatedly."""
        with self._connection() as conn:
            try:
                conn.execute(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS temp.__fts5_capability_probe USING fts5(x)"
                )
                conn.execute("DROP TABLE IF EXISTS temp.__fts5_capability_probe")
            except sqlite3.OperationalError as exc:
                raise FTS5UnavailableError(
                    "SQLite FTS5 extension is required for retrieval but is not "
                    "available in this Python/SQLite build. There is no fallback "
                    "(no LIKE-based search, no degraded scoring) -- see "
                    "docs/decisions/ADR-002-retrieval-engine.md. Retrieval cannot "
                    "be served until a Python/SQLite build with FTS5 is used."
                ) from exc
        self._capability_confirmed = True

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        # CREATE TABLE/INDEX IF NOT EXISTS is cheap and idempotent, so this
        # runs on every connection rather than being gated by a cached
        # flag -- that way a database file that was deleted or recreated
        # out from under a long-lived retriever instance (e.g. between
        # test runs) is always correctly re-initialized on next use,
        # instead of silently staying "initialized" against a stale flag.
        conn.executescript(_SCHEMA_SQL)
        conn.execute(
            "INSERT OR IGNORE INTO schema_meta (key, value) VALUES ('schema_version', ?)",
            (_SCHEMA_VERSION,),
        )
        conn.commit()

    def initialize(self) -> None:
        if not self._capability_confirmed:
            self.check_capability()
        with self._connection() as conn:
            self._ensure_schema(conn)

    def _ensure_ready(self, conn: sqlite3.Connection) -> None:
        if not self._capability_confirmed:
            self.check_capability()
        self._ensure_schema(conn)

    # -- ingestion --------------------------------------------------------

    def upsert_documents(
        self, prepared: list[tuple[DocumentRecord, list[ChunkRecord]]]
    ) -> IngestionBatchResult:
        if not prepared:
            return IngestionBatchResult(indexed=0, updated=0, unchanged=0, rejected=0, items=())

        items: list[IngestionItemResult] = []
        indexed = updated = unchanged = 0

        with self._connection() as conn:
            self._ensure_ready(conn)
            try:
                conn.execute("BEGIN IMMEDIATE")
                for document_record, chunk_records in prepared:
                    existing = conn.execute(
                        """
                        SELECT content_hash, title, metadata_json, source_type,
                               classification, trust_level
                        FROM documents WHERE document_id = ?
                        """,
                        (document_record.document_id,),
                    ).fetchone()

                    if existing is None:
                        self._insert_document(conn, document_record, chunk_records)
                        items.append(
                            IngestionItemResult(
                                external_id=document_record.external_id,
                                source_key=document_record.source_key,
                                document_id=document_record.document_id,
                                status="indexed",
                                chunk_count=len(chunk_records),
                            )
                        )
                        indexed += 1
                    elif _is_unchanged(existing, document_record):
                        items.append(
                            IngestionItemResult(
                                external_id=document_record.external_id,
                                source_key=document_record.source_key,
                                document_id=document_record.document_id,
                                status="unchanged",
                            )
                        )
                        unchanged += 1
                    else:
                        self._replace_document(conn, document_record, chunk_records)
                        items.append(
                            IngestionItemResult(
                                external_id=document_record.external_id,
                                source_key=document_record.source_key,
                                document_id=document_record.document_id,
                                status="updated",
                                chunk_count=len(chunk_records),
                            )
                        )
                        updated += 1
                conn.commit()
            except Exception as exc:
                conn.rollback()
                raise IngestionBatchError(
                    f"Ingestion batch failed and was rolled back; no partial write "
                    f"was committed: {exc}"
                ) from exc

        return IngestionBatchResult(
            indexed=indexed, updated=updated, unchanged=unchanged, rejected=0, items=tuple(items)
        )

    def _insert_document(
        self, conn: sqlite3.Connection, document: DocumentRecord, chunks: list[ChunkRecord]
    ) -> None:
        conn.execute(
            """
            INSERT INTO documents (
                document_id, external_id, source_key, source_id, source_type,
                classification, trust_level, title, content_hash, metadata_json,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document.document_id, document.external_id, document.source_key,
                document.source_id, document.source_type, document.classification,
                document.trust_level, document.title, document.content_hash,
                _metadata_json(document.metadata),
                document.created_at, document.updated_at,
            ),
        )
        self._insert_chunks(conn, chunks)

    def _replace_document(
        self, conn: sqlite3.Connection, document: DocumentRecord, chunks: list[ChunkRecord]
    ) -> None:
        old_rowids = [
            row["rowid"]
            for row in conn.execute(
                "SELECT rowid FROM chunks WHERE document_id = ?", (document.document_id,)
            ).fetchall()
        ]
        for rowid in old_rowids:
            conn.execute("DELETE FROM chunks_fts WHERE rowid = ?", (rowid,))
        conn.execute("DELETE FROM chunks WHERE document_id = ?", (document.document_id,))

        conn.execute(
            """
            UPDATE documents SET
                title = ?, content_hash = ?, metadata_json = ?, updated_at = ?,
                source_id = ?, source_type = ?, classification = ?, trust_level = ?
            WHERE document_id = ?
            """,
            (
                document.title, document.content_hash,
                _metadata_json(document.metadata),
                document.updated_at, document.source_id, document.source_type,
                document.classification, document.trust_level, document.document_id,
            ),
        )
        self._insert_chunks(conn, chunks)

    def _insert_chunks(self, conn: sqlite3.Connection, chunks: list[ChunkRecord]) -> None:
        for chunk in chunks:
            cursor = conn.execute(
                """
                INSERT INTO chunks (
                    chunk_id, document_id, chunk_index, text, content_hash, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk.chunk_id, chunk.document_id, chunk.chunk_index, chunk.text,
                    chunk.content_hash, _metadata_json(chunk.metadata),
                ),
            )
            conn.execute(
                "INSERT INTO chunks_fts (rowid, text) VALUES (?, ?)",
                (cursor.lastrowid, chunk.text),
            )

    # -- retrieval ----------------------------------------------------

    def search(self, query: RetrievalQuery) -> RetrievalResult:
        if query.top_k < 1 or query.top_k > self._config.max_top_k:
            raise ValueError(
                f"top_k must be between 1 and {self._config.max_top_k}, got {query.top_k}."
            )

        normalized_query, terms = _extract_safe_terms(
            query.query, self._config.max_query_chars, self._config.max_query_terms
        )
        if not terms:
            raise EmptySearchQueryError(
                "Query contains no searchable terms after sanitization."
            )
        match_expression = _build_safe_match_query(terms)

        with self._connection() as conn:
            self._ensure_ready(conn)
            rows = conn.execute(
                """
                SELECT
                    c.chunk_id AS chunk_id,
                    c.document_id AS document_id,
                    c.text AS text,
                    c.metadata_json AS chunk_metadata_json,
                    d.title AS title,
                    d.source_id AS source_id,
                    d.source_type AS source_type,
                    d.classification AS classification,
                    d.trust_level AS trust_level,
                    bm25(chunks_fts) AS score
                FROM chunks_fts
                JOIN chunks c ON c.rowid = chunks_fts.rowid
                JOIN documents d ON d.document_id = c.document_id
                WHERE chunks_fts MATCH ?
                ORDER BY score ASC, c.chunk_id ASC
                LIMIT ?
                """,
                (match_expression, query.top_k),
            ).fetchall()

        hits = tuple(
            RetrievalHit(
                chunk_id=row["chunk_id"],
                document_id=row["document_id"],
                title=row["title"],
                text=row["text"],
                rank=index + 1,
                retrieval_score=row["score"],
                source_id=row["source_id"],
                source_type=row["source_type"],
                classification=row["classification"],
                trust_level=row["trust_level"],
                metadata=json.loads(row["chunk_metadata_json"]),
            )
            for index, row in enumerate(rows)
        )
        return RetrievalResult(
            normalized_query=normalized_query,
            term_count=len(terms),
            total_hits=len(hits),
            hits=hits,
        )

    # -- metadata / lifecycle -------------------------------------------

    def get_document(self, document_id: str) -> DocumentRecord | None:
        with self._connection() as conn:
            self._ensure_ready(conn)
            row = conn.execute(
                "SELECT * FROM documents WHERE document_id = ?", (document_id,)
            ).fetchone()
        if row is None:
            return None
        return DocumentRecord(
            document_id=row["document_id"],
            external_id=row["external_id"],
            source_key=row["source_key"],
            source_id=row["source_id"],
            source_type=row["source_type"],
            classification=row["classification"],
            trust_level=row["trust_level"],
            title=row["title"],
            content_hash=row["content_hash"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata=json.loads(row["metadata_json"]),
        )

    def delete_document(self, document_id: str) -> bool:
        with self._connection() as conn:
            self._ensure_ready(conn)
            old_rowids = [
                row["rowid"]
                for row in conn.execute(
                    "SELECT rowid FROM chunks WHERE document_id = ?", (document_id,)
                ).fetchall()
            ]
            for rowid in old_rowids:
                conn.execute("DELETE FROM chunks_fts WHERE rowid = ?", (rowid,))
            conn.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
            cursor = conn.execute(
                "DELETE FROM documents WHERE document_id = ?", (document_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
