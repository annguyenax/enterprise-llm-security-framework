"""Tests for app/retrieval/sqlite_bm25.py (Phase 12B SQLite FTS5/BM25
retriever). Every test uses pytest's `tmp_path` fixture for a fresh,
isolated on-disk SQLite file -- never `:memory:`, since this retriever
opens a new short-lived connection per operation, and `:memory:` databases
are private to a single connection and would not persist between calls.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from unittest.mock import patch

import pytest

from app.retrieval.models import ChunkRecord, DocumentRecord, RetrievalQuery
from app.retrieval.sqlite_bm25 import (
    EmptySearchQueryError,
    FTS5UnavailableError,
    IngestionBatchError,
    SqliteBM25Config,
    SqliteBM25Retriever,
    _build_safe_match_query,
    _extract_safe_terms,
)


def _make_retriever(tmp_path, **overrides) -> SqliteBM25Retriever:
    config = SqliteBM25Config(db_path=str(tmp_path / "retrieval.db"), **overrides)
    return SqliteBM25Retriever(config)


def _document(document_id="doc_1", external_id="ext-1", content_hash="hash1") -> DocumentRecord:
    return DocumentRecord(
        document_id=document_id, external_id=external_id, source_key="api_upload",
        source_id="api_upload", source_type="api_upload", classification="internal",
        trust_level="untrusted_external", title="Title", content_hash=content_hash,
        created_at="t1", updated_at="t1", metadata={},
    )


def _chunk(document_id, index, text, content_hash="ch1") -> ChunkRecord:
    return ChunkRecord(
        chunk_id=f"{document_id}_c{index:04d}", document_id=document_id, chunk_index=index,
        text=text, content_hash=content_hash, metadata={},
    )


# -- FTS5 capability -------------------------------------------------------


def test_capability_succeeds_in_supported_environment(tmp_path):
    retriever = _make_retriever(tmp_path)
    retriever.check_capability()  # must not raise


class _FTS5LessConnection:
    """Minimal fake connection simulating a SQLite build without the FTS5
    extension compiled in. sqlite3.Connection is an immutable C type and
    cannot be patched directly (setattr on it raises TypeError), so
    check_capability's failure path is exercised via this fake instead."""

    def execute(self, sql: str, *args: object) -> None:
        if "USING fts5" in sql:
            raise sqlite3.OperationalError("no such module: fts5")

    def close(self) -> None:
        pass


def test_capability_failure_raises_fts5_unavailable_error(tmp_path):
    retriever = _make_retriever(tmp_path)

    @contextmanager
    def fake_connection():
        yield _FTS5LessConnection()

    with patch.object(retriever, "_connection", fake_connection):
        with pytest.raises(FTS5UnavailableError):
            retriever.check_capability()


def test_no_fallback_when_capability_check_fails(tmp_path):
    """When FTS5 is unavailable, every public operation must fail the
    same way -- never silently degrade to another search strategy."""
    retriever = _make_retriever(tmp_path)
    with patch.object(
        SqliteBM25Retriever, "check_capability", side_effect=FTS5UnavailableError("no fts5")
    ):
        with pytest.raises(FTS5UnavailableError):
            retriever.initialize()
        with pytest.raises(FTS5UnavailableError):
            retriever.search(RetrievalQuery(query="anything", top_k=5))
        with pytest.raises(FTS5UnavailableError):
            retriever.upsert_documents([(_document(), [_chunk("doc_1", 0, "text")])])


# -- initialization / schema / persistence ---------------------------------


def test_initialize_creates_schema(tmp_path):
    retriever = _make_retriever(tmp_path)
    retriever.initialize()
    assert (tmp_path / "retrieval.db").exists()


def test_foreign_keys_enabled(tmp_path):
    retriever = _make_retriever(tmp_path)
    retriever.initialize()
    with retriever._connection() as conn:  # noqa: SLF001 -- test-only access
        row = conn.execute("PRAGMA foreign_keys").fetchone()
        assert row[0] == 1


