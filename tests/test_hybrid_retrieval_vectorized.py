"""Tests for the vectorized semantic ranking path and the off-topic gate.

The load-bearing test here is `test_vectorized_scores_match_a_reference_loop`:
an optimization that changes results is not an optimization, it is a
behaviour change wearing a performance costume. That test recomputes cosine
with the same pure-Python loop the previous implementation used and asserts
the vectorized path agrees to float32 precision, on random vectors rather
than convenient ones.

The rest cover the two things most likely to go wrong in this rewrite:
storage round-tripping (a corrupt or legacy cache row must degrade, never
crash the query) and the off-topic decision's failure modes.
"""
import json
import math
import sqlite3
from pathlib import Path

import numpy as np
import pytest

from app.workspace import store
from app.workspace.hybrid_retrieval import (
    OFF_TOPIC_THRESHOLD,
    OffTopicError,
    decode_vector,
    encode_vector,
    evaluate_off_topic,
    max_score,
    normalize,
    semantic_rank,
)


class FakeEmbedder:
    """Deterministic embedder: no network, no Ollama, no model download."""

    def __init__(self, vectors: dict[str, list[float]], dim: int = 8) -> None:
        self.vectors = vectors
        self.dim = dim
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        out = []
        for text in texts:
            # Exact match first. Substring matching alone silently collides:
            # the key "noi dung doc-1" is a substring of "noi dung doc-10",
            # so document 10 would be handed document 1's vector and the
            # comparison against the reference loop would fail for reasons
            # that have nothing to do with the code under test.
            if text in self.vectors:
                out.append(list(self.vectors[text]))
                continue
            for key, vector in self.vectors.items():
                if key in text:
                    out.append(list(vector))
                    break
            else:
                out.append([0.0] * (self.dim - 1) + [1.0])
        return out


@pytest.fixture
def workspace(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "workspace.db")
    monkeypatch.setattr(store, "DOC_ROOT", tmp_path / "documents")
    store.initialize()
    return tmp_path


