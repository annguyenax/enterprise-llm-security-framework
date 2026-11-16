"""Anthropic provider tests. No network: urlopen is monkeypatched."""
from __future__ import annotations

import json
from dataclasses import replace
from urllib.error import HTTPError

import pytest

from app.schemas.requests import RAGContextChunk
from app.services.llm_provider import LLMProviderRequest
from app.services.providers import anthropic, ollama
from app.services.providers._shared import system_prompt

FAKE_KEY = "sk-ant-test-FAKE-0000"


class _Response:
    def __init__(self, body: dict):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self) -> bytes:
        return json.dumps(self._body).encode("utf-8")


def _ok_body(text="Trả lời", **extra):
    body = {
        "model": "claude-sonnet-5-5",
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 11, "output_tokens": 7},
    }
    body.update(extra)
    return body


def _request(metadata=None, chunks=None, prompt="bảo hành sofa bao lâu?"):
    return LLMProviderRequest(
        prompt=prompt,
        sanitized_prompt=prompt,
        context_chunks=chunks or [],
        metadata=metadata or {"role": "member", "department": "CSKH"},
        request_id="test",
    )


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE_KEY)
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    monkeypatch.delenv("ANTHROPIC_MAX_TOKENS", raising=False)
    monkeypatch.setattr(anthropic, "settings", replace(anthropic.settings, llm_model_name="claude-sonnet-5-5"))


def _capture(monkeypatch, body=None):
    captured: dict = {}

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["headers"] = {k.lower(): v for k, v in req.header_items()}
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _Response(body or _ok_body())

    monkeypatch.setattr(anthropic, "urlopen", fake_urlopen)
    return captured


def test_request_shape_and_headers(env, monkeypatch):
    cap = _capture(monkeypatch)
    resp = anthropic.AnthropicLLMProvider().generate(_request())
    assert cap["url"] == "https://api.anthropic.com/v1/messages"
    assert cap["headers"]["x-api-key"] == FAKE_KEY
    assert cap["headers"]["anthropic-version"] == "2023-06-01"
    assert cap["body"]["model"] == "claude-sonnet-5-5"
    assert cap["body"]["max_tokens"] == 1024
    assert cap["body"]["messages"][-1] == {"role": "user", "content": "bảo hành sofa bao lâu?"}
    assert all(m["role"] in {"user", "assistant"} for m in cap["body"]["messages"])
    assert resp.text == "Trả lời"
    assert resp.is_mock is False
    assert resp.usage == {"input_units": 11, "output_units": 7}
    assert resp.metadata == {"stop_reason": "end_turn"}


@pytest.mark.parametrize("unguarded", [False, True])
def test_system_prompt_parity_with_ollama(env, monkeypatch, unguarded):
    meta = {"role": "leader", "department": "KinhDoanh"}
    if unguarded:
        meta["unguarded_lab"] = True
    chunk = RAGContextChunk(doc_id="d1", text="Bảo hành 12 tháng.", metadata={"filename": "bao-hanh.md"})

    cap = _capture(monkeypatch)
    anthropic.AnthropicLLMProvider().generate(_request(meta, [chunk]))

    ocap: dict = {}

    def fake_ollama(req, timeout):
        ocap.update(json.loads(req.data.decode("utf-8")))
        return _Response({"message": {"content": "ok"}})

    monkeypatch.setattr(ollama, "urlopen", fake_ollama)
    ollama.OllamaLLMProvider().generate(_request(meta, [chunk]))

    ollama_system = "\n\n".join(m["content"] for m in ocap["messages"] if m["role"] == "system")
    assert cap["body"]["system"] == ollama_system
    assert cap["body"]["system"].startswith(system_prompt(meta))
    assert "Bảo hành 12 tháng." in cap["body"]["system"]


def test_history_is_normalized_and_ordered(env, monkeypatch):
    cap = _capture(monkeypatch)
    meta = {
        "history": [
            {"role": "assistant", "content": "chào"},  # leading assistant dropped
            {"role": "user", "content": "a"},
            {"role": "user", "content": "b"},  # merged
            {"role": "assistant", "content": "c"},
            {"role": "system", "content": "ignored"},
            "not-a-dict",
        ]
    }
    anthropic.AnthropicLLMProvider().generate(_request(meta, prompt="q"))
    assert cap["body"]["messages"] == [
        {"role": "user", "content": "a\n\nb"},
        {"role": "assistant", "content": "c"},
        {"role": "user", "content": "q"},
    ]


def test_missing_key_fails_closed(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        anthropic.AnthropicLLMProvider()


@pytest.mark.parametrize("url", ["http://api.anthropic.com", "ftp://x", "http://10.0.0.5:8080"])
def test_non_https_base_url_rejected(env, monkeypatch, url):
    monkeypatch.setenv("ANTHROPIC_BASE_URL", url)
    with pytest.raises(ValueError):
        anthropic.AnthropicLLMProvider()


def test_localhost_http_allowed_for_tests(env, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://127.0.0.1:9999")
    cap = _capture(monkeypatch)
    anthropic.AnthropicLLMProvider().generate(_request())
    assert cap["url"] == "http://127.0.0.1:9999/v1/messages"


def test_empty_response_raises(env, monkeypatch):
    _capture(monkeypatch, {"content": [{"type": "tool_use", "id": "x"}]})
    with pytest.raises(RuntimeError, match="empty"):
        anthropic.AnthropicLLMProvider().generate(_request())


def test_http_error_does_not_leak_key_or_body(env, monkeypatch):
    def boom(req, timeout):
        raise HTTPError(req.full_url, 401, "secret body " + FAKE_KEY, {}, None)

    monkeypatch.setattr(anthropic, "urlopen", boom)
    with pytest.raises(RuntimeError) as info:
        anthropic.AnthropicLLMProvider().generate(_request())
    assert FAKE_KEY not in str(info.value)
    assert "401" in str(info.value)


def test_key_not_in_repr_or_metadata(env, monkeypatch):
    _capture(monkeypatch)
    provider = anthropic.AnthropicLLMProvider()
    resp = provider.generate(_request())
    assert FAKE_KEY not in repr(resp)
    assert FAKE_KEY not in repr(provider.build_payload(_request()))


def test_registered_under_anthropic(env):
    from app.services.llm_provider import get_llm_provider

    assert isinstance(get_llm_provider("anthropic"), anthropic.AnthropicLLMProvider)
