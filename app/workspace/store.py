from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.retrieval.acl import AclFacts, RetrievalPrincipal, DEPARTMENT_WILDCARD, acl_metadata, canonical_timestamp
from app.retrieval.enterprise_acl_bm25 import (
    EnterpriseAclBm25Retriever,
    EnterpriseAclBm25Config,
)
from app.retrieval.models import DocumentRecord, ChunkRecord, RetrievalQuery
from app.services.chunking import chunk_text

DB_PATH = Path(os.getenv("WORKSPACE_DB_PATH", "data/workspace.db"))
DOC_ROOT = Path(os.getenv("WORKSPACE_DOCUMENT_ROOT", "data/documents"))
ROLE_RANK = {"member": 1, "leader": 2, "superadmin": 3}

_RETRIEVER: EnterpriseAclBm25Retriever | None = None

def get_retriever() -> EnterpriseAclBm25Retriever:
    global _RETRIEVER
    if _RETRIEVER is None:
        _RETRIEVER = EnterpriseAclBm25Retriever(
            EnterpriseAclBm25Config(
                db_path=settings.enterprise_kb_db_path,
                busy_timeout_ms=settings.retrieval_busy_timeout_ms,
                max_query_chars=settings.retrieval_max_query_chars,
                max_query_terms=settings.retrieval_max_query_terms,
                max_top_k=settings.retrieval_max_top_k,
            )
        )
        _RETRIEVER.initialize()
    return _RETRIEVER

# Guard decisions a stored document may legitimately carry. `block` and
# `human_review` are absent by design: those uploads are refused by the
# route and must never reach storage, so accepting them here would let a
# future call site persist content the guard rejected.
STORABLE_GUARD_DECISIONS = frozenset({"allow", "log_only", "sanitize"})


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db


