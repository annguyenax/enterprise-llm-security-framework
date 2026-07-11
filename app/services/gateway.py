"""Gateway orchestration: Input Guard -> RAG Guard -> (mock LLM) -> Output
Guard -> audit log.

No real LLM is called in this phase. Real LLM provider integration is a
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

MOCK_RESPONSE = (
    "Phase 4 mock response: guard evaluation completed. "
    "Real LLM and RAG retrieval are not enabled in this phase."
)

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


def run_chat(
    prompt: str, context_chunks: list[RAGContextChunk], metadata: dict
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
      3. Generate the (fixed, mock) assistant response.
      4. Evaluate the Output Guard on that response.
         - BLOCK or HUMAN_REVIEW -> withhold the response.
         - SANITIZE -> return the redacted response.
         - LOG_ONLY / ALLOW -> return the response unmodified.
      5. final_decision = most_severe(input_decision, rag_decision, output_decision).
    """
    request_id = str(uuid.uuid4())

    input_result = evaluate_input(prompt)

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
            metadata=metadata,
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
    # `effective_prompt` is what a real LLM call would receive in a later
    # phase; it does not change the mock response in this phase.
    effective_prompt = (
        input_result.sanitized_text if input_result.decision == Decision.SANITIZE else prompt
    )
    _ = effective_prompt  # not used yet -- no real LLM call in this phase

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
            metadata=metadata,
        )
        return ChatResponse(
            request_id=request_id,
            input_guard=input_result,
            rag_guard=rag_result,
            output_guard=None,
            final_decision=final_decision,
            response=response_text,
        )

    # SANITIZE -> use the sanitized chunks; LOG_ONLY/ALLOW -> use the
    # original chunks. `effective_chunks` is what a real LLM call would
    # receive in a later phase; it does not change the mock response here.
    effective_chunks = (
        rag_result.sanitized_chunks
        if rag_result is not None and rag_result.decision == Decision.SANITIZE
        else context_chunks
    )
    _ = effective_chunks  # not used yet -- no real LLM call in this phase

    output_result = evaluate_output(MOCK_RESPONSE)

    if output_result.decision == Decision.BLOCK:
        final_response_text = _BLOCKED_OUTPUT_MESSAGE
    elif output_result.decision == Decision.HUMAN_REVIEW:
        final_response_text = _HELD_FOR_REVIEW_OUTPUT_MESSAGE
    elif output_result.decision == Decision.SANITIZE and output_result.sanitized_text:
        final_response_text = output_result.sanitized_text
    else:
        final_response_text = MOCK_RESPONSE

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
        metadata=metadata,
    )

    return ChatResponse(
        request_id=request_id,
        input_guard=input_result,
        rag_guard=rag_result,
        output_guard=output_result,
        final_decision=final_decision,
        response=final_response_text,
    )
