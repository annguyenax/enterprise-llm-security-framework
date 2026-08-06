"""Optional local Ollama embeddings for workspace hybrid retrieval."""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from pathlib import Path
from typing import Any, Callable, Protocol
from urllib.parse import urlparse
from urllib.request import Request, urlopen


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


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return -1.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return -1.0
    return dot / (left_norm * right_norm)


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
    """Rank only already-authorized documents and cache document vectors."""
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
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        prepared.append((document, text, content_hash))

    cached: dict[str, list[float]] = {}
    with connect_factory() as db:
        for document, _text, content_hash in prepared:
            row = db.execute(
                "SELECT vector_json FROM document_embeddings WHERE document_id=? AND model=? AND content_hash=?",
                (document["id"], cache_model, content_hash),
            ).fetchone()
            if row is not None:
                cached[str(document["id"])] = [float(value) for value in json.loads(row[0])]

    missing = [item for item in prepared if str(item[0]["id"]) not in cached]
    query_vector = embedder.embed([query_input])[0]
    if missing:
        with connect_factory() as db:
            for start in range(0, len(missing), 8):
                batch = missing[start:start + 8]
                inputs = [
                    f"search_document: {text}" if uses_nomic_prefix else text
                    for _document, text, _hash in batch
                ]
                vectors = embedder.embed(inputs)
                for (document, _text, content_hash), vector in zip(batch, vectors):
                    cached[str(document["id"])] = vector
                    db.execute(
                        """INSERT INTO document_embeddings(document_id,model,content_hash,vector_json,updated_at)
                           VALUES(?,?,?,?,datetime('now'))
                           ON CONFLICT(document_id,model) DO UPDATE SET
                             content_hash=excluded.content_hash,
                             vector_json=excluded.vector_json,
                             updated_at=excluded.updated_at""",
                        (document["id"], cache_model, content_hash, json.dumps(vector)),
                    )

    ranked = [
        (document, _cosine(query_vector, cached[str(document["id"])]))
        for document, _text, _hash in prepared
        if str(document["id"]) in cached
    ]
    ranked.sort(key=lambda item: (-item[1], str(item[0]["id"])))
    return ranked[:limit]
