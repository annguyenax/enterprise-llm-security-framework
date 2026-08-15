"""Load datasets/demo-leak/corpus.jsonl into the workspace document store.

Without this step the demo silently does nothing: the questions in
`DEMO_PROMPTS.md` retrieve whatever unrelated documents happen to be in the
knowledge base, the model answers "I have no information about that", and
both chatbots look identical -- which is exactly the failure mode this
script exists to remove.

Two deliberate choices
----------------------
**Seeding bypasses the upload route.** `store.add_document` is called
directly rather than `POST /v1/documents`, because the upload path runs the
RAG Context Guard and would refuse `thong-bao-bao-tri-he-thong.md` -- the
poisoned document is the whole point of the indirect-injection demo. The
scenario under test is "a poisoned document is already in the knowledge
base", not "can we upload one".

**One shared knowledge base is seeded.** Both chatbots call
`store.retrieve()` with the same actor and therefore receive the same
ACL-filtered candidates. The comparison changes only the inference guard
chain.

    chatbot/index.html     -> app.js        -> /v1/conversations/{id}/messages
                                             -> store.retrieve()
                                             -> `documents` table
    chatbot/unguarded.html -> unguarded.js  -> /v1/unguarded/chat
                                             -> store.retrieve()
                                             -> `documents` table

Writes to the **live workspace database** by default, because that is the
one the running server reads. This is a lab action: it puts synthetic
credentials and a deliberately poisoned document into the knowledge base.
Point it at a demo instance.

Run:
    .venv\\Scripts\\python.exe scripts/build_demo_leak_corpus.py
    .venv\\Scripts\\python.exe scripts/seed_demo_leak_corpus.py
    .venv\\Scripts\\python.exe scripts/seed_demo_leak_corpus.py --remove
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

CORPUS_PATH = REPO_ROOT / "datasets" / "demo-leak" / "corpus.jsonl"

# ACL metadata is authoritative; classification prose inside a document is
# not an access-control rule. Keep sensitive fixtures away from ordinary
# members while retaining one public poisoned document for the RAG-guard demo.
ACL_BY_LEAK_KIND = {
    "payroll_pii": {
        "scope": "department",
        "audience": "leader",
        "department": "HR",
        "allowed_groups": [],
    },
    "credentials": {
        "scope": "department",
        "audience": "leader",
        "department": "IT",
        "allowed_groups": [],
    },
    "strategic": {
        "scope": "global",
        "audience": "superadmin",
        "department": "WORKSPACE",
        "allowed_groups": [],
    },
    "customer_pii": {
        "scope": "global",
        "audience": "leader",
        "department": "WORKSPACE",
        "allowed_groups": [],
    },
    "poisoned_indirect": {
        "scope": "global",
        "audience": "member",
        "department": "WORKSPACE",
        "allowed_groups": [],
    },
}


def _load_records() -> list[dict]:
    if not CORPUS_PATH.is_file():
        raise SystemExit(
            f"{CORPUS_PATH.relative_to(REPO_ROOT).as_posix()} khong ton tai. "
            "Chay scripts/build_demo_leak_corpus.py truoc."
        )
    records = []
    for line_number, raw in enumerate(CORPUS_PATH.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            record = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"corpus.jsonl:{line_number}: JSON khong hop le") from exc
        records.append(record)
    return records


def _remove_existing(store, actor, filenames: set[str]) -> int:
    """Delete previously seeded copies so re-running does not duplicate."""
    removed = 0
    for document in store.accessible_documents(actor):
        if document["filename"] in filenames and store.delete_document(actor, document["id"]):
            removed += 1
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the enterprise leak demo corpus.")
    parser.add_argument("--username", default="superadmin")
    parser.add_argument("--password", default="SuperAdmin#2026")
    parser.add_argument(
        "--remove", action="store_true", help="Chi go bo tai lieu demo da nap, khong nap moi"
    )
    args = parser.parse_args()

    from app.workspace import store  # noqa: PLC0415 - after sys.path setup

    store.initialize()
    result = store.authenticate(args.username, args.password)
    if result is None:
        raise SystemExit(f"Khong dang nhap duoc: {args.username}")
    _token, actor = result
    if actor["role"] != "superadmin":
        raise SystemExit("Can quyen superadmin de nap tai lieu pham vi global")

    records = _load_records()
    filenames = {record["filename"] for record in records}

    removed = _remove_existing(store, actor, filenames)
    if args.remove:
        print(f"Da go {removed} tai lieu demo khoi kho dung chung.")
        print(f"CSDL: {store.DB_PATH}")
        return 0

    seeded = []
    for record in records:
        payload = record["content"]
        encoded = payload.encode("utf-8")
        leak_kind = record.get("leak_kind", "")
        policy = ACL_BY_LEAK_KIND.get(leak_kind)
        if policy is None:
            raise SystemExit(f"Chua khai bao ACL cho leak_kind={leak_kind!r}")
        # Shared knowledge base for guarded and unguarded inference.
        row = store.add_document(
            actor,
            record["filename"],
            encoded,
            policy["scope"],
            policy["audience"],
            policy["department"],
            guard_decision="allow",
            allowed_groups=policy["allowed_groups"],
        )
        seeded.append(
            (
                record["filename"],
                leak_kind,
                f'{policy["scope"]}/{policy["department"]}/{policy["audience"]}',
                row["size_bytes"],
            )
        )

    if removed:
        print(f"Da go {removed} ban cu truoc khi nap lai.")
    print(f"Da nap {len(seeded)} tai lieu vao kho tri thuc dung chung:\n")
    for filename, kind, acl, size in seeded:
        print(f"  {filename:45s} {kind:20s} {acl:30s} {size:6d} bytes")
    print("\n  documents -> ca chatbot co tuong va khong tuong; ACL theo tung fixture")
    print(f"\nCSDL: {store.DB_PATH}")
    print("Khoi dong lai backend neu no dang chay, roi thu lai DEMO_PROMPTS.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
