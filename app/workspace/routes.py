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
from app.workspace import store
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
    assistant=store.add_message(conversation_id,"assistant",result.response,decision=result.final_decision.value,request_id=result.request_id,latency_ms=round((time.perf_counter()-started)*1000),sources=sources)
    return {"assistant_message":assistant,"provider_name":result.provider_name,"model_name":result.model_name}


@router.put("/messages/{message_id}/feedback", status_code=204)
def feedback(message_id: int, body: FeedbackBody, user: dict = Depends(actor)) -> Response:
    try: store.set_feedback(user,message_id,body.value)
    except LookupError: raise HTTPException(404,"Không tìm thấy tin nhắn")
    return Response(status_code=204)


@router.get("/documents")
def documents(user: dict = Depends(actor)) -> list[dict]: return store.accessible_documents(user)


@router.post("/documents")
def upload_document(content: Annotated[bytes, Body()], scope: str = Query("user"), audience: str = Query("member"), department: str = Query(""), x_filename: Annotated[str | None, Header()] = None, user: dict = Depends(actor)) -> dict:
    if len(content)>1_000_000: raise HTTPException(413,"Tệp vượt quá giới hạn 1 MB")
    filename=unquote(x_filename or "document.txt")
    if Path(filename).suffix.lower() not in (".txt",".md"): raise HTTPException(415,"Chỉ hỗ trợ TXT và Markdown")
    try: text=content.decode("utf-8")
    except UnicodeDecodeError: raise HTTPException(400,"Tệp phải dùng UTF-8")
    guard=evaluate_rag_context([RAGContextChunk(doc_id="upload",text=text,metadata={})])
    if guard.decision in (Decision.BLOCK,Decision.HUMAN_REVIEW): raise HTTPException(422,"Tài liệu bị RAG Guard từ chối: "+"; ".join(guard.reasons))
    # Store exactly what the guard approved. On SANITIZE that is the cleaned
    # text -- writing the caller's original bytes would leave the removed
    # content on disk and hand it back on every later retrieval.
    stored_text=guard.sanitized_chunks[0].text if guard.decision==Decision.SANITIZE and guard.sanitized_chunks else text
    if not stored_text.strip(): raise HTTPException(422,"Tài liệu không còn nội dung hợp lệ sau khi RAG Guard làm sạch")
    try: return store.add_document(user,Path(filename).name,stored_text.encode("utf-8"),scope,audience,department or user["department"],guard_decision=guard.decision.value)
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
