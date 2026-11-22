# Task A — Anthropic (Claude) provider

Read first: CLAUDE.md, AGENT_RULES.md, docs/p4-claude-sql/00_CONTRACT.md.

Implement `app/services/providers/anthropic.py`:
- stdlib only (`urllib.request`), like `app/services/providers/ollama.py`. Do NOT add the `anthropic` SDK.
- POST `{ANTHROPIC_BASE_URL}/v1/messages`, headers `x-api-key` (from env `ANTHROPIC_API_KEY`),
  `anthropic-version: 2023-06-01`, `content-type: application/json`.
- Body: `model` = settings.llm_model_name (expected `claude-sonnet-5-5`), `max_tokens` from
  `ANTHROPIC_MAX_TOKENS` (default 1024), `system` = SAME system prompt text as ollama.py for the
  guarded path and for `metadata["unguarded_lab"] is True` (refactor the shared text into a small
  helper only if you can do it without changing ollama.py behaviour; otherwise duplicate and add a
  test asserting both providers produce identical system strings).
- Messages: history (last 12, user/assistant only, content[:4000]), then CONTEXT block, then user
  `sanitized_prompt`. Anthropic has no `system` role inside messages: put the CONTEXT block into the
  final user turn (prefixed) or into `system`; document which and why.
- Parse `content[*].text` where type == "text"; usage -> `input_units`/`output_units`
  from `usage.input_tokens`/`usage.output_tokens`; metadata `stop_reason`.
- Fail closed: missing key -> `RuntimeError` with message that does NOT include the key;
  base URL must be https (allow http only for 127.0.0.1/localhost for tests); empty text -> RuntimeError;
  HTTP errors -> RuntimeError without echoing response body secrets.
- `register_provider("anthropic", AnthropicLLMProvider)`.
- `app/main.py`: add one conditional import for `anthropic`, mirroring the ollama one.
- `.env.example`: add the anthropic block with placeholders (see contract).

Tests `tests/test_anthropic_provider.py` (monkeypatch `urlopen`, NO network):
request shape, headers, system prompt parity with ollama (guarded + unguarded), history ordering,
missing key error hides key, non-https rejected, usage mapping, empty response error.

Do not call the real API. Write `docs/p4-claude-sql/report-A.md` per contract template.
