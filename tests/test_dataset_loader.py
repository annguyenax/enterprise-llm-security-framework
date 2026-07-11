"""Tests for app/services/dataset_loader.py (Phase 5 dataset ingestion)."""
from app.services.dataset_loader import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    chunk_document,
    load_all_chunks,
    load_all_documents,
)


def test_loads_5_clean_and_5_poisoned_documents():
    documents = load_all_documents()
    clean_docs = [d for d in documents if not d.is_poisoned]
    poisoned_docs = [d for d in documents if d.is_poisoned]

    assert len(clean_docs) == 5
    assert len(poisoned_docs) == 5


def test_every_document_has_doc_id_and_source_path():
    for document in load_all_documents():
        assert document.doc_id
        assert document.source_path
        assert document.content


def test_chunking_is_deterministic():
    documents = load_all_documents()
    document = documents[0]

    first_pass = chunk_document(document)
    second_pass = chunk_document(document)

    assert [c.text for c in first_pass] == [c.text for c in second_pass]
    assert [c.chunk_index for c in first_pass] == [c.chunk_index for c in second_pass]


def test_chunks_preserve_doc_id_and_source_path():
    documents = load_all_documents()
    document = next(d for d in documents if not d.is_poisoned)

    chunks = chunk_document(document)

    assert len(chunks) >= 1
    for chunk in chunks:
        assert chunk.doc_id == document.doc_id
        assert chunk.source_path == document.source_path
        assert chunk.is_poisoned == document.is_poisoned


def test_load_all_chunks_matches_manual_chunking():
    documents = load_all_documents()
    expected = []
    for document in documents:
        expected.extend(chunk_document(document))

    actual = load_all_chunks()

    assert len(actual) == len(expected)
    assert [c.text for c in actual] == [c.text for c in expected]


def test_poisoned_document_attack_payload_fits_in_a_single_chunk():
    """Each poisoned doc's 'Poisoned Content' fenced block is short enough
    to stay within one chunk at the default chunk size, so a RAG Guard rule
    can never have its trigger pattern split across a chunk boundary."""
    documents = load_all_documents()
    poisoned_docs = [d for d in documents if d.is_poisoned]

    for document in poisoned_docs:
        assert len(document.content) <= DEFAULT_CHUNK_SIZE
        chunks = chunk_document(document)
        assert len(chunks) == 1


def test_chunk_size_and_overlap_defaults_are_positive_and_consistent():
    assert DEFAULT_CHUNK_SIZE > 0
    assert 0 <= DEFAULT_CHUNK_OVERLAP < DEFAULT_CHUNK_SIZE
