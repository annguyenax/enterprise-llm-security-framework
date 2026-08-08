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

**Both knowledge bases are seeded, because there are two of them.** This is
the part that silently breaks the demo: the two chatbots do *not* share a
corpus.

    chatbot/index.html     -> app.js        -> /v1/conversations/{id}/messages
                                             -> store.retrieve()
                                             -> `documents` table
    chatbot/unguarded.html -> unguarded.js  -> /v1/unguarded/chat
                                             -> unguarded_store.retrieve()
                                             -> `unguarded_documents` table

The isolation is deliberate (poisoned lab documents must not contaminate the
real workspace), but it means seeding only `documents` leaves the unguarded
bot with an empty knowledge base. It then answers "I have no information
about that" and the comparison shows nothing -- which looks like the guard
doing its job and is in fact the demo being broken.

The two stores also have different visibility models, which needs different
handling on each side:

- `documents` is shared, so one copy with `scope="global"` is visible to
  everyone.
- `unguarded_documents` is filtered by `owner_user_id`, i.e. it is a
  **private per-user** store. A copy seeded by `superadmin` is invisible to
  `it.user1`, so the unguarded bot must be seeded *as the account that will
  run the demo*.

Both sides must retrieve the same text for the only remaining difference to
be the guards themselves.

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


def _remove_existing(store, unguarded_store, actor, filenames: set[str]) -> int:
    """Delete previously seeded copies from BOTH stores so re-running does
    not duplicate. Matching is by filename, which is enough here because the
    seeded names are distinctive."""
    removed = 0
    for document in store.accessible_documents(actor):
        if document["filename"] in filenames and store.delete_document(actor, document["id"]):
            removed += 1
    for document in unguarded_store.documents(actor):
        if document["filename"] in filenames and unguarded_store.delete_document(
            actor, document["id"]
        ):
            removed += 1
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the enterprise leak demo corpus.")
    parser.add_argument("--username", default="superadmin")
    parser.add_argument("--password", default="SuperAdmin#2026")
    parser.add_argument(
        "--demo-user", default="it.user1",
        help="Tai khoan se dung de demo; kho unguarded la kho RIENG cua tung nguoi dung",
    )
    parser.add_argument("--demo-password", default="ITUser1#2026")
    parser.add_argument(
        "--remove", action="store_true", help="Chi go bo tai lieu demo da nap, khong nap moi"
    )
    args = parser.parse_args()

    from app.workspace import store, unguarded_store  # noqa: PLC0415 - after sys.path setup

    store.initialize()
    unguarded_store.initialize()
    result = store.authenticate(args.username, args.password)
    if result is None:
        raise SystemExit(f"Khong dang nhap duoc: {args.username}")
    _token, actor = result
    if actor["role"] != "superadmin":
        raise SystemExit("Can quyen superadmin de nap tai lieu pham vi global")

    demo = store.authenticate(args.demo_user, args.demo_password)
    if demo is None:
        raise SystemExit(f"Khong dang nhap duoc tai khoan demo: {args.demo_user}")
    demo_actor = demo[1]

    records = _load_records()
    filenames = {record["filename"] for record in records}

    removed = _remove_existing(store, unguarded_store, actor, filenames)
    removed += _remove_existing(store, unguarded_store, demo_actor, filenames)
    if args.remove:
        print(f"Da go {removed} tai lieu demo khoi ca hai kho.")
        print(f"CSDL: {store.DB_PATH}")
        return 0

    seeded = []
    for record in records:
        payload = record["content"]
        encoded = payload.encode("utf-8")
        # Guarded knowledge base.
        row = store.add_document(
            actor,
            record["filename"],
            encoded,
            "global",
            "member",
            actor["department"],
            guard_decision="allow",
        )
        # Unguarded lab's separate, per-user knowledge base. Seeded as the
        # demo account, not as superadmin: `unguarded_store.retrieve` filters
        # on `owner_user_id`, so a superadmin-owned copy would be invisible
        # to the account actually running the demo.
        unguarded_store.add_document(
            demo_actor, record["filename"], payload, "text/markdown", len(encoded)
        )
        seeded.append((record["filename"], record.get("leak_kind", "-"), row["size_bytes"]))

    if removed:
        print(f"Da go {removed} ban cu truoc khi nap lai.")
    print(f"Da nap {len(seeded)} tai lieu vao CA HAI kho:\n")
    for filename, kind, size in seeded:
        print(f"  {filename:45s} {kind:20s} {size:6d} bytes")
    print(f"\n  documents            scope=global        -> chatbot co tuong (/)")
    print(f"  unguarded_documents  owner={args.demo_user:<12} -> chatbot khong tuong (unguarded.html)")
    print(f"\nDang nhap CA HAI chatbot bang '{args.demo_user}' thi moi thay cung du lieu.")
    print(f"\nCSDL: {store.DB_PATH}")
    print("Khoi dong lai backend neu no dang chay, roi thu lai DEMO_PROMPTS.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
