import sqlite3
from pathlib import Path

import pytest

from app.workspace.hybrid_retrieval import OllamaEmbedder, semantic_rank


class FakeEmbedder:
    def __init__(self):
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        vectors = []
        for text in texts:
            normalized = text.casefold()
            vectors.append([1.0, 0.0] if "lương" in normalized else [0.0, 1.0])
        return vectors


def test_semantic_rank_prefers_meaning_and_caches_document_vectors(tmp_path: Path):
    database = tmp_path / "workspace.db"
    with sqlite3.connect(database) as db:
        db.execute("""CREATE TABLE document_embeddings (
            document_id TEXT NOT NULL, model TEXT NOT NULL, content_hash TEXT NOT NULL,
            vector_json TEXT NOT NULL, updated_at TEXT NOT NULL,
            PRIMARY KEY(document_id,model))""")

    salary = tmp_path / "salary.md"
    contract = tmp_path / "contract.md"
    salary.write_text("Chính sách lương và thu nhập.", encoding="utf-8")
    contract.write_text("Điều khoản bảo trì hệ thống.", encoding="utf-8")
    documents = [
        {"id": "salary", "storage_path": str(salary)},
        {"id": "contract", "storage_path": str(contract)},
    ]
    embedder = FakeEmbedder()

    def connect():
        return sqlite3.connect(database)

    first = semantic_rank(
        "lương tháng này",
        documents,
        model="synthetic-embed",
        base_url="http://127.0.0.1:11434",
        connect_factory=connect,
        limit=2,
        embedder=embedder,
    )
    second = semantic_rank(
        "lương tháng này",
        documents,
        model="synthetic-embed",
        base_url="http://127.0.0.1:11434",
        connect_factory=connect,
        limit=2,
        embedder=embedder,
    )

    assert first[0][0]["id"] == "salary"
    assert second[0][0]["id"] == "salary"
    assert len(embedder.calls[0]) == 1  # query
    assert len(embedder.calls[1]) == 2  # two uncached documents in one batch
    assert len(embedder.calls[2]) == 1  # only the query is recomputed


def test_ollama_embedder_rejects_non_local_endpoint():
    with pytest.raises(ValueError, match="local HTTP"):
        OllamaEmbedder("model", "https://example.invalid")
