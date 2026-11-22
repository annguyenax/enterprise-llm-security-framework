"""Local Ollama provider, enabled only with LLM_PROVIDER=ollama."""
from __future__ import annotations

import errno
import json
import logging
import math
import os
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, HTTPRedirectHandler, ProxyHandler, build_opener

from app.core.config import Settings, settings as application_settings
from app.services.llm_provider import BaseLLMProvider, LLMProviderRequest, LLMProviderResponse, register_provider
from app.services.providers._shared import context_instruction, history_messages, system_prompt


class _RejectRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HTTPError(req.full_url, code, "Ollama redirect rejected", headers, fp)


def urlopen(request, timeout):
    # Never use environment proxies or follow a local redirect off-machine.
    return build_opener(ProxyHandler({}), _RejectRedirect()).open(request, timeout=timeout)


class OllamaProviderError(RuntimeError):
    def __init__(self, message, metadata):
        super().__init__(message)
        self.metadata = metadata
        self.attempt_trace = metadata["attempt_trace"]


class OllamaLLMProvider(BaseLLMProvider):
    provider_name = "ollama"

    def __init__(self, settings: Settings | None = None, *, deadline=None,
                 run_id=None, event_sink=None, evaluation=False,
                 base_url=None, keep_alive=None) -> None:
        self.settings = settings if settings is not None else application_settings
        self.model_name = self.settings.llm_model_name
        self.base_url = base_url if base_url is not None else os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        parsed = urlparse(self.base_url)
        if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
                or parsed.username is not None or parsed.password is not None
                or parsed.query or parsed.fragment or parsed.path not in {"", "/"}):
            raise ValueError("OLLAMA_BASE_URL must point to the local machine over HTTP")
        if evaluation and self.base_url != "http://127.0.0.1:11434":
            raise ValueError("evaluation permits only http://127.0.0.1:11434/api/chat")
        self.base_url = self.base_url.rstrip("/")
        self.keep_alive = keep_alive if keep_alive is not None else os.getenv("OLLAMA_KEEP_ALIVE", "30m")
        if deadline is not None and (type(deadline) not in {int, float} or not math.isfinite(deadline)):
            raise ValueError("deadline must be a finite monotonic timestamp")
        self.deadline = deadline
        self.run_id = run_id
        self.event_sink = event_sink

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
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "think": self.settings.ollama_think,
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": self.settings.ollama_temperature,
                "seed": self.settings.ollama_seed,
                "num_ctx": self.settings.ollama_num_ctx,
                "num_predict": self.settings.ollama_num_predict,
            },
        }
        serialized = json.dumps(payload).encode()
        trace = []
        metadata = {
            "run_id": self.run_id,
            "model_tag": payload["model"],
            "options": dict(payload["options"]),
            "think": payload["think"],
            "model_digest_expected": self.settings.ollama_model_digest,
            "model_quantization_expected": self.settings.ollama_model_quantization,
            "model_digest_observed": None,
            "ollama_version_expected": self.settings.ollama_expected_version,
            "ollama_version_observed": None,
            "repeat_count": self.settings.llm_repeat_count,
            "attempt_trace": trace,
            "attempt_count": 0,
            "retry_count": 0,
        }

        def emit(event, attempt, **details):
            record = {
                "event": event, "run_id": self.run_id, "request_id": request.request_id,
                "attempt_index": attempt, "max_retries": self.settings.ollama_max_retries,
                "provider_id": self.provider_name, "endpoint": self.base_url + "/api/chat",
                "model_tag": payload["model"],
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                **details,
            }
            trace.append(record)
            # The runner attaches a durable content-free sink before generation.
            # Standard logging goes to stderr, never the worker IPC stream.
            logging.getLogger(__name__).info("ollama_attempt %s", json.dumps(record))
            if self.event_sink is not None:
                self.event_sink(record, metadata)

        for attempt in range(1, self.settings.ollama_max_retries + 2):
            remaining = None if self.deadline is None else self.deadline - time.monotonic()
            if remaining is not None and remaining <= 0:
                emit("budget_exhausted", attempt, outcome="timeout", elapsed_seconds=0.0)
                raise OllamaProviderError("Ollama case deadline exhausted", metadata)
            timeout = self.settings.llm_provider_timeout_seconds
            if remaining is not None:
                timeout = min(timeout, remaining)
            metadata["attempt_count"] = attempt
            metadata["retry_count"] = attempt - 1
            started = time.monotonic()
            emit("attempt_start", attempt, timeout_seconds=timeout)
            status = None
            try:
                if self.deadline is not None:
                    timeout = min(timeout, self.deadline - time.monotonic())
                    if timeout <= 0:
                        raise TimeoutError("Ollama case deadline exhausted before transport")
                http_request = Request(self.base_url + "/api/chat", data=serialized,
                                       headers={"Content-Type": "application/json"}, method="POST")
                with urlopen(http_request, timeout=timeout) as response:
                    status = getattr(response, "status", 200)
                    if status != 200:
                        raise HTTPError(http_request.full_url, status, "unexpected status", {}, None)
                    data = json.loads(response.read().decode("utf-8"))
                if (not isinstance(data, dict) or not isinstance(data.get("message"), dict)
                        or not isinstance(data["message"].get("content"), str)):
                    raise ValueError("Ollama response structure is invalid")
                text = data["message"]["content"].strip()
                if not text:
                    raise ValueError("Ollama returned an empty response")
                usage = {}
                for source, target in (("prompt_eval_count", "input_units"), ("eval_count", "output_units")):
                    value = data.get(source, 0)
                    if type(value) is not int or value < 0:
                        raise ValueError("Ollama usage structure is invalid")
                    usage[target] = value
                if self.deadline is not None and time.monotonic() >= self.deadline:
                    raise TimeoutError("Ollama case deadline exhausted")
            except Exception as exc:
                retryable = False
                if isinstance(exc, HTTPError):
                    status = exc.code
                    retryable = status == 500
                    exc.close()
                else:
                    reason = exc.reason if isinstance(exc, URLError) else exc
                    retryable = isinstance(reason, (ConnectionRefusedError, ConnectionResetError, TimeoutError)) or (
                        isinstance(reason, OSError) and reason.errno in {errno.ECONNREFUSED, errno.ECONNRESET, errno.ETIMEDOUT}
                    )
                delay = (0.5, 1.0)[attempt - 1] if attempt <= self.settings.ollama_max_retries else None
                remaining = None if self.deadline is None else self.deadline - time.monotonic()
                retry = retryable and delay is not None and (remaining is None or remaining > delay)
                outcome = "retry" if retry else "terminal_failure"
                if isinstance(exc, ValueError) and str(exc) == "Ollama returned an empty response":
                    outcome = "empty_response"
                if remaining is not None and remaining <= 0:
                    outcome = "timeout"
                emit("attempt_end", attempt, elapsed_seconds=time.monotonic() - started,
                     http_status=status, exception_class=type(exc).__name__, outcome=outcome)
                if not retry:
                    raise OllamaProviderError("Ollama request failed closed: " + type(exc).__name__, metadata) from exc
                # Durable logging takes real time too. Recheck before sleeping.
                if self.deadline is not None and self.deadline - time.monotonic() <= delay:
                    emit("budget_exhausted", attempt, outcome="timeout", elapsed_seconds=time.monotonic() - started)
                    raise OllamaProviderError("Ollama case deadline exhausted", metadata) from exc
                sleep_started = time.monotonic()
                time.sleep(delay)
                emit("backoff_end", attempt, backoff_seconds=time.monotonic() - sleep_started,
                     scheduled_backoff_seconds=delay)
                continue
            metadata["done_reason"] = data.get("done_reason")
            emit("attempt_end", attempt, elapsed_seconds=time.monotonic() - started,
                 http_status=status, exception_class=None, outcome="success")
            return LLMProviderResponse(text=text, provider_name=self.provider_name,
                model_name=payload["model"], is_mock=False, usage=usage, metadata=metadata)
        raise AssertionError("unreachable retry state")


register_provider("ollama", OllamaLLMProvider)
