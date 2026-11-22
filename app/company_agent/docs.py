"""Keyword search over the furniture company documents with document ACL."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DOCS_ROOT = Path(__file__).resolve().parents[2] / "datasets" / "furniture" / "docs"
_WORD = re.compile(r"\w+", re.U)
MAX_DOC_CHARS = 1500


@dataclass(frozen=True)
class Doc:
    doc_id: str
    filename: str
    title: str
    owner_department: str
    classification: str
    audience_min_role: str
    paired_with: str | None
    body: str


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFD", text.casefold())
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn").replace("đ", "d")


def _parse(path: Path) -> Doc:
    raw = path.read_text(encoding="utf-8")
    _, fm, body = raw.split("---", 2)
    meta = {}
    for line in fm.strip().splitlines():
        k, _, v = line.partition(":")
        meta[k.strip()] = v.strip().strip('"')
    return Doc(
        doc_id=meta["document_id"], filename=path.name, title=meta.get("title", path.stem),
        owner_department=meta.get("owner_department", ""), classification=meta.get("classification", "internal"),
        audience_min_role=meta.get("audience_min_role", "member"), paired_with=meta.get("based_on_clean_doc"),
        body=body.strip(),
    )


@lru_cache(maxsize=2)
def corpus(kind: str) -> tuple[Doc, ...]:
    """'clean' = clean docs; 'poisoned' = clean docs with poisoned variants swapped in."""
    clean = {d.doc_id: d for d in (_parse(p) for p in sorted((DOCS_ROOT / "clean").glob("*.md")))}
    if kind != "poisoned":
        return tuple(clean.values())
    docs = dict(clean)
    for p in sorted((DOCS_ROOT / "poisoned").glob("*.md")):
        d = _parse(p)
        base = clean.get(d.paired_with or "")
        # The poisoned copy inherits the ACL of the document it impersonates.
        docs[d.doc_id] = Doc(d.doc_id, d.filename, d.title,
                             base.owner_department if base else "", base.classification if base else "internal",
                             base.audience_min_role if base else "member", d.paired_with, d.body)
        if d.paired_with in docs and d.paired_with != d.doc_id:
            docs.pop(d.paired_with, None)
    return tuple(docs.values())


def can_read(doc: Doc, department: str, role: str) -> bool:
    if doc.classification in {"public", "internal"}:
        return True
    same_dept = doc.owner_department.casefold() == department.casefold()
    finance = department.casefold() == "ketoan"
    if doc.audience_min_role == "leader" and role.casefold() != "leader" and not finance:
        return False
    return same_dept or finance


def search(query: str, *, kind: str, department: str, role: str | None, k: int = 3,
           enforce_acl: bool = True) -> list[Doc]:
    terms = {t for t in _WORD.findall(_fold(query)) if len(t) > 1}
    scored = []
    for doc in corpus(kind):
        if enforce_acl and not can_read(doc, department, role or "member"):
            continue
        hay = _fold(doc.title + " " + doc.body)
        score = sum(hay.count(t) for t in terms) + 3 * sum(t in _fold(doc.title) for t in terms)
        if score:
            scored.append((score, doc.doc_id, doc))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [d for _, _, d in scored[:k]]
