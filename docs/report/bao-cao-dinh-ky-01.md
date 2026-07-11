# Báo cáo định kỳ 01

**Đề tài:** Xây dựng Hệ thống Bảo mật LLM Chống Tấn công Prompt Injection và Data Poisoning trong Môi trường Doanh nghiệp

**Nhóm sinh viên:**
- Nguyễn Văn An — N22DCAT001 — D22CQAT01-N
- Lê Đình Nghĩa — N22DCAT038 — D22CQAT01-N

**Giảng viên hướng dẫn:** Nguyễn Hoàng Thanh

**Thời hạn nộp báo cáo:** 12–13/07/2026

**Giai đoạn hiện tại:** Phase 0 — Khởi tạo scaffold dự án, chưa triển khai code ứng dụng.

---

## 1. Quá trình tìm hiểu

- Tìm hiểu tổng quan các dạng tấn công đặc thù đối với hệ thống LLM/RAG trong doanh nghiệp: prompt injection, indirect prompt injection (thông qua tài liệu được truy hồi), jailbreak, rò rỉ thông tin nhạy cảm (sensitive information leakage), và data/document poisoning trong RAG.
- Tham khảo khung phân loại rủi ro OWASP Top 10 for LLM Applications để làm cơ sở ánh xạ (mapping) các mối đe dọa cụ thể của đề tài (xem `docs/research/owasp-llm-top10-mapping.md` — sẽ hoàn thiện chi tiết ở Phase 1).
- Khảo sát sơ bộ hướng tiếp cận kỹ thuật: dùng LLM Security Gateway / Guardrail Proxy đặt trước một RAG demo, thay vì huấn luyện/fine-tune mô hình — phù hợp với quy mô đồ án thực tập (lab-scale).
- Xác định các ràng buộc kỹ thuật ban đầu: sử dụng LLM qua API (không huấn luyện local trong MVP), dữ liệu hoàn toàn tổng hợp (synthetic), không dùng PII/secrets thật.
- Lưu ý: các nội dung nghiên cứu chi tiết (related work, tool comparison, dataset review) được lên kế hoạch triển khai ở Phase 1; báo cáo này ghi nhận phạm vi và hướng đi đã thống nhất tính đến thời điểm nộp báo cáo 01.

## 2. Đề cương chi tiết các công việc thực hiện

Xem chi tiết đầy đủ tại [PROJECT_PLAN.md](../../PROJECT_PLAN.md) và [TASK_BOARD.md](../../TASK_BOARD.md). Tóm tắt các giai đoạn:

| Phase | Nội dung chính |
|---|---|
| 0 | Khởi tạo scaffold repo, kế hoạch dự án, tài liệu nghiên cứu khung, quy tắc agent, khung báo cáo LaTeX |
| 1 | Nghiên cứu sâu: OWASP LLM Top 10, related work, so sánh công cụ/framework |
| 2 | Threat modeling (STRIDE) và thiết kế bộ dữ liệu kiểm thử tổng hợp |
| 3 | Khung Gateway: FastAPI app, cấu hình, logging |
| 4 | Input Guard (phát hiện prompt injection, jailbreak) |
| 5 | RAG Guard + pipeline RAG demo |
| 6 | Output Guard (chống rò rỉ thông tin nhạy cảm) |
| 7 | Bộ đánh giá (evaluation harness) + chạy red-team trên MVP |
| 8 | Tổng hợp kết quả, hoàn thiện báo cáo, sơ đồ |
| 9 | Hoàn thiện, chuẩn bị demo, nộp bài |

**Trạng thái hiện tại:** Phase 0 đang triển khai — tạo cấu trúc thư mục, tài liệu kế hoạch, quy tắc agent, khung nghiên cứu, sơ đồ kiến trúc/threat model, và khung báo cáo LaTeX. Chưa có code ứng dụng.

## 3. Outline quyển báo cáo

Xem chi tiết tại [docs/report/report-outline.md](report-outline.md). Cấu trúc tổng quát:

1. Mở đầu (đặt vấn đề, mục tiêu, phạm vi)
2. Chương 1 — Tổng quan và cơ sở lý thuyết (LLM, RAG, các dạng tấn công, OWASP LLM Top 10)
3. Chương 2 — Phân tích thiết kế hệ thống (kiến trúc gateway, threat model, thiết kế dữ liệu)
4. Chương 3 — Triển khai (Input Guard, RAG Guard, Output Guard, logging/evaluation)
5. Chương 4 — Kiểm thử và đánh giá (red-team, kết quả)
6. Kết luận và hướng phát triển
7. Tài liệu tham khảo
8. Phụ lục

## 4. Phân chia công việc, kế hoạch thực hiện

| Thành viên | Vai trò trọng tâm |
|---|---|
| Nguyễn Văn An | Input Guard, OWASP mapping, threat model, sensitive-leak detection, so sánh baseline |
| Lê Đình Nghĩa | RAG Guard/pipeline, dataset tổng hợp, logging/metrics, related work |
| Cả hai | Kiến trúc tổng thể, threat modeling, viết báo cáo, demo, review chéo |

Kế hoạch thực hiện bám theo `TASK_BOARD.md`, cập nhật trạng thái theo tuần trong `docs/weekly-notes/`. Phase 0 dự kiến hoàn tất trước hạn nộp báo cáo 01 (12–13/07/2026); Phase 1 bắt đầu ngay sau khi Phase 0 được xác nhận hoàn thành.

## 5. Các khó khăn, vướng mắc

- Chưa chốt lựa chọn framework RAG (LlamaIndex vs LangChain) và vector store (ChromaDB vs phương án khác) — quyết định sẽ được ghi nhận qua ADR ở Phase 5, hiện tạm hoãn để tránh khóa cứng thiết kế quá sớm.
- Cần thời gian tìm hiểu thêm về các kỹ thuật phát hiện indirect prompt injection từ tài liệu RAG — đây là mảng có ít tài liệu chuẩn hóa hơn so với prompt injection trực tiếp.
- Ràng buộc không dùng dữ liệu thật (PII/secrets/tài liệu nội bộ) đòi hỏi nhóm phải tự thiết kế bộ dữ liệu tổng hợp đủ đa dạng để kiểm thử có ý nghĩa — công việc này cần đầu tư thời gian ở Phase 2.
- Giới hạn về việc gọi API trả phí: nhóm cần lên kế hoạch sử dụng ngân sách API hợp lý và xin phê duyệt trước khi thực hiện các lượt gọi API tốn phí trong giai đoạn đánh giá (Phase 7).
- Thời gian giữa các giai đoạn khá sát với deadline báo cáo định kỳ; cần đảm bảo mỗi phase đều có tài liệu/evidence đầy đủ trước khi chuyển giai đoạn.
