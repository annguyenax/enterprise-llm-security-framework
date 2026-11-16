"""Local Ollama provider, enabled only with LLM_PROVIDER=ollama."""
from __future__ import annotations

import json
import os
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.core.config import settings
from app.services.llm_provider import BaseLLMProvider, LLMProviderRequest, LLMProviderResponse, register_provider
from app.services.providers._shared import context_instruction, history_messages, system_prompt


class OllamaLLMProvider(BaseLLMProvider):
    provider_name = "ollama"

    def __init__(self) -> None:
        self.model_name = settings.llm_model_name
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
        parsed = urlparse(self.base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("OLLAMA_BASE_URL must point to the local machine over HTTP")

    def generate(self, request: LLMProviderRequest) -> LLMProviderResponse:
        # Prompt text lives in _shared.py so the Anthropic provider uses the
        # exact same instructions (A/B parity). The unguarded A/B lab
        # (`POST /v1/unguarded/chat`) sets metadata["unguarded_lab"]; see
        # _shared.system_prompt for why the baseline prompt differs.
        messages = [{"role": "system", "content": system_prompt(request.metadata)}]
        messages.extend(history_messages(request.metadata))
        # Keep freshly retrieved evidence next to the current question. Small
        # local models otherwise tend to copy an earlier assistant refusal
        # from conversation history even after retrieval has been corrected.
        context = context_instruction(request.context_chunks)
        if context is not None:
            messages.append({"role": "system", "content": context})
        messages.append({"role": "user", "content": request.sanitized_prompt})
        payload = json.dumps({
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "think": False,
            "keep_alive": os.getenv("OLLAMA_KEEP_ALIVE", "30m"),
            "options": {"temperature": 0.4, "num_predict": 512},
        }).encode()
        http_request = Request(self.base_url + "/api/chat", data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(http_request, timeout=settings.llm_provider_timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
        text = str(data.get("message", {}).get("content", "")).strip()
        if not text: raise RuntimeError("Ollama returned an empty response")
        return LLMProviderResponse(text=text, provider_name=self.provider_name, model_name=self.model_name, is_mock=False, usage={"input_units":int(data.get("prompt_eval_count",0)),"output_units":int(data.get("eval_count",0))}, metadata={"done_reason":data.get("done_reason")})


register_provider("ollama", OllamaLLMProvider)
