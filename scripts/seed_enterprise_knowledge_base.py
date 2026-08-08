"""Load datasets/enterprise-kb-full/ into the workspace so the chatbot works.

Reads the document tree built by `scripts/build_enterprise_knowledge_base.py`
and loads every document into the workspace `documents` table -- the store
the guarded chatbot at `/` retrieves from -- with access control derived
from each document's declared sensitivity and department.

Three things this script has to reconcile
------------------------------------------
1. **The knowledge base has three business departments; the workspace ships
   with two.** The skeleton models Kế toán / IT / Nhân sự, but
   `store.initialize()` only seeds IT, HR and WORKSPACE. Rather than change
   the seed (which several tests assert exact counts against), this script
   creates the KETOAN department and its users idempotently at load time.

2. **Two different sensitivity vocabularies.** The documents carry the
   four-tier `public/internal/confidential/restricted` scale; the workspace
   `documents` table expresses access as `(scope, audience_role, department)`.
   `SENSITIVITY_TO_ACCESS` is the single, explicit mapping between them.

3. **Every document is content-scanned before storage.** Each file goes
   through the RAG Context Guard exactly as an upload would, and is stored
   with the guard's real decision -- so a document the guard sanitizes is
   stored sanitized, never with an inaccurate "allow" (the Slice 0 fix).

Loading is done AS superadmin, because only superadmin may set an arbitrary
`scope`/`department` on `store.add_document`; a normal user is forced into
their own department. This writes to the live workspace database, which is a
lab action -- it puts synthetic payroll, credentials and strategic
documents into the knowledge base the running chatbot reads.

Run:
    .venv\\Scripts\\python.exe scripts/build_enterprise_knowledge_base.py
    .venv\\Scripts\\python.exe scripts/seed_enterprise_knowledge_base.py
    .venv\\Scripts\\python.exe scripts/seed_enterprise_knowledge_base.py --remove
"""
from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

KB_ROOT = REPO_ROOT / "datasets" / "enterprise-kb-full"

# sensitivity -> (scope, audience_role). See the module docstring for why the
# two vocabularies exist. `restricted` maps to audience=leader, which -- with
# department scoping -- means "the department's leader and superadmin only";
# for the WORKSPACE department that is superadmin alone.
SENSITIVITY_TO_ACCESS = {
    "public": ("global", "member"),
    "internal": ("department", "member"),
    "confidential": ("department", "leader"),
    "restricted": ("department", "leader"),
}

# Department created on demand so the skeleton's three-department design is
# real. IT/HR/WORKSPACE already exist from store.initialize().
KETOAN_DEPARTMENT = ("KETOAN", "Phòng Kế toán")
KETOAN_USERS = (
    # username, password, role
    ("ketoan.leader", "KeToanLeader#2026", "leader"),
    ("ketoan.user1", "KeToanUser1#2026", "member"),
)


def _ensure_accounting(store) -> None:
    """Create the KETOAN department and its users if absent. Idempotent:
    `INSERT OR IGNORE` leaves an existing row untouched, so reruns are safe
    and existing passwords are never rewritten."""
    stamp = store.now()
    with store.connect() as db:
        db.execute(
            "INSERT OR IGNORE INTO departments(code,name,created_at) VALUES(?,?,?)",
            (KETOAN_DEPARTMENT[0], KETOAN_DEPARTMENT[1], stamp),
        )
        for username, password, role in KETOAN_USERS:
            exists = db.execute(
                "SELECT 1 FROM users WHERE username=? COLLATE NOCASE", (username,)
            ).fetchone()
            if exists:
                continue
            salt = secrets.token_bytes(16)
            db.execute(
                "INSERT INTO users(username,password_hash,salt,role,department,created_at) VALUES(?,?,?,?,?,?)",
                (username, store.password_hash(password, salt), salt.hex(), role, KETOAN_DEPARTMENT[0], stamp),
            )


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Read the flat `key: value` front-matter block, mirroring
    `app/services/dataset_loader.py` -- no PyYAML dependency (AGENT_RULES
    rule 11), and the KB's front-matter is deliberately flat."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    block = text[3:end].strip("\n")
    body = text[end + 4:].lstrip("\n")
    meta: dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    return meta, body


