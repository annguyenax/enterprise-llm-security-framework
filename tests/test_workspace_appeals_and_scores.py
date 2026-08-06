"""Tests for the appeal workflow and the guard/retrieval scores shown in the UI.

Two features, one shared concern: both put information in front of a user
that was previously internal, so both need to be exact about what they
claim.

- **Appeals** are the first user-initiated escalation path in this project.
  A blocked message is refused conversation content, so the queue that
  exposes it must stay superadmin-only, must verify ownership from the
  database rather than the request, and must not let a user appeal a
  message that was never withheld.

- **Scores** must never be invented. A guard stage that did not run, or a
  retrieval path with no embedding model available, yields `None` -- not
  `0.0`. "Not evaluated" and "evaluated as harmless" are different claims,
  and a UI that renders them identically is a false statement about the
  system.
"""
from pathlib import Path

import pytest

from app.workspace import store


def _login(username: str, password: str) -> dict:
    result = store.authenticate(username, password)
    assert result is not None
    return result[1]


@pytest.fixture
def workspace(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "workspace.db")
    monkeypatch.setattr(store, "DOC_ROOT", tmp_path / "documents")
    store.initialize()
    return {
        "member": _login("it.user1", "ITUser1#2026"),
        "other": _login("it.user2", "ITUser2#2026"),
        "leader": _login("it.leader", "ITLeader#2026"),
        "admin": _login("superadmin", "SuperAdmin#2026"),
    }


def _blocked_message(actor: dict, decision: str = "block") -> tuple[str, dict]:
    conversation = store.create_conversation(actor, "Hội thoại thử")
    store.add_message(conversation["id"], "user", "Câu hỏi công việc")
    assistant = store.add_message(
        conversation["id"], "assistant", "Bị chặn", decision=decision, request_id="req-1"
    )
    return conversation["id"], assistant


# --- Appeal creation --------------------------------------------------------


def test_user_can_appeal_their_own_blocked_message(workspace):
    _cid, assistant = _blocked_message(workspace["member"])
    appeal = store.create_appeal(workspace["member"], assistant["id"], "Đây là câu hỏi công việc bình thường")
    assert appeal["status"] == "pending"
    assert appeal["message_id"] == assistant["id"]


@pytest.mark.parametrize("decision", ["block", "human_review"])
def test_both_withholding_decisions_are_appealable(workspace, decision):
    _cid, assistant = _blocked_message(workspace["member"], decision)
    assert store.create_appeal(workspace["member"], assistant["id"], "Lý do")["status"] == "pending"


@pytest.mark.parametrize("decision", ["allow", "sanitize", "log_only", None])
def test_a_message_the_user_actually_received_is_not_appealable(workspace, decision):
    """There is nothing to appeal about an answer that was delivered."""
    _cid, assistant = _blocked_message(workspace["member"], decision)
    with pytest.raises(ValueError):
        store.create_appeal(workspace["member"], assistant["id"], "Lý do")


def test_a_user_cannot_appeal_someone_elses_message(workspace):
    """Ownership is re-checked against the conversation, not taken from the
    request -- a message id is guessable."""
    _cid, assistant = _blocked_message(workspace["member"])
    with pytest.raises(LookupError):
        store.create_appeal(workspace["other"], assistant["id"], "Không phải của tôi")


def test_appeal_cannot_be_submitted_twice(workspace):
    _cid, assistant = _blocked_message(workspace["member"])
    store.create_appeal(workspace["member"], assistant["id"], "Lần một")
    with pytest.raises(ValueError):
        store.create_appeal(workspace["member"], assistant["id"], "Lần hai")


@pytest.mark.parametrize("reason", ["", "   ", "\n\t "])
def test_appeal_requires_a_reason(workspace, reason):
    _cid, assistant = _blocked_message(workspace["member"])
    with pytest.raises(ValueError):
        store.create_appeal(workspace["member"], assistant["id"], reason)


def test_appeal_reason_is_length_bounded(workspace):
    _cid, assistant = _blocked_message(workspace["member"])
    with pytest.raises(ValueError):
        store.create_appeal(workspace["member"], assistant["id"], "x" * 2001)


def test_appeal_on_a_missing_message_is_not_found(workspace):
    with pytest.raises(LookupError):
        store.create_appeal(workspace["member"], 999999, "Lý do")


# --- Review queue access ----------------------------------------------------


@pytest.mark.parametrize("role", ["member", "leader", "other"])
def test_only_superadmin_may_read_the_appeal_queue(workspace, role):
    """An appeal quotes blocked conversation content. `conversations` keeps
    that private from every role including superadmin; the appeal is the one
    narrow, user-initiated exception and must not widen to leaders."""
    with pytest.raises(PermissionError):
        store.list_appeals(workspace[role])


def test_superadmin_sees_pending_appeals_first(workspace):
    _cid, first = _blocked_message(workspace["member"])
    _cid2, second = _blocked_message(workspace["other"])
    store.create_appeal(workspace["member"], first["id"], "Lý do A")
    store.create_appeal(workspace["other"], second["id"], "Lý do B")
    store.resolve_appeal(workspace["admin"], store.message_appeal(first["id"])["id"], "accepted")

    queue = store.list_appeals(workspace["admin"])
    assert len(queue) == 2
    assert queue[0]["status"] == "pending"


# --- Resolution -------------------------------------------------------------


