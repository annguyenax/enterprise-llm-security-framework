# app/

Application code for the LLM Security Gateway / Guardrail Proxy.

**Status: Phase 5.1 - RAG Guard red-team hardening.** Rule-based Input,
RAG Context, and Output guards, deterministic dataset loading, JSONL audit
logging, and a mock chat pipeline are implemented. No real LLM call or vector
retrieval exists yet.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness check. |
| POST | `/v1/guard/input` | Evaluate a raw prompt. |
| POST | `/v1/guard/output` | Evaluate a candidate output. |
| POST | `/v1/guard/rag-context` | Evaluate caller-supplied context chunks. |
| POST | `/v1/gateway/chat` | Input -> RAG -> mock response -> Output -> audit log. |

## Guard Design

All three guards use small, explainable regex and keyword rules with the shared
decision order `block > human_review > sanitize > log_only > allow`.

- **Input Guard:** prompt injection, role and hierarchy attacks, jailbreaks,
  sensitive extraction, context manipulation, and tool misuse.
- **RAG Context Guard:** hidden instructions, system/developer overrides,
  transcript injection, fake-secret redaction, approval/policy bypass, and
  compound signals. Phase 5.1 adds detection-only normalization for whitespace,
  zero-width characters, and common light leetspeak.
- **Output Guard:** synthetic and realistic-looking secrets, email-like PII,
  system-instruction leakage, and classification markers.

RAG sanitization operates on original chunk text and preserves `doc_id` and
`metadata`. Hidden instruction blocks are removed selectively when possible.

## Not Implemented

- No real LLM provider call; `services/gateway.py` returns a fixed mock string.
- No embeddings, similarity search, vector database, or real retrieval. Callers
  supply `context_chunks` directly.
- No semantic classifier or LLM judge. Rule-based detection can miss semantic,
  deeply obfuscated, or encoded attacks and may still produce false positives.

## Audit Logging

Guard decisions are appended as UTF-8 JSON Lines to `logs/audit.jsonl` by
default. Secret-like content is redacted before logging. Raw context chunks are
not written to the decision summary.

## Not Production-Ready

This is a lab-scale university proof of concept. It does not claim complete
prompt-injection protection or provide a production security guarantee.