def _iter_documents():
    """Yield (relative_path, metadata, body) for every KB markdown file."""
    if not KB_ROOT.is_dir():
        raise SystemExit(
            f"{KB_ROOT.relative_to(REPO_ROOT).as_posix()} khong ton tai. "
            "Chay scripts/build_enterprise_knowledge_base.py truoc."
        )
    for path in sorted(KB_ROOT.rglob("*.md")):
        meta, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
        if not meta.get("workspace_department"):
            continue  # skip any stray non-KB markdown
        yield path, meta, body


def _seeded_filenames() -> set[str]:
    return {path.name for path, _m, _b in _iter_documents()}


def _remove_existing(store, actor, filenames: set[str]) -> int:
    removed = 0
    for document in store.accessible_documents(actor):
        if document["filename"] in filenames and store.delete_document(actor, document["id"]):
            removed += 1
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the full enterprise knowledge base.")
    parser.add_argument("--username", default="superadmin")
    parser.add_argument("--password", default="SuperAdmin#2026")
    parser.add_argument("--remove", action="store_true", help="Go bo tai lieu KB da nap, khong nap moi")
    args = parser.parse_args()

    from app.guards.rag_guard import evaluate_rag_context  # noqa: PLC0415
    from app.core.decisions import Decision  # noqa: PLC0415
    from app.schemas.requests import RAGContextChunk  # noqa: PLC0415
    from app.workspace import store  # noqa: PLC0415

    store.initialize()
    _ensure_accounting(store)

    result = store.authenticate(args.username, args.password)
    if result is None:
        raise SystemExit(f"Khong dang nhap duoc: {args.username}")
    _token, actor = result
    if actor["role"] != "superadmin":
        raise SystemExit("Can quyen superadmin de nap tai lieu vao nhieu phong ban")

    filenames = _seeded_filenames()
    removed = _remove_existing(store, actor, filenames)
    if args.remove:
        print(f"Da go {removed} tai lieu KB khoi kho.")
        return 0

    loaded: list[tuple[str, str, str, str]] = []
    for path, meta, body in _iter_documents():
        sensitivity = meta.get("sensitivity", "internal")
        if sensitivity not in SENSITIVITY_TO_ACCESS:
            raise SystemExit(f"{path.name}: sensitivity khong hop le: {sensitivity!r}")
        scope, audience = SENSITIVITY_TO_ACCESS[sensitivity]
        department = meta["workspace_department"]

        # Content-scan exactly as an upload would, and store the guard's real
        # decision. Blocking decisions are refused rather than force-stored.
        guard = evaluate_rag_context([RAGContextChunk(doc_id=path.name, text=body, metadata={})])
        if guard.decision in (Decision.BLOCK, Decision.HUMAN_REVIEW):
            print(f"  BO QUA (guard chan): {path.name} -> {guard.decision.value}")
            continue
        stored = (
            guard.sanitized_chunks[0].text
            if guard.decision == Decision.SANITIZE and guard.sanitized_chunks
            else body
        )

        store.add_document(
            actor,
            path.name,
            stored.encode("utf-8"),
            scope,
            audience,
            department,
            guard_decision=guard.decision.value,
            mime_type="text/markdown",
        )
        loaded.append((meta.get("title", path.name), department, f"{scope}/{audience}", sensitivity))

    if removed:
        print(f"Da go {removed} ban cu truoc khi nap lai.")
    print(f"Da nap {len(loaded)} tai lieu vao kho cua chatbot:\n")
    for title, dept, access, sensitivity in loaded:
        print(f"  [{dept:9s}] {access:18s} {sensitivity:12s} {title}")
    print("\nTai khoan truy cap theo phong:")
    print("  superadmin / SuperAdmin#2026   -> thay toan bo")
    print("  it.leader  / ITLeader#2026     -> IT (gom tai lieu MAT cua IT)")
    print("  it.user1   / ITUser1#2026      -> IT (chi DEPARTMENT_INTERNAL tro xuong)")
    print("  hr.leader  / HRLeader#2026     -> HR")
    print("  ketoan.leader / KeToanLeader#2026 -> Ke toan")
    print(f"\nCSDL: {store.DB_PATH}")
    print("Khoi dong lai backend neu dang chay, roi thu tren chatbot.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
