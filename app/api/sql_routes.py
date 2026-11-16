"""P4 SQL agent lab endpoints (guarded vs. intentionally unguarded)."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.audit_logger import log_event
from app.services.llm_provider import get_llm_provider
from app.sql_agent.agent import default_db_path, run_sql_chat
from app.sql_agent.models import SqlActor

router = APIRouter(tags=["sql-agent-lab"])


class SqlChatBody(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    department: str = Field(..., min_length=1, max_length=40)
    role: str = Field("member", min_length=1, max_length=20)


def _run(body: SqlChatBody, guarded: bool, endpoint: str) -> dict:
    db = default_db_path()
    if not db.is_file():
        raise HTTPException(
            status_code=503,
            detail="Furniture database not built. Run scripts/build_furniture_db.py first.",
        )
    result = run_sql_chat(
        body.question,
        SqlActor(body.department, body.role),
        guarded=guarded,
        provider=get_llm_provider(settings.llm_provider),
        db_path=db,
    )
    reasons = []
    for part in (result.input_guard, result.sql_guard, result.result_guard, result.output_guard):
        if part:
            reasons.extend(part.get("reasons", []))
    log_event(
        endpoint=endpoint,
        request_id=result.request_id,
        input_preview=body.question,
        final_decision=result.final_decision,
        reasons=reasons,
        metadata={
            "mode": result.mode,
            "department": body.department,
            "role": body.role,
            "sql_guard": (result.sql_guard or {}).get("decision"),
            "result_guard": (result.result_guard or {}).get("decision"),
            "statements_executed": result.statements_executed,
        },
        provider_metadata={"provider": result.provider_name, "model": result.model_name},
    )
    data = asdict(result)
    data["final_decision"] = result.final_decision.value
    return data


@router.post("/v1/sql/chat")
def sql_chat(body: SqlChatBody) -> dict:
    return _run(body, True, "/v1/sql/chat")


@router.post("/v1/unguarded/sql/chat")
def unguarded_sql_chat(body: SqlChatBody) -> dict:
    return _run(body, False, "/v1/unguarded/sql/chat")
