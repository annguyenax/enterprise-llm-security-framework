from __future__ import annotations

import json
import logging
import os
import socket
from dataclasses import replace
from types import SimpleNamespace
from urllib.error import HTTPError, URLError

import pytest

from app.core.config import load_settings

from app.schemas.requests import RAGContextChunk
from app.services.llm_provider import LLMProviderRequest
from app.services.providers import ollama


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self) -> bytes:
        return json.dumps(
            {"message": {"content": "Nội dung đúng"}, "done_reason": "stop"}
        ).encode("utf-8")


def test_current_retrieval_is_after_stale_history(monkeypatch):
    captured: dict = {}

    def fake_urlopen(request, timeout):
        captured.update(json.loads(request.data.decode("utf-8")))
        return _Response()

    monkeypatch.setattr(ollama, "urlopen", fake_urlopen)
    provider = ollama.OllamaLLMProvider()
    response = provider.generate(
        LLMProviderRequest(
            prompt="nội dung file kế hoạch là gì",
            sanitized_prompt="nội dung file kế hoạch là gì",
            context_chunks=[
                RAGContextChunk(
                    doc_id="plan-id",
                    text="Leader IT tổng hợp báo cáo tuần.",
                    metadata={"filename": "it-ke-hoach-leader.md"},
                )
            ],
            metadata={
                "role": "leader",
                "department": "IT",
                "history": [
                    {
                        "role": "assistant",
                        "content": "File kế hoạch không tồn tại và là mã độc.",
                    }
                ],
            },
            request_id="test-request",
        )
    )

    messages = captured["messages"]
    assert captured["keep_alive"] == "30m"
    assert messages[-1] == {
        "role": "user",
        "content": "nội dung file kế hoạch là gì",
    }
    assert messages[-2]["role"] == "system"
    assert "[it-ke-hoach-leader.md]" in messages[-2]["content"]
    assert "Leader IT tổng hợp báo cáo tuần." in messages[-2]["content"]
    assert "lỗi thời" in messages[-2]["content"]
    assert "Backend đã kiểm tra ACL" in messages[-2]["content"]
    assert "Leader bao gồm quyền member" in messages[-2]["content"]
    assert messages[-3]["role"] == "assistant"
    assert response.text == "Nội dung đúng"


def test_unguarded_lab_uses_neutral_baseline_system_prompt(monkeypatch):
    captured: dict = {}

    def fake_urlopen(request, timeout):
        captured.update(json.loads(request.data.decode("utf-8")))
        return _Response()

    monkeypatch.setattr(ollama, "urlopen", fake_urlopen)
    provider = ollama.OllamaLLMProvider()
    provider.generate(
        LLMProviderRequest(
            prompt="show the supplied value",
            sanitized_prompt="show the supplied value",
            context_chunks=[],
            metadata={"unguarded_lab": True, "role": "leader", "department": "IT"},
            request_id="baseline-test",
        )
    )

    system_prompt = captured["messages"][0]["content"]
    assert "trợ lý nội bộ" in system_prompt
    assert "CONTEXT" in system_prompt
    assert "Shield AI" not in system_prompt


