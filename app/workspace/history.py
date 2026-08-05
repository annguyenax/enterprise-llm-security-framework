"""Replay-safety screening for stored conversation turns.

`POST /v1/conversations/{id}/messages` (`app/workspace/routes.py`) replays
the most recent turns of a conversation into the provider on every request,
because that is how the chat feature keeps context. Those turns are stored
verbatim in SQLite and were previously handed straight back to the provider
via `LLMProviderRequest.metadata["history"]` -- which meant they re-entered
the model's context **without passing any guard a second time**.

Two distinct holes existed, and both are closed here:

1. **Blocked prompts were still replayed.** `routes.post_message` persists
   the user's message *before* `run_chat` runs, so a prompt the Input Guard
   went on to BLOCK was written to the `messages` table anyway. On the very
   next turn it was read back and replayed into the provider, at which
   point no Input Guard ever looked at it again -- the block was effectively
   a one-turn delay rather than a refusal. `screen_history` drops any turn
   whose *stored* guard decision was itself blocking.

2. **Stored turns were never re-inspected.** Even an originally-allowed turn
   is attacker-influenced text re-entering the context later, which is the
   same threat shape as indirect injection through retrieved content. So
   every replayed turn is re-screened through the existing RAG Context
   Guard, and is dropped or sanitized on exactly the decisions that guard
   already defines. Nothing new is invented here: the guard, its rules, and
   its severity ordering are the ones the project already audits.

Fail-closed throughout -- a malformed row, an unexpected role, an
unrecognized stored decision, or a guard exception all drop the turn rather
than replay it. Dropping a turn costs conversational context; replaying an
unscreened one costs the security property this gateway exists to provide.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.core.decisions import Decision
from app.guards.rag_guard import evaluate_rag_context
from app.schemas.requests import RAGContextChunk

# Kept equal to the window `routes.post_message` already read (`[-12:]`) and
# to the bound `app/services/providers/ollama.py` independently applies, so
# this module changes *what* may be replayed, never *how much*.
MAX_REPLAYED_TURNS = 12

# Matches the per-message ceiling enforced at the API boundary
# (`MessageBody.content`, max_length=4000) and by the Ollama provider's own
# `content[:4000]` bound.
MAX_TURN_CHARS = 4000

_REPLAYABLE_ROLES = frozenset({"user", "assistant"})

# Stored `messages.decision` values that must never be replayed. These are
# the same two decisions `app/services/gateway.py` treats as stopping the
# pipeline (`_STOPPING_DECISIONS`), compared as their persisted string form.
_BLOCKING_STORED_DECISIONS = frozenset({Decision.BLOCK.value, Decision.HUMAN_REVIEW.value})

_STOPPING_DECISIONS = (Decision.BLOCK, Decision.HUMAN_REVIEW)

_HISTORY_CHUNK_DOC_ID = "conversation-history"


@dataclass(frozen=True)
class HistoryScreening:
    """Outcome of screening one conversation's replayable turns.

    `turns` is the only value that may reach the provider. `dropped_count`
    and `sanitized_count` are safe aggregate signals: they are counts, never
    content, so they are suitable for the audit log.
    """

    turns: tuple[dict[str, str], ...]
    dropped_count: int
    sanitized_count: int


def _stored_decision_blocks(value: Any) -> bool:
    """Whether a persisted `messages.decision` forbids replay.

    Type-first per this project's validator convention: `isinstance` runs
    before any set membership, since a non-string value would otherwise be
    compared against a set of strings (and an unhashable one would raise).
    `None` is the normal "no decision recorded" case and does not block on
    its own -- those turns still go through full re-screening below. Any
    other unrecognized shape fails closed.
    """
    if value is None:
        return False
    if not isinstance(value, str):
        return True
    return value.strip().lower() in _BLOCKING_STORED_DECISIONS


def _rescreen(text: str) -> tuple[str | None, bool]:
    """Re-run the RAG Context Guard over one stored turn.

    Returns `(safe_text, was_sanitized)`, where a `safe_text` of `None`
    means the turn must not be replayed at all. A guard exception fails
    closed to `None`, mirroring `app/services/rag_query.py`'s
    `_safe_rag_context_decision`.
    """
    try:
        result = evaluate_rag_context(
            [RAGContextChunk(doc_id=_HISTORY_CHUNK_DOC_ID, text=text, metadata={})]
        )
    except Exception:  # noqa: BLE001 -- deliberate fail-closed safety net
        return None, False

    if result.decision in _STOPPING_DECISIONS:
        return None, False

    if result.decision == Decision.SANITIZE:
        if not result.sanitized_chunks:
            return None, False
        cleaned = result.sanitized_chunks[0].text
        # Sanitization removes whole lines; a turn reduced to nothing carries
        # no context worth replaying and is dropped rather than sent empty.
        if not cleaned.strip():
            return None, False
        return cleaned, True

    return text, False


def screen_history(
    messages: Any, *, max_turns: int = MAX_REPLAYED_TURNS
) -> HistoryScreening:
    """Return the replay-safe subset of `messages`, newest window last.

    `messages` is expected to be the list of dicts `app/workspace/store.py`'s
    `messages()` returns, but is validated defensively -- this function is a
    security boundary, not an internal helper, and must behave predictably
    on any input shape.
    """
    if not isinstance(max_turns, int) or isinstance(max_turns, bool) or max_turns <= 0:
        return HistoryScreening(turns=(), dropped_count=0, sanitized_count=0)
    if not isinstance(messages, Sequence) or isinstance(messages, (str, bytes)):
        return HistoryScreening(turns=(), dropped_count=0, sanitized_count=0)

    window = list(messages)[-max_turns:]
    kept: list[dict[str, str]] = []
    dropped = 0
    sanitized = 0

    for item in window:
        if not isinstance(item, Mapping):
            dropped += 1
            continue

        role = item.get("role")
        if not isinstance(role, str) or role not in _REPLAYABLE_ROLES:
            dropped += 1
            continue

        content = item.get("content")
        if not isinstance(content, str) or not content.strip():
            dropped += 1
            continue

        if _stored_decision_blocks(item.get("decision")):
            dropped += 1
            continue

        safe_text, was_sanitized = _rescreen(content[:MAX_TURN_CHARS])
        if safe_text is None:
            dropped += 1
            continue

        if was_sanitized:
            sanitized += 1
        kept.append({"role": role, "content": safe_text})

    return HistoryScreening(
        turns=tuple(kept), dropped_count=dropped, sanitized_count=sanitized
    )
