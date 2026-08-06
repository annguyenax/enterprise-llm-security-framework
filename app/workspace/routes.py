from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Annotated
from urllib.parse import unquote

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel, Field

from app.core.decisions import Decision
from app.guards.rag_guard import evaluate_rag_context
from app.schemas.requests import RAGContextChunk
from app.services.gateway import run_chat
from app.services.upload_scanner import scan_upload
from app.workspace import store
from app.workspace.file_parsing import (
    SUPPORTED_TEXT_SUFFIXES,
    FileParseError,
    extract_text_from_bytes,
)
from app.workspace.history import MAX_REPLAYED_TURNS, screen_history

router = APIRouter(prefix="/v1", tags=["workspace"])


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=8, max_length=128)


class ConversationBody(BaseModel):
    title: str = Field(min_length=1, max_length=80)


class MessageBody(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class FeedbackBody(BaseModel):
    value: int = Field(ge=-1, le=1)


class DepartmentTaskBody(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=4000)
    department: str = Field(min_length=1, max_length=40)
    due_at: str | None = None


class DelegateTaskBody(BaseModel):
    assigned_user_id: int
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=4000)
    due_at: str | None = None


class ProgressBody(BaseModel):
    progress: int = Field(ge=0, le=100)


class AppealBody(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class AppealResolutionBody(BaseModel):
    status: str = Field(pattern="^(accepted|rejected)$")
    note: str = Field(default="", max_length=1000)


def guard_risk(result) -> dict:
    """Extract the per-stage `risk_score` values already computed by the
    guards, so the UI can show why a decision was made rather than only
    what it was.

    Nothing new is measured here: `risk_score` is the maximum weight among
    the rules a stage matched (see `app/guards/rag_guard.py`), which is why
    the UI labels it as a rule-based risk score and not a model confidence.
    A stage that did not run is `None`, never `0.0` -- "not evaluated" and
    "evaluated as harmless" are different facts.
    """
    return {
        "risk_input": getattr(result.input_guard, "risk_score", None),
        "risk_rag": getattr(result.rag_guard, "risk_score", None) if result.rag_guard else None,
        "risk_output": getattr(result.output_guard, "risk_score", None) if result.output_guard else None,
    }


def bearer(authorization: Annotated[str | None, Header()] = None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Bạn cần đăng nhập")
    return authorization.split(" ", 1)[1]


def actor(token: str = Depends(bearer)) -> dict:
    user = store.current_user(token)
    if not user:
        raise HTTPException(401, "Phiên đăng nhập đã hết hạn")
    return user


def translate_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PermissionError): return HTTPException(403, "Bạn không có quyền thực hiện thao tác này")
    if isinstance(exc, ValueError): return HTTPException(400, str(exc))
    return HTTPException(404, str(exc) or "Không tìm thấy dữ liệu")


@router.get("/auth/status")
def auth_status() -> dict:
    return {"registration_open": len(store.users()) == 0}


@router.post("/auth/login")
def login(body: Credentials) -> dict:
    result = store.authenticate(body.username, body.password)
    if not result: raise HTTPException(401, "Tên đăng nhập hoặc mật khẩu không đúng")
    return {"token": result[0], "user": result[1]}


@router.post("/auth/register")
def register() -> None:
    raise HTTPException(403, "Đăng ký công khai đã đóng; superadmin quản lý tài khoản")


@router.get("/auth/me")
def me(user: dict = Depends(actor)) -> dict: return user


@router.post("/auth/logout", status_code=204)
def signout(token: str = Depends(bearer)) -> Response:
    store.logout(token); return Response(status_code=204)


@router.get("/departments")
def departments(_: dict = Depends(actor)) -> list[dict]: return store.departments()


@router.get("/team")
def team(department: str | None = None, user: dict = Depends(actor)) -> list[dict]:
    try: return store.team(user, department)
    except Exception as exc: raise translate_error(exc)


@router.get("/conversations")
def conversations(user: dict = Depends(actor)) -> list[dict]: return store.conversations(user)


@router.post("/conversations")
def create_conversation(body: ConversationBody, user: dict = Depends(actor)) -> dict: return store.create_conversation(user, body.title)


@router.patch("/conversations/{conversation_id}")
def rename_conversation(conversation_id: str, body: ConversationBody, user: dict = Depends(actor)) -> dict:
    if not store.update_conversation(user, conversation_id, body.title): raise HTTPException(404, "Không tìm thấy hội thoại")
    return {"id": conversation_id, "title": body.title}


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str, user: dict = Depends(actor)) -> Response:
    if not store.delete_conversation(user, conversation_id): raise HTTPException(404, "Không tìm thấy hội thoại")
    return Response(status_code=204)