def initialize() -> None:
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS departments (code TEXT PRIMARY KEY COLLATE NOCASE, name TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE COLLATE NOCASE, password_hash TEXT NOT NULL, salt TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('superadmin','leader','member')), department TEXT NOT NULL REFERENCES departments(code), created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, expires_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS conversations (id TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, title TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE, role TEXT NOT NULL, content TEXT NOT NULL, decision TEXT, request_id TEXT, latency_ms INTEGER, sources_json TEXT, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS feedback (message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, value INTEGER NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(message_id,user_id));
        CREATE TABLE IF NOT EXISTS documents (id TEXT PRIMARY KEY, owner_user_id INTEGER REFERENCES users(id), department TEXT, scope TEXT NOT NULL CHECK(scope IN ('user','department','global')), audience_role TEXT NOT NULL CHECK(audience_role IN ('member','leader','superadmin')), filename TEXT NOT NULL, mime_type TEXT NOT NULL, size_bytes INTEGER NOT NULL, guard_decision TEXT NOT NULL, storage_path TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS tasks (
          id TEXT PRIMARY KEY,
          parent_task_id TEXT REFERENCES tasks(id) ON DELETE CASCADE,
          title TEXT NOT NULL,
          description TEXT NOT NULL DEFAULT '',
          department TEXT NOT NULL REFERENCES departments(code),
          assigned_user_id INTEGER NOT NULL REFERENCES users(id),
          created_by INTEGER NOT NULL REFERENCES users(id),
          status TEXT NOT NULL DEFAULT 'todo' CHECK(status IN ('todo','in_progress','done')),
          progress INTEGER NOT NULL DEFAULT 0 CHECK(progress BETWEEN 0 AND 100),
          due_at TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_tasks_department ON tasks(department);
        CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON tasks(assigned_user_id);
        """)
        if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            stamp = now()
            db.executemany("INSERT OR IGNORE INTO departments(code,name,created_at) VALUES(?,?,?)", (("WORKSPACE","Workspace",stamp),("IT","Phòng IT",stamp),("HR","Phòng Nhân sự",stamp)))
            samples = (
                ("superadmin","SuperAdmin#2026","superadmin","WORKSPACE"),
                ("it.leader","ITLeader#2026","leader","IT"),("it.user1","ITUser1#2026","member","IT"),("it.user2","ITUser2#2026","member","IT"),
                ("hr.leader","HRLeader#2026","leader","HR"),("hr.user1","HRUser1#2026","member","HR"),("hr.user2","HRUser2#2026","member","HR"),
            )
            for username, password, role, department in samples:
                salt=secrets.token_bytes(16)
                db.execute("INSERT INTO users(username,password_hash,salt,role,department,created_at) VALUES(?,?,?,?,?,?)",(username,password_hash(password,salt),salt.hex(),role,department,stamp))


def public_user(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    return {key: row[key] for key in ("id", "username", "role", "department", "created_at") if key in row.keys()}


def password_hash(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000).hex()


def authenticate(username: str, password: str) -> tuple[str, dict[str, Any]] | None:
    with connect() as db:
        row = db.execute("SELECT * FROM users WHERE username=? COLLATE NOCASE", (username.strip(),)).fetchone()
        if not row or not secrets.compare_digest(password_hash(password, bytes.fromhex(row["salt"])), row["password_hash"]):
            return None
        token = secrets.token_urlsafe(32)
        expires = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        db.execute("DELETE FROM sessions WHERE expires_at < ?", (now(),))
        db.execute("INSERT INTO sessions(token_hash,user_id,expires_at) VALUES(?,?,?)", (hashlib.sha256(token.encode()).hexdigest(), row["id"], expires))
        return token, public_user(row)


def current_user(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    with connect() as db:
        row = db.execute("""SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id
                          WHERE s.token_hash=? AND s.expires_at>?""", (hashlib.sha256(token.encode()).hexdigest(), now())).fetchone()
        return public_user(row) if row else None


def logout(token: str) -> None:
    with connect() as db:
        db.execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))


def departments() -> list[dict[str, Any]]:
    with connect() as db:
        return [dict(r) for r in db.execute("SELECT code,name,created_at FROM departments ORDER BY code")]


def users() -> list[dict[str, Any]]:
    with connect() as db:
        return [public_user(r) for r in db.execute("SELECT * FROM users ORDER BY department,role,username")]


def team(actor: dict[str, Any], department: str | None = None) -> list[dict[str, Any]]:
    if actor["role"] == "member":
        raise PermissionError
    target = department if actor["role"] == "superadmin" and department else actor["department"]
    with connect() as db:
        rows = db.execute("SELECT * FROM users WHERE department=? AND role!='superadmin' ORDER BY CASE role WHEN 'leader' THEN 0 ELSE 1 END, username", (target,))
        return [public_user(r) for r in rows]


def conversations(actor: dict[str, Any]) -> list[dict[str, Any]]:
    # Conversations are private for every role. Superadmin receives aggregate
    # statistics elsewhere, never another user's conversation content.
    where, args = "c.user_id=?", (actor["id"],)
    with connect() as db:
        rows = db.execute(f"""SELECT c.*,u.username owner_username,u.department owner_department,
                         COUNT(m.id) message_count FROM conversations c JOIN users u ON u.id=c.user_id
                         LEFT JOIN messages m ON m.conversation_id=c.id WHERE {where}
                         GROUP BY c.id ORDER BY c.updated_at DESC""", args)
        return [dict(r) for r in rows]


def conversation(actor: dict[str, Any], conversation_id: str) -> sqlite3.Row | None:
    with connect() as db:
        row = db.execute("SELECT * FROM conversations WHERE id=?", (conversation_id,)).fetchone()
        return row if row and row["user_id"] == actor["id"] else None


def create_conversation(actor: dict[str, Any], title: str) -> dict[str, Any]:
    cid, stamp = str(uuid.uuid4()), now()
    with connect() as db:
        db.execute("INSERT INTO conversations VALUES(?,?,?,?,?)", (cid, actor["id"], title[:80], stamp, stamp))
    return {"id": cid, "user_id": actor["id"], "title": title[:80], "created_at": stamp, "updated_at": stamp}


def update_conversation(actor: dict[str, Any], cid: str, title: str) -> bool:
    if not conversation(actor, cid): return False
    with connect() as db: db.execute("UPDATE conversations SET title=?,updated_at=? WHERE id=?", (title[:80], now(), cid))
    return True


def delete_conversation(actor: dict[str, Any], cid: str) -> bool:
    if not conversation(actor, cid): return False
    with connect() as db:
        db.execute("DELETE FROM conversations WHERE id=?", (cid,))
    return True


def messages(actor: dict[str, Any], cid: str) -> list[dict[str, Any]]:
    if not conversation(actor, cid): raise LookupError
    with connect() as db:
        rows = db.execute("""SELECT m.*,f.value feedback FROM messages m LEFT JOIN feedback f
                           ON f.message_id=m.id AND f.user_id=? WHERE m.conversation_id=? ORDER BY m.id""", (actor["id"], cid))
        result=[]
        for row in rows:
            item=dict(row); item["sources"]=json.loads(item.pop("sources_json") or "[]"); result.append(item)
        return result


def add_message(cid: str, role: str, content: str, **extra: Any) -> dict[str, Any]:
    stamp=now(); sources=extra.get("sources", [])
    with connect() as db:
        cur=db.execute("""INSERT INTO messages(conversation_id,role,content,decision,request_id,latency_ms,sources_json,created_at)
                        VALUES(?,?,?,?,?,?,?,?)""", (cid,role,content,extra.get("decision"),extra.get("request_id"),extra.get("latency_ms"),json.dumps(sources,ensure_ascii=False),stamp))
        db.execute("UPDATE conversations SET updated_at=? WHERE id=?", (stamp,cid))
    return {"id":cur.lastrowid,"conversation_id":cid,"role":role,"content":content,"decision":extra.get("decision"),"request_id":extra.get("request_id"),"latency_ms":extra.get("latency_ms"),"sources":sources,"created_at":stamp,"feedback":None}


def set_message_decision(message_id: int, decision: str) -> None:
    """Record the guard decision for an already-stored message.

    `post_message` persists the user's turn before the gateway runs (so the
    turn is never lost if the pipeline fails), which means the decision is
    only known afterwards. Storing it matters for replay safety, not just
    for display: `app/workspace/history.py` refuses to replay any turn whose
    recorded decision was blocking, and a turn with no decision recorded at
    all is treated as unscreened and re-inspected from scratch."""
    with connect() as db:
        db.execute("UPDATE messages SET decision=? WHERE id=?", (decision, message_id))


def set_feedback(actor: dict[str, Any], message_id: int, value: int) -> None:
    with connect() as db:
        row=db.execute("SELECT c.user_id FROM messages m JOIN conversations c ON c.id=m.conversation_id WHERE m.id=? AND m.role='assistant'",(message_id,)).fetchone()
        if not row or row["user_id"] != actor["id"]: raise LookupError
        db.execute("INSERT INTO feedback VALUES(?,?,?,?) ON CONFLICT(message_id,user_id) DO UPDATE SET value=excluded.value,created_at=excluded.created_at",(message_id,actor["id"],value,now()))


def accessible_documents(actor: dict[str, Any]) -> list[dict[str, Any]]:
    rank=ROLE_RANK[actor["role"]]
    with connect() as db:
        rows=db.execute("SELECT d.*,u.username owner_username FROM documents d LEFT JOIN users u ON u.id=d.owner_user_id ORDER BY d.created_at DESC")
        result=[]
        for r in rows:
            allowed = actor["role"] == "superadmin" or (ROLE_RANK.get(r["audience_role"],3) <= rank and ((r["scope"] == "user" and r["owner_user_id"] == actor["id"]) or (r["scope"] == "department" and r["department"] == actor["department"]) or r["scope"] == "global"))
            if allowed: result.append(dict(r))
        return result


def retrieve(actor: dict[str, Any], query: str, limit: int = 4) -> tuple[list[Any], list[dict[str, Any]]]:
    from app.schemas.requests import RAGContextChunk
    from app.retrieval.sqlite_bm25 import EmptySearchQueryError
    principal = RetrievalPrincipal(user_id=actor["id"], role=actor["role"], department=actor["department"], max_sensitivity_rank=ROLE_RANK[actor["role"]])
    try:
        as_of = canonical_timestamp(datetime.now(timezone.utc))
        result = get_retriever().search(RetrievalQuery(query=query, top_k=limit, principal=principal, as_of=as_of))
    except EmptySearchQueryError:
        return [], []

    chunks = [RAGContextChunk(doc_id=hit.document_id, text=hit.text, metadata={"filename": hit.metadata.get("filename", "unknown"), "scope": hit.metadata.get("scope", "unknown")}) for hit in result.hits]
    sources = [{"id": hit.document_id, "filename": hit.metadata.get("filename", "unknown"), "scope": hit.metadata.get("scope", "unknown")} for hit in result.hits]
    return chunks, sources


def authorized_workspace_context(actor: dict[str, Any]) -> str:
    """Build a small structured context after enforcing role/department scope."""
    with connect() as db:
        if actor["role"] == "superadmin":
            people = db.execute("""SELECT u.username,u.role,u.department,d.name department_name
                FROM users u JOIN departments d ON d.code=u.department
                ORDER BY u.department,CASE u.role WHEN 'superadmin' THEN 0 WHEN 'leader' THEN 1 ELSE 2 END,u.username""").fetchall()
            heading = "Quyền SuperAdmin: dữ liệu cơ cấu toàn workspace."
        elif actor["role"] == "leader":
            people = db.execute("""SELECT u.username,u.role,u.department,d.name department_name
                FROM users u JOIN departments d ON d.code=u.department
                WHERE u.department=? AND u.role!='superadmin'
                ORDER BY CASE u.role WHEN 'leader' THEN 0 ELSE 1 END,u.username""",(actor["department"],)).fetchall()
            heading = f"Quyền Leader: chỉ dữ liệu nhân sự phòng {actor['department']}."
        else:
            people = db.execute("""SELECT u.username,u.role,u.department,d.name department_name
                FROM users u JOIN departments d ON d.code=u.department
                WHERE u.id=? OR (u.department=? AND u.role='leader')
                ORDER BY CASE WHEN u.id=? THEN 0 ELSE 1 END""",(actor["id"],actor["department"],actor["id"])).fetchall()
            heading = "Quyền Nhân viên: chỉ danh tính bản thân và leader phụ trách; không có danh sách đồng nghiệp."
    role_counts={role:sum(1 for p in people if p["role"]==role) for role in ROLE_RANK}
    department_counts={}
    for p in people:
        values=department_counts.setdefault(p["department"],{"leader":0,"member":0,"superadmin":0})
        values[p["role"]]+=1
    lines=[heading,f"Người đang hỏi: {actor['username']} | vai trò={actor['role']} | phòng={actor['department']}",f"Tổng tài khoản được phép thấy: {len(people)} | SuperAdmin={role_counts['superadmin']} | Leader={role_counts['leader']} | Nhân viên(member)={role_counts['member']}"]
    lines.extend(f"Thống kê phòng {department}: tổng={sum(counts.values())}, leader={counts['leader']}, nhân viên(member)={counts['member']}, superadmin={counts['superadmin']}" for department,counts in sorted(department_counts.items()))
    lines.extend(f"- {p['username']} | chức vụ={p['role']} | phòng={p['department']} ({p['department_name']})" for p in people)
    visible_tasks=list_tasks(actor)
    lines.append(f"Số công việc được phép thấy: {len(visible_tasks)}")
    lines.extend(f"- Công việc: {t['title']} | giao cho={t['assigned_username']} | tiến độ={t['progress']}% | trạng thái={t['status']}" for t in visible_tasks[:20])
    return "\n".join(lines)


def workspace_counts() -> dict[str, int]:
    with connect() as db:
        return {name: db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] for name in ("users","conversations","documents","tasks")}


def add_document(actor: dict[str, Any], filename: str, content: bytes, scope: str, audience: str, department: str, *, guard_decision: str) -> dict[str, Any]:
    """Persist one uploaded document. `content` must already be the exact
    bytes the RAG Context Guard approved -- for a SANITIZE decision that is
    the *sanitized* text, not the caller's original upload.

    `guard_decision` is keyword-only and required, so no call site can
    silently record a decision the guard did not actually make. It
    previously read `"allow"` unconditionally, which meant a document the
    guard had SANITIZEd was stored with its original bytes on disk *and* an
    audit row claiming a clean pass -- and every later retrieval read the
    unsanitized file back. Blocking decisions are rejected here as a
    fail-closed backstop; the route already refuses them earlier."""
    if scope not in {"user","department","global"} or audience not in ROLE_RANK: raise ValueError("Phạm vi hoặc đối tượng tài liệu không hợp lệ")
    if not isinstance(guard_decision, str) or guard_decision not in STORABLE_GUARD_DECISIONS:
        raise ValueError("Quyết định của guard không hợp lệ cho việc lưu trữ tài liệu")
    if scope == "department" and actor["role"] == "member": raise PermissionError
    if scope == "global" and actor["role"] != "superadmin": raise PermissionError
    if actor["role"] != "superadmin": department=actor["department"]
    did=str(uuid.uuid4()); DOC_ROOT.mkdir(parents=True,exist_ok=True); path=DOC_ROOT/f"{did}.txt"; path.write_bytes(content)
    row={"id":did,"owner_user_id":actor["id"],"department":department,"scope":scope,"audience_role":audience,"filename":filename,"mime_type":"text/plain","size_bytes":len(content),"guard_decision":guard_decision,"storage_path":str(path),"created_at":now()}
    with connect() as db: db.execute("INSERT INTO documents VALUES(:id,:owner_user_id,:department,:scope,:audience_role,:filename,:mime_type,:size_bytes,:guard_decision,:storage_path,:created_at)",row)

    text = content.decode("utf-8", errors="replace")
    chunks = []
    for chunk in chunk_text(text):
        chash = hashlib.sha256(chunk.text.encode()).hexdigest()
        chunks.append(ChunkRecord(chunk_id=f"{did}_{chunk.chunk_index}", document_id=did, chunk_index=chunk.chunk_index, text=chunk.text, content_hash=chash, metadata={}))

    access_roles = {"member", "leader", "superadmin"} if audience == "member" else ({"leader", "superadmin"} if audience == "leader" else {"superadmin"})
    if scope == "global":
        access_departments = {DEPARTMENT_WILDCARD}
    elif scope == "department":
        access_departments = {department}
    else:
        access_departments = {f"user_{actor['id']}"}

    facts = AclFacts(sensitivity_rank=ROLE_RANK[audience], access_roles=frozenset(access_roles), access_departments=frozenset(access_departments))
    dhash = hashlib.sha256(content).hexdigest()
    dmeta = {"filename": filename, "scope": scope, "owner_department": department}
    dmeta.update(acl_metadata(facts))

    doc = DocumentRecord(document_id=did, external_id=did, source_key="workspace", source_id=did, source_type="workspace", classification="internal", trust_level="authenticated", title=filename, content_hash=dhash, created_at=row["created_at"], updated_at=row["created_at"], metadata=dmeta)

    get_retriever().upsert_documents([(doc, chunks)])

    return row


def delete_document(actor: dict[str, Any], did: str) -> bool:
    allowed={d["id"]:d for d in accessible_documents(actor)}; doc=allowed.get(did)
    if not doc or (actor["role"] != "superadmin" and doc["owner_user_id"] != actor["id"]): return False
    with connect() as db: db.execute("DELETE FROM documents WHERE id=?",(did,))
    try: Path(doc["storage_path"]).unlink(missing_ok=True)
    except OSError: pass
    get_retriever().delete_document(did)
    return True


def _task_dict(row: sqlite3.Row) -> dict[str, Any]: return dict(row)


def list_tasks(actor: dict[str, Any]) -> list[dict[str, Any]]:
    if actor["role"] == "superadmin": where,args="1=1",()
    elif actor["role"] == "leader": where,args="t.department=?",(actor["department"],)
    else: where,args="t.assigned_user_id=?",(actor["id"],)
    with connect() as db:
        rows=db.execute(f"""SELECT t.*,a.username assigned_username,c.username creator_username,
          (SELECT COUNT(*) FROM tasks x WHERE x.parent_task_id=t.id) child_count
          FROM tasks t JOIN users a ON a.id=t.assigned_user_id JOIN users c ON c.id=t.created_by
          WHERE {where} ORDER BY t.created_at DESC""",args)
        return [_task_dict(r) for r in rows]


def create_department_task(actor: dict[str, Any], title: str, description: str, department: str, due_at: str | None) -> dict[str, Any]:
    if actor["role"] != "superadmin": raise PermissionError
    with connect() as db:
        leader=db.execute("SELECT id FROM users WHERE department=? AND role='leader'",(department,)).fetchone()
        if not leader: raise LookupError("Phòng ban chưa có leader")
        tid,stamp=str(uuid.uuid4()),now()
        db.execute("INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(tid,None,title[:160],description[:4000],department,leader["id"],actor["id"],"todo",0,due_at,stamp,stamp))
    return next(t for t in list_tasks(actor) if t["id"]==tid)


def delegate_task(actor: dict[str, Any], parent_id: str, assigned_user_id: int, title: str, description: str, due_at: str | None) -> dict[str, Any]:
    if actor["role"] not in ("leader","superadmin"): raise PermissionError
    with connect() as db:
        parent=db.execute("SELECT * FROM tasks WHERE id=? AND parent_task_id IS NULL",(parent_id,)).fetchone()
        target=db.execute("SELECT * FROM users WHERE id=?",(assigned_user_id,)).fetchone()
        if not parent or not target: raise LookupError("Không tìm thấy công việc hoặc nhân viên")
        if actor["role"]=="leader" and (parent["department"]!=actor["department"] or parent["assigned_user_id"]!=actor["id"]): raise PermissionError
        if target["department"]!=parent["department"] or target["role"]!="member": raise ValueError("Chỉ được giao cho nhân viên thuộc đúng phòng ban")
        tid,stamp=str(uuid.uuid4()),now()
        db.execute("INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(tid,parent_id,title[:160],description[:4000],parent["department"],target["id"],actor["id"],"todo",0,due_at,stamp,stamp))
    return next(t for t in list_tasks(actor) if t["id"]==tid)


def update_progress(actor: dict[str, Any], task_id: str, progress: int) -> dict[str, Any]:
    with connect() as db:
        task=db.execute("SELECT * FROM tasks WHERE id=?",(task_id,)).fetchone()
        if not task: raise LookupError
        if actor["role"]!="superadmin" and task["assigned_user_id"]!=actor["id"]: raise PermissionError
        status="done" if progress==100 else ("in_progress" if progress else "todo")
        db.execute("UPDATE tasks SET progress=?,status=?,updated_at=? WHERE id=?",(progress,status,now(),task_id))
        if task["parent_task_id"]:
            avg=db.execute("SELECT CAST(AVG(progress) AS INTEGER) p FROM tasks WHERE parent_task_id=?",(task["parent_task_id"],)).fetchone()["p"]
            ps="done" if avg==100 else ("in_progress" if avg else "todo")
            db.execute("UPDATE tasks SET progress=?,status=?,updated_at=? WHERE id=?",(avg,ps,now(),task["parent_task_id"]))
    return next(t for t in list_tasks(actor) if t["id"]==task_id)


initialize()
