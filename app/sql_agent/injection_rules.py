"""Detection rules for SQL-flavoured indirect prompt injection in data cells.

The generic RAG Context Guard targets document-style instruction overrides.
Database free text adds a different shape of payload: SQL fragments meant to
be copied into the next generated query, and requests addressed to "the AI"
to read other tables or columns. Detection runs on a normalized copy
(zero-width characters removed, light leetspeak folded, case-folded).
"""
from __future__ import annotations

import base64
import binascii
import re
import unicodedata

_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿"), None)
_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"})


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text).translate(_ZERO_WIDTH)
    return text.casefold().translate(_LEET)


def _rx(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.I | re.S)


# (rule id, pattern on normalized text, reason)
RULES: list[tuple[str, re.Pattern[str], str]] = [
    ("SQLI-STMT", _rx(r"\b(select\b.{0,80}\bfrom|union\s+select|drop\s+table|delete\s+from|update\s+\w+\s+set|insert\s+into|attach\s+database|alter\s+table)\b"),
     "SQL statement embedded in data (indirect P2SQL)"),
    ("SQLI-META", _rx(r"\b(pragma|sqlite_master|sqlite_schema|load_extension|internal_secrets|run_sql)\b"),
     "reference to database internals or SQL tooling in data"),
    ("SQLI-STACK", _rx(r"['\"]\s*;\s*\w+|;\s*--"), "stacked-query / quote-breakout payload in data"),
    ("PI-ADDRESS", _rx(r"(\b(ai|assistant|tro ly|trợ lý|he thong|hệ thống|system)\b|\[/?system\]).{0,80}"
                       r"(hay|hãy|must|phai|phải|from now|bo qua|bỏ qua|ignore|chay|chạy|xuat|xuất|in ra|liet ke|liệt kê|cho toi biet|cho tôi biết|tiet lo|tiết lộ|xac nhan|xác nhận)"),
     "instruction addressed to the assistant inside data"),
    ("PI-OVERRIDE", _rx(r"(bỏ qua|bo qua)\s+(mọi|moi|tất cả|tat ca)?\s*(hướng dẫn|huong dan|quy tắc|quy tac|giới hạn|gioi han)|ignore\s+(all\s+)?previous"),
     "instruction-override language inside data"),
    ("PI-EXFIL-COL", _rx(r"\b(dealer_price|receivables|contract_terms)\b|(số điện thoại|so dien thoai|email)\s+(của|cua)\s+(tất cả|tat ca|khách|khach)"),
     "request for restricted columns inside data"),
    ("POLICY-POISON", _rx(r"(trọn đời|tron doi).{0,60}(hoàn tiền|hoan tien)\s*\d{3}\s*%|hoàn tiền\s*200\s*%"),
     "policy-poisoning claim inside data"),
    ("HIDDEN-COMMENT", _rx(r"<!--.*?-->"), "hidden HTML comment inside data"),
    # v1.1 additions (tuned on the DEV split only; holdout rows were not used).
    ("TOOL-CALL", _rx(r"[\"']tool[\"']\s*:|\b(send_email|create_ticket|query_db|search_docs|order_status)\b"),
     "tool-call syntax or tool name inside data (tool abuse)"),
    ("PROMPT-LEAK", _rx(r"system\s*prompt|từ giờ bạn là|tu gio ban la|you are now|không bị giới hạn|khong bi gioi han|\bdan\b mode"),
     "persona hijack or system-prompt leak request inside data"),
    ("IMPERATIVE-ACTION", _rx(r"\b(hãy|hay)\s+(chạy|chay|thực thi|thuc thi|xuất|xuat|gửi|gui|in ra|xoá|xoa|xóa)\b"),
     "imperative action verb inside data"),
    ("PAYMENT-REDIRECT", _rx(r"(chuyển hướng|chuyen huong|đổi sang|doi sang|tài khoản mới|tai khoan moi|đã đổi|da doi).{0,60}(stk|tài khoản|tai khoan|thanh toán|thanh toan|chuyển khoản|chuyen khoan)"),
     "payment-account change claim inside data (fraud)"),
    ("RESOURCE-EXHAUSTION", _rx(r"lặp lại.{0,30}\d{3,}\s*lần|lap lai.{0,30}\d{3,}\s*lan|repeat.{0,30}\d{3,}\s*times|(mọi|moi|tất cả|tat ca) (các )?bảng|all tables"),
     "resource-exhaustion request inside data"),
    ("EXTERNAL-LINK", _rx(r"https?://(?![\w.-]*example\.test\b)[\w.-]+"),
     "link to a non-company domain inside data (exfiltration/phishing)"),
    ("MD-IMAGE", _rx(r"!\[[^\]]*\]\(|<img\b"), "markdown/HTML image inside data (zero-click exfiltration)"),
]

_B64 = re.compile(r"[A-Za-z0-9+/]{24,}={0,2}")


def _decoded_blobs(text: str) -> list[str]:
    out = []
    for blob in _B64.findall(text):
        try:
            decoded = base64.b64decode(blob + "=" * (-len(blob) % 4), validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError, ValueError):
            continue
        if decoded.isprintable() or any(ch.isalpha() for ch in decoded):
            out.append(decoded)
    return out


def _match_plain(text: str) -> list[tuple[str, str]]:
    norm = normalize(text)
    return [(rid, reason) for rid, pattern, reason in RULES if pattern.search(norm) or pattern.search(text)]


def match(text: str) -> list[tuple[str, str]]:
    hits = _match_plain(text)
    for decoded in _decoded_blobs(text):
        inner = _match_plain(decoded)
        if inner:
            hits.append(("B64-PAYLOAD", "base64-encoded instruction inside data"))
            hits.extend(inner)
    seen, out = set(), []
    for hit in hits:
        if hit[0] not in seen:
            seen.add(hit[0])
            out.append(hit)
    return out
