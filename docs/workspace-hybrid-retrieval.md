# Workspace hybrid retrieval

Workspace retrieval giữ nhánh tìm chính xác/gần đúng theo tên file, sau đó có
thể kết hợp BM25 với vector embedding cục bộ. Hai danh sách hạng được trộn bằng
reciprocal-rank fusion, tránh cộng trực tiếp điểm BM25 và cosine không cùng
thang đo.

Vector tài liệu được cache trong bảng `document_embeddings` theo model và hash
nội dung. Chỉ những tài liệu đã qua ACL của người đang hỏi mới được gửi tới
embedding và xếp hạng semantic. Kết quả từ index tiếp tục được lọc lại bằng ACL
workspace trước khi trở thành context cho LLM.

Với `nomic-embed-text`, query và document dùng đúng tiền tố `search_query` /
`search_document`. Tài liệu chưa có cache được xử lý theo batch nhỏ để lần truy
vấn đầu không tạo một request embedding quá lớn.

Không có model nào được tự tải. Để kích hoạt sau khi đã cài một model embedding
trong Ollama:

```powershell
$env:WORKSPACE_EMBEDDING_MODEL='nomic-embed-text'
$env:OLLAMA_EMBEDDING_BASE_URL='http://127.0.0.1:11434'
```

Nếu endpoint embedding lỗi, hệ thống giảm cấp về BM25. Đây là lỗi khả dụng tìm
kiếm, không phải lý do nới lỏng ACL. Model `qwen3:4b-instruct` đang dùng cho chat
không quảng bá capability embedding nên không được dùng thay thế âm thầm.

Kiểm thử:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_hybrid_retrieval.py tests\test_business_document_seed.py -q
```