def test_persistence_across_connections(tmp_path):
    retriever = _make_retriever(tmp_path)
    retriever.upsert_documents([(_document(), [_chunk("doc_1", 0, "warranty policy text")])])

    # A brand-new retriever instance pointed at the same file must see the
    # same data -- proves data survives independent short-lived connections.
    other = _make_retriever(tmp_path)
    doc = other.get_document("doc_1")
    assert doc is not None
    assert doc.content_hash == "hash1"


def test_upsert_new_document_indexes_all_chunks(tmp_path):
    retriever = _make_retriever(tmp_path)
    chunks = [_chunk("doc_1", 0, "alpha text"), _chunk("doc_1", 1, "beta text")]
    result = retriever.upsert_documents([(_document(), chunks)])
    assert result.indexed == 1
    assert result.updated == 0
    assert result.unchanged == 0
    assert result.items[0].status == "indexed"
    assert result.items[0].chunk_count == 2


def test_upsert_unchanged_content_is_noop(tmp_path):
    retriever = _make_retriever(tmp_path)
    doc = _document()
    chunks = [_chunk("doc_1", 0, "same text")]
    retriever.upsert_documents([(doc, chunks)])
    result = retriever.upsert_documents([(doc, chunks)])
    assert result.unchanged == 1
    assert result.indexed == 0


def test_no_stale_fts_rows_after_upsert_replaces_content(tmp_path):
    retriever = _make_retriever(tmp_path)
    retriever.upsert_documents([(_document(), [_chunk("doc_1", 0, "old shipping content")])])

    updated_doc = _document(content_hash="hash2")
    retriever.upsert_documents([(updated_doc, [_chunk("doc_1", 0, "new warranty content")])])

    stale_hits = retriever.search(RetrievalQuery(query="shipping", top_k=5))
    assert stale_hits.total_hits == 0

    fresh_hits = retriever.search(RetrievalQuery(query="warranty", top_k=5))
    assert fresh_hits.total_hits == 1
    assert fresh_hits.hits[0].text == "new warranty content"


def test_atomic_rollback_on_unexpected_failure(tmp_path):
    retriever = _make_retriever(tmp_path)
    good_doc = _document(document_id="doc_good", external_id="ext-good")
    bad_chunks_causing_error = [_chunk("doc_good", 0, "x")]

    with patch.object(
        SqliteBM25Retriever, "_insert_chunks", side_effect=sqlite3.OperationalError("boom")
    ):
        with pytest.raises(IngestionBatchError):
            retriever.upsert_documents([(good_doc, bad_chunks_causing_error)])

    # Nothing from the failed batch should have been committed.
    assert retriever.get_document("doc_good") is None


def test_deterministic_search_ordering(tmp_path):
    retriever = _make_retriever(tmp_path)
    retriever.upsert_documents(
        [
            (_document(document_id="doc_a", external_id="a"), [_chunk("doc_a", 0, "warranty warranty warranty")]),
            (_document(document_id="doc_b", external_id="b"), [_chunk("doc_b", 0, "warranty mention")]),
        ]
    )
    first = retriever.search(RetrievalQuery(query="warranty", top_k=5))
    second = retriever.search(RetrievalQuery(query="warranty", top_k=5))
    assert [h.chunk_id for h in first.hits] == [h.chunk_id for h in second.hits]
    # More occurrences of the term should rank doc_a's chunk ahead of doc_b's.
    assert first.hits[0].document_id == "doc_a"


def test_sequential_short_lived_connections_do_not_corrupt_state(tmp_path):
    retriever = _make_retriever(tmp_path)
    for i in range(5):
        retriever.upsert_documents(
            [(_document(document_id=f"doc_{i}", external_id=f"ext-{i}"), [_chunk(f"doc_{i}", 0, f"content number {i}")])]
        )
    for i in range(5):
        assert retriever.get_document(f"doc_{i}") is not None


