"""Gateway orchestration: Input Guard -> RAG Guard -> LLM Provider -> Output
Guard -> audit log.

No real external LLM is called in this phase. Real provider integration is a
later, explicitly-approved phase (see TASK_BOARD.md and AGENT_RULES.md
rule 4 - no paid API calls without approval). Real RAG retrieval (vector
database, embeddings) is also not implemented yet (Phase 6+) - callers of
this gateway may optionally supply `context_chunks` directly (as if they
had already been retrieved elsewhere), and the RAG Guard (Phase 5)
evaluates them before the mock LLM stage.

Final-decision logic (Phase 4.1 hardening, extended in Phase 5):
deterministic severity order
    block > human_review > sanitize > log_only > allow
implemented via app.core.decisions.most_severe(). BLOCK and HUMAN_REVIEW on
the input side, or on the RAG Guard side, all stop the pipeline before any
(mock) LLM call, matching redteam/expected-behaviors.yaml's own definition
that human_review has "the same practical effect as Block" for this MVP (no
live human-review queue exists yet). The same two decisions on the output
side withhold the response instead of returning the mock text.
"""
from __future__ import annotations

import uuid

from app.core.decisions import Decision, most_severe
from app.guards.input_guard import evaluate_input
from app.guards.output_guard import evaluate_output
from app.guards.rag_guard import evaluate_rag_context
from app.schemas.requests import RAGContextChunk
from app.schemas.responses import ChatResponse
from app.services.audit_logger import log_event
from app.services.llm_provider import (
    BaseLLMProvider,
    LLMProviderRequest,
    get_llm_provider,
)
from app.core.config import settings

_BLOCKED_INPUT_TEMPLATE = (
    "Your request was blocked by the Input Guard and was not sent to the "
    "(mock) language model. Reason(s): {reasons}"
)

_HELD_FOR_REVIEW_INPUT_TEMPLATE = (
    "Your request was flagged for human review by the Input Guard and was "
    "not sent to the (mock) language model. Reason(s): {reasons}"
)

_BLOCKED_RAG_TEMPLATE = (
    "Retrieved context was blocked by the RAG Context Guard and was not "
    "sent to the (mock) language model. Reason(s): {reasons}"
)

_HELD_FOR_REVIEW_RAG_TEMPLATE = (
    "Retrieved context was flagged for human review by the RAG Context "
    "Guard and was not sent to the (mock) language model. Reason(s): {reasons}"
)

_BLOCKED_OUTPUT_MESSAGE = (
    "The (mock) assistant response was blocked by the Output Guard before being returned."
)

_HELD_FOR_REVIEW_OUTPUT_MESSAGE = (
    "The (mock) assistant response was flagged for human review by the Output "
    "Guard and is being withheld pending review."
)

# Decisions that stop the pipeline before proceeding to the next stage
# (mock LLM call, or returning the response to the caller).
_STOPPING_DECISIONS = (Decision.BLOCK, Decision.HUMAN_REVIEW)

# Metadata keys whose values are conversation *content* rather than routing
# facts. Callers legitimately place these in `metadata` because that is how
# the provider contract carries them (`LLMProviderRequest.metadata` -- see
# app/services/providers/ollama.py, which reads `metadata["history"]`), but
# the same dict was previously handed verbatim to `log_event`, which meant
# every turn of every conversation was persisted in `logs/audit.jsonl`.
#
# That is the opposite of the policy `app/services/rag_query.py` already
# applies to the same class of data: it audits only a `query_hash` plus a
# length, never the text itself (see `commit_rag_query_audit`). This
# constant plus `_audit_safe_metadata` bring `/v1/gateway/chat` in line with
# that policy. `app/services/audit_logger.py` enforces the same rule
# independently as a defense-in-depth net, so a future call site that
# forgets to transform its metadata still cannot write conversation content
# to the audit sink.
_NON_AUDITABLE_METADATA_KEYS = frozenset({"history"})


