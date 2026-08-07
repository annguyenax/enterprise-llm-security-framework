"""Isolated document store for the intentionally unguarded comparison lab."""
from __future__ import annotations

import re
import unicodedata
import uuid
from typing import Any

from app.schemas.requests import RAGContextChunk
from app.workspace import store


def initialize() -> None:
    with store.connect() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS unguarded_documents (
                id TEXT PRIMARY KEY,
                owner_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                filename TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def documents(actor: dict[str, Any]) -> list[dict[str, Any]]:
    initialize()
    with store.connect() as db:
        rows = db.execute(
            """SELECT id,filename,mime_type,size_bytes,created_at
               FROM unguarded_documents WHERE owner_user_id=? ORDER BY created_at DESC""",
            (actor["id"],),
        )
        return [dict(row) | {"guard_decision": "not_evaluated"} for row in rows]


def add_document(
    actor: dict[str, Any], filename: str, content: str, mime_type: str, size_bytes: int
) -> dict[str, Any]:
    initialize()
    document_id = str(uuid.uuid4())
    created_at = store.now()
    with store.connect() as db:
        db.execute(
            """INSERT INTO unguarded_documents
               (id,owner_user_id,filename,mime_type,size_bytes,content,created_at)
               VALUES(?,?,?,?,?,?,?)""",
            (document_id, actor["id"], filename, mime_type, size_bytes, content, created_at),
        )
    return {
        "id": document_id,
        "filename": filename,
        "mime_type": mime_type,
        "size_bytes": size_bytes,
        "created_at": created_at,
        "guard_decision": "not_evaluated",
    }


def delete_document(actor: dict[str, Any], document_id: str) -> bool:
    initialize()
    with store.connect() as db:
        cursor = db.execute(
            "DELETE FROM unguarded_documents WHERE id=? AND owner_user_id=?",
            (document_id, actor["id"]),
        )
        return cursor.rowcount > 0


def retrieve(
    actor: dict[str, Any], query: str, limit: int = 4
) -> tuple[list[RAGContextChunk], list[dict[str, Any]]]:
    initialize()
    query_terms = _terms(query)
    with store.connect() as db:
        rows = [
            dict(row)
            for row in db.execute(
                "SELECT * FROM unguarded_documents WHERE owner_user_id=? ORDER BY created_at DESC",
                (actor["id"],),
            )
        ]
    scored = []
    for document in rows:
        searchable = f'{document["filename"]}\n{document["content"]}'
        score = sum(_normalize(searchable).count(term) for term in query_terms)
        if score:
            scored.append((score, document))
    scored.sort(key=lambda item: item[0], reverse=True)
    selected = scored[:limit]
    chunks = [
        RAGContextChunk(
            doc_id=document["id"],
            text=document["content"][:3000],
            metadata={"filename": document["filename"], "scope": "unguarded-private"},
        )
        for _, document in selected
    ]
    sources = [
        {"id": document["id"], "filename": document["filename"], "scope": "unguarded-private"}
        for _, document in selected
    ]
    return chunks, sources


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize(
        "NFKD", value.casefold().translate(str.maketrans({"đ": "d"}))
    )
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", ascii_text).strip()


def _terms(value: str) -> set[str]:
    return {term for term in _normalize(value).split() if len(term) > 2}