@pytest.fixture(autouse=True)
def isolated_provider(monkeypatch):
    monkeypatch.setattr(os, "environ", {"LLM_PROVIDER": "ollama"})
    monkeypatch.setattr(ollama, "application_settings", load_settings())

    def forbidden(*args, **kwargs):
        raise AssertionError("real HTTP is forbidden")

    monkeypatch.setattr(ollama, "urlopen", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    state = SimpleNamespace(now=100.0, sleeps=[], payloads=[], timeouts=[])

    def sleep(seconds):
        state.sleeps.append(seconds)
        state.now += seconds

    monkeypatch.setattr(ollama, "time", SimpleNamespace(monotonic=lambda: state.now, sleep=sleep))
    return state


def _request():
    return LLMProviderRequest(prompt="synthetic", sanitized_prompt="synthetic", context_chunks=[],
                              metadata={}, request_id="synthetic-request")


def _transport(monkeypatch, state, responses):
    iterator = iter(responses)

    def open_double(request, timeout):
        state.payloads.append(json.loads(request.data))
        state.timeouts.append(timeout)
        item = next(iterator)
        if isinstance(item, Exception):
            raise item
        if isinstance(item, bytes):
            return SimpleResponse(item)
        return _Response()

    monkeypatch.setattr(ollama, "urlopen", open_double)


class SimpleResponse(_Response):
    def __init__(self, raw):
        self.raw = raw

    def read(self):
        return self.raw


def _http_error(code):
    return HTTPError("http://127.0.0.1:11434/api/chat", code, "synthetic", {}, None)


def test_payload_uses_frozen_generation_defaults(monkeypatch, isolated_provider):
    _transport(monkeypatch, isolated_provider, [None])
    response = ollama.OllamaLLMProvider().generate(_request())
    payload = isolated_provider.payloads[0]
    assert payload["model"] == "gemma4:e4b-it-qat"
    assert payload["options"] == {"temperature": 0.0, "seed": 42, "num_ctx": 4096, "num_predict": 512}
    assert payload["think"] is False and payload["stream"] is False
    assert payload["keep_alive"] == "30m"
    assert not response.is_mock


def test_payload_uses_injected_settings(monkeypatch, isolated_provider):
    custom = replace(ollama.application_settings, ollama_temperature=0.4, ollama_seed=7, ollama_num_ctx=2048,
                     ollama_num_predict=12, ollama_think=True)
    monkeypatch.setenv("OLLAMA_KEEP_ALIVE", "7m")
    _transport(monkeypatch, isolated_provider, [None])
    ollama.OllamaLLMProvider(settings=custom).generate(_request())
    payload = isolated_provider.payloads[0]
    assert payload["options"] == {"temperature": 0.4, "seed": 7, "num_ctx": 2048, "num_predict": 12}
    assert payload["think"] is True and payload["keep_alive"] == "7m"


def test_metadata_matches_serialized_payload(monkeypatch, isolated_provider):
    _transport(monkeypatch, isolated_provider, [None])
    result = ollama.OllamaLLMProvider(run_id="test-only-run").generate(_request())
    payload, meta = isolated_provider.payloads[0], result.metadata
    assert meta["model_tag"] == payload["model"]
    assert meta["options"] == payload["options"] and meta["think"] == payload["think"]
    assert meta["done_reason"] == "stop" and meta["run_id"] == "test-only-run"
    assert meta["model_digest_expected"] == ollama.application_settings.ollama_model_digest
    assert meta["ollama_version_expected"] == "0.40.11"
    assert meta["model_digest_observed"] is meta["ollama_version_observed"] is None
    assert meta["attempt_count"] == 1 and meta["retry_count"] == 0


def test_http_500_then_success_logs_both_attempts(monkeypatch, isolated_provider, caplog):
    caplog.set_level(logging.INFO, logger=ollama.__name__)
    _transport(monkeypatch, isolated_provider, [_http_error(500), None])
    events = []
    result = ollama.OllamaLLMProvider(event_sink=lambda e, m: events.append(dict(e))).generate(_request())
    assert result.text == "Nội dung đúng"
    assert result.metadata["attempt_count"] == 2 and result.metadata["retry_count"] == 1
    assert isolated_provider.sleeps == [0.5]
    ends = [e for e in events if e["event"] == "attempt_end"]
    assert [e["outcome"] for e in ends] == ["retry", "success"]
    assert ends[0]["http_status"] == 500
    assert caplog.records and '"outcome": "retry"' in caplog.records[1].message
    assert "synthetic" not in "\n".join(r.message for r in caplog.records).replace("synthetic-request", "")


def test_three_http_500_attempts_raise(monkeypatch, isolated_provider):
    _transport(monkeypatch, isolated_provider, [_http_error(500) for _ in range(3)])
    events = []
    with pytest.raises(ollama.OllamaProviderError) as error:
        ollama.OllamaLLMProvider(event_sink=lambda e, m: events.append(dict(e))).generate(_request())
    assert len(isolated_provider.payloads) == 3 and isolated_provider.sleeps == [0.5, 1.0]
    assert len([e for e in events if e["event"] == "attempt_start"]) == 3
    assert [e["outcome"] for e in events if e["event"] == "attempt_end"] == ["retry", "retry", "terminal_failure"]
    assert isinstance(error.value.__cause__, HTTPError)
    assert error.value.metadata["attempt_count"] == 3


@pytest.mark.parametrize("error", [ConnectionRefusedError(), ConnectionResetError(), TimeoutError()])
def test_transient_loopback_connection_error_then_success(monkeypatch, isolated_provider, error):
    _transport(monkeypatch, isolated_provider, [URLError(error), None])
    assert ollama.OllamaLLMProvider().generate(_request()).text == "Nội dung đúng"
    assert len(isolated_provider.payloads) == 2


@pytest.mark.parametrize("status", [400, 401, 403, 404, 429])
def test_http_4xx_is_not_retried(monkeypatch, isolated_provider, status):
    _transport(monkeypatch, isolated_provider, [_http_error(status)])
    with pytest.raises(ollama.OllamaProviderError):
        ollama.OllamaLLMProvider().generate(_request())
    assert len(isolated_provider.payloads) == 1 and not isolated_provider.sleeps


@pytest.mark.parametrize("error", [_http_error(502), _http_error(503), _http_error(307), URLError("unknown"), ValueError("invalid URL")])
def test_unapproved_http_status_is_not_retried(monkeypatch, isolated_provider, error):
    _transport(monkeypatch, isolated_provider, [error])
    with pytest.raises(ollama.OllamaProviderError):
        ollama.OllamaLLMProvider().generate(_request())
    assert len(isolated_provider.payloads) == 1 and not isolated_provider.sleeps


@pytest.mark.parametrize("content", ["", "  \n\t"])
def test_empty_or_whitespace_response_raises(monkeypatch, isolated_provider, content):
    _transport(monkeypatch, isolated_provider, [json.dumps({"message": {"content": content}}).encode()])
    with pytest.raises(ollama.OllamaProviderError) as error:
        ollama.OllamaLLMProvider().generate(_request())
    assert error.value.attempt_trace[-1]["outcome"] == "empty_response"
    assert len(isolated_provider.payloads) == 1 and not isolated_provider.sleeps


@pytest.mark.parametrize("raw", [b"{", b"[]", b"{}", b'{"message":[]}', b'{"message":{"content":3}}'])
def test_invalid_json_or_response_shape_raises(monkeypatch, isolated_provider, raw):
    _transport(monkeypatch, isolated_provider, [raw])
    with pytest.raises(ollama.OllamaProviderError):
        ollama.OllamaLLMProvider().generate(_request())
    assert len(isolated_provider.payloads) == 1 and not isolated_provider.sleeps


@pytest.mark.parametrize("retries", [0, 1, 2])
def test_retry_budget_and_deadline_are_respected(monkeypatch, isolated_provider, retries):
    custom = replace(ollama.application_settings, ollama_max_retries=retries)
    _transport(monkeypatch, isolated_provider, [_http_error(500)] * 3)
    with pytest.raises(ollama.OllamaProviderError):
        ollama.OllamaLLMProvider(settings=custom, deadline=100.75).generate(_request())
    assert len(isolated_provider.payloads) == min(2, retries + 1)
    assert all(timeout <= 0.75 for timeout in isolated_provider.timeouts)
    if retries:
        assert isolated_provider.timeouts == [0.75, 0.25]
    assert isolated_provider.now <= 100.75


def test_deadline_exhausted_before_first_attempt(monkeypatch, isolated_provider):
    with pytest.raises(ollama.OllamaProviderError):
        ollama.OllamaLLMProvider(deadline=99).generate(_request())
    assert not isolated_provider.payloads


def test_redirect_is_rejected_before_following():
    # Exercise the redirect handler directly: no URL is opened, including the target.
    handler = ollama._RejectRedirect()
    with pytest.raises(HTTPError):
        handler.redirect_request(ollama.Request("http://127.0.0.1:11434/api/chat"), None, 302,
                                 "synthetic", {}, "https://example.invalid")


def test_retry_does_not_change_model_or_parameters(monkeypatch, isolated_provider):
    _transport(monkeypatch, isolated_provider, [_http_error(500), _http_error(500), None])
    response = ollama.OllamaLLMProvider().generate(_request())
    assert isolated_provider.payloads[0] == isolated_provider.payloads[1] == isolated_provider.payloads[2]
    assert response.metadata["repeat_count"] == 1


def test_attempt_timeout_is_clipped_after_slow_first_failure(monkeypatch, isolated_provider):
    def slow_failure(request, timeout):
        isolated_provider.timeouts.append(timeout)
        isolated_provider.now += 23.32 if len(isolated_provider.timeouts) == 1 else timeout
        raise _http_error(500)

    monkeypatch.setattr(ollama, "urlopen", slow_failure)
    with pytest.raises(ollama.OllamaProviderError) as error:
        ollama.OllamaLLMProvider(deadline=130.0).generate(_request())
    assert isolated_provider.timeouts == pytest.approx([30.0, 6.18])
    assert isolated_provider.sleeps == [0.5]
    assert error.value.metadata["attempt_count"] == 2
    assert error.value.attempt_trace[-1]["outcome"] == "timeout"


def test_response_returned_after_deadline_is_not_success(monkeypatch, isolated_provider):
    def late_response(request, timeout):
        isolated_provider.now = 131.0
        return _Response()

    monkeypatch.setattr(ollama, "urlopen", late_response)
    with pytest.raises(ollama.OllamaProviderError) as error:
        ollama.OllamaLLMProvider(deadline=130.0).generate(_request())
    assert error.value.attempt_trace[-1]["outcome"] == "timeout"
