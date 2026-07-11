"""Deterministic, paragraph-aware chunking for Phase 12B ingestion.

Distinct from `app/services/dataset_loader.py`'s v1 fixed-size
character-window chunker, which is kept unchanged and still used only by
the v1 benchmark loader. This is the v2 chunker used by the new ingestion
pipeline (`app/services/ingestion.py`), per
`docs/modernization-v2-architecture.md` §2's `app/services/chunking.py`
module entry.

This module must never read or depend on any benchmark-only field such as
`is_poisoned` -- it only ever sees plain text, by construction (there is no
`Document` type with such a field anywhere near this module).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_BLANK_LINE_PATTERN = re.compile(r"\n\s*\n+")


class EmptyDocumentError(ValueError):
    """Raised when the input text is empty or whitespace-only."""


class DocumentTooLongError(ValueError):
    """Raised when the input text exceeds `ChunkingConfig.max_document_chars`."""


@dataclass(frozen=True)
class ChunkingConfig:
    max_chunk_chars: int = 800
    overlap_chars: int = 100
    max_document_chars: int = 200_000

    def __post_init__(self) -> None:
        if self.max_chunk_chars <= 0:
            raise ValueError("max_chunk_chars must be positive.")
        if self.overlap_chars < 0 or self.overlap_chars >= self.max_chunk_chars:
            raise ValueError("overlap_chars must be >= 0 and < max_chunk_chars.")
        if self.max_document_chars <= 0:
            raise ValueError("max_document_chars must be positive.")


@dataclass(frozen=True)
class TextChunk:
    chunk_index: int
    text: str


def normalize_line_endings(text: str) -> str:
    """Normalize CRLF/CR to LF so paragraph splitting is platform-independent."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def split_paragraphs(text: str) -> list[str]:
    """Split on one-or-more blank lines; strip each paragraph; drop empties."""
    normalized = normalize_line_endings(text)
    return [p.strip() for p in _BLANK_LINE_PATTERN.split(normalized) if p.strip()]


def _hard_split(paragraph: str, config: ChunkingConfig) -> list[str]:
    """Deterministically slice a single oversized paragraph into
    max_chunk_chars windows with the configured overlap, mirroring
    app/services/dataset_loader.py's v1 character-window approach -- used
    only as a fallback for the rare paragraph that alone exceeds the
    configured chunk size, never for normal-sized paragraphs."""
    step = config.max_chunk_chars - config.overlap_chars
    pieces: list[str] = []
    start = 0
    while start < len(paragraph):
        piece = paragraph[start : start + config.max_chunk_chars].strip()
        if piece:
            pieces.append(piece)
        start += step
    return pieces


def _pack_paragraphs(paragraphs: list[str], config: ChunkingConfig) -> list[str]:
    """Greedily pack paragraphs into windows of at most max_chunk_chars,
    carrying the trailing `overlap_chars` of one chunk into the start of
    the next chunk when a new paragraph forces a chunk boundary.

    Deterministic edge case: if including the configured overlap tail
    would itself push a new chunk over max_chunk_chars (tail + next
    paragraph > max_chunk_chars, even though the paragraph alone fits),
    the overlap is dropped for that boundary rather than exceeding the
    configured maximum -- the max-chunk-size invariant always wins over
    the overlap request. This is deliberate, deterministic behavior, not
    an error.
    """
    chunks: list[str] = []
    buffer = ""

    for paragraph in paragraphs:
        if len(paragraph) > config.max_chunk_chars:
            if buffer:
                chunks.append(buffer)
                buffer = ""
            chunks.extend(_hard_split(paragraph, config))
            continue

        candidate = f"{buffer}\n\n{paragraph}" if buffer else paragraph
        if len(candidate) <= config.max_chunk_chars:
            buffer = candidate
            continue

        chunks.append(buffer)
        tail = buffer[-config.overlap_chars :] if config.overlap_chars else ""
        seeded = f"{tail}\n\n{paragraph}" if tail else paragraph
        buffer = seeded if len(seeded) <= config.max_chunk_chars else paragraph

    if buffer:
        chunks.append(buffer)
    return chunks


def chunk_text(text: str, config: ChunkingConfig | None = None) -> list[TextChunk]:
    """Split `text` into deterministic, paragraph-aware, non-empty chunks.

    Raises `EmptyDocumentError` for empty/whitespace-only input and
    `DocumentTooLongError` if the (line-ending-normalized) text exceeds
    `config.max_document_chars`. Never returns an empty chunk list for
    valid, non-empty input, and never returns an empty-string chunk.
    """
    active_config = config or ChunkingConfig()
    normalized = normalize_line_endings(text)

    if not normalized.strip():
        raise EmptyDocumentError("Document text is empty or whitespace-only.")
    if len(normalized) > active_config.max_document_chars:
        raise DocumentTooLongError(
            f"Document length {len(normalized)} exceeds maximum "
            f"{active_config.max_document_chars} characters."
        )

    paragraphs = split_paragraphs(normalized)
    raw_chunks = _pack_paragraphs(paragraphs, active_config)
    return [
        TextChunk(chunk_index=index, text=chunk)
        for index, chunk in enumerate(c for c in raw_chunks if c.strip())
    ]
