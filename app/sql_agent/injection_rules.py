"""Detection rules for SQL-flavoured indirect prompt injection in data cells.

The generic RAG Context Guard targets document-style instruction overrides.
Database free text adds a different shape of payload: SQL fragments meant to
be copied into the next generated query, and requests addressed to "the AI"
to read other tables or columns. Detection runs on a normalized copy
(zero-width characters removed, light leetspeak folded, case-folded).
"""
from __future__ import annotations

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
]


def match(text: str) -> list[tuple[str, str]]:
    norm = normalize(text)
    return [(rid, reason) for rid, pattern, reason in RULES if pattern.search(norm) or pattern.search(text)]