def _document(tmp_path: Path, doc_id: str, text: str) -> dict:
    """Create a document on disk AND in the documents table.

    The row matters: `document_embeddings.document_id` is a foreign key into
    `documents(id)`, so caching a vector for a document that was never
    registered fails the constraint -- which is the schema doing its job.
    """
    root = tmp_path / "documents"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{doc_id}.txt"
    path.write_text(text, encoding="utf-8")
    with store.connect() as db:
        db.execute(
            """INSERT OR IGNORE INTO documents
                 (id,owner_user_id,department,scope,audience_role,filename,
                  mime_type,size_bytes,guard_decision,storage_path,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (
                doc_id, None, "IT", "global", "member", f"{doc_id}.txt",
                "text/plain", len(text.encode("utf-8")), "allow", str(path), store.now(),
            ),
        )
    return {"id": doc_id, "storage_path": str(path), "filename": f"{doc_id}.txt"}


# --- vector encoding --------------------------------------------------------


def test_encode_decode_round_trips_as_unit_norm():
    blob, dim = encode_vector([3.0, 4.0])
    assert dim == 2
    restored = decode_vector(blob, dim)
    assert restored.dtype == np.dtype("<f4")
    assert math.isclose(float(np.linalg.norm(restored)), 1.0, rel_tol=1e-6)
    # 3-4-5 triangle: normalizing gives 0.6 / 0.8.
    assert np.allclose(restored, [0.6, 0.8], atol=1e-6)


def test_blob_is_portable_little_endian_float32():
    """The BLOB is persisted, so its layout is a storage format, not an
    implementation detail -- a machine with different native endianness must
    read back the same vector."""
    blob, dim = encode_vector([1.0, 0.0, 0.0, 0.0])
    assert len(blob) == dim * 4
    assert np.frombuffer(blob, dtype="<f4")[0] == pytest.approx(1.0)


@pytest.mark.parametrize("bad", [[0.0, 0.0], [float("nan"), 1.0], [float("inf"), 0.0], []])
def test_directionless_vectors_are_rejected(bad):
    """A zero or non-finite vector has no direction, so it has no meaningful
    cosine. Rejecting beats silently scoring 0 against the whole corpus."""
    with pytest.raises(RuntimeError):
        normalize(bad)


# --- the optimization must not change results -------------------------------


def _reference_cosine(left, right) -> float:
    """The exact pure-Python cosine the previous implementation used."""
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return -1.0
    return dot / (left_norm * right_norm)


def test_vectorized_scores_match_a_reference_loop(workspace, tmp_path):
    rng = np.random.default_rng(20260808)
    dim = 32
    raw = {f"doc-{i}": rng.normal(size=dim).tolist() for i in range(25)}
    query_vector = rng.normal(size=dim).tolist()

    documents = [_document(tmp_path, doc_id, f"noi dung {doc_id}") for doc_id in raw]
    embedder = FakeEmbedder({**{f"noi dung {k}": v for k, v in raw.items()},
                             "cau hoi": query_vector}, dim=dim)

    ranked = semantic_rank(
        "cau hoi", documents, model="fake-model", base_url="http://127.0.0.1:11434",
        connect_factory=store.connect, limit=len(documents), embedder=embedder,
    )

    assert len(ranked) == len(documents)
    for document, score in ranked:
        expected = _reference_cosine(raw[document["id"]], query_vector)
        assert score == pytest.approx(expected, abs=1e-5)


def test_ordering_is_descending_with_document_id_tiebreak(workspace, tmp_path):
    """Identical vectors must still produce a deterministic order, matching
    the previous implementation's `(-score, str(id))` sort."""
    shared = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    documents = [_document(tmp_path, f"doc-{i}", f"noi dung {i}") for i in ("c", "a", "b")]
    embedder = FakeEmbedder({f"noi dung {i}": shared for i in ("c", "a", "b")} | {"hoi": shared})

    ranked = semantic_rank(
        "hoi", documents, model="fake", base_url="http://127.0.0.1:11434",
        connect_factory=store.connect, limit=10, embedder=embedder,
    )
    assert [document["id"] for document, _score in ranked] == ["doc-a", "doc-b", "doc-c"]


def test_limit_is_respected(workspace, tmp_path):
    rng = np.random.default_rng(7)
    documents = [_document(tmp_path, f"d{i}", f"noi dung {i}") for i in range(10)]
    embedder = FakeEmbedder(
        {f"noi dung {i}": rng.normal(size=8).tolist() for i in range(10)} | {"hoi": [1.0] + [0.0] * 7}
    )
    ranked = semantic_rank(
        "hoi", documents, model="fake", base_url="http://127.0.0.1:11434",
        connect_factory=store.connect, limit=3, embedder=embedder,
    )
    assert len(ranked) == 3


# --- caching ----------------------------------------------------------------


def test_documents_are_embedded_once_and_served_from_cache(workspace, tmp_path):
    documents = [_document(tmp_path, "d1", "noi dung mot")]
    embedder = FakeEmbedder({"noi dung mot": [1.0, 0, 0, 0, 0, 0, 0, 0], "hoi": [1.0, 0, 0, 0, 0, 0, 0, 0]})
    kwargs = dict(
        model="fake", base_url="http://127.0.0.1:11434",
        connect_factory=store.connect, limit=5, embedder=embedder,
    )
    semantic_rank("hoi", documents, **kwargs)
    first_call_count = len(embedder.calls)
    semantic_rank("hoi", documents, **kwargs)

    # Second run re-embeds only the query, never the document.
    assert len(embedder.calls) == first_call_count + 1
    assert all("noi dung mot" not in text for text in embedder.calls[-1])


def test_stored_vector_is_persisted_as_blob(workspace, tmp_path):
    documents = [_document(tmp_path, "d1", "noi dung mot")]
    embedder = FakeEmbedder({"noi dung mot": [3.0, 4.0, 0, 0, 0, 0, 0, 0], "hoi": [1.0, 0, 0, 0, 0, 0, 0, 0]})
    semantic_rank(
        "hoi", documents, model="fake", base_url="http://127.0.0.1:11434",
        connect_factory=store.connect, limit=5, embedder=embedder,
    )
    with store.connect() as db:
        row = db.execute("SELECT vector_f32, dim FROM document_embeddings").fetchone()
    assert row["dim"] == 8
    assert math.isclose(float(np.linalg.norm(decode_vector(row["vector_f32"], row["dim"]))), 1.0, rel_tol=1e-6)


def test_legacy_json_only_cache_is_backfilled_not_re_embedded(workspace, tmp_path):
    """An existing cache from before the BLOB column must upgrade in place;
    forcing a full re-embed on upgrade would be an outage on a big corpus."""
    import hashlib

    text = "noi dung cu"
    document = _document(tmp_path, "d-legacy", text)
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    with store.connect() as db:
        db.execute(
            """INSERT INTO document_embeddings(document_id,model,content_hash,vector_json,updated_at)
               VALUES(?,?,?,?,datetime('now'))""",
            ("d-legacy", "fake", content_hash, json.dumps([3.0, 4.0, 0, 0, 0, 0, 0, 0])),
        )

    embedder = FakeEmbedder({"hoi": [0.6, 0.8, 0, 0, 0, 0, 0, 0]})
    ranked = semantic_rank(
        "hoi", [document], model="fake", base_url="http://127.0.0.1:11434",
        connect_factory=store.connect, limit=5, embedder=embedder,
    )
    assert ranked and ranked[0][1] == pytest.approx(1.0, abs=1e-5)
    # Only the query was embedded — the document came from the legacy row.
    assert all("noi dung cu" not in text for call in embedder.calls for text in call)
    with store.connect() as db:
        row = db.execute("SELECT vector_f32 FROM document_embeddings WHERE document_id='d-legacy'").fetchone()
    assert row["vector_f32"]


def test_corrupt_blob_does_not_break_the_query(workspace, tmp_path):
    import hashlib

    text = "noi dung hong"
    document = _document(tmp_path, "d-bad", text)
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    with store.connect() as db:
        db.execute(
            """INSERT INTO document_embeddings(document_id,model,content_hash,vector_json,vector_f32,dim,updated_at)
               VALUES(?,?,?,?,?,?,datetime('now'))""",
            ("d-bad", "fake", content_hash, json.dumps([1.0, 0, 0, 0, 0, 0, 0, 0]), b"\x00\x01\x02", 8),
        )
    embedder = FakeEmbedder({"hoi": [1.0, 0, 0, 0, 0, 0, 0, 0]})
    ranked = semantic_rank(
        "hoi", [document], model="fake", base_url="http://127.0.0.1:11434",
        connect_factory=store.connect, limit=5, embedder=embedder,
    )
    assert ranked and ranked[0][1] == pytest.approx(1.0, abs=1e-5)


def test_mixed_dimension_cache_does_not_raise(workspace, tmp_path):
    """Switching embedding models mid-corpus leaves rows of two widths.
    Stacking those would raise; the query must survive."""
    documents = [
        _document(tmp_path, "d8", "noi dung tam"),
        _document(tmp_path, "d4", "noi dung bon"),
    ]
    embedder = FakeEmbedder({
        "noi dung tam": [1.0, 0, 0, 0, 0, 0, 0, 0],
        "noi dung bon": [1.0, 0, 0, 0],
        "hoi": [1.0, 0, 0, 0, 0, 0, 0, 0],
    })
    ranked = semantic_rank(
        "hoi", documents, model="fake", base_url="http://127.0.0.1:11434",
        connect_factory=store.connect, limit=5, embedder=embedder,
    )
    assert [document["id"] for document, _s in ranked] == ["d8"]


# --- off-topic gate ---------------------------------------------------------


def _ranked(*scores: float):
    return [({"id": f"d{i}"}, score) for i, score in enumerate(scores)]


def test_off_topic_error_is_not_a_valueerror():
    """`store.retrieve` catches ValueError around the semantic path and
    treats it as 'embeddings unavailable'. A ValueError subclass would be
    swallowed there and the gate would silently never fire."""
    assert not issubclass(OffTopicError, ValueError)
    assert issubclass(OffTopicError, Exception)


def test_on_topic_query_passes_and_returns_best_score():
    assert evaluate_off_topic(_ranked(0.11, 0.62, 0.4), threshold=0.3) == pytest.approx(0.62)


def test_off_topic_query_raises_with_diagnostics():
    with pytest.raises(OffTopicError) as excinfo:
        evaluate_off_topic(_ranked(0.05, 0.21), threshold=0.3)
    assert excinfo.value.max_score == pytest.approx(0.21)
    assert excinfo.value.threshold == pytest.approx(0.3)


def test_threshold_boundary_is_inclusive_of_the_threshold():
    assert evaluate_off_topic(_ranked(0.3), threshold=0.3) == pytest.approx(0.3)
    with pytest.raises(OffTopicError):
        evaluate_off_topic(_ranked(0.29999), threshold=0.3)


def test_no_scores_defaults_to_allowing_the_request():
    """Embeddings unavailable is not evidence of off-topic. Failing closed
    here would turn an Ollama outage into a full outage."""
    assert evaluate_off_topic([], threshold=0.3) is None


def test_no_scores_can_fail_closed_when_explicitly_requested():
    with pytest.raises(OffTopicError):
        evaluate_off_topic([], threshold=0.3, fail_closed=True)


def test_max_score_distinguishes_absent_from_zero():
    assert max_score([]) is None
    assert max_score(_ranked(0.0)) == 0.0


def test_default_threshold_is_the_documented_placeholder():
    assert OFF_TOPIC_THRESHOLD == 0.3
