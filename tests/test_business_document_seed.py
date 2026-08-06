from pathlib import Path

from app.retrieval.enterprise_acl_bm25 import (
    EnterpriseAclBm25Config,
    EnterpriseAclBm25Retriever,
)
from app.workspace import store
from app.workspace.business_document_seed import BUSINESS_DOCUMENTS, seed_business_documents


def test_business_seed_is_idempotent_and_enforces_acl(monkeypatch, tmp_path: Path):
    retriever = EnterpriseAclBm25Retriever(
        EnterpriseAclBm25Config(db_path=str(tmp_path / "enterprise-kb.db"))
    )
    retriever.initialize()
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "workspace.db")
    monkeypatch.setattr(store, "DOC_ROOT", tmp_path / "documents")
    monkeypatch.setattr(store, "_RETRIEVER", retriever)

    first = seed_business_documents()
    second = seed_business_documents()
    assert len(first["created"]) == len(BUSINESS_DOCUMENTS) == 18
    assert second == {
        "created": [],
        "skipped": [item["filename"] for item in BUSINESS_DOCUMENTS],
        "total": 18,
    }

    users = {user["username"]: user for user in store.users()}
    visible = {
        username: {doc["filename"] for doc in store.accessible_documents(actor)}
        for username, actor in users.items()
    }

    assert "hop-dong-doi-tac-alpha-cloud-2026.md" in visible["superadmin"]
    assert "hop-dong-doi-tac-alpha-cloud-2026.md" not in visible["it.leader"]
    assert "bao-cao-chi-phi-nhan-su-q2-2026.md" in visible["it.leader"]
    assert "bao-cao-chi-phi-nhan-su-q2-2026.md" not in visible["it.user1"]
    assert "hop-dong-bao-tri-he-thong-beta-tech.md" in visible["it.leader"]
    assert "hop-dong-bao-tri-he-thong-beta-tech.md" not in visible["hr.leader"]
    assert "hop-dong-lao-dong-it-user1.md" in visible["it.user1"]
    assert "hop-dong-lao-dong-it-user1.md" not in visible["it.user2"]
    assert "hop-dong-lao-dong-hr-user1.md" not in visible["it.user1"]

    chunks, sources = store.retrieve(
        users["it.user1"], "đọc file hop-dong-lao-dong-it-user1.md"
    )
    assert len(chunks) == 1
    assert sources[0]["filename"] == "hop-dong-lao-dong-it-user1.md"
    assert "24 triệu đồng" in chunks[0].text


def test_explicit_user_and_group_grants_are_authoritative(monkeypatch, tmp_path: Path):
    retriever = EnterpriseAclBm25Retriever(
        EnterpriseAclBm25Config(db_path=str(tmp_path / "enterprise-kb.db"))
    )
    retriever.initialize()
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "workspace.db")
    monkeypatch.setattr(store, "DOC_ROOT", tmp_path / "documents")
    monkeypatch.setattr(store, "_RETRIEVER", retriever)
    store.initialize()
    users = {user["username"]: user for user in store.users()}

    row = store.add_document(
        users["it.user1"],
        "hop-dong-chia-se-co-kiem-soat.md",
        b"Synthetic employment contract shared with HR leader.",
        "user",
        "member",
        "IT",
        guard_decision="allow",
        mime_type="text/markdown",
        allowed_users=["it.user2"],
        allowed_groups=["HR:leader"],
    )

    assert row["allowed_users"] == ["it.user2"]
    assert row["allowed_groups"] == ["HR:leader"]
    visible = {
        username: {doc["filename"]: doc for doc in store.accessible_documents(actor)}
        for username, actor in users.items()
    }
    assert visible["it.user2"][row["filename"]]["access_reason"] == "explicit-user"
    assert visible["hr.leader"][row["filename"]]["access_reason"] == "explicit-group"
    assert row["filename"] not in visible["hr.user1"]
    assert row["filename"] not in visible["it.leader"]

    chunks, sources = store.retrieve(users["hr.leader"], "employment contract shared HR")
    assert sources[0]["filename"] == row["filename"]
    assert "shared with HR leader" in chunks[0].text
    denied_chunks, denied_sources = store.retrieve(
        users["hr.user1"], "employment contract shared HR"
    )
    assert all(chunk.doc_id != row["id"] for chunk in denied_chunks)
    assert all(source["id"] != row["id"] for source in denied_sources)