def _audit_safe_metadata(metadata: dict) -> dict:
    """Return a copy of `metadata` with conversation content replaced by a
    non-reversible summary, leaving every other key untouched.

    Deliberately shape-preserving for callers that carry no conversation
    content at all (the common `/v1/gateway/chat` case): if none of the
    non-auditable keys are present, the original dict is returned unchanged,
    so existing audit-event shapes and their tests do not move.

    Type-first, per this project's validator convention: `metadata` is
    checked with `isinstance` before any membership test, and a non-list
    `history` value counts as zero turns rather than raising -- a malformed
    metadata dict must never be able to fail a request through the audit
    path.
    """
    if not isinstance(metadata, dict):
        return {}
    if not _NON_AUDITABLE_METADATA_KEYS.intersection(metadata):
        return metadata
    safe = {
        key: value
        for key, value in metadata.items()
        if key not in _NON_AUDITABLE_METADATA_KEYS
    }
    if "history" in metadata:
        history = metadata["history"]
        safe["history_turns"] = len(history) if isinstance(history, (list, tuple)) else 0
    return safe


def run_chat(
    prompt: str,
    context_chunks: list[RAGContextChunk],
    metadata: dict,
    provider: BaseLLMProvider | None = None,
) -> ChatResponse:
    """Run the full mock gateway pipeline for one chat request.

    Decision flow (see module docstring for the severity order):
      1. Evaluate the Input Guard.
         - BLOCK or HUMAN_REVIEW -> stop here, no RAG Guard, no mock LLM call.
         - SANITIZE -> continue using the sanitized prompt.
         - LOG_ONLY / ALLOW -> continue using the original prompt.
      2. If `context_chunks` were supplied, evaluate the RAG Context Guard.
         - BLOCK or HUMAN_REVIEW -> stop here, no mock LLM call.
         - SANITIZE -> continue using the sanitized chunks.
         - LOG_ONLY / ALLOW -> continue using the original chunks.
      3. Generate a candidate response through the configured provider.
      4. Evaluate the Output Guard on that response.
         - BLOCK or HUMAN_REVIEW -> withhold the response.
         - SANITIZE -> return the redacted response.
         - LOG_ONLY / ALLOW -> return the response unmodified.
      5. final_decision = most_severe(input_decision, rag_decision, output_decision).
    """
    request_id = str(uuid.uuid4())

    from app.guards.semantic_guard import evaluate_input_semantic

    input_result = evaluate_input(prompt)
    # Semantic path always runs after a non-stopping Input Guard result.
    # evaluate_input_semantic uses a fast local pre-screen first and only
    # calls Ollama when the provider is not mock and the pre-screen is
    # inconclusive — so mock/dev stays low-latency while Vietnamese and
    # other semantic attacks still get blocked.
    if input_result.decision not in _STOPPING_DECISIONS:
        semantic_result = evaluate_input_semantic(prompt)
        if semantic_result.decision in _STOPPING_DECISIONS:
            input_result = semantic_result

    if input_result.decision in _STOPPING_DECISIONS:
        template = (
            _BLOCKED_INPUT_TEMPLATE
            if input_result.decision == Decision.BLOCK
            else _HELD_FOR_REVIEW_INPUT_TEMPLATE
        )
        response_text = template.format(reasons="; ".join(input_result.reasons) or "policy violation")

        log_event(
            endpoint="/v1/gateway/chat",
            request_id=request_id,
            input_preview=prompt,
            input_decision=input_result,
            rag_decision=None,
            output_decision=None,
            final_decision=input_result.decision,
            reasons=input_result.reasons,
            metadata=_audit_safe_metadata(metadata),
        )
        return ChatResponse(
            request_id=request_id,
            input_guard=input_result,
            rag_guard=None,
            output_guard=None,
            final_decision=input_result.decision,
            response=response_text,
        )

    # SANITIZE -> use the cleaned prompt; LOG_ONLY/ALLOW -> use the original.
    effective_prompt = (
        (input_result.sanitized_text or "")
        if input_result.decision == Decision.SANITIZE
        else prompt
    )

    rag_result = evaluate_rag_context(context_chunks) if context_chunks else None

    if rag_result is not None and rag_result.decision in _STOPPING_DECISIONS:
        template = (
            _BLOCKED_RAG_TEMPLATE
            if rag_result.decision == Decision.BLOCK
            else _HELD_FOR_REVIEW_RAG_TEMPLATE
        )
        response_text = template.format(reasons="; ".join(rag_result.reasons) or "policy violation")
        final_decision = most_severe([input_result.decision, rag_result.decision])
        all_reasons = list(input_result.reasons) + list(rag_result.reasons)

        log_event(
            endpoint="/v1/gateway/chat",
            request_id=request_id,
            input_preview=prompt,
            input_decision=input_result,
            rag_decision=rag_result,
            output_decision=None,
            final_decision=final_decision,
            reasons=all_reasons,
            metadata=_audit_safe_metadata(metadata),
        )
        return ChatResponse(
            request_id=request_id,
            input_guard=input_result,
            rag_guard=rag_result,
            output_guard=None,
            final_decision=final_decision,
            response=response_text,
        )

    # SANITIZE -> use the sanitized chunks; LOG_ONLY/ALLOW -> use originals.
    effective_chunks = (
        (rag_result.sanitized_chunks or [])
        if rag_result is not None and rag_result.decision == Decision.SANITIZE
        else context_chunks
    )

    active_provider = provider or get_llm_provider(settings.llm_provider)
    provider_result = active_provider.generate(
        LLMProviderRequest(
            prompt=prompt,
            sanitized_prompt=effective_prompt,
            context_chunks=effective_chunks,
            metadata=metadata,
            request_id=request_id,
        )
    )
    from app.guards.semantic_guard import evaluate_output_semantic

    output_result = evaluate_output(provider_result.text)
    if output_result.decision not in _STOPPING_DECISIONS and getattr(settings, 'llm_provider', '') != 'mock':
        semantic_out_result = evaluate_output_semantic(provider_result.text)
        if semantic_out_result.decision in _STOPPING_DECISIONS:
            output_result = semantic_out_result

    if output_result.decision == Decision.BLOCK:
        final_response_text = _BLOCKED_OUTPUT_MESSAGE
    elif output_result.decision == Decision.HUMAN_REVIEW:
        final_response_text = _HELD_FOR_REVIEW_OUTPUT_MESSAGE
    elif output_result.decision == Decision.SANITIZE and output_result.sanitized_text:
        final_response_text = output_result.sanitized_text
    else:
        final_response_text = provider_result.text

    all_decisions = [input_result.decision, output_result.decision]
    if rag_result is not None:
        all_decisions.append(rag_result.decision)
    final_decision = most_severe(all_decisions)

    all_reasons = list(input_result.reasons)
    if rag_result is not None:
        all_reasons += list(rag_result.reasons)
    all_reasons += list(output_result.reasons)

    log_event(
        endpoint="/v1/gateway/chat",
        request_id=request_id,
        input_preview=prompt,
        input_decision=input_result,
        rag_decision=rag_result,
        output_decision=output_result,
        final_decision=final_decision,
        reasons=all_reasons,
        metadata=_audit_safe_metadata(metadata),
        provider_metadata={
            "provider_name": provider_result.provider_name,
            "model_name": provider_result.model_name,
            "is_mock": provider_result.is_mock,
        },
    )

    return ChatResponse(
        request_id=request_id,
        input_guard=input_result,
        rag_guard=rag_result,
        output_guard=output_result,
        final_decision=final_decision,
        response=final_response_text,
        provider_name=provider_result.provider_name,
        model_name=provider_result.model_name,
        is_mock=provider_result.is_mock,
    )


def run_unguarded_chat(
    prompt: str,
    context_chunks: list[RAGContextChunk],
    metadata: dict,
    provider: BaseLLMProvider | None = None,
) -> ChatResponse:
    """Run the chat directly against the LLM without ANY security guards (for A/B demo purposes)."""
    request_id = str(uuid.uuid4())
    active_provider = provider or get_llm_provider(settings.llm_provider)

    provider_result = active_provider.generate(
        LLMProviderRequest(
            prompt=prompt,
            sanitized_prompt=prompt,
            context_chunks=context_chunks,
            metadata=metadata,
            request_id=request_id,
        )
    )

    from app.schemas.responses import GuardDecisionResponse, RAGGuardResponse

    # Mock ALWAYS ALLOW for guards
    dummy_decision = GuardDecisionResponse(decision=Decision.ALLOW)
    dummy_rag = RAGGuardResponse(decision=Decision.ALLOW)

    return ChatResponse(
        request_id=request_id,
        input_guard=dummy_decision,
        rag_guard=dummy_rag,
        output_guard=dummy_decision,
        final_decision=Decision.ALLOW,
        response=provider_result.text,
        provider_name=provider_result.provider_name,
        model_name=provider_result.model_name,
        is_mock=provider_result.is_mock,
    )
