"""Dataset ingestion / loader for the synthetic RAG benchmark (Phase 5).

Reads the markdown documents already committed under `datasets/clean/` and
`datasets/poisoned/` (Phase 3 synthetic benchmark - see
docs/dataset/dataset-methodology.md) and turns them into `Document` /
`DocumentChunk` objects that a (not-yet-built) RAG pipeline could hand to
the RAG Guard. This is a lab-scale simulation only:

- No vector database, no embeddings, no similarity search (Phase 6+).
- Chunking is a simple deterministic fixed-size character window, not a
  real chunking strategy (sentence/token aware, etc).
- Front-matter parsing is a minimal hand-rolled `key: value` reader, not a
  real YAML parser - the dataset only ever uses flat `key: value` pairs
  (see any file under datasets/clean or datasets/poisoned), so this is
  sufficient without adding a PyYAML dependency (AGENT_RULES.md rule 11).

Each dataset markdown file mixes two things in one document: the actual
"content" a RAG pipeline would ingest, and this project's own evaluator
commentary (attack type, expected risk, explanation). `_extract_content`
pulls out only the former:
  - Clean docs: the section whose heading starts with "Policy" (handles
    the one heading-text variant in `product-faq.md`, "Policy / Product
    Summary", without needing to touch the dataset file).
  - Poisoned docs: the fenced code block inside the "Poisoned Content"
    section - this is the text a real ingestion pipeline would have added
    to the vector store; the surrounding prose is evaluator commentary.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

CLEAN_DIR = Path("datasets/clean")
POISONED_DIR = Path("datasets/poisoned")

DEFAULT_CHUNK_SIZE = 400  # characters
DEFAULT_CHUNK_OVERLAP = 50  # characters

_FRONT_MATTER_PATTERN = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
_HEADING_PATTERN = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_CODE_FENCE_PATTERN = re.compile(r"```(?:\w+)?\r?\n(.*?)```", re.DOTALL)


@dataclass(frozen=True)
class Document:
    doc_id: str
    title: str
    source_path: str
    is_poisoned: bool
    content: str
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class DocumentChunk:
    doc_id: str
    source_path: str
    chunk_index: int
    text: str
    is_poisoned: bool


def _parse_front_matter(raw_text: str) -> tuple[dict[str, str], str]:
    """Parse a simple `---\\nkey: value\\n---` front-matter block.

    Not a general YAML parser: values are read as plain strings, with
    surrounding double quotes stripped if present (e.g. `version: "2.1"`).
    Lines that are not `key: value` are ignored. Returns (metadata, body)
    where body is everything after the closing `---`.
    """
    match = _FRONT_MATTER_PATTERN.match(raw_text)
    if not match:
        return {}, raw_text

    metadata: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key:
            metadata[key] = value

    body = raw_text[match.end():]
    return metadata, body


def _extract_section(body: str, heading_prefix: str) -> str | None:
    """Return the text between a `## <heading_prefix>...` heading and the
    next `## ` heading (or end of document), or None if not found."""
    headings = list(_HEADING_PATTERN.finditer(body))
    for index, heading_match in enumerate(headings):
        if heading_match.group(1).strip().startswith(heading_prefix):
            start = heading_match.end()
            end = headings[index + 1].start() if index + 1 < len(headings) else len(body)
            return body[start:end].strip()
    return None


def _extract_content(body: str, is_poisoned: bool) -> str:
    """Extract the "real" ingestible document content, separate from this
    project's own evaluator commentary embedded in the same file."""
    if is_poisoned:
        section = _extract_section(body, "Poisoned Content")
        if section is not None:
            fence_match = _CODE_FENCE_PATTERN.search(section)
            if fence_match:
                return fence_match.group(1).strip()
            return section
        return body.strip()

    section = _extract_section(body, "Policy")
    if section is not None:
        return section
    return body.strip()


def _load_document(path: Path, is_poisoned: bool) -> Document:
    raw_text = path.read_text(encoding="utf-8")
    metadata, body = _parse_front_matter(raw_text)
    content = _extract_content(body, is_poisoned)

    doc_id = metadata.get("document_id", path.stem)
    title = metadata.get("title", path.stem)

    return Document(
        doc_id=doc_id,
        title=title,
        source_path=str(path),
        is_poisoned=is_poisoned,
        content=content,
        metadata=metadata,
    )


def load_all_documents(
    clean_dir: Path = CLEAN_DIR, poisoned_dir: Path = POISONED_DIR
) -> list[Document]:
    """Load every markdown document from the clean and poisoned dataset
    directories, sorted by source path for deterministic ordering."""
    documents: list[Document] = []
    for path in sorted(Path(clean_dir).glob("*.md")):
        documents.append(_load_document(path, is_poisoned=False))
    for path in sorted(Path(poisoned_dir).glob("*.md")):
        documents.append(_load_document(path, is_poisoned=True))
    return documents


def chunk_document(
    document: Document,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[DocumentChunk]:
    """Split a document's content into deterministic, fixed-size,
    overlapping character windows. Not a real (sentence/token-aware)
    chunking strategy - a simple, explainable stand-in for one."""
    text = document.content
    if not text:
        return []

    step = chunk_size - overlap
    chunks: list[DocumentChunk] = []
    start = 0
    index = 0
    while start < len(text):
        chunk_text = text[start : start + chunk_size].strip()
        if chunk_text:
            chunks.append(
                DocumentChunk(
                    doc_id=document.doc_id,
                    source_path=document.source_path,
                    chunk_index=index,
                    text=chunk_text,
                    is_poisoned=document.is_poisoned,
                )
            )
            index += 1
        start += step

    return chunks


def load_all_chunks(
    clean_dir: Path = CLEAN_DIR,
    poisoned_dir: Path = POISONED_DIR,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[DocumentChunk]:
    """Convenience: load every document and chunk it in one call."""
    chunks: list[DocumentChunk] = []
    for document in load_all_documents(clean_dir, poisoned_dir):
        chunks.extend(chunk_document(document, chunk_size=chunk_size, overlap=overlap))
    return chunks
