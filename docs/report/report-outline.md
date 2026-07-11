# Report Outline (Quyển báo cáo)

This outline maps to `report-latex/main.tex` chapter structure. Fill in each chapter as the corresponding phase produces evidence — do not write content ahead of actual implementation/results.

## Mở đầu (Introduction)

- Lý do chọn đề tài
- Mục tiêu đề tài (MVP scope, xem PROJECT_PLAN.md)
- Đối tượng và phạm vi nghiên cứu
- Phương pháp thực hiện
- Bố cục báo cáo

## Chương 1 — Tổng quan và cơ sở lý thuyết

1.1. Tổng quan về LLM và ứng dụng RAG trong doanh nghiệp
1.2. Các dạng tấn công đặc thù: prompt injection, indirect prompt injection, jailbreak, sensitive information leakage, RAG/data poisoning
1.3. OWASP Top 10 for LLM Applications — ánh xạ vào đề tài
1.4. Khảo sát công trình liên quan (related work)
1.5. So sánh công cụ/framework hiện có (guardrail libraries, RAG frameworks, vector DBs)

## Chương 2 — Phân tích và thiết kế hệ thống

2.1. Yêu cầu chức năng và phi chức năng của MVP
2.2. Kiến trúc tổng thể: LLM Security Gateway / Guardrail Proxy
2.3. Threat model (STRIDE) cho gateway và RAG pipeline
2.4. Thiết kế luồng dữ liệu (data flow)
2.5. Thiết kế bộ dữ liệu kiểm thử tổng hợp (synthetic red-team + poisoned documents)

## Chương 3 — Triển khai

3.1. Gateway skeleton (FastAPI, cấu hình, logging)
3.2. Input Guard: phát hiện prompt injection / jailbreak
3.3. RAG Guard: sanitize tài liệu truy hồi, phòng chống indirect injection và document poisoning
3.4. Output Guard: phát hiện/ngăn rò rỉ thông tin nhạy cảm
3.5. Logging và cơ chế đánh giá (evaluation harness)

## Chương 4 — Kiểm thử và đánh giá

4.1. Phương pháp đánh giá và metric sử dụng
4.2. Kết quả kiểm thử với bộ dữ liệu tổng hợp
4.3. So sánh baseline (không có guard) và có guard
4.4. Hạn chế của kết quả và MVP

## Kết luận và hướng phát triển

- Tổng kết kết quả đạt được so với mục tiêu MVP
- Hạn chế của đề tài
- Hướng phát triển tiếp theo (ví dụ: local model qua Ollama, mở rộng bộ test, production hardening)

## Tài liệu tham khảo

- Quản lý trong `report-latex/references.bib`. Chỉ trích dẫn nguồn có thật đã được nhóm kiểm tra — xem AGENT_RULES.md mục 2.

## Phụ lục

- Bộ prompt red-team tổng hợp (rút gọn)
- Cấu hình hệ thống dùng khi đánh giá
- Log/kết quả chạy thử (nếu có, gắn evidence cụ thể)
