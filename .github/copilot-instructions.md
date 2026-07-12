# Repository Code Review Instructions

When performing a code review, act as a strict read-only security and
software-engineering reviewer.

Do not modify files.
Do not implement fixes.
Do not claim tests passed unless test evidence is visible.
Review only the actual current diff.

Project context:
This is an offline academic RAG security gateway implemented with FastAPI,
SQLite FTS5/BM25, deterministic guards, centralized DLP, structured audit
logging, and a Mock LLM Provider.

Review priorities:

1. Security boundaries
- Caller must not control trust, classification, source type, provenance,
  canonical IDs, context chunks, guard decisions, or guard profiles.
- Runtime must never use is_poisoned, expected_decision, benchmark labels,
  dataset paths, or red-team filenames as security signals.

2. Fail-closed behavior
- Verify blocked stages cannot call downstream components.
- Verify rejected context never reaches the provider.
- Verify provider receives sanitized query and inspected context only.
- Verify DLP inspects every output character returned to the caller.
- Verify Output Guard receives only DLP-redacted output.

3. Secret leakage
- Check API responses, audit logs, exception handling, nested metadata,
  provider metadata, DLP findings, and fallback paths.
- Look for bearer tokens, secret assignments, private keys, API keys,
  repeated secrets, and uninspected output tails.

4. RAG pipeline order
Input Guard
→ Retrieval
→ Provenance Guard
→ Per-chunk Context Guard
→ Aggregate Context Enforcement
→ Mock Provider
→ DLP
→ Output Guard
→ Audit
→ Safe Response

5. Retrieval and SQLite
- FTS5 MATCH injection
- stale FTS rows
- transaction rollback
- deterministic ranking
- short-lived connections
- resource limits
- no fallback to LIKE

6. Audit safety
- No raw query
- No full retrieved context
- No provider output
- No raw secret
- No internal exception or stack trace
- One safe terminal audit attempt per accepted request

7. Configuration
- Positive bounds
- Consistent top_k relationships
- Safe hard ceilings
- Strict environment parsing
- Backward-compatible defaults

8. Compatibility
- /v1/gateway/chat must remain unchanged
- /v1/retrieve and /v1/documents/ingest must remain compatible
- No network call or real LLM dependency
- No frozen benchmark artifact modification

Output format:

## Critical
## Major
## Minor
## Missing regression tests
## Final verdict: PASS or REVISE

For every issue include:
- exact file and function
- code evidence
- failure or attack scenario
- minimal correction
- blocking: yes/no