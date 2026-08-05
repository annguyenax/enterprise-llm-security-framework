"""Ingest datasets/enterprise-kb/ into the enterprise ACL retriever.

Reads the corpus produced by `scripts/build_enterprise_kb.py`, resolves each
document's trust through the server-controlled source policy, projects its
operator-declared metadata into ACL facts, chunks it, and indexes it.

Run:
    .venv\\Scripts\\python.exe scripts/build_enterprise_kb.py
    .venv\\Scripts\\python.exe scripts/validate_enterprise_kb.py
    .venv\\Scripts\\python.exe scripts/ingest_enterprise_kb.py

Two properties this script exists to preserve:

- **Trust is never read from the corpus.** `source_key` is the only
  trust-relevant value the artifact supplies, and it is passed to
  `resolve_source_policy`, which maps it to server-defined
  `trust_level`/`classification`/`source_type`. The corpus has no field for
  those, and the validator rejects any row that adds one.

- **`allow_internal=True` is used deliberately and only here.** The
  enterprise KB is a curated internal corpus loaded by an operator at the
  console, not content arriving from an unauthenticated HTTP caller, so it
  is exactly the "internal tooling" case `resolve_source_policy` documents.
  The public ingestion route never passes that flag and therefore still
  cannot select an elevated trust tier.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.config import settings  # noqa: E402
from app.core.source_policy import resolve_source_policy  # noqa: E402
from app.retrieval.acl import EnterpriseDocMetadata, acl_metadata  # noqa: E402
from app.retrieval.enterprise_acl_bm25 import (  # noqa: E402
    EnterpriseAclBm25Config,
    EnterpriseAclBm25Retriever,
)
from app.retrieval.models import ChunkRecord, DocumentRecord  # noqa: E402
from app.services.chunking import ChunkingConfig, chunk_text  # noqa: E402

CORPUS_PATH = REPO_ROOT / "datasets" / "enterprise-kb" / "corpus" / "documents.jsonl"


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_rows() -> list[dict]:
    if not CORPUS_PATH.is_file():
        raise SystemExit(
            "datasets/enterprise-kb/corpus/documents.jsonl khong ton tai. "
            "Chay scripts/build_enterprise_kb.py truoc."
        )
    rows = []
    for line in CORPUS_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _prepare(rows: list[dict]) -> list[tuple[DocumentRecord, list[ChunkRecord]]]:
    stamp = datetime.now(timezone.utc).isoformat()
    prepared: list[tuple[DocumentRecord, list[ChunkRecord]]] = []

    for row in rows:
        # Validated here too, not only by the validator script: this is the
        # boundary where untrusted-shaped data becomes typed records, and it
        # must not depend on someone having remembered to run the validator.
        metadata = EnterpriseDocMetadata(
            source_key=row["source_key"],
            sensitivity=row["sensitivity"],
            access_roles=frozenset(row["access_roles"]),
            access_departments=frozenset(row["access_departments"]),
            owner_department=row["owner_department"],
            valid_from=row["valid_from"],
            valid_to=row["valid_to"],
        )
        policy = resolve_source_policy(row["source_key"], allow_internal=True)

        document_metadata: dict[str, object] = {
            "owner_department": metadata.owner_department,
            "sensitivity": metadata.sensitivity.value,
            "language": row["language"],
        }
        document_metadata.update(acl_metadata(metadata.to_facts()))

        text = row["content"]
        document_id = row["document_id"]
        document = DocumentRecord(
            document_id=document_id,
            external_id=row["external_id"],
            source_key=policy.source_key,
            source_id=policy.policy_id,
            source_type=policy.source_type,
            classification=policy.classification,
            trust_level=policy.trust_level,
            title=row["title"],
            content_hash=_content_hash(text),
            created_at=stamp,
            updated_at=stamp,
            metadata=document_metadata,
        )

        chunking_config = ChunkingConfig(
            max_chunk_chars=settings.retrieval_chunk_max_chars,
            overlap_chars=settings.retrieval_chunk_overlap_chars,
            max_document_chars=settings.retrieval_max_document_chars,
        )
        chunks = [
            ChunkRecord(
                chunk_id=f"{document_id}-c{piece.chunk_index:04d}",
                document_id=document_id,
                chunk_index=piece.chunk_index,
                text=piece.text,
                content_hash=_content_hash(piece.text),
                metadata={"title": row["title"]},
            )
            for piece in chunk_text(text, chunking_config)
        ]
        prepared.append((document, chunks))

    return prepared


def ingest(db_path: str | None = None) -> tuple[int, int]:
    """Index the whole corpus. Returns `(documents, chunks)`."""
    retriever = EnterpriseAclBm25Retriever(
        EnterpriseAclBm25Config(
            db_path=db_path or settings.enterprise_kb_db_path,
            busy_timeout_ms=settings.retrieval_busy_timeout_ms,
            max_query_chars=settings.retrieval_max_query_chars,
            max_query_terms=settings.retrieval_max_query_terms,
            max_top_k=settings.retrieval_max_top_k,
        )
    )
    retriever.initialize()
    prepared = _prepare(_load_rows())
    retriever.upsert_documents(prepared)
    return len(prepared), sum(len(chunks) for _doc, chunks in prepared)


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest the enterprise knowledge base.")
    parser.add_argument(
        "--db-path",
        default=None,
        help="Ghi de duong dan CSDL (mac dinh: settings.enterprise_kb_db_path).",
    )
    args = parser.parse_args()

    documents, chunks = ingest(args.db_path)
    print(f"Da nap {documents} tai lieu, {chunks} chunk.")
    print(f"CSDL: {args.db_path or settings.enterprise_kb_db_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
