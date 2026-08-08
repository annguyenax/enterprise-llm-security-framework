"""Local Ollama embeddings for workspace hybrid retrieval, vectorized.

What changed and why
--------------------
The previous implementation scored documents with a pure-Python cosine loop
(`sum(a * b for a, b in zip(...))`) executed once per document per query. At
300 documents x 768 dimensions that is ~230k interpreted multiply-adds on
every question.

Replacing only the loop with NumPy would not have fixed it. Vectors were
cached as `vector_json TEXT`, so every query still paid ~768 float parses
per document just to rebuild the arrays -- the JSON parser simply becomes
the new bottleneck. So both halves changed:

1. **Storage.** Vectors are persisted as raw little-endian float32
   (`document_embeddings.vector_f32`) and are **L2-normalized at write
   time**. Reading is `np.frombuffer`, a memcpy rather than a parse.
   `vector_json` is still read as a fallback and backfilled in place, so an
   existing cache upgrades without re-embedding anything.

2. **Scoring.** Because stored vectors are unit-norm, cosine similarity is
   exactly the dot product, so the whole corpus is scored with one
   `matrix @ query` call -- a single BLAS-backed operation instead of N
   Python loops.

Ordering is still `(-score, document_id)`, byte-identical to the previous
implementation: NumPy computes the scores, and the final sort stays in
Python because sorting a few hundred pairs is free next to the dot product,
and keeping it preserves the exact deterministic tie-break.

Access control is unchanged and unchanged-by-design: this module only ever
ranks documents the caller already authorized. It is a relevance function,
not an ACL boundary.
"""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from pathlib import Path
from typing import Any, Callable, Protocol, Sequence
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import numpy as np

# Cosine similarity below which a query is treated as unrelated to the whole
# knowledge base.
#
# **This default is a placeholder, not a tuned value.** Cosine distributions
# are a property of the embedding model, not a universal constant: many
# modern models (including the `nomic-embed-text` family this module
# special-cases) score genuinely unrelated Vietnamese text well above 0.3,
# which would make this gate pass everything. Calibrate it against your own
# corpus before relying on it -- see `scripts/calibrate_off_topic.py`, which
# reports the score distribution for on-topic vs off-topic probes and
# suggests a threshold. Shipping an uncalibrated gate is worse than shipping
# none: it produces confident-looking blocks with no evidence behind them.
OFF_TOPIC_THRESHOLD = 0.3

_FLOAT32 = np.dtype("<f4")  # explicit little-endian: BLOBs must be portable


