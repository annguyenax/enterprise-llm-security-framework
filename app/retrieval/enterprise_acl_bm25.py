"""Access-controlled SQLite FTS5/BM25 retriever for the enterprise KB.

Implements the same `app.retrieval.base.Retriever` contract as
`SqliteBM25Retriever` and registers itself through the ADR-004 registry, so
a backend can be selected by configuration without editing gateway code.

**Naming.** Registered as `enterprise_acl_bm25`, not `enterprise_hybrid`.
This backend is BM25 plus an ACL pre-filter; there is no dense retrieval in
it, and no fusion of two rankings. Calling it "hybrid" in a project whose
claims get independently audited would overstate what the code does. The
seam for dense retrieval is here (`_candidate_sql` is the only thing a
future hybrid backend would need to change), and renaming at that point is
a one-line registry change.

Why a separate class instead of extending the Phase 12B retriever
-----------------------------------------------------------------
`SqliteBM25Retriever` is audited, is what every frozen-benchmark evaluation
runs against, and has no ACL columns. Adding them there would change a
component three independent audits have already signed off on. This class
owns its own schema and its own database file, imports the
security-critical query-construction helpers from the Phase 12B module
rather than reimplementing them, and leaves that module untouched.

The one property that matters most
----------------------------------
**ACL filtering happens inside the candidate SQL, before `LIMIT`.** Ranking
first and filtering second would be wrong twice over: a low-clearance user
would lose legitimate results to documents they may not see, and the size
of the resulting gap is itself a signal about how many restricted documents
matched -- an existence oracle. Here, a document the principal may not read
is never a candidate at all.

`evaluate_acl` still runs afterwards in `app/guards/acl_guard.py`. That is
defence in depth, not redundancy: the two implementations of the same rule
have to agree, and a test asserts they do.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterator

from app.retrieval.acl import (
    DEPARTMENT_WILDCARD,
    AclFacts,
    RetrievalPrincipal,
    acl_facts_from_metadata,
    acl_metadata,
    canonical_timestamp,
    is_canonical_timestamp,
)
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
from app.retrieval.registry import register_retriever
from app.retrieval.sqlite_bm25 import (
    EmptySearchQueryError,
    FTS5UnavailableError,
    _build_safe_match_query,
    _connect,
    _extract_safe_terms,
)

RETRIEVER_NAME = "enterprise_acl_bm25"

_SCHEMA_VERSION = "1"

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
    -- Access-control columns. Separate, indexable columns rather than keys
    -- inside metadata_json: a JSON blob cannot be pre-filtered in SQL, and
    -- pre-filtering is the whole point.
    sensitivity_rank INTEGER NOT NULL,
    owner_department TEXT NOT NULL,
    valid_from TEXT,
    valid_to TEXT,
    UNIQUE (source_key, external_id)
);
CREATE INDEX IF NOT EXISTS idx_documents_sensitivity ON documents (sensitivity_rank);

-- Set-valued ACL columns are normalized into their own tables so they can
-- be pre-filtered with an indexed EXISTS rather than a LIKE over a
-- delimited string (which would also make 'it' match 'audit').
CREATE TABLE IF NOT EXISTS document_acl_roles (
    document_id TEXT NOT NULL REFERENCES documents (document_id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    PRIMARY KEY (document_id, role)
);
CREATE TABLE IF NOT EXISTS document_acl_departments (
    document_id TEXT NOT NULL REFERENCES documents (document_id) ON DELETE CASCADE,
    department TEXT NOT NULL,
    PRIMARY KEY (document_id, department)
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

# The ACL pre-filter. Applied in the same statement as the MATCH and before
# LIMIT, so unreadable documents never occupy a top_k slot.
_CANDIDATE_SQL = """
SELECT
    c.chunk_id            AS chunk_id,
    c.document_id         AS document_id,
    c.text                AS text,
    c.metadata_json       AS chunk_metadata_json,
    d.title               AS title,
    d.source_id           AS source_id,
    d.source_type         AS source_type,
    d.classification      AS classification,
    d.trust_level         AS trust_level,
    d.sensitivity_rank    AS sensitivity_rank,
    d.valid_from          AS valid_from,
    d.valid_to            AS valid_to,
    bm25(chunks_fts)      AS score
