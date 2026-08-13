from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import sqlite3
import unicodedata
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
STORABLE_GUARD_DECISIONS = frozenset(
    {"allow", "log_only", "sanitize", "not_evaluated"}
)


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
        CREATE TABLE IF NOT EXISTS document_user_grants (
          document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
          user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          granted_by INTEGER NOT NULL REFERENCES users(id),
          created_at TEXT NOT NULL,
          PRIMARY KEY(document_id,user_id)
        );
        CREATE TABLE IF NOT EXISTS document_group_grants (
          document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
          department TEXT NOT NULL REFERENCES departments(code),
          minimum_role TEXT NOT NULL CHECK(minimum_role IN ('member','leader','superadmin')),
          granted_by INTEGER NOT NULL REFERENCES users(id),
          created_at TEXT NOT NULL,
          PRIMARY KEY(document_id,department,minimum_role)
        );
        CREATE TABLE IF NOT EXISTS document_embeddings (
          document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
          model TEXT NOT NULL,
          content_hash TEXT NOT NULL,
          vector_json TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          PRIMARY KEY(document_id,model)
        );
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
        CREATE TABLE IF NOT EXISTS appeals (
          id TEXT PRIMARY KEY,
          message_id INTEGER NOT NULL UNIQUE REFERENCES messages(id) ON DELETE CASCADE,
          user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          reason TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','accepted','rejected')),
          created_at TEXT NOT NULL,
          resolved_at TEXT,
          resolved_by INTEGER REFERENCES users(id),
          resolution_note TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_appeals_status ON appeals(status);
        """)
        # Additive column migration for databases created before guard risk
        # scores were surfaced. `CREATE TABLE IF NOT EXISTS` above leaves an
        # existing table untouched, so new columns have to be added
        # explicitly -- and only when they are actually missing, since
        # SQLite has no `ADD COLUMN IF NOT EXISTS`.
        existing = {row["name"] for row in db.execute("PRAGMA table_info(messages)")}
        for column in ("risk_input", "risk_rag", "risk_output"):
            if column not in existing:
                db.execute(f"ALTER TABLE messages ADD COLUMN {column} REAL")
        # Embedding vectors are additionally stored as raw little-endian
        # float32 (`vector_f32`), L2-normalized at write time. `vector_json`
        # is kept so an existing cache stays readable and can be backfilled
        # lazily rather than forcing a full re-embed on upgrade.
        #
        # The BLOB is not a micro-optimization: `json.loads` on a 768-dim
        # vector costs ~768 float parses per document per query, which is the
        # same order as the cosine loop it was meant to replace. Reading a
        # BLOB with `np.frombuffer` is a memcpy, so the vectorized dot
        # product actually becomes the dominant cost instead of the parser.
        embedding_columns = {row["name"] for row in db.execute("PRAGMA table_info(document_embeddings)")}
        if "vector_f32" not in embedding_columns:
            db.execute("ALTER TABLE document_embeddings ADD COLUMN vector_f32 BLOB")
        if "dim" not in embedding_columns:
            db.execute("ALTER TABLE document_embeddings ADD COLUMN dim INTEGER")
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
        rows = db.execute("""SELECT m.*,f.value feedback,a.id appeal_id,a.status appeal_status,
                             a.resolution_note appeal_note FROM messages m
                           LEFT JOIN feedback f ON f.message_id=m.id AND f.user_id=?
                           LEFT JOIN appeals a ON a.message_id=m.id
                           WHERE m.conversation_id=? ORDER BY m.id""", (actor["id"], cid))
        result=[]
        for row in rows:
            item=dict(row); item["sources"]=json.loads(item.pop("sources_json") or "[]"); result.append(item)
        return result


def add_message(cid: str, role: str, content: str, **extra: Any) -> dict[str, Any]:
    """Persist one message. `risk_input`/`risk_rag`/`risk_output` are the
    per-stage `risk_score` values the guards already compute; storing them
    means a reloaded conversation shows the same scores as the live reply
    instead of losing them on refresh."""
    stamp=now(); sources=extra.get("sources", [])
    risk={key:extra.get(key) for key in ("risk_input","risk_rag","risk_output")}
    with connect() as db:
        cur=db.execute("""INSERT INTO messages(conversation_id,role,content,decision,request_id,latency_ms,sources_json,created_at,risk_input,risk_rag,risk_output)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?)""", (cid,role,content,extra.get("decision"),extra.get("request_id"),extra.get("latency_ms"),json.dumps(sources,ensure_ascii=False),stamp,risk["risk_input"],risk["risk_rag"],risk["risk_output"]))
        db.execute("UPDATE conversations SET updated_at=? WHERE id=?", (stamp,cid))
    return {"id":cur.lastrowid,"conversation_id":cid,"role":role,"content":content,"decision":extra.get("decision"),"request_id":extra.get("request_id"),"latency_ms":extra.get("latency_ms"),"sources":sources,"created_at":stamp,"feedback":None,**risk,"appeal":None}


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


APPEALABLE_DECISIONS = frozenset({"block", "human_review"})
APPEAL_RESOLUTIONS = frozenset({"accepted", "rejected"})


def _appeal_row(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def message_appeal(message_id: int) -> dict[str, Any] | None:
    with connect() as db:
        row = db.execute("SELECT * FROM appeals WHERE message_id=?", (message_id,)).fetchone()
        return _appeal_row(row) if row else None


def create_appeal(actor: dict[str, Any], message_id: int, reason: str) -> dict[str, Any]:
    """Record one appeal against a message the gateway refused.

    Ownership is re-checked here against the conversation, not taken from
    the request: a message id is guessable, and `set_feedback` already
    follows the same pattern for the same reason. Only decisions that
    actually withheld an answer are appealable -- there is nothing to appeal
    about a reply the user received.
    """
    text = reason.strip()
    if not text:
        raise ValueError("Bạn cần nêu lý do kháng cáo")
    if len(text) > 2000:
        raise ValueError("Lý do kháng cáo tối đa 2000 ký tự")
    with connect() as db:
        row = db.execute(
            """SELECT m.id, m.decision, c.user_id FROM messages m
               JOIN conversations c ON c.id=m.conversation_id
               WHERE m.id=? AND m.role='assistant'""",
            (message_id,),
        ).fetchone()
        if not row or row["user_id"] != actor["id"]:
            raise LookupError("Không tìm thấy tin nhắn")
        if (row["decision"] or "") not in APPEALABLE_DECISIONS:
            raise ValueError("Chỉ tin nhắn bị chặn hoặc chờ duyệt mới có thể kháng cáo")
        if db.execute("SELECT 1 FROM appeals WHERE message_id=?", (message_id,)).fetchone():
            raise ValueError("Tin nhắn này đã được kháng cáo")
        aid, stamp = str(uuid.uuid4()), now()
        db.execute(
            "INSERT INTO appeals(id,message_id,user_id,reason,status,created_at) VALUES(?,?,?,?,'pending',?)",
            (aid, message_id, actor["id"], text, stamp),
        )
    return {"id": aid, "message_id": message_id, "status": "pending", "created_at": stamp, "reason": text}


def list_appeals(actor: dict[str, Any]) -> list[dict[str, Any]]:
    """Superadmin-only review queue.

    Deliberately not readable by leaders: an appeal quotes the prompt that
    was blocked, which is private conversation content, and `conversations`
    already keeps those private from every role including superadmin. The
    appeal is the one narrow, user-initiated exception -- the user chose to
    escalate this specific message -- so it must not widen any further.
    """
    if actor["role"] != "superadmin":
        raise PermissionError
    with connect() as db:
        rows = db.execute(
            """SELECT a.*, u.username, u.department, m.content AS message_content,
                      m.decision AS message_decision, m.request_id, r.username AS resolved_by_username
               FROM appeals a
               JOIN users u ON u.id=a.user_id
               JOIN messages m ON m.id=a.message_id
               LEFT JOIN users r ON r.id=a.resolved_by
               ORDER BY CASE a.status WHEN 'pending' THEN 0 ELSE 1 END, a.created_at DESC"""
        )
        return [_appeal_row(row) for row in rows]


def resolve_appeal(actor: dict[str, Any], appeal_id: str, status: str, note: str = "") -> dict[str, Any]:
    if actor["role"] != "superadmin":
        raise PermissionError
    if status not in APPEAL_RESOLUTIONS:
        raise ValueError("Kết quả xử lý không hợp lệ")
    with connect() as db:
        row = db.execute("SELECT status FROM appeals WHERE id=?", (appeal_id,)).fetchone()
        if not row:
            raise LookupError("Không tìm thấy kháng cáo")
        if row["status"] != "pending":
            raise ValueError("Kháng cáo này đã được xử lý")
        db.execute(
            "UPDATE appeals SET status=?,resolved_at=?,resolved_by=?,resolution_note=? WHERE id=?",
            (status, now(), actor["id"], note.strip()[:1000], appeal_id),
        )
    return next(item for item in list_appeals(actor) if item["id"] == appeal_id)


def accessible_documents(actor: dict[str, Any]) -> list[dict[str, Any]]:
    rank=ROLE_RANK[actor["role"]]
    with connect() as db:
        rows=db.execute("SELECT d.*,u.username owner_username FROM documents d LEFT JOIN users u ON u.id=d.owner_user_id ORDER BY d.created_at DESC")
        result=[]
        for r in rows:
            user_grants = [
                dict(row) for row in db.execute(
                    """SELECT u.id,u.username FROM document_user_grants g
                       JOIN users u ON u.id=g.user_id WHERE g.document_id=?
                       ORDER BY u.username""",
                    (r["id"],),
                )
            ]
            group_grants = [
                dict(row) for row in db.execute(
                    """SELECT department,minimum_role FROM document_group_grants
                       WHERE document_id=? ORDER BY department,minimum_role""",
                    (r["id"],),
                )
            ]
            legacy_allowed = ROLE_RANK.get(r["audience_role"],3) <= rank and (
                (r["scope"] == "user" and r["owner_user_id"] == actor["id"])
                or (r["scope"] == "department" and r["department"] == actor["department"])
                or r["scope"] == "global"
            )
            explicitly_allowed = any(grant["id"] == actor["id"] for grant in user_grants)
            group_allowed = any(
                grant["department"].casefold() == actor["department"].casefold()
                and rank >= ROLE_RANK[grant["minimum_role"]]
                for grant in group_grants
            )
            allowed = actor["role"] == "superadmin" or legacy_allowed or explicitly_allowed or group_allowed
            if allowed:
                item = dict(r)
                item["allowed_users"] = [grant["username"] for grant in user_grants]
                item["allowed_groups"] = [
                    f'{grant["department"]}:{grant["minimum_role"]}'
                    for grant in group_grants
                ]
                item["access_reason"] = (
                    "superadmin" if actor["role"] == "superadmin" else
                    "explicit-user" if explicitly_allowed else
                    "explicit-group" if group_allowed else
                    "scope"
                )
                result.append(item)
        return result


def sharing_options(actor: dict[str, Any]) -> dict[str, list[str]]:
    """Return stable identifiers accepted by upload sharing parameters."""
    with connect() as db:
        usernames = [
            str(row[0]) for row in db.execute(
                "SELECT username FROM users WHERE id<>? ORDER BY username", (actor["id"],)
            )
        ]
        departments = [
            str(row[0]) for row in db.execute(
                "SELECT code FROM departments WHERE code<>'WORKSPACE' ORDER BY code"
            )
        ]
    groups = [f"{department}:{role}" for department in departments for role in ("member", "leader")]
    return {"users": usernames, "groups": groups}


def _filename_terms(value: str) -> set[str]:
    """Comparable ASCII terms for Vietnamese queries and slug-like names."""
    # Vietnamese đ/Đ is a distinct letter and NFKD does not decompose it.
    # Translate it explicitly so "hợp đồng" matches "hop-dong".
    normalized = unicodedata.normalize(
        "NFKD", value.casefold().translate(str.maketrans({"đ": "d"}))
    )
    ascii_value = "".join(char for char in normalized if not unicodedata.combining(char))
    return {
        term
        for term in re.findall(r"[a-z0-9]+", ascii_value)
        if term not in {"file", "tai", "lieu", "noi", "dung", "txt", "md", "pdf"}
    }


def _direct_document_context(document: dict[str, Any]) -> tuple[list[Any], list[dict[str, Any]]] | None:
    from app.schemas.requests import RAGContextChunk

    try:
        text = Path(str(document["storage_path"])).read_text(encoding="utf-8")
    except OSError:
        return None
    filename = str(document["filename"])
    metadata = {"filename": filename, "scope": document["scope"]}
    return (
        [RAGContextChunk(doc_id=document["id"], text=text, metadata=metadata)],
        [{"id": document["id"], "filename": filename, "scope": document["scope"]}],
    )


def _display_cosine(score: Any) -> float | None:
    """Clamp a cosine similarity to [0, 1] for display.

    `hybrid_retrieval._cosine` returns the sentinel `-1.0` for a dimension
    mismatch or a zero vector, and genuine cosines can be negative for
    unrelated text. Neither is meaningful as a "relevance" percentage, so
    both floor at 0 -- while `None` stays `None`, because "no semantic score
    was computed" and "the semantic score was zero" are different facts and
    the UI must not conflate them.
    """
    if not isinstance(score, (int, float)) or isinstance(score, bool):
        return None
    return round(max(0.0, min(1.0, float(score))), 4)


def retrieve(actor: dict[str, Any], query: str, limit: int = 4) -> tuple[list[Any], list[dict[str, Any]]]:
    from app.schemas.requests import RAGContextChunk
    from app.retrieval.sqlite_bm25 import EmptySearchQueryError
    # An exact filename request is stronger than lexical similarity. Resolve
    # it against the already ACL-filtered workspace directory and provide
    # only that document, avoiding unrelated BM25 hits that can confuse a
    # small local model.
    normalized_query = query.casefold()
    accessible = accessible_documents(actor)
    accessible_ids = {str(document["id"]) for document in accessible}
    for document in accessible:
        filename = str(document["filename"])
        if filename.casefold() not in normalized_query:
            continue
        direct = _direct_document_context(document)
        if direct is not None:
            return direct

    # Possessive questions such as "lương của tôi" describe ownership, not a
    # filename. Prefer the caller's own private payslip/contract before global
    # policies or department aggregates can enter the context.
    query_terms = _filename_terms(query)
    personal_reference = {"cua", "toi"} <= query_terms or {"cua", "minh"} <= query_terms
    if personal_reference:
        own_documents = [
            document for document in accessible
            if document["scope"] == "user" and document["owner_user_id"] == actor["id"]
        ]
        category_terms: set[str] = set()
        if "luong" in query_terms or {"thu", "nhap"} <= query_terms:
            category_terms = {"phieu", "luong"}
        elif {"hop", "dong"} <= query_terms:
            category_terms = {"hop", "dong", "lao", "dong"}
        personal_matches = [
            document for document in own_documents
            if category_terms and category_terms <= _filename_terms(str(document["filename"]))
        ]
        if len(personal_matches) == 1:
            direct = _direct_document_context(personal_matches[0])
            if direct is not None:
                return direct

    # Natural-language references such as "file kế hoạch" should resolve a
    # unique slug-like filename (`it-ke-hoach-leader.md`) without mixing in
    # unrelated BM25 hits. Never guess when two accessible files tie.
    scored = [
        (len(query_terms & _filename_terms(str(document["filename"]))), document)
        for document in accessible
    ]
    best_score = max((score for score, _ in scored), default=0)
    best = [document for score, document in scored if score == best_score]
    if best_score >= 2 and len(best) == 1:
        direct = _direct_document_context(best[0])
        if direct is not None:
            return direct

    principal = RetrievalPrincipal(user_id=actor["id"], role=actor["role"], department=actor["department"], max_sensitivity_rank=ROLE_RANK[actor["role"]])
    try:
        as_of = canonical_timestamp(datetime.now(timezone.utc))
        candidate_limit = min(settings.retrieval_max_top_k, max(limit * 10, limit))
        result = get_retriever().search(RetrievalQuery(query=query, top_k=candidate_limit, principal=principal, as_of=as_of))
    except EmptySearchQueryError:
        return [], []

    # The workspace database is authoritative for explicit user/group grants.
    # Re-filter every candidate here before its text can enter the LLM context.
    lexical_hits = [hit for hit in result.hits if hit.document_id in accessible_ids]

    semantic_rows: list[tuple[dict[str, Any], float]] = []
    if settings.workspace_embedding_model.strip():
        try:
            from app.workspace.hybrid_retrieval import semantic_rank
            semantic_rows = semantic_rank(
                query,
                accessible,
                model=settings.workspace_embedding_model,
                base_url=settings.ollama_embedding_base_url,
                connect_factory=connect,
                limit=max(limit * 3, limit),
            )
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError):
            # Semantic retrieval is an availability enhancement, not an ACL
            # boundary. BM25 remains available and is still filtered above.
            semantic_rows = []

    if semantic_rows:
        # Reciprocal-rank fusion avoids mixing incomparable BM25 and cosine
        # score scales. ACL filtering happened before both candidate lists.
        fused: dict[str, float] = {}
        lexical_by_id = {}
        for rank, hit in enumerate(lexical_hits, start=1):
            lexical_by_id.setdefault(hit.document_id, hit)
            fused[hit.document_id] = fused.get(hit.document_id, 0.0) + 1.0 / (60 + rank)
        semantic_by_id = {}
        for rank, (document, _score) in enumerate(semantic_rows, start=1):
            did = str(document["id"])
            semantic_by_id[did] = document
            fused[did] = fused.get(did, 0.0) + 1.0 / (60 + rank)
        # Per-source scores surfaced for the UI. Kept as three separate,
        # honestly-named numbers rather than one blended "relevance": cosine
        # similarity and BM25 are different scales measuring different
        # things, which is precisely why fusion here is rank-based (RRF) and
        # not a weighted sum of the raw values.
        lexical_rank_by_id = {}
        for rank, hit in enumerate(lexical_hits, start=1):
            lexical_rank_by_id.setdefault(hit.document_id, rank)
        semantic_score_by_id = {str(document["id"]): score for document, score in semantic_rows}
        semantic_rank_by_id = {str(document["id"]): rank for rank, (document, _s) in enumerate(semantic_rows, start=1)}

        ordered_ids = sorted(fused, key=lambda did: (-fused[did], did))[:limit]
        chunks=[]; sources=[]
        for did in ordered_ids:
            hit = lexical_by_id.get(did)
            if hit is not None:
                filename=hit.metadata.get("filename", "unknown"); scope=hit.metadata.get("scope", "unknown")
                chunks.append(RAGContextChunk(doc_id=did,text=hit.text,metadata={"filename":filename,"scope":scope}))
            else:
                document=semantic_by_id[did]; direct=_direct_document_context(document)
                if direct is None: continue
                chunks.extend(direct[0]); filename=document["filename"]; scope=document["scope"]
            sources.append({
                "id":did,"filename":filename,"scope":scope,"retrieval":"hybrid",
                "semantic_score":_display_cosine(semantic_score_by_id.get(did)),
                "semantic_rank":semantic_rank_by_id.get(did),
                "lexical_rank":lexical_rank_by_id.get(did),
                "fused_score":round(fused[did],6),
            })
        return chunks,sources

    hits = lexical_hits[:limit]
    chunks = [RAGContextChunk(doc_id=hit.document_id, text=hit.text, metadata={"filename": hit.metadata.get("filename", "unknown"), "scope": hit.metadata.get("scope", "unknown")}) for hit in hits]
    # No `semantic_score` on this path, and deliberately not a zero: the
    # embedding model was unavailable or disabled, which is not the same
    # claim as "this document scored zero semantically". The UI shows the
    # lexical rank alone rather than inventing a number.
    sources = [{"id": hit.document_id, "filename": hit.metadata.get("filename", "unknown"), "scope": hit.metadata.get("scope", "unknown"), "retrieval":"bm25", "semantic_score":None, "semantic_rank":None, "lexical_rank":index, "fused_score":None} for index, hit in enumerate(hits, start=1)]
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


def _upsert_document_index(row: dict[str, Any], content: bytes) -> None:
    """Build the retrieval representation from one authoritative workspace row."""
    did = str(row["id"])
    filename = str(row["filename"])
    scope = str(row["scope"])
    audience = str(row["audience_role"])
    department = str(row["department"] or "")
    owner_user_id = row["owner_user_id"]

    text = content.decode("utf-8", errors="replace")
    chunk_metadata = {"filename": filename, "scope": scope}
    chunks = []
    for chunk in chunk_text(text):
        chash = hashlib.sha256(chunk.text.encode()).hexdigest()
        chunks.append(ChunkRecord(chunk_id=f"{did}_{chunk.chunk_index}", document_id=did, chunk_index=chunk.chunk_index, text=chunk.text, content_hash=chash, metadata=chunk_metadata))

    access_roles = {"member", "leader", "superadmin"} if audience == "member" else ({"leader", "superadmin"} if audience == "leader" else {"superadmin"})
    if scope == "global":
        access_departments = {DEPARTMENT_WILDCARD}
    elif scope == "department":
        access_departments = {department}
    else:
        access_departments = {f"user_{owner_user_id}"}

    # The enterprise index has a compact role/department ACL. Add explicit
    # grants as candidate-producing tokens, then apply the authoritative
    # workspace ACL again after retrieval to avoid cross-product overgrant.
    with connect() as db:
        for grant in db.execute(
            "SELECT user_id FROM document_user_grants WHERE document_id=?", (did,)
        ):
            access_departments.add(f'user_{grant["user_id"]}')
        for grant in db.execute(
            "SELECT department,minimum_role FROM document_group_grants WHERE document_id=?",
            (did,),
        ):
            access_departments.add(str(grant["department"]))
            minimum_rank = ROLE_RANK[str(grant["minimum_role"])]
            access_roles.update(role for role, role_rank in ROLE_RANK.items() if role_rank >= minimum_rank)

    facts = AclFacts(sensitivity_rank=ROLE_RANK[audience], access_roles=frozenset(access_roles), access_departments=frozenset(access_departments))
    dmeta = {"filename": filename, "scope": scope, "owner_department": department}
    dmeta.update(acl_metadata(facts))
    stamp = str(row["created_at"])
    doc = DocumentRecord(document_id=did, external_id=did, source_key="workspace", source_id=did, source_type="workspace", classification="internal", trust_level="authenticated", title=filename, content_hash=hashlib.sha256(content).hexdigest(), created_at=stamp, updated_at=stamp, metadata=dmeta)
    get_retriever().upsert_documents([(doc, chunks)])


def synchronize_document_index() -> dict[str, int]:
    """Reconcile persistent workspace rows/files with the ACL retrieval index.

    Seed documents can predate the retriever database, and interrupted tests
    can leave index-only workspace records. Startup reconciliation repairs
    both directions without changing the authoritative workspace rows/files.
    """
    with connect() as db:
        rows = [dict(row) for row in db.execute("SELECT * FROM documents")]
    authoritative_ids = {str(row["id"]) for row in rows}
    retriever = get_retriever()
    removed = 0
    for orphan_id in retriever.document_ids_for_source("workspace") - authoritative_ids:
        removed += int(retriever.delete_document(orphan_id))

    indexed = skipped = 0
    for row in rows:
        path = Path(str(row["storage_path"]))
        try:
            content = path.read_bytes()
        except OSError:
            retriever.delete_document(str(row["id"]))
            skipped += 1
            continue
        _upsert_document_index(row, content)
        indexed += 1
    return {"indexed": indexed, "removed": removed, "skipped": skipped}


def add_document(actor: dict[str, Any], filename: str, content: bytes, scope: str, audience: str, department: str, *, guard_decision: str, mime_type: str = "text/plain", allowed_users: list[str] | None = None, allowed_groups: list[str] | None = None) -> dict[str, Any]:
    """Persist one uploaded document. `content` must already be the exact
    bytes the RAG Context Guard approved -- for a SANITIZE decision that is
    the *sanitized* text, not the caller's original upload.

    `guard_decision` is keyword-only and required, so no call site can
    silently record a decision the guard did not actually make. The explicit
    `not_evaluated` value is reserved for the intentionally unguarded lab
    upload route; guarded upload paths must pass their actual decision. It
    previously read `"allow"` unconditionally, which meant a document the
    guard had SANITIZEd was stored with its original bytes on disk *and* an
    audit row claiming a clean pass -- and every later retrieval read the
    unsanitized file back. Blocking decisions are rejected here as a
    fail-closed backstop; the route already refuses them earlier."""
    if scope not in {"user","department","global"} or audience not in ROLE_RANK: raise ValueError("Phạm vi hoặc đối tượng tài liệu không hợp lệ")
    if not isinstance(guard_decision, str) or guard_decision not in STORABLE_GUARD_DECISIONS:
        raise ValueError("Quyết định của guard không hợp lệ cho việc lưu trữ tài liệu")
    if not isinstance(mime_type, str) or not mime_type.strip():
        raise ValueError("MIME type của tài liệu không hợp lệ")
    if scope == "department" and actor["role"] == "member": raise PermissionError
    if scope == "global" and actor["role"] != "superadmin": raise PermissionError
    if actor["role"] != "superadmin": department=actor["department"]
    allowed_users = sorted({value.strip() for value in (allowed_users or []) if value.strip()})
    allowed_groups = sorted({value.strip() for value in (allowed_groups or []) if value.strip()})
    if len(allowed_users) > 20 or len(allowed_groups) > 20:
        raise ValueError("Mỗi tài liệu chỉ được chia sẻ thêm tối đa 20 user và 20 nhóm")
    with connect() as db:
        user_rows = list(db.execute(
            f"SELECT id,username FROM users WHERE username IN ({','.join('?' for _ in allowed_users)}) COLLATE NOCASE"
            if allowed_users else "SELECT id,username FROM users WHERE 0",
            allowed_users,
        ))
        departments = {str(row[0]).casefold(): str(row[0]) for row in db.execute("SELECT code FROM departments")}
    found_users = {str(row["username"]).casefold() for row in user_rows}
    missing_users = [name for name in allowed_users if name.casefold() not in found_users]
    if missing_users:
        raise ValueError("Không tìm thấy user được chia sẻ: " + ", ".join(missing_users))
    parsed_groups: list[tuple[str, str]] = []
    for value in allowed_groups:
        parts = value.split(":", 1)
        if len(parts) != 2 or parts[0].casefold() not in departments or parts[1] not in ROLE_RANK:
            raise ValueError(f"Nhóm chia sẻ không hợp lệ: {value}; dùng định dạng PHONGBAN:role")
        parsed_groups.append((departments[parts[0].casefold()], parts[1]))
    did=str(uuid.uuid4()); DOC_ROOT.mkdir(parents=True,exist_ok=True); path=DOC_ROOT/f"{did}.txt"; path.write_bytes(content)
    row={"id":did,"owner_user_id":actor["id"],"department":department,"scope":scope,"audience_role":audience,"filename":filename,"mime_type":mime_type,"size_bytes":len(content),"guard_decision":guard_decision,"storage_path":str(path),"created_at":now()}
    with connect() as db:
        db.execute("INSERT INTO documents VALUES(:id,:owner_user_id,:department,:scope,:audience_role,:filename,:mime_type,:size_bytes,:guard_decision,:storage_path,:created_at)",row)
        db.executemany(
            "INSERT INTO document_user_grants VALUES(?,?,?,?)",
            ((did, grant["id"], actor["id"], row["created_at"]) for grant in user_rows),
        )
        db.executemany(
            "INSERT INTO document_group_grants VALUES(?,?,?,?,?)",
            ((did, group_department, minimum_role, actor["id"], row["created_at"]) for group_department, minimum_role in parsed_groups),
        )

    _upsert_document_index(row, content)
    row["allowed_users"] = [str(grant["username"]) for grant in user_rows]
    row["allowed_groups"] = [f"{group_department}:{minimum_role}" for group_department, minimum_role in parsed_groups]
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
