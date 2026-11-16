"""Guard query RESULTS before they go back to the LLM (indirect P2SQL defense).

Free-text cells (order notes, product reviews) are attacker-controllable
data. They are run through the existing RAG Context Guard as if they were
retrieved chunks, through SQL-specific injection rules (injection_rules.py),
and through DLP redaction, before the second model call.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import settings
from app.core.decisions import Decision, most_severe
from app.guards.dlp_guard import scan_and_redact
from app.guards.rag_guard import evaluate_rag_context
from app.schemas.requests import RAGContextChunk
from app.sql_agent.injection_rules import match as match_sql_injection
from app.sql_agent.models import SqlExecution

WITHHELD = "[nội dung bị giữ lại bởi Result Guard]"


@dataclass
class ResultGuardOutcome:
    decision: Decision
    rows: list[list]
    reasons: list[str] = field(default_factory=list)
    cells_sanitized: int = 0


def guard_rows(execution: SqlExecution) -> ResultGuardOutcome:
    decisions = [Decision.ALLOW]
    reasons: list[str] = []
    changed = 0
    out_rows: list[list] = []
    for r_idx, row in enumerate(execution.rows):
        new_row = []
        for c_idx, cell in enumerate(row):
            if not isinstance(cell, str) or not cell.strip():
                new_row.append(cell)
                continue
            col = execution.columns[c_idx] if c_idx < len(execution.columns) else str(c_idx)
            verdict = evaluate_rag_context(
                [RAGContextChunk(doc_id=f"row{r_idx}.{col}", text=cell, metadata={"filename": f"sql:{col}"})]
            )
            value = cell
            if verdict.decision in {Decision.BLOCK, Decision.HUMAN_REVIEW}:
                value = WITHHELD
            elif verdict.decision == Decision.SANITIZE and verdict.sanitized_chunks:
                value = verdict.sanitized_chunks[0].text
            if verdict.decision not in {Decision.ALLOW, Decision.LOG_ONLY}:
                decisions.append(Decision.SANITIZE)
                reasons.extend(f"{col}: {reason}" for reason in verdict.reasons)
            sql_hits = match_sql_injection(cell)
            if sql_hits:
                # The whole cell is attacker-controlled text; withhold it rather
                # than try to cut the payload out.
                value = WITHHELD
                decisions.append(Decision.SANITIZE)
                reasons.extend(f"{col}: {reason}" for _rid, reason in sql_hits)
            dlp = scan_and_redact(value, max_chars=settings.dlp_max_inspect_chars)
            if dlp.redaction_count:
                decisions.append(Decision.SANITIZE)
                reasons.append(f"{col}: {dlp.redaction_count} sensitive value(s) redacted")
                value = dlp.redacted_text
            if value != cell:
                changed += 1
            new_row.append(value)
        out_rows.append(new_row)
    return ResultGuardOutcome(
        decision=most_severe(decisions),
        rows=out_rows,
        reasons=sorted(set(reasons)),
        cells_sanitized=changed,
    )
