from __future__ import annotations

from dataclasses import dataclass, field

from app.core.decisions import Decision


@dataclass(frozen=True)
class SqlActor:
    department: str
    role: str


@dataclass(frozen=True)
class SqlGuardResult:
    decision: Decision
    reasons: list[str] = field(default_factory=list)
    normalized_sql: str | None = None
    tables_read: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SqlExecution:
    columns: list[str]
    rows: list[list]
    truncated: bool = False
    statements_executed: int = 1
    database_modified: bool = False
