"""Nhà Mộc Việt assistant endpoints (guarded vs. intentionally unguarded)."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.company_agent.agent import approve_action, outbox, result_to_dict, run_agent
from app.core.config import settings
from app.services.audit_logger import log_event
from app.services.llm_provider import get_llm_provider
from app.sql_agent.agent import default_db_path
from app.sql_agent.models import SqlActor

router = APIRouter(tags=["company-agent-lab"])


class HistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=4000)


class AgentBody(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    department: str = Field(..., min_length=1, max_length=40)
    role: str = Field("member", min_length=1, max_length=20)
    corpus: Literal["clean", "poisoned"] = "clean"
    history: list[HistoryItem] = Field(default_factory=list, max_length=12)


class ApprovalBody(BaseModel):
    approver_role: str = Field(..., min_length=1, max_length=20)


def _run(body: AgentBody, guarded: bool, endpoint: str) -> dict:
    db = default_db_path()
    if not db.is_file():
        raise HTTPException(503, "Furniture database not built. Run scripts/build_furniture_db.py first.")
    result = run_agent(
        body.message, SqlActor(body.department, body.role), guarded=guarded,
        provider=get_llm_provider(settings.llm_provider), corpus=body.corpus, db_path=db,
        history=[h.model_dump() for h in body.history],
    )
    log_event(
        endpoint=endpoint, request_id=result.request_id, input_preview=body.message,
        final_decision=result.final_decision,
        reasons=[r for s in result.steps for r in s.reasons],
        metadata={"mode": result.mode, "department": body.department, "role": body.role,
                  "corpus": body.corpus, "tools": [s.tool for s in result.steps],
                  "pending_actions": len(result.pending_actions),
                  "executed_actions": len(result.executed_actions)},
        provider_metadata={"provider": result.provider_name, "model": result.model_name},
    )
    return result_to_dict(result)


@router.post("/v1/agent/chat")
def agent_chat(body: AgentBody) -> dict:
    return _run(body, True, "/v1/agent/chat")


@router.post("/v1/unguarded/agent/chat")
def unguarded_agent_chat(body: AgentBody) -> dict:
    return _run(body, False, "/v1/unguarded/agent/chat")


@router.post("/v1/agent/actions/{action_id}/approve")
def approve(action_id: str, body: ApprovalBody) -> dict:
    try:
        action = approve_action(action_id, body.approver_role)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from None
    if action is None:
        raise HTTPException(404, "action not found")
    return action


@router.get("/v1/agent/outbox")
def get_outbox() -> list[dict]:
    return outbox()
