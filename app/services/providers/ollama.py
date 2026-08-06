"""Local Ollama provider, enabled only with LLM_PROVIDER=ollama."""
from __future__ import annotations

import json
import os
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.core.config import settings
from app.services.llm_provider import BaseLLMProvider, LLMProviderRequest, LLMProviderResponse, register_provider


class OllamaLLMProvider(BaseLLMProvider):
    provider_name = "ollama"

    def __init__(self) -> None:
        self.model_name = settings.llm_model_name
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
        parsed = urlparse(self.base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("OLLAMA_BASE_URL must point to the local machine over HTTP")

    def generate(self, request: LLMProviderRequest) -> LLMProviderResponse:
        role = str(request.metadata.get("role", "member"))
        department = str(request.metadata.get("department", "unknown"))
        system = (
            "Bạn là Shield AI, trợ lý nội bộ. Trả lời bằng tiếng Việt, rõ ràng và ngắn gọn. "
            f"Người dùng có vai trò {role}, phòng ban {department}. "
            "Chỉ dùng tài liệu được cung cấp trong CONTEXT cho thông tin nội bộ; nếu không có dữ liệu thì nói rõ. "
            "Không suy đoán hoặc tiết lộ dữ liệu của người dùng/phòng ban khác. "
            "Khi trả lời về cơ cấu tổ chức, phải phân biệt rõ tổng tài khoản, SuperAdmin, Leader và nhân viên(member); không gọi Leader là nhân viên."
        )
        messages = [{"role": "system", "content": system}]
        history = request.metadata.get("history", [])
        if isinstance(history, list):
            for item in history[-12:]:
                if isinstance(item, dict) and item.get("role") in {"user", "assistant"} and isinstance(item.get("content"), str):
                    messages.append({"role": item["role"], "content": item["content"][:4000]})
        if request.context_chunks:
            context = "\n\n".join(
                f"[{c.metadata.get('filename', c.doc_id)}]\n{c.text}"
                for c in request.context_chunks
            )
            # Keep freshly retrieved evidence next to the current question. Small
            # local models otherwise tend to copy an earlier assistant refusal
            # from conversation history even after retrieval has been corrected.
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "CONTEXT HIỆN TẠI ĐÃ ĐƯỢC PHÂN QUYỀN VÀ ÁP DỤNG CHO CÂU HỎI KẾ TIẾP. "
                        "Đây là nguồn dữ liệu ưu tiên cao nhất. Mỗi khối bắt đầu bằng [tên-file]. "
                        "Nếu lịch sử trước đó nói file không tồn tại, không hợp lệ hoặc là mã độc "
                        "nhưng file xuất hiện dưới đây, hãy coi nhận định cũ là lỗi thời và trả lời "
                        "theo nội dung hiện tại. Không tự gọi tài liệu là mã độc và không trộn file khác."
                        "\n\n" + context
                    ),
                }
            )
        messages.append({"role": "user", "content": request.sanitized_prompt})
        payload = json.dumps({"model": self.model_name, "messages": messages, "stream": False, "think": False, "options": {"temperature": 0.4, "num_predict": 512}}).encode()
        http_request = Request(self.base_url + "/api/chat", data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(http_request, timeout=settings.llm_provider_timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
        text = str(data.get("message", {}).get("content", "")).strip()
        if not text: raise RuntimeError("Ollama returned an empty response")
        return LLMProviderResponse(text=text, provider_name=self.provider_name, model_name=self.model_name, is_mock=False, usage={"input_units":int(data.get("prompt_eval_count",0)),"output_units":int(data.get("eval_count",0))}, metadata={"done_reason":data.get("done_reason")})


register_provider("ollama", OllamaLLMProvider)
