from __future__ import annotations

import json

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
