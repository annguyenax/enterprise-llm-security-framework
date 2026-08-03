# ADR-004 — Khớp nối phối hợp: LLM Provider & Retriever (đóng băng interface)

- **Trạng thái:** Accepted (giai đoạn phối hợp An × Nghĩa)
- **Bối cảnh:** Hai người làm song song. An sở hữu Gateway/Guards; Nghĩa xây LLM thật +
  kho tri thức doanh nghiệp + kiến trúc DN. Mục tiêu: song song **không giẫm chân**, ít
  merge conflict, mỗi giai đoạn có review + merge.
- **Liên quan:** ADR-001 (MVP scope), ADR-002 (retrieval engine), `CONTRIBUTING.md`.

## Quyết định

Cố định **hai hợp đồng (interface)** làm ranh giới tích hợp. Hai bên chỉ giao tiếp qua
chúng; không sửa mã nội bộ của nhau.

### 1. LLM Provider — `app/services/llm_provider.py`
- Hợp đồng: `BaseLLMProvider.generate(request: LLMProviderRequest) -> LLMProviderResponse`.
  - `LLMProviderRequest(prompt, sanitized_prompt, context_chunks, metadata, request_id)`.
  - `LLMProviderResponse(text, provider_name, model_name, is_mock, usage?, metadata)`.
- **Cơ chế đăng ký (mới):** `register_provider(name, factory)` +
  `get_llm_provider(name)`. Nghĩa thêm provider trong `app/services/providers/<tên>.py`,
  gọi `register_provider(...)` ở module đó, **không** sửa `get_llm_provider`.
- Ràng buộc bảo mật giữ nguyên: chỉ provider **offline/được duyệt**; provider thật cần
  phê duyệt riêng của người hướng dẫn (AGENT_RULES) trước khi bật mặc định; bằng chứng
  *deterministic (mock)* và *stochastic (LLM thật)* là **hai lớp claim tách biệt**.

### 2. Retriever / Kho tri thức — `app/retrieval/base.py`
- Hợp đồng ABC `Retriever`: `initialize`, `upsert_documents`, `search`, `get_document`,
  `delete_document`; dùng model `RetrievalQuery/RetrievalResult/ChunkRecord/DocumentRecord`.
- **Cơ chế đăng ký (mới):** `app/retrieval/registry.py` — `register_retriever(name, factory)`
  + `get_retriever(name, **kw)`. Nghĩa xây retriever thật (vector/embedding/kho tri thức DN)
  implement ABC và đăng ký; pipeline của An chọn backend qua cấu hình, **mặc định vẫn
  `sqlite_bm25`** để không vỡ demo/đánh giá hiện có.
- `search()` **không** gọi mạng/guard/LLM (giữ đúng ADR-002).

## Quy tắc thay đổi interface
Mọi thay đổi chữ ký của hai hợp đồng trên phải qua **PR riêng, cả hai duyệt**. Không đổi lén.

## Hệ quả
- Bề mặt va chạm ≈ 0: An sửa `app/guards`,`app/core`,`app/api`,`gateway/rag_query`; Nghĩa
  sửa `app/services/providers`,`app/retrieval`,`app/knowledge_base`,`datasets/enterprise-kb`.
- Tương thích ngược: hành vi hiện tại (`get_llm_provider("mock")`, retriever BM25) **không
  đổi**; toàn bộ test hiện có vẫn phải xanh.
- Release allowlist: file mới dạng `.py/.md/.txt` đã được luật `extension` phủ; **không**
  thêm file không đuôi (vd `CODEOWNERS`) nếu chưa cập nhật allowlist trong PR riêng.
"""