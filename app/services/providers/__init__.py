"""LLM provider implementations owned by the knowledge-base/LLM workstream.

Collaboration seam (see docs/decisions/ADR-004-collaboration-interfaces.md):
new offline/approved providers live here as separate modules and register
themselves via ``app.services.llm_provider.register_provider(name, factory)``.
This keeps the shared ``get_llm_provider`` factory unchanged, minimizing merge
conflicts with the gateway workstream.

A registered provider MUST implement ``BaseLLMProvider`` and, for evaluation
integrity, keep deterministic (mock) evidence separate from stochastic
(real-model) evidence. A real/paid provider must not be enabled by default
without explicit maintainer approval (AGENT_RULES).
"""