def test_delete_document_removes_chunks_and_fts_rows(tmp_path):
    retriever = _make_retriever(tmp_path)
    retriever.upsert_documents([(_document(), [_chunk("doc_1", 0, "searchable content")])])
    assert retriever.delete_document("doc_1") is True
    assert retriever.get_document("doc_1") is None
    assert retriever.search(RetrievalQuery(query="searchable", top_k=5)).total_hits == 0
    assert retriever.delete_document("doc_1") is False


# -- query security ---------------------------------------------------------


@pytest.mark.parametrize(
    "raw_query",
    [
        'warranty "quoted phrase"',
        "warranty (parentheses)",
        "warranty*",
        "warranty:column",
        "warranty NEAR/3 policy",
        "warranty OR policy AND NOT scope",
        "warranty' OR '1'='1",
        "'; DROP TABLE documents; --",
        "\x00\x01warranty\x02\x03",
        "!!!@@@###$$$",
        "a" * 5000,
    ],
)
def test_query_sanitization_never_raises_unexpectedly(tmp_path, raw_query):
    retriever = _make_retriever(tmp_path, max_query_chars=500, max_query_terms=12)
    retriever.upsert_documents([(_document(), [_chunk("doc_1", 0, "warranty policy content")])])
    try:
        retriever.search(RetrievalQuery(query=raw_query, top_k=5))
    except EmptySearchQueryError:
        pass  # acceptable: query had no extractable terms


def test_empty_normalized_query_is_rejected(tmp_path):
    retriever = _make_retriever(tmp_path)
    retriever.upsert_documents([(_document(), [_chunk("doc_1", 0, "content")])])
    with pytest.raises(EmptySearchQueryError):
        retriever.search(RetrievalQuery(query="*** ((( ))) :::", top_k=5))


def test_unicode_vietnamese_query(tmp_path):
    retriever = _make_retriever(tmp_path)
    retriever.upsert_documents(
        [(_document(), [_chunk("doc_1", 0, "Chính sách bảo mật yêu cầu mật khẩu mạnh")])]
    )
    result = retriever.search(RetrievalQuery(query="mật khẩu", top_k=5))
    assert result.total_hits == 1


def test_reserved_words_treated_as_literal_terms_not_operators(tmp_path):
    retriever = _make_retriever(tmp_path)
    retriever.upsert_documents([(_document(), [_chunk("doc_1", 0, "the word NEAR appears literally here")])])
    result = retriever.search(RetrievalQuery(query="NEAR", top_k=5))
    assert result.total_hits == 1


def test_repeated_query_returns_stable_result(tmp_path):
    retriever = _make_retriever(tmp_path)
    retriever.upsert_documents([(_document(), [_chunk("doc_1", 0, "stable content for repetition test")])])
    first = retriever.search(RetrievalQuery(query="stable content", top_k=5))
    second = retriever.search(RetrievalQuery(query="stable content", top_k=5))
    assert first == second


def test_extract_safe_terms_truncates_and_bounds_term_count():
    normalized, terms = _extract_safe_terms("a" * 1000, max_query_chars=10, max_query_terms=3)
    assert len(normalized) == 10
    normalized2, terms2 = _extract_safe_terms(
        "one two three four five six", max_query_chars=500, max_query_terms=3
    )
    assert terms2 == ["one", "two", "three"]


def test_build_safe_match_query_quotes_every_term():
    expression = _build_safe_match_query(["warranty", "NEAR"])
    assert expression == '"warranty" "NEAR"'


def test_top_k_bounds_enforced(tmp_path):
    retriever = _make_retriever(tmp_path, max_top_k=5)
    retriever.upsert_documents([(_document(), [_chunk("doc_1", 0, "content")])])
    with pytest.raises(ValueError):
        retriever.search(RetrievalQuery(query="content", top_k=100))
    with pytest.raises(ValueError):
        retriever.search(RetrievalQuery(query="content", top_k=0))