@router.get("/conversations/{conversation_id}/messages")
def get_messages(conversation_id: str, user: dict = Depends(actor)) -> list[dict]:
    try: return store.messages(user, conversation_id)
    except LookupError: raise HTTPException(404, "Không tìm thấy hội thoại")


@router.post("/conversations/{conversation_id}/messages")
def post_message(conversation_id: str, body: MessageBody, user: dict = Depends(actor)) -> dict:
    conv=store.conversation(user,conversation_id)
    if not conv: raise HTTPException(404,"Không tìm thấy hội thoại")
    if conv["user_id"] != user["id"]: raise HTTPException(403,"Superadmin chỉ được kiểm tra, không gửi thay người dùng")
    # Stored turns are re-screened before they may re-enter the provider's
    # context; see app/workspace/history.py for the two replay holes this
    # closes. `screening.turns` is the only history value allowed past here.
    screening=screen_history(store.messages(user,conversation_id),max_turns=MAX_REPLAYED_TURNS)
    user_message=store.add_message(conversation_id,"user",body.content)
    chunks,sources=store.retrieve(user,body.content)
    started=time.perf_counter()
    workspace_directory = store.authorized_workspace_context(user)
    # `history` is provider-visible only. app/services/gateway.py replaces it
    # with a `history_turns` count before anything reaches the audit log, so
    # conversation content is never persisted to logs/audit.jsonl.
    result=run_chat(body.content,chunks,{"workspace_user_id":user["id"],"role":user["role"],"department":user["department"],"workspace_directory":workspace_directory,"history":[dict(turn) for turn in screening.turns],"history_turns_dropped":screening.dropped_count,"history_turns_sanitized":screening.sanitized_count})
    # Recorded so a turn the Input Guard refused can never be replayed on a
    # later request (history.py drops blocking decisions).
    store.set_message_decision(user_message["id"],result.input_guard.decision.value)
    assistant=store.add_message(conversation_id,"assistant",result.response,decision=result.final_decision.value,request_id=result.request_id,latency_ms=round((time.perf_counter()-started)*1000),sources=sources,**guard_risk(result))
    return {"assistant_message":assistant,"provider_name":result.provider_name,"model_name":result.model_name}

@router.post("/conversations/{conversation_id}/messages_unguarded")
def post_message_unguarded(conversation_id: str, body: MessageBody, user: dict = Depends(actor)) -> dict:
    conv=store.conversation(user,conversation_id)
    if not conv: raise HTTPException(404,"Không tìm thấy hội thoại")
    if conv["user_id"] != user["id"]: raise HTTPException(403,"Superadmin chỉ được kiểm tra, không gửi thay người dùng")

    screening=screen_history(store.messages(user,conversation_id),max_turns=MAX_REPLAYED_TURNS)
    user_message=store.add_message(conversation_id,"user",body.content)
    chunks,sources=store.retrieve(user,body.content)
    started=time.perf_counter()
    workspace_directory = store.authorized_workspace_context(user)

    from app.services.gateway import run_unguarded_chat
    result=run_unguarded_chat(body.content,chunks,{"workspace_user_id":user["id"],"role":user["role"],"department":user["department"],"workspace_directory":workspace_directory,"history":[dict(turn) for turn in screening.turns],"history_turns_dropped":screening.dropped_count,"history_turns_sanitized":screening.sanitized_count})

    store.set_message_decision(user_message["id"],result.input_guard.decision.value)
    assistant=store.add_message(conversation_id,"assistant",result.response,decision=result.final_decision.value,request_id=result.request_id,latency_ms=round((time.perf_counter()-started)*1000),sources=sources,**guard_risk(result))
    return {"assistant_message":assistant,"provider_name":result.provider_name,"model_name":result.model_name}


