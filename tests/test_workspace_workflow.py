from pathlib import Path

import pytest

from app.retrieval.enterprise_acl_bm25 import (
    EnterpriseAclBm25Config,
    EnterpriseAclBm25Retriever,
)
from app.workspace import store


def _login(username: str, password: str) -> dict:
    result = store.authenticate(username, password)
    assert result is not None
    return result[1]


def test_hierarchical_task_permissions_and_parent_progress(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "workspace.db")
    monkeypatch.setattr(store, "DOC_ROOT", tmp_path / "documents")
    store.initialize()
    superadmin = _login("superadmin", "SuperAdmin#2026")
    leader = _login("it.leader", "ITLeader#2026")
    member = _login("it.user1", "ITUser1#2026")
    hr_member = _login("hr.user1", "HRUser1#2026")

    assert len(store.team(leader)) == 3
    with pytest.raises(PermissionError):
        store.team(member)

    parent = store.create_department_task(superadmin, "Triển khai PoC", "Synthetic", "IT", None)
    child = store.delegate_task(leader, parent["id"], member["id"], "Kiểm thử", "Synthetic", None)
    with pytest.raises(ValueError):
        store.delegate_task(leader, parent["id"], hr_member["id"], "Sai phòng", "Synthetic", None)

    store.update_progress(member, child["id"], 50)
    tasks = store.list_tasks(leader)
    updated_parent = next(item for item in tasks if item["id"] == parent["id"])
    assert updated_parent["progress"] == 50
    assert store.list_tasks(member)[0]["id"] == child["id"]


def test_role_scoped_database_context_and_private_conversations(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "workspace.db")
    monkeypatch.setattr(store, "DOC_ROOT", tmp_path / "documents")
    isolated_retriever = EnterpriseAclBm25Retriever(
        EnterpriseAclBm25Config(db_path=str(tmp_path / "enterprise-kb.db"))
    )
    isolated_retriever.initialize()
    monkeypatch.setattr(store, "_RETRIEVER", isolated_retriever)
    store.initialize()
    superadmin = _login("superadmin", "SuperAdmin#2026")
    leader = _login("it.leader", "ITLeader#2026")
    member = _login("it.user1", "ITUser1#2026")

    super_context = store.authorized_workspace_context(superadmin)
    assert "hr.user2" in super_context
    assert "SuperAdmin=1 | Leader=2 | Nhân viên(member)=4" in super_context
    assert "it.user2" in store.authorized_workspace_context(leader)
    assert "hr.user1" not in store.authorized_workspace_context(leader)
    member_context = store.authorized_workspace_context(member)
    assert "it.leader" in member_context
    assert "it.user2" not in member_context

    private = store.create_conversation(member, "Riêng của nhân viên")
    own = store.create_conversation(superadmin, "Riêng của quản trị")
    assert [item["id"] for item in store.conversations(superadmin)] == [own["id"]]
    assert store.conversation(superadmin, private["id"]) is None

    _, sources = store.retrieve(
        superadmin,
        "Cho tôi biết công ty đang gồm những ai và có bao nhiêu thành viên nhân viên?",
    )
    assert sources == []