class OffTopicError(Exception):
    """Raised when no document is semantically close enough to the query.

    **Deliberately NOT a subclass of `ValueError`.** `app/workspace/store.py`
    wraps the semantic path in `except (OSError, RuntimeError, ValueError,
    json.JSONDecodeError)` and treats anything caught there as "embeddings
    unavailable, fall back to BM25". A `ValueError` subclass would therefore
    be swallowed silently and the off-topic gate would never fire -- it would
    look implemented and do nothing. Inheriting straight from `Exception`
    means the caller has to handle it explicitly, which is the point.
    """

    def __init__(self, max_score: float, threshold: float) -> None:
        super().__init__(
            f"Query is off-topic for this knowledge base "
            f"(best match {max_score:.4f} < threshold {threshold:.4f})"
        )
        self.max_score = max_score
        self.threshold = threshold


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class OllamaEmbedder:
    def __init__(self, model: str, base_url: str, timeout_seconds: int = 30) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        parsed = urlparse(self.base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("Ollama embedding endpoint must be local HTTP")

    def embed(self, texts: list[str]) -> list[list[float]]:
        payload = json.dumps({"model": self.model, "input": texts}).encode("utf-8")
        request = Request(
            self.base_url + "/api/embed",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
        vectors = data.get("embeddings")
        if not isinstance(vectors, list) or len(vectors) != len(texts):
            raise RuntimeError("Ollama returned an invalid embedding response")
        parsed_vectors = []
        for vector in vectors:
            if not isinstance(vector, list) or not vector:
                raise RuntimeError("Ollama returned an empty embedding vector")
            parsed_vectors.append([float(value) for value in vector])
        return parsed_vectors


# --- vector encoding -------------------------------------------------------


def normalize(vector: Sequence[float]) -> np.ndarray:
    """Return `vector` as unit-norm float32.

    Normalizing once at write time is what lets query-time cosine collapse
    into a plain dot product. A zero or non-finite vector has no direction
    and therefore no meaningful cosine, so it is rejected here rather than
    silently scoring 0 against everything.
    """
    array = np.asarray(vector, dtype=_FLOAT32).ravel()
    if array.size == 0:
        raise RuntimeError("Embedding vector is empty")
    if not np.all(np.isfinite(array)):
        raise RuntimeError("Embedding vector contains non-finite values")
    norm = float(np.linalg.norm(array))
    if not math.isfinite(norm) or norm == 0.0:
        raise RuntimeError("Embedding vector has zero norm")
    return (array / norm).astype(_FLOAT32, copy=False)


def encode_vector(vector: Sequence[float]) -> tuple[bytes, int]:
    """Normalize and pack a vector into a portable float32 BLOB."""
    array = normalize(vector)
    return array.tobytes(), int(array.size)


def decode_vector(blob: bytes, dim: int | None = None) -> np.ndarray:
    """Unpack a stored BLOB. Read-only view -- callers must not mutate it.

    Every malformed-input path raises `RuntimeError`, including the
    `ValueError` NumPy itself raises when a truncated buffer is not a
    multiple of the element size. Callers recover from a bad cache row by
    catching one exception type; letting NumPy's own `ValueError` escape
    meant a single corrupt BLOB took the whole query down.
    """
    try:
        array = np.frombuffer(blob, dtype=_FLOAT32)
    except (ValueError, TypeError, BufferError) as exc:
        raise RuntimeError("Stored embedding is not a readable float32 buffer") from exc
    if array.size == 0 or (dim is not None and array.size != dim):
        raise RuntimeError("Stored embedding has an unexpected length")
    return array


# --- ranking ---------------------------------------------------------------


def _blob_columns_available(db: sqlite3.Connection) -> bool:
    """Whether this database has the float32 BLOB columns.

    `semantic_rank` accepts an arbitrary `connect_factory`, so it must not
    assume `store.initialize()` ran and migrated the schema -- callers
    (including tests and any other embedder of this module) legitimately
    supply a database with only the original `vector_json` column. Probing
    keeps the fast path where it is available and degrades to the legacy
    layout where it is not, instead of failing the whole query with
    `no such column`.

    Positional indexing is used because `PRAGMA table_info` rows come back
    as plain tuples on a connection without `row_factory` set.
    """
    return {"vector_f32", "dim"} <= {
        row[1] for row in db.execute("PRAGMA table_info(document_embeddings)")
    }


def _load_cached(
    db: sqlite3.Connection,
    document_id: Any,
    cache_model: str,
    content_hash: str,
    *,
    has_blob: bool,
) -> np.ndarray | None:
    """Read one cached vector, preferring the BLOB and backfilling from the
    legacy JSON column when only that is present."""
    columns = "vector_json, vector_f32, dim" if has_blob else "vector_json, NULL, NULL"
    row = db.execute(
        f"""SELECT {columns} FROM document_embeddings
            WHERE document_id=? AND model=? AND content_hash=?""",
        (document_id, cache_model, content_hash),
    ).fetchone()
    if row is None:
        return None

    raw, blob, dim = row[0], row[1], row[2]
    if blob:
        try:
            return decode_vector(blob, dim)
        except RuntimeError:
            # A corrupt BLOB is re-derived below rather than failing the
            # query: the JSON column is still authoritative during upgrade.
            pass

    if not raw:
        return None
    try:
        array = normalize(json.loads(raw))
    except (ValueError, TypeError, RuntimeError):
        return None
    if has_blob:
        db.execute(
            "UPDATE document_embeddings SET vector_f32=?, dim=? WHERE document_id=? AND model=?",
            (array.tobytes(), int(array.size), document_id, cache_model),
        )
    return array


def semantic_rank(
    query: str,
    documents: list[dict[str, Any]],
    *,
    model: str,
    base_url: str,
    connect_factory: Callable[[], sqlite3.Connection],
    limit: int,
    embedder: Embedder | None = None,
) -> list[tuple[dict[str, Any], float]]:
    """Rank only already-authorized documents, newest scoring path.

    Returns `(document, cosine_similarity)` pairs sorted by descending score
    with `document_id` as a stable tie-break -- the same contract, and the
    same ordering, as before this was vectorized.

    Never raises `OffTopicError`: this function reports relevance, it does
    not make policy decisions. See `evaluate_off_topic` for that, and the
    module docstring for why the split matters.
    """
    if not query.strip() or not documents or not model.strip():
        return []

    embedder = embedder or OllamaEmbedder(model, base_url)
    uses_nomic_prefix = "nomic-embed-text" in model.casefold()
    cache_model = model + ("|search-document-v1" if uses_nomic_prefix else "")
    query_input = f"search_query: {query}" if uses_nomic_prefix else query

    prepared: list[tuple[dict[str, Any], str, str]] = []
    for document in documents:
        try:
            text = Path(str(document["storage_path"])).read_text(encoding="utf-8")[:12_000]
        except OSError:
            continue
        prepared.append((document, text, hashlib.sha256(text.encode("utf-8")).hexdigest()))
    if not prepared:
        return []

    cached: dict[str, np.ndarray] = {}
    with connect_factory() as db:
        has_blob = _blob_columns_available(db)
        for document, _text, content_hash in prepared:
            vector = _load_cached(
                db, document["id"], cache_model, content_hash, has_blob=has_blob
            )
            if vector is not None:
                cached[str(document["id"])] = vector

    missing = [item for item in prepared if str(item[0]["id"]) not in cached]
    query_vector = normalize(embedder.embed([query_input])[0])

    if missing:
        with connect_factory() as db:
            has_blob = _blob_columns_available(db)
            for start in range(0, len(missing), 8):
                batch = missing[start:start + 8]
                inputs = [
                    f"search_document: {text}" if uses_nomic_prefix else text
                    for _document, text, _hash in batch
                ]
                vectors = embedder.embed(inputs)
                for (document, _text, content_hash), raw_vector in zip(batch, vectors):
                    array = normalize(raw_vector)
                    cached[str(document["id"])] = array
                    # `vector_json` is still written even when the BLOB is
                    # available: it keeps the cache readable by the previous
                    # implementation, so rolling this change back does not
                    # require re-embedding the corpus.
                    payload_json = json.dumps([float(value) for value in array])
                    if has_blob:
                        db.execute(
                            """INSERT INTO document_embeddings
                                 (document_id,model,content_hash,vector_json,vector_f32,dim,updated_at)
                               VALUES(?,?,?,?,?,?,datetime('now'))
                               ON CONFLICT(document_id,model) DO UPDATE SET
                                 content_hash=excluded.content_hash,
                                 vector_json=excluded.vector_json,
                                 vector_f32=excluded.vector_f32,
                                 dim=excluded.dim,
                                 updated_at=excluded.updated_at""",
                            (
                                document["id"], cache_model, content_hash,
                                payload_json, array.tobytes(), int(array.size),
                            ),
                        )
                    else:
                        db.execute(
                            """INSERT INTO document_embeddings
                                 (document_id,model,content_hash,vector_json,updated_at)
                               VALUES(?,?,?,?,datetime('now'))
                               ON CONFLICT(document_id,model) DO UPDATE SET
                                 content_hash=excluded.content_hash,
                                 vector_json=excluded.vector_json,
                                 updated_at=excluded.updated_at""",
                            (document["id"], cache_model, content_hash, payload_json),
                        )

    ordered = [
        (document, cached[str(document["id"])])
        for document, _text, _hash in prepared
        if str(document["id"]) in cached
    ]
    if not ordered:
        return []

    # A model change mid-corpus can leave mixed dimensions in the cache;
    # stacking those would raise. Keep the majority dimension (the current
    # model's) and drop the stragglers, which get re-embedded next time
    # their content hash misses.
    width = max(
        {vector.size for _document, vector in ordered},
        key=lambda size: sum(1 for _d, v in ordered if v.size == size),
    )
    ordered = [(document, vector) for document, vector in ordered if vector.size == width]
    if not ordered or query_vector.size != width:
        return []

    # The whole point: one BLAS-backed matrix-vector product replaces N
    # Python loops. Both operands are unit-norm, so this IS cosine.
    matrix = np.vstack([vector for _document, vector in ordered])
    scores = matrix @ query_vector

    ranked = [
        (document, float(score))
        for (document, _vector), score in zip(ordered, scores)
    ]
    ranked.sort(key=lambda item: (-item[1], str(item[0]["id"])))
    return ranked[:limit]


# --- off-topic decision ----------------------------------------------------


def max_score(ranked: Sequence[tuple[dict[str, Any], float]]) -> float | None:
    """Best cosine in a ranked result, or `None` when nothing was scored.

    `None` is not `0.0`: an empty result means the embedding model was
    disabled or unavailable, which is a very different fact from "nothing in
    the corpus is related". The off-topic gate must not conflate them.
    """
    if not ranked:
        return None
    return max(score for _document, score in ranked)


def evaluate_off_topic(
    ranked: Sequence[tuple[dict[str, Any], float]],
    *,
    threshold: float = OFF_TOPIC_THRESHOLD,
    fail_closed: bool = False,
) -> float | None:
    """Raise `OffTopicError` when the best match is below `threshold`.

    Returns the best score when the query is on-topic (or `None` when no
    score was available and `fail_closed` is False).

    **Availability policy is explicit, not implicit.** When embeddings are
    unavailable there is no evidence either way. `fail_closed=False` (the
    default) lets the request continue to the guards and BM25 retrieval,
    matching how `app/workspace/store.py` already treats the semantic path --
    "an availability enhancement, not an ACL boundary". Set `fail_closed=True`
    only if you have decided that a degraded embedding service should stop
    traffic; off-topic filtering is a cost control, and failing closed on it
    turns an Ollama outage into a full outage.
    """
    best = max_score(ranked)
    if best is None:
        if fail_closed:
            raise OffTopicError(max_score=float("-inf"), threshold=threshold)
        return None
    if best < threshold:
        raise OffTopicError(max_score=best, threshold=threshold)
    return best
