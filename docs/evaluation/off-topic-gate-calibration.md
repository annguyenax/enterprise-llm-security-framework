# Relevance / Off-Topic Gating — Calibration Finding

**Trạng thái:** Cơ chế đã hiện thực ở dạng **opt-in, mặc định TẮT**. Hiệu chuẩn
(calibration) trên corpus thật cho thấy **ngưỡng cosine không tách được** câu
trong miền (on-topic) và ngoài miền (off-topic) với embedding hiện tại, nên gate
**không được bật mặc định**. Đây là một phát hiện đo được, không phải tính năng bỏ
dở.

## 1. Vấn đề

Pipeline RAG hiện gọi LLM cho cả câu hỏi **ngoài luồng** (off-topic, không liên
quan kho tri thức doanh nghiệp), gây tốn token/GPU không cần thiết. Mong muốn: một
lớp *relevance gating* từ chối sớm câu off-topic **trước khi gọi LLM**
(Stop-before-LLM cho off-topic).

## 2. Cơ chế đã hiện thực

- `app/workspace/hybrid_retrieval.py`: `evaluate_off_topic(ranked, threshold,
  fail_closed)` — nếu cosine tốt nhất của kết quả truy hồi `< threshold` thì raise
  `OffTopicError`; `fail_closed=False` (mặc định) để một sự cố embedding không làm
  sập toàn hệ thống (off-topic là kiểm soát chi phí, không phải ranh giới ACL).
- `OffTopicError` **cố tình không** kế thừa `ValueError` để không bị `store.py`
  nuốt nhầm ở nhánh fallback BM25.
- Gate **chưa nối vào luồng production** (`/v1/rag/query`, workspace chat) và
  **mặc định TẮT**, vì kết quả hiệu chuẩn bên dưới.

## 3. Phương pháp hiệu chuẩn

Script: `scripts/calibrate_off_topic.py`. Chấm 6 câu on-topic và 6 câu off-topic
(tổng hợp, tiếng Việt) bằng cosine so với corpus thật, rồi xét hai phân bố có
tách được bằng một ngưỡng nào không.

```
WORKSPACE_EMBEDDING_MODEL=nomic-embed-text
OLLAMA_EMBEDDING_BASE_URL=http://127.0.0.1:11434
.venv\Scripts\python.exe scripts/calibrate_off_topic.py
```

## 4. Kết quả (model `nomic-embed-text`, corpus 61 tài liệu)

| Nhóm | Cosine (min – max) | Ví dụ |
|---|---|---|
| **On-topic** | 0.7361 – 0.8104 | nghỉ phép thường niên; quên mật khẩu; hoàn ứng công tác; hạn mức ăn uống; MFA; onboarding IT |
| **Off-topic** | 0.6916 – **0.7583** | thơ mùa thu Hà Nội; nấu phở bò; quicksort Python; kết quả bóng đá; gợi ý phim; dịch tiếng Nhật |

**Hai phân bố CHỒNG LẤN:** on-topic thấp nhất `0.7361` ≤ off-topic cao nhất
`0.7583`. **Không tồn tại ngưỡng cosine đơn** tách được hai nhóm với model này.

## 5. Kết luận

- Cosine similarity **không có ý nghĩa tuyệt đối** giữa các embedding model.
  `nomic-embed-text` chấm văn bản không liên quan (kể cả tiếng Việt) khá cao, nên
  một ngưỡng cosine sẽ **hoặc cho qua tất cả, hoặc chặn nhầm việc thật**.
- Đặt bất kỳ ngưỡng nào lúc này sẽ tạo ra "block trông có vẻ đúng nhưng không có
  cơ sở" — tệ hơn là không có gate. Vì vậy gate được **giữ opt-in, mặc định TẮT**.

## 6. Hướng phát triển (đã có bằng chứng để đề xuất)

1. **Đổi/ nâng embedding model** có phân tách on/off-topic tốt hơn, rồi hiệu chuẩn
   lại bằng chính script này (kỳ vọng xuất hiện khoảng trống giữa hai phân bố).
2. **Bộ lọc miền theo từ khoá** (HR / IT / chính sách / kho) như tín hiệu phụ,
   kết hợp cosine — đo OTR (off-topic refuse rate) / IDR (in-domain false refuse) /
   token tiết kiệm trên tập tay ~30 câu.
3. **Intent router bằng LLM nhỏ** (một câu hỏi phân loại trước RAG) — chính xác
   hơn nhưng tốn một lượt token mỗi truy vấn, cần cân nhắc ROI.

Mọi hướng trên **không** ảnh hưởng số liệu bảo mật đã khoá (TPR/FPR 425 case) —
relevance gating là kiểm soát chi phí/UX, đo bằng metric riêng (OTR/IDR/token).