@pytest.mark.parametrize("status", ["accepted", "rejected"])
def test_superadmin_resolves_an_appeal(workspace, status):
    _cid, assistant = _blocked_message(workspace["member"])
    appeal = store.create_appeal(workspace["member"], assistant["id"], "Lý do")
    resolved = store.resolve_appeal(workspace["admin"], appeal["id"], status, "Đã xem xét")
    assert resolved["status"] == status
    assert resolved["resolution_note"] == "Đã xem xét"
    assert resolved["resolved_by_username"] == "superadmin"
    assert resolved["resolved_at"]


@pytest.mark.parametrize("role", ["member", "leader"])
def test_non_superadmin_cannot_resolve(workspace, role):
    _cid, assistant = _blocked_message(workspace["member"])
    appeal = store.create_appeal(workspace["member"], assistant["id"], "Lý do")
    with pytest.raises(PermissionError):
        store.resolve_appeal(workspace[role], appeal["id"], "accepted")


@pytest.mark.parametrize("status", ["approved", "pending", "", "ACCEPTED"])
def test_invalid_resolution_status_is_rejected(workspace, status):
    _cid, assistant = _blocked_message(workspace["member"])
    appeal = store.create_appeal(workspace["member"], assistant["id"], "Lý do")
    with pytest.raises(ValueError):
        store.resolve_appeal(workspace["admin"], appeal["id"], status)


def test_an_appeal_cannot_be_resolved_twice(workspace):
    _cid, assistant = _blocked_message(workspace["member"])
    appeal = store.create_appeal(workspace["member"], assistant["id"], "Lý do")
    store.resolve_appeal(workspace["admin"], appeal["id"], "accepted")
    with pytest.raises(ValueError):
        store.resolve_appeal(workspace["admin"], appeal["id"], "rejected")


def test_resolving_a_missing_appeal_is_not_found(workspace):
    with pytest.raises(LookupError):
        store.resolve_appeal(workspace["admin"], "khong-ton-tai", "accepted")


# --- Appeal state reaches the message list ----------------------------------


def test_message_list_carries_appeal_state(workspace):
    cid, assistant = _blocked_message(workspace["member"])
    rows = store.messages(workspace["member"], cid)
    assert rows[-1]["appeal_status"] is None

    appeal = store.create_appeal(workspace["member"], assistant["id"], "Lý do")
    assert store.messages(workspace["member"], cid)[-1]["appeal_status"] == "pending"

    store.resolve_appeal(workspace["admin"], appeal["id"], "accepted", "Hợp lệ")
    row = store.messages(workspace["member"], cid)[-1]
    assert row["appeal_status"] == "accepted"
    assert row["appeal_note"] == "Hợp lệ"


# --- Guard risk scores ------------------------------------------------------


def test_risk_scores_persist_across_reload(workspace):
    """A reloaded conversation must show the same scores as the live reply;
    losing them on refresh would make the badge look unreliable."""
    conversation = store.create_conversation(workspace["member"], "Điểm")
    store.add_message(
        conversation["id"], "assistant", "Trả lời",
        decision="allow", risk_input=0.0, risk_rag=0.72, risk_output=0.3,
    )
    row = store.messages(workspace["member"], conversation["id"])[-1]
    assert row["risk_input"] == 0.0
    assert row["risk_rag"] == 0.72
    assert row["risk_output"] == 0.3


def test_a_stage_that_did_not_run_stores_none_not_zero(workspace):
    """`None` and `0.0` are different claims: one says the stage never ran,
    the other says it ran and found nothing. The UI renders them
    differently, so storage must keep them distinct."""
    conversation = store.create_conversation(workspace["member"], "Điểm")
    store.add_message(conversation["id"], "assistant", "Trả lời", decision="block", risk_input=0.9)
    row = store.messages(workspace["member"], conversation["id"])[-1]
    assert row["risk_input"] == 0.9
    assert row["risk_rag"] is None
    assert row["risk_output"] is None


def test_guard_risk_extracts_present_stages_only():
    """`guard_risk` must not invent a score for a stage the pipeline
    skipped -- e.g. RAG and Output never run when the Input Guard blocks."""
    from types import SimpleNamespace

    from app.workspace.routes import guard_risk

    blocked = SimpleNamespace(
        input_guard=SimpleNamespace(risk_score=0.85), rag_guard=None, output_guard=None
    )
    assert guard_risk(blocked) == {"risk_input": 0.85, "risk_rag": None, "risk_output": None}

    full = SimpleNamespace(
        input_guard=SimpleNamespace(risk_score=0.0),
        rag_guard=SimpleNamespace(risk_score=0.4),
        output_guard=SimpleNamespace(risk_score=0.1),
    )
    assert guard_risk(full) == {"risk_input": 0.0, "risk_rag": 0.4, "risk_output": 0.1}


# --- Retrieval score display helper -----------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (0.87, 0.87),
        (1.4, 1.0),        # clamped
        (-1.0, 0.0),       # _cosine's error sentinel must not read as relevance
        (-0.3, 0.0),       # genuinely negative cosine is not a relevance percentage
        (0, 0.0),
        (None, None),      # "not computed" must survive as None
        ("0.9", None),
        (True, None),      # bool is an int subclass; excluded explicitly
    ],
)
def test_display_cosine_clamps_without_inventing_values(raw, expected):
    assert store._display_cosine(raw) == expected
