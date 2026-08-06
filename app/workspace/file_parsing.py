from __future__ import annotations

import csv
import json
import re
from html import unescape
from io import BytesIO
from pathlib import Path

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover - optional dependency
    PdfReader = None

SUPPORTED_TEXT_SUFFIXES = {
    ".txt",
    ".md",
    ".csv",
    ".json",
    ".jsonl",
    ".html",
    ".htm",
    ".pdf",
    ".py",
    ".js",
    ".ts",
    ".sh",
    ".ps1",
    ".bat",
    ".cmd",
}

CODE_MIME_TYPES = {
    ".py": "text/x-python",
    ".js": "text/javascript",
    ".ts": "text/typescript",
    ".sh": "text/x-shellscript",
    ".ps1": "text/x-powershell",
    ".bat": "text/x-batch",
    ".cmd": "text/x-batch",
}


class FileParseError(ValueError):
    """Raised when a file cannot be parsed into text for RAG ingestion."""


def extract_text_from_bytes(filename: str, content: bytes) -> tuple[str, str | None]:
    """Extract text from uploaded bytes.

    Returns `(text, mime_type)` where mime_type is a simple hint for storage.
    For unsupported binary formats the function raises FileParseError.
    """
    suffix = Path(filename).suffix.lower()

    if suffix in {".txt", ".md"} | CODE_MIME_TYPES.keys():
        try:
            return content.decode("utf-8"), CODE_MIME_TYPES.get(suffix, "text/plain")
        except UnicodeDecodeError as exc:
            raise FileParseError("Tệp phải dùng UTF-8") from exc

    if suffix == ".csv":
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise FileParseError("Tệp CSV phải dùng UTF-8") from exc
        rows = list(csv.reader(text.splitlines()))
        if not rows:
            return "", "text/csv"
        return "\n".join(" | ".join(row) for row in rows if any(cell.strip() for cell in row)), "text/csv"

    if suffix in {".json", ".jsonl"}:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise FileParseError("Tệp JSON phải dùng UTF-8") from exc

        if suffix == ".jsonl":
            items = []
            for line_number, line in enumerate(text.splitlines(), start=1):
                if not line.strip():
                    continue
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise FileParseError(
                        f"Tệp JSONL không hợp lệ ở dòng {line_number}"
                    ) from exc
            return "\n".join(
                json.dumps(item, ensure_ascii=False) for item in items
            ), "application/x-ndjson"

        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise FileParseError("Tệp JSON không hợp lệ") from exc
        if isinstance(payload, dict):
            return json.dumps(payload, ensure_ascii=False, indent=2), "application/json"
        if isinstance(payload, list):
            return "\n".join(json.dumps(item, ensure_ascii=False) for item in payload), "application/json"
        return json.dumps(payload, ensure_ascii=False), "application/json"

    if suffix in {".html", ".htm"}:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise FileParseError("Tệp HTML phải dùng UTF-8") from exc
        text = re.sub(r"<script.*?</script>", " ", text, flags=re.I | re.S)
        text = re.sub(r"<style.*?</style>", " ", text, flags=re.I | re.S)
        text = re.sub(r"<[^>]+>", " ", text)
        text = unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        return text, "text/html"

    if suffix == ".pdf":
        if PdfReader is None:
            raise FileParseError("PDF parsing chưa được cài sẵn trong môi trường hiện tại")
        try:
            reader = PdfReader(BytesIO(content))
        except Exception as exc:
            raise FileParseError("Không đọc được nội dung PDF") from exc
        pages: list[str] = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            pages.append(page_text)
        return "\n\n".join(pages).strip(), "application/pdf"

    raise FileParseError("Loại tệp này chưa được hỗ trợ cho RAG")