@router.put("/messages/{message_id}/feedback", status_code=204)
def feedback(message_id: int, body: FeedbackBody, user: dict = Depends(actor)) -> Response:
    try: store.set_feedback(user,message_id,body.value)
    except LookupError: raise HTTPException(404,"Không tìm thấy tin nhắn")
    return Response(status_code=204)


@router.post("/messages/{message_id}/appeal", status_code=201)
def appeal_message(message_id: int, body: AppealBody, user: dict = Depends(actor)) -> dict:
    """Submit an appeal against a message the gateway withheld.

    Ownership, appealability, and duplicate submission are all enforced in
    `store.create_appeal` against the database, never from the request.
    """
    try: return store.create_appeal(user, message_id, body.reason)
    except LookupError: raise HTTPException(404, "Không tìm thấy tin nhắn")
    except Exception as exc: raise translate_error(exc)


@router.get("/admin/appeals")
def admin_appeals(user: dict = Depends(actor)) -> list[dict]:
    try: return store.list_appeals(user)
    except PermissionError: raise HTTPException(403, "Chỉ superadmin được truy cập")


@router.patch("/admin/appeals/{appeal_id}")
def resolve_appeal(appeal_id: str, body: AppealResolutionBody, user: dict = Depends(actor)) -> dict:
    try: return store.resolve_appeal(user, appeal_id, body.status, body.note)
    except LookupError: raise HTTPException(404, "Không tìm thấy kháng cáo")
    except Exception as exc: raise translate_error(exc)


@router.get("/documents")
def documents(user: dict = Depends(actor)) -> list[dict]: return store.accessible_documents(user)


@router.get("/documents/sharing-options")
def document_sharing_options(user: dict = Depends(actor)) -> dict:
    return store.sharing_options(user)