FROM chunks_fts
JOIN chunks c    ON c.rowid = chunks_fts.rowid
JOIN documents d ON d.document_id = c.document_id
WHERE chunks_fts MATCH ?
  AND d.sensitivity_rank <= ?
  AND (d.valid_from IS NULL OR d.valid_from <= ?)
  AND (d.valid_to   IS NULL OR d.valid_to   >  ?)
  AND EXISTS (
        SELECT 1 FROM document_acl_roles r
        WHERE r.document_id = d.document_id AND r.role = ?
      )
  AND EXISTS (
        SELECT 1 FROM document_acl_departments p
        WHERE p.document_id = d.document_id
          AND p.department IN (?, ?, ?)
      )
ORDER BY score ASC, c.chunk_id ASC
LIMIT ?
"""


class MissingPrincipalError(ValueError):
    """Raised when a search reaches this backend without a principal.

    Fail-closed by construction: this retriever has no notion of an
    anonymous query, so there is no default principal to fall back to and no
    "public documents only" degraded mode. Serving a reduced result set to
    an unidentified caller would be a silent partial authentication.
    """


class AclFactsUnavailableError(ValueError):
    """Raised at ingestion when a document arrives without ACL facts.

    A document with no access-control facts cannot be filtered, so it is
    refused at the door rather than stored in a state where the pre-filter
    would have to guess.
    """


@dataclass(frozen=True)
class EnterpriseAclBm25Config:
    db_path: str
    busy_timeout_ms: int = 5000
    max_query_chars: int = 500
    max_query_terms: int = 12
    max_top_k: int = 50


class EnterpriseAclBm25Retriever(Retriever):
    """BM25 retrieval with an in-SQL access-control pre-filter."""

    def __init__(self, config: EnterpriseAclBm25Config) -> None:
        self._config = config
        self._capability_confirmed = False

    # -- connection / schema ---------------------------------------------

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = _connect(self._config.db_path, self._config.busy_timeout_ms)
        try:
            yield conn
        finally:
            conn.close()

    def check_capability(self) -> None:
        """Same fail-loudly FTS5 probe as the Phase 12B backend: there is no
        degraded, non-FTS5 search path here either (ADR-002)."""
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
                    "-- see docs/decisions/ADR-002-retrieval-engine.md."
                ) from exc
        self._capability_confirmed = True

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript(_SCHEMA_SQL)
        conn.execute(
            "INSERT OR IGNORE INTO schema_meta (key, value) VALUES ('schema_version', ?)",
            (_SCHEMA_VERSION,),
        )
        conn.commit()

    def _ensure_ready(self, conn: sqlite3.Connection) -> None:
        if not self._capability_confirmed:
            self.check_capability()
        self._ensure_schema(conn)

    def initialize(self) -> None:
        if not self._capability_confirmed:
            self.check_capability()
        with self._connection() as conn:
            self._ensure_schema(conn)

    # -- ingestion --------------------------------------------------------

    @staticmethod
    def _facts_from_document(document: DocumentRecord) -> AclFacts:
        facts = acl_facts_from_metadata(document.metadata)
        if facts is None:
            raise AclFactsUnavailableError(
                f"document {document.document_id!r} carries no ACL facts; "
                "this backend cannot index a document it cannot filter"
            )
        if not facts.is_well_formed():
            raise AclFactsUnavailableError(
                f"document {document.document_id!r} carries malformed ACL facts"
            )
        return facts

    def upsert_documents(
        self, prepared: list[tuple[DocumentRecord, list[ChunkRecord]]]
    ) -> IngestionBatchResult:
        if not prepared:
            return IngestionBatchResult(
                indexed=0, updated=0, unchanged=0, rejected=0, items=()
            )

        # Validate the whole batch before opening a write transaction, so a
        # document with unusable ACL facts cannot leave a partial write.
        validated: list[tuple[DocumentRecord, list[ChunkRecord], AclFacts]] = []
        for document, chunks in prepared:
            validated.append((document, chunks, self._facts_from_document(document)))

        items: list[IngestionItemResult] = []
        indexed = updated = 0

        with self._connection() as conn:
            self._ensure_ready(conn)
            try:
                conn.execute("BEGIN IMMEDIATE")
                for document, chunks, facts in validated:
                    existed = (
                        conn.execute(
                            "SELECT 1 FROM documents WHERE document_id = ?",
                            (document.document_id,),
                        ).fetchone()
                        is not None
                    )
                    self._delete_document_rows(conn, document.document_id)
                    self._insert_document(conn, document, facts)
                    self._insert_chunks(conn, chunks)
                    if existed:
                        updated += 1
                        status = "updated"
                    else:
                        indexed += 1
                        status = "indexed"
                    items.append(
                        IngestionItemResult(
                            external_id=document.external_id,
                            source_key=document.source_key,
                            document_id=document.document_id,
                            status=status,
                            chunk_count=len(chunks),
                        )
                    )
                conn.commit()
            except Exception:
                conn.rollback()
                raise

        return IngestionBatchResult(
            indexed=indexed,
            updated=updated,
            unchanged=0,
            rejected=0,
            items=tuple(items),
        )

    @staticmethod
    def _delete_document_rows(conn: sqlite3.Connection, document_id: str) -> None:
        rowids = [
            row["rowid"]
            for row in conn.execute(
                "SELECT rowid FROM chunks WHERE document_id = ?", (document_id,)
            ).fetchall()
        ]
        for rowid in rowids:
            conn.execute("DELETE FROM chunks_fts WHERE rowid = ?", (rowid,))
        conn.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
        conn.execute("DELETE FROM document_acl_roles WHERE document_id = ?", (document_id,))
        conn.execute(
            "DELETE FROM document_acl_departments WHERE document_id = ?", (document_id,)
        )
        conn.execute("DELETE FROM documents WHERE document_id = ?", (document_id,))

    @staticmethod
    def _insert_document(
        conn: sqlite3.Connection, document: DocumentRecord, facts: AclFacts
    ) -> None:
        conn.execute(
            """
            INSERT INTO documents (
                document_id, external_id, source_key, source_id, source_type,
                classification, trust_level, title, content_hash, metadata_json,
                created_at, updated_at, sensitivity_rank, owner_department,
                valid_from, valid_to
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document.document_id,
                document.external_id,
                document.source_key,
                document.source_id,
                document.source_type,
                document.classification,
                document.trust_level,
                document.title,
                document.content_hash,
                json.dumps(dict(document.metadata), ensure_ascii=False, sort_keys=True),
                document.created_at,
                document.updated_at,
                facts.sensitivity_rank,
                str(document.metadata.get("owner_department", "")),
                facts.valid_from,
                facts.valid_to,
            ),
        )
        conn.executemany(
            "INSERT INTO document_acl_roles (document_id, role) VALUES (?, ?)",
            [(document.document_id, role) for role in sorted(facts.access_roles)],
        )
        conn.executemany(
            "INSERT INTO document_acl_departments (document_id, department) VALUES (?, ?)",
            [
                (document.document_id, department)
                for department in sorted(facts.access_departments)
            ],
        )

    @staticmethod
    def _insert_chunks(conn: sqlite3.Connection, chunks: list[ChunkRecord]) -> None:
        for chunk in chunks:
            cursor = conn.execute(
                """
                INSERT INTO chunks (
                    chunk_id, document_id, chunk_index, text, content_hash, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk.chunk_id,
                    chunk.document_id,
                    chunk.chunk_index,
                    chunk.text,
                    chunk.content_hash,
                    json.dumps(dict(chunk.metadata), ensure_ascii=False, sort_keys=True),
                ),
            )
            conn.execute(
                "INSERT INTO chunks_fts (rowid, text) VALUES (?, ?)",
                (cursor.lastrowid, chunk.text),
            )

    # -- retrieval --------------------------------------------------------

    def search(self, query: RetrievalQuery) -> RetrievalResult:
        """Return ACL-filtered ranked hits.

        `query.as_of` fixes the instant that time-bounded access rules are
        evaluated at. It falls back to the current time only when the caller
        supplies none; any caller that needs reproducibility (the test
        suite, any evaluation) passes it, making retrieval over a fixed
        corpus a pure function of its inputs.
        """
        if query.top_k < 1 or query.top_k > self._config.max_top_k:
            raise ValueError(
                f"top_k must be between 1 and {self._config.max_top_k}, got {query.top_k}."
            )

        principal = query.principal
        if not isinstance(principal, RetrievalPrincipal) or not principal.is_well_formed():
            raise MissingPrincipalError(
                "enterprise_acl_bm25 requires a well-formed RetrievalPrincipal; "
                "there is no anonymous or reduced-visibility search mode."
            )

        as_of = query.as_of
        if as_of is None:
            as_of = canonical_timestamp(datetime.now(timezone.utc))
        if not is_canonical_timestamp(as_of):
            raise ValueError("as_of must be a canonical UTC timestamp")

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
                _CANDIDATE_SQL,
                (
                    match_expression,
                    principal.max_sensitivity_rank,
                    as_of,
                    as_of,
                    principal.role,
                    principal.department,
                    DEPARTMENT_WILDCARD,
                    f"user_{principal.user_id}",
                    query.top_k,
                ),
            ).fetchall()

        hits = tuple(
            self._row_to_hit(row, index) for index, row in enumerate(rows)
        )
        return RetrievalResult(
            normalized_query=normalized_query,
            term_count=len(terms),
            total_hits=len(hits),
            hits=hits,
        )

    def _row_to_hit(self, row: sqlite3.Row, index: int) -> RetrievalHit:
        chunk_metadata = json.loads(row["chunk_metadata_json"])
        if not isinstance(chunk_metadata, dict):
            chunk_metadata = {}
        roles = [
            r["role"] for r in self._acl_rows("document_acl_roles", "role", row["document_id"])
        ]
        departments = [
            r["department"]
            for r in self._acl_rows(
                "document_acl_departments", "department", row["document_id"]
            )
        ]
        facts = AclFacts(
            sensitivity_rank=row["sensitivity_rank"],
            access_roles=frozenset(roles),
            access_departments=frozenset(departments),
            valid_from=row["valid_from"],
            valid_to=row["valid_to"],
        )
        chunk_metadata.update(acl_metadata(facts))
        return RetrievalHit(
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
            metadata=chunk_metadata,
        )

    def _acl_rows(self, table: str, column: str, document_id: str) -> list[sqlite3.Row]:
        # `table`/`column` are module-private literals, never caller input.
        with self._connection() as conn:
            return conn.execute(
                f"SELECT {column} FROM {table} WHERE document_id = ? ORDER BY {column}",
                (document_id,),
            ).fetchall()

    # -- metadata / lifecycle ---------------------------------------------

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
            existed = (
                conn.execute(
                    "SELECT 1 FROM documents WHERE document_id = ?", (document_id,)
                ).fetchone()
                is not None
            )
            if existed:
                self._delete_document_rows(conn, document_id)
                conn.commit()
            return existed


def _factory() -> EnterpriseAclBm25Retriever:
    """Registry factory. Reads configuration at construction time rather
    than import time, so a test that changes settings still gets the right
    database path."""
    from app.core.config import settings

    return EnterpriseAclBm25Retriever(
        EnterpriseAclBm25Config(
            db_path=settings.enterprise_kb_db_path,
            busy_timeout_ms=settings.retrieval_busy_timeout_ms,
            max_query_chars=settings.retrieval_max_query_chars,
            max_query_terms=settings.retrieval_max_query_terms,
            max_top_k=settings.retrieval_max_top_k,
        )
    )


register_retriever(RETRIEVER_NAME, _factory)
