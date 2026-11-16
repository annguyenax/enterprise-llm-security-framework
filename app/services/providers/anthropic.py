"""Anthropic (Claude) provider, enabled only with LLM_PROVIDER=anthropic.

Cloud counterpart of `ollama.py` for the 2x2 comparison
{local qwen3, Claude} x {guarded, unguarded}. Uses the standard library only
(no SDK dependency) and the same prompt text as Ollama via `_shared.py`.

Every call is a paid API call: AGENT_RULES rule 4 requires explicit
maintainer approval before enabling this provider for any run. The key is
read from `ANTHROPIC_API_KEY` at construction time and never logged,
echoed in errors, or returned in metadata.

Message layout: the Messages API has no `system` role inside `messages`,
so the shared system prompt and the CONTEXT block are joined into the
top-level `system` parameter. This keeps retrieved evidence at the same
(system-level) position it has in the Ollama provider, so both models see
equivalent authority for CONTEXT and the comparison is not confounded.
"""
from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.core.config import settings
from app.services.llm_provider import (
    BaseLLMProvider,
    LLMProviderRequest,
    LLMProviderResponse,
    register_provider,
)
from app.services.providers._shared import context_instruction, history_messages, system_prompt

ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_BASE_URL = "https://api.anthropic.com"
DEFAULT_MAX_TOKENS = 1024
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _normalize_turns(turns: list[dict[str, str]]) -> list[dict[str, str]]:
    """Make history valid for the Messages API.

    The API requires the conversation to start with a user turn and to
    alternate roles. Leading assistant turns are dropped and consecutive
    turns with the same role are merged.
    """
    out: list[dict[str, str]] = []
    for turn in turns:
        if not out and turn["role"] != "user":
            continue
        if out and out[-1]["role"] == turn["role"]:
            out[-1] = {"role": turn["role"], "content": out[-1]["content"] + "\n\n" + turn["content"]}
        else:
            out.append(dict(turn))
    return out


class AnthropicLLMProvider(BaseLLMProvider):
    provider_name = "anthropic"

    def __init__(self) -> None:
        self.model_name = settings.llm_model_name
        self._api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if not self._api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set; the anthropic provider is disabled")
        self.base_url = os.getenv("ANTHROPIC_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
        parsed = urlparse(self.base_url)
        is_local_http = parsed.scheme == "http" and parsed.hostname in _LOCAL_HOSTS
        if parsed.scheme != "https" and not is_local_http:
            raise ValueError("ANTHROPIC_BASE_URL must use https (http only allowed for localhost)")
        try:
            self.max_tokens = int(os.getenv("ANTHROPIC_MAX_TOKENS", str(DEFAULT_MAX_TOKENS)))
        except ValueError as exc:
            raise ValueError("ANTHROPIC_MAX_TOKENS must be an integer") from exc
        if not 1 <= self.max_tokens <= 8192:
            raise ValueError("ANTHROPIC_MAX_TOKENS must be between 1 and 8192")

    def build_payload(self, request: LLMProviderRequest) -> dict:
        system = system_prompt(request.metadata)
        context = context_instruction(request.context_chunks)
        if context is not None:
            system = system + "\n\n" + context
        turns = history_messages(request.metadata)
        turns.append({"role": "user", "content": request.sanitized_prompt})
        return {
            "model": self.model_name,
            "max_tokens": self.max_tokens,
            "temperature": 0.4,
            "system": system,
            "messages": _normalize_turns(turns),
        }

    def generate(self, request: LLMProviderRequest) -> LLMProviderResponse:
        payload = json.dumps(self.build_payload(request)).encode("utf-8")
        http_request = Request(
            self.base_url + "/v1/messages",
            data=payload,
            headers={
                "content-type": "application/json",
                "x-api-key": self._api_key,
                "anthropic-version": ANTHROPIC_VERSION,
            },
            method="POST",
        )
        try:
            with urlopen(http_request, timeout=settings.llm_provider_timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            # Do not echo the response body: it may quote request content.
            raise RuntimeError(f"Anthropic API returned HTTP {exc.code}") from None
        except URLError as exc:
            raise RuntimeError("Anthropic API is unreachable") from None

        blocks = data.get("content", []) if isinstance(data, dict) else []
        text = "".join(
            b.get("text", "")
            for b in blocks
            if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str)
        ).strip()
        if not text:
            raise RuntimeError("Anthropic returned an empty response")
        usage = data.get("usage", {}) if isinstance(data.get("usage"), dict) else {}
        return LLMProviderResponse(
            text=text,
            provider_name=self.provider_name,
            model_name=str(data.get("model") or self.model_name),
            is_mock=False,
            usage={
                "input_units": int(usage.get("input_tokens", 0) or 0),
                "output_units": int(usage.get("output_tokens", 0) or 0),
            },
            metadata={"stop_reason": data.get("stop_reason")},
        )


register_provider("anthropic", AnthropicLLMProvider)