@router.post("/documents")
def upload_document(content: Annotated[bytes, Body()], scope: str = Query("user"), audience: str = Query("member"), department: str = Query(""), allowed_users: str = Query(""), allowed_groups: str = Query(""), x_filename: Annotated[str | None, Header()] = None, user: dict = Depends(actor)) -> dict:
    # Keep direct function-level tests/callers compatible with FastAPI's Query
    # marker defaults; HTTP requests always provide plain strings here.
    if not isinstance(allowed_users, str): allowed_users = ""
    if not isinstance(allowed_groups, str): allowed_groups = ""
    if len(content)>1_000_000: raise HTTPException(413,"Tệp vượt quá giới hạn 1 MB")
    filename=unquote(x_filename or "document.txt")
    suffix=Path(filename).suffix.lower()
    if suffix not in SUPPORTED_TEXT_SUFFIXES:
        raise HTTPException(415,"Chỉ hỗ trợ tài liệu văn bản, mã nguồn UTF-8 và PDF")
    scan_result=scan_upload(filename,content)
    if not scan_result.allowed:
        message="Tệp bị Upload Scanner từ chối: "+(scan_result.reason or "Nội dung không an toàn")
        stages=list(scan_result.checks) or [{"stage":"upload_scanner","engine":scan_result.engine,"decision":"block","rule_ids":[scan_result.rule_id] if scan_result.rule_id else [],"reasons":[scan_result.reason] if scan_result.reason else [],"detected_type":scan_result.detected_type}]
        raise HTTPException(422,{"message":message,"security_report":{"final_decision":"block","stages":stages}})
    try:
        text, mime_type = extract_text_from_bytes(filename, content)
    except FileParseError as exc:
        raise HTTPException(400, str(exc)) from exc
    guard=evaluate_rag_context([RAGContextChunk(doc_id="upload",text=text,metadata={})])
    if guard.decision in (Decision.BLOCK,Decision.HUMAN_REVIEW,Decision.SANITIZE):
        message="Tài liệu có nội dung không an toàn và đã bị từ chối toàn bộ: "+"; ".join(guard.reasons)
        stages=list(scan_result.checks) or [{"stage":"upload_scanner","engine":scan_result.engine,"decision":"allow","rule_ids":[],"reasons":[],"detected_type":scan_result.detected_type}]
        stages.append({"stage":"rag_guard","engine":"rag-context-guard","decision":guard.decision.value,"rule_ids":guard.matched_rules,"reasons":guard.reasons,"risk_score":guard.risk_score})
        raise HTTPException(422,{"message":message,"security_report":{"final_decision":"block","stages":stages}})
    if not text.strip(): raise HTTPException(422,"Tài liệu không có nội dung hợp lệ")
    try:
        stored=store.add_document(user,Path(filename).name,text.encode("utf-8"),scope,audience,department or user["department"],guard_decision=guard.decision.value,mime_type=mime_type or "text/plain",allowed_users=[value.strip() for value in allowed_users.split(",") if value.strip()],allowed_groups=[value.strip() for value in allowed_groups.split(",") if value.strip()])
        stored["upload_scan"]={"engine":scan_result.engine,"detected_type":scan_result.detected_type}
        stages=list(scan_result.checks) or [{"stage":"upload_scanner","engine":scan_result.engine,"decision":"allow","rule_ids":[],"reasons":[],"detected_type":scan_result.detected_type}]
        stages.append({"stage":"rag_guard","engine":"rag-context-guard","decision":guard.decision.value,"rule_ids":guard.matched_rules,"reasons":guard.reasons,"risk_score":guard.risk_score})
        stored["security_report"]={"final_decision":guard.decision.value,"stages":stages}
        return stored
    except Exception as exc: raise translate_error(exc)


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: str, user: dict = Depends(actor)) -> Response:
    if not store.delete_document(user,document_id): raise HTTPException(403,"Bạn không được xóa tài liệu này")
    return Response(status_code=204)


@router.get("/tasks")
def tasks(user: dict = Depends(actor)) -> list[dict]: return store.list_tasks(user)


@router.post("/tasks/department")
def create_department_task(body: DepartmentTaskBody, user: dict = Depends(actor)) -> dict:
    try: return store.create_department_task(user,body.title,body.description,body.department,body.due_at)
    except Exception as exc: raise translate_error(exc)


@router.post("/tasks/{task_id}/delegate")
def delegate(task_id: str, body: DelegateTaskBody, user: dict = Depends(actor)) -> dict:
    try: return store.delegate_task(user,task_id,body.assigned_user_id,body.title,body.description,body.due_at)
    except Exception as exc: raise translate_error(exc)


@router.patch("/tasks/{task_id}/progress")
def progress(task_id: str, body: ProgressBody, user: dict = Depends(actor)) -> dict:
    try: return store.update_progress(user,task_id,body.progress)
    except Exception as exc: raise translate_error(exc)


@router.get("/admin/stats")
def admin_stats(user: dict = Depends(actor)) -> dict:
    if user["role"]!="superadmin": raise HTTPException(403,"Chỉ superadmin được truy cập")
    all_users=store.users(); counts=store.workspace_counts()
    recent=[]; decisions={}
    log=Path("logs/audit.jsonl")
    if log.exists():
        for line in log.read_text(encoding="utf-8",errors="ignore").splitlines()[-100:]:
            try:
                event=json.loads(line); decision=event.get("final_decision") or event.get("decision") or "unknown"; decisions[decision]=decisions.get(decision,0)+1; recent.append({"decision":decision,"request_id":event.get("request_id"),"timestamp":event.get("timestamp"),"matched_rules":event.get("matched_rules",[])})
            except json.JSONDecodeError: pass
    return {"workspace":counts,"users":all_users,"departments":store.departments(),"audit":{"total":sum(decisions.values()),"decisions":decisions,"recent":list(reversed(recent[-20:]))}}
