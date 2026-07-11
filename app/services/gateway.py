"""Gateway orchestration: Input Guard -> (mock LLM) -> Output Guard -> audit log.

No real LLM is called in this phase. Real LLM provider integration is a
later, explicitly-approved phase (see TASK_BOARD.md and AGENT_RULES.md
rule 4 — no paid API calls without approval). Real RAG retrieval is also
not implemented yet (Phase 5).
"""
from __future__ import annotations

import uuid

from app.core.decisions import Decision, most_severe
from app.guards.input_guard import evaluate_input
from app.guards.output_guard import evaluate_output
from app.schemas.responses import ChatResponse
from app.services.audit_logger import log_event

MOCK_RESPONSE = (
    "Mock response generated after guard evaluation. "
    "Real LLM integration is planned for a later phase."
)

_BLOCKED_INPUT_TEMPLATE = (
    "Your request was blocked by the Input Guard and was not sent to the "
    "(mock) language model. Reason(s): {reasons}"
)

_BLOCKED_OUTPUT_MESSAGE = (
    "The (mock) assistant response was blocked by the Output Guard before being returned."
)


def run_chat(prompt: str, metadata: dict) -> ChatResponse:
    """Run the full mock gateway pipeline for one chat request."""
    request_id = str(uuid.uuid4())

    input_result = evaluate_input(prompt)

    if input_result.decision == Decision.BLOCK:
        response_text = _BLOCKED_INPUT_TEMPLATE.format(
            reasons="; ".join(input_result.reasons) or "policy violation"
        )
        log_event(
            endpoint="/v1/gateway/chat",
            request_id=request_id,
            input_preview=prompt,
            input_decision=input_result,
            output_decision=None,
            final_decision=Decision.BLOCK,
            reasons=input_result.reasons,
            metadata=metadata,
        )
        return ChatResponse(
            request_id=request_id,
            input_guard=input_result,
            output_guard=None,
            final_decision=Decision.BLOCK,
            response=response_text,
        )

    # SANITIZE -> use the cleaned prompt; ALLOW/LOG_ONLY/HUMAN_REVIEW -> use
    # the original prompt as-is. `effective_prompt` is what a real LLM call
    # would receive in a later phase; it does not change the mock response.
    effective_prompt = (
        input_result.sanitized_text if input_result.decision == Decision.SANITIZE else prompt
    )
    _ = effective_prompt  # not used yet -- no real LLM call in this phase

    output_result = evaluate_output(MOCK_RESPONSE)

    if output_result.decision == Decision.BLOCK:
        final_response_text = _BLOCKED_OUTPUT_MESSAGE
    elif output_result.decision == Decision.SANITIZE and output_result.sanitized_text:
        final_response_text = output_result.sanitized_text
    else:
        final_response_text = MOCK_RESPONSE

    final_decision = most_severe([input_result.decision, output_result.decision])
    all_reasons = list(input_result.reasons) + list(output_result.reasons)

    log_event(
        endpoint="/v1/gateway/chat",
        request_id=request_id,
        input_preview=prompt,
        input_decision=input_result,
        output_decision=output_result,
        final_decision=final_decision,
        reasons=all_reasons,
        metadata=metadata,
    )

    return ChatResponse(
        request_id=request_id,
        input_guard=input_result,
        output_guard=output_result,
        final_decision=final_decision,
        response=final_response_text,
    )
