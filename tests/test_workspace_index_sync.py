import sqlite3
from pathlib import Path

from app.retrieval.enterprise_acl_bm25 import (
    EnterpriseAclBm25Config,
    EnterpriseAclBm25Retriever,
)
from app.workspace import store


def test_startup_sync_indexes_seed_document_with_filename_and_acl(monkeypatch, tmp_path: Path):
    workspace_db = tmp_path / "workspace.db"
    retrieval_db = tmp_path / "enterprise-kb.db"
    upload_root = tmp_path / "uploads"
    upload_root.mkdir()
    document_path = upload_root / "leader-plan.txt"
    document_path.write_text(
        "Ke hoach leader IT: phan cong cong viec va bao cao tuan.",
        encoding="utf-8",
    )

    retriever = EnterpriseAclBm25Retriever(
        EnterpriseAclBm25Config(db_path=str(retrieval_db))
    )
    retriever.initialize()
    monkeypatch.setattr(store, "DB_PATH", workspace_db)
    monkeypatch.setattr(store, "DOC_ROOT", tmp_path / "documents")
    monkeypatch.setattr(store, "_RETRIEVER", retriever)
    store.initialize()

    leader = store.authenticate("it.leader", "ITLeader#2026")[1]
    member = store.authenticate("it.user1", "ITUser1#2026")[1]
    row = {
        "id": "seed-it-leader-plan",
        "owner_user_id": leader["id"],
        "department": "IT",
        "scope": "department",
        "audience_role": "leader",
        "filename": "it-ke-hoach-leader.md",
        "mime_type": "text/markdown",
        "size_bytes": document_path.stat().st_size,
        "guard_decision": "allow",
        "storage_path": str(document_path),
        "created_at": store.now(),
    }
    with store.connect() as db:
        db.execute(
            "INSERT INTO documents VALUES(:id,:owner_user_id,:department,:scope,:audience_role,:filename,:mime_type,:size_bytes,:guard_decision,:storage_path,:created_at)",
            row,
        )

    result = store.synchronize_document_index()
    assert result == {"indexed": 1, "removed": 0, "skipped": 0}

    # Simulate an older chunk written before workspace metadata was copied to
    # chunks. Retrieval must still inherit filename/scope from the document.
    with sqlite3.connect(retrieval_db) as db:
        db.execute(
            "UPDATE chunks SET metadata_json='{}' WHERE document_id=?",
            (row["id"],),
        )

    chunks, sources = store.retrieve(leader, "ke hoach leader IT")
    assert sources == [
        {
            "id": row["id"],
            "filename": "it-ke-hoach-leader.md",
            "scope": "department",
        }
    ]
    assert chunks[0].metadata["filename"] == "it-ke-hoach-leader.md"
    assert store.retrieve(member, "ke hoach leader IT") == ([], [])

    exact_chunks, exact_sources = store.retrieve(
        leader, "Cho tôi nội dung file it-ke-hoach-leader.md"
    )
    assert len(exact_chunks) == 1
    assert exact_sources[0]["filename"] == "it-ke-hoach-leader.md"
    assert store.retrieve(member, "Cho tôi file it-ke-hoach-leader.md") == ([], [])

    generic_chunks, generic_sources = store.retrieve(
        leader, "Nội dung file kế hoạch là gì?"
    )
    assert len(generic_chunks) == 1
    assert generic_sources[0]["filename"] == "it-ke-hoach-leader.md"
