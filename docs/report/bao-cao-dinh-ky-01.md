# Báo cáo định kỳ 01

**Đề tài:** Xây dựng Hệ thống Bảo mật LLM Chống Tấn công Prompt Injection và Data Poisoning trong Môi trường Doanh nghiệp

**Nhóm sinh viên:**
- Nguyễn Văn An — N22DCAT001 — D22CQAT01-N
- Lê Đình Nghĩa — N22DCAT038 — D22CQAT01-N

**Giảng viên hướng dẫn:** Nguyễn Hoàng Thanh

**Thời hạn nộp báo cáo:** 12–13/07/2026

**Giai đoạn hiện tại:** Phase 0 hoàn tất (scaffold). Phase 1 (nghiên cứu) đã có bản nháp đầu tiên. Phase 2 (kiến trúc & threat model) đã có bản thiết kế đầy đủ, bao gồm cả phần thiết kế dữ liệu red-team & tiêu chí đánh giá (gọi tắt "Phase 2.5"). Vẫn chỉ ở mức tài liệu — chưa triển khai code ứng dụng, chưa cài đặt package, chưa gọi API nào.

---

## 1. Quá trình tìm hiểu

### Giai đoạn Phase 0 (nền tảng)

- Tìm hiểu tổng quan các dạng tấn công đặc thù đối với hệ thống LLM/RAG trong doanh nghiệp: prompt injection, indirect prompt injection (thông qua tài liệu được truy hồi), jailbreak, rò rỉ thông tin nhạy cảm (sensitive information leakage), và data/document poisoning trong RAG.
- Khảo sát sơ bộ hướng tiếp cận kỹ thuật: dùng LLM Security Gateway / Guardrail Proxy đặt trước một RAG demo, thay vì huấn luyện/fine-tune mô hình — phù hợp với quy mô đồ án thực tập (lab-scale).
- Xác định các ràng buộc kỹ thuật ban đầu: sử dụng LLM qua API (không huấn luyện local trong MVP), dữ liệu hoàn toàn tổng hợp (synthetic), không dùng PII/secrets thật.

### Giai đoạn Phase 1 (nghiên cứu sâu — đang triển khai)

- Nhóm sử dụng Gemini để tổng hợp một bản nghiên cứu sơ bộ (`docs/research/raw/gemini-phase-1-research.md`) về bối cảnh bảo mật LLM doanh nghiệp: OWASP Top 10 for LLM Applications, OWASP LLMSVS, các công cụ guardrail/red-team (NeMo Guardrails, Lakera Guard, deepteam, garak, Microsoft PyRIT), và 3 nguồn học thuật (PoisonedRAG, PIDP-Attack, một bài tổng quan trên tạp chí MDPI *Information*).
- Toàn bộ trích dẫn từ bản nghiên cứu AI này đã được **xác minh chéo qua tìm kiếm web thực tế** (không chỉ tin vào AI) trước khi đưa vào tài liệu chính thức, theo đúng AGENT_RULES.md mục 2 (không bịa trích dẫn). Quá trình xác minh phát hiện và sửa 2 lỗi nhỏ trong bản gốc của Gemini: sai tên tác giả đầu của PoisonedRAG (Zou, Y. → đúng là Zou, W.), và sai năm xuất bản của bài MDPI (2025 → đúng là 2026).
- Kết quả đã được cập nhật vào `docs/research/related-work.md`, `owasp-llm-top10-mapping.md`, `llmsvs-checklist.md`, `tool-comparison.md`, `dataset-review.md`. Đây vẫn là **nghiên cứu thứ cấp có AI hỗ trợ**, các thành viên trong nhóm chưa đọc trực tiếp toàn văn các bài báo — cần xác minh thủ công trước khi trích dẫn chính thức trong báo cáo LaTeX.
- Chưa tìm được bộ dataset red-team công khai cụ thể nào để review trực tiếp; chỉ ghi nhận garak/PyRIT/deepteam có kèm theo bộ probe/dataset riêng, cần mở và đánh giá ở phiên làm việc sau.

### Giai đoạn Phase 2 (kiến trúc & threat model — đang triển khai)

- Xây dựng đầy đủ **yêu cầu chức năng (Functional Requirements)** và **yêu cầu phi chức năng (Non-Functional Requirements)** cho MVP, ghi tại `docs/diagrams/architecture.md` mục 1–2 — bao gồm ràng buộc tường minh: toàn bộ hệ thống phải chạy được trên laptop 16GB RAM của 2 sinh viên, không cần GPU, không cần hạ tầng cloud ngoài API của nhà cung cấp LLM.
- Cập nhật sơ đồ kiến trúc Mermaid (`architecture.md`) chi tiết hơn: thêm khối Config/Settings, Vector Store, và đường log riêng cho từng guard; cập nhật sơ đồ luồng dữ liệu Mermaid (`data-flow.md`) với 2 luồng — (1) luồng request/response như Phase 0, và (2) luồng ingestion tài liệu tổng hợp vào Vector Store kèm gắn provenance/source ID.
- Thêm **bảng phân chia trách nhiệm module** (Module Responsibility Table) — liệt kê rõ 9 module (Demo UI/API, Security Gateway, Config, Input Guard, RAG Guard, Vector Store, LLM Provider Adapter, Output Guard, Logging/Evaluation), trách nhiệm, module liên quan, và phase triển khai dự kiến.
- Mở rộng threat model STRIDE (`threat-model.md`) với mức đánh giá rủi ro định tính (High/Medium/Low — không phải số liệu đo thực tế), và bổ sung mục "Threats Deferred to Future Thesis Scope" liệt kê rõ các nhóm rủi ro liên quan đến Kubernetes, SIEM, fine-tuning — được ghi nhận nhưng **không mô hình hóa chi tiết** vì các hạ tầng đó không thuộc MVP.
- Cập nhật ADR-001 với bảng **"MVP Scope vs. Future Thesis Scope"**, khẳng định rõ ràng: Kubernetes, tích hợp SIEM, và fine-tuning/huấn luyện mô hình local **không phải yêu cầu của MVP thực tập**, chỉ được ghi nhận như hướng mở rộng cho luận văn/đồ án tương lai nếu có.
- Toàn bộ công việc Phase 2 lần này chỉ dừng ở tài liệu thiết kế — không viết code, không cài đặt package, không gọi API nào, đúng theo AGENT_RULES.md.

### Giai đoạn Phase 2.5 (thiết kế dữ liệu red-team & tiêu chí đánh giá — đang triển khai)

- Tạo thư mục `docs/evaluation/` với 3 tài liệu thiết kế mới:
  - `red-team-test-design.md` — thiết kế 5 tài liệu doanh nghiệp "sạch" (HR, IT helpdesk, security guideline, product FAQ, finance reimbursement), 5 nhóm tài liệu RAG "nhiễm độc" (chèn lệnh ẩn, ghi đè system instruction, rò rỉ bí mật, yêu cầu bỏ qua chính sách, indirect injection qua transcript), và 7 nhóm prompt injection (direct, role override, instruction hierarchy, jailbreak, trích xuất thông tin nhạy cảm, thao túng ngữ cảnh RAG, lạm dụng tool/action).
  - `metrics-definition.md` — định nghĩa chính xác 6 metric: Attack Success Rate (ASR), Block Rate, False Positive Rate (FPR), False Negative Rate (FNR), Latency Overhead, và Reason Logging Completeness — kèm công thức tính, đối chiếu lại với các metric đã ghi nhận từ Phase 1 (JSR → là một trường hợp con của ASR).
  - `evaluation-plan.md` — quy trình đánh giá dự kiến (baseline không-guard vs có-guard), phân công vai trò, ràng buộc mang từ các phase trước.
- Toàn bộ ví dụ tài liệu/prompt trong các file trên đều là **dữ liệu hư cấu 100%** — dùng công ty giả định "Northwind Retail Group" (gợi nhớ đến công ty mẫu "Northwind Traders" nổi tiếng của Microsoft, để tín hiệu rõ đây là dữ liệu mẫu), không dùng PII/secret thật, chuỗi "bí mật" giả đều có định dạng rõ ràng không thể nhầm với secret thật (ví dụ `FAKE-SECRET-0000-EXAMPLE`).
- Cập nhật `docs/research/dataset-review.md` để tham chiếu sang bộ thiết kế mới này, làm rõ: đây mới là **thiết kế**, chưa có file dữ liệu thật nào được tạo trong `datasets/` hay `redteam/`.
- Chưa viết bất kỳ dòng code Python nào, chưa cài đặt package nào, chưa gọi API nào trong toàn bộ phiên làm việc Phase 2.5.

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
- Sử dụng AI (Gemini, Claude) để hỗ trợ tổng hợp tài liệu nghiên cứu giúp tiết kiệm thời gian, nhưng phát sinh thêm bước xác minh trích dẫn (fact-checking) bắt buộc trước khi đưa vào báo cáo chính thức — đã phát hiện 2 lỗi trích dẫn nhỏ (tên tác giả, năm xuất bản) trong lần rà soát đầu tiên, cho thấy quy trình xác minh này là cần thiết và nên duy trì cho các phase nghiên cứu tiếp theo.
- Các trích dẫn học thuật (đặc biệt là PIDP-Attack, công bố tháng 3/2026) đều là preprint chưa qua bình duyệt (chưa peer-reviewed) — cần thận trọng khi trích dẫn số liệu do chính tác giả tự công bố.
- Yêu cầu phi chức năng về độ trễ (latency) của các guard hiện chưa có con số cụ thể — cố tình để ở dạng định tính ("hợp lý cho demo") vì chưa có lần chạy đánh giá thực tế nào (Phase 7); đưa số liệu giả định vào lúc này sẽ vi phạm AGENT_RULES.md mục 3.
- Ràng buộc phần cứng 16GB RAM có thể giới hạn lựa chọn embedding model cho RAG Guard (embedding model local nặng có thể không khả thi) — quyết định cụ thể vẫn hoãn đến ADR ở Phase 5.
- Các mức đánh giá rủi ro (High/Medium/Low) trong threat model là đánh giá định tính của nhóm, chưa dựa trên số liệu đo thực tế — cần được kiểm chứng lại bằng kết quả evaluation ở Phase 7.
- Một số trường hợp thiết kế test (ví dụ RT-POISON-004 "yêu cầu bỏ qua chính sách") là ranh giới mờ giữa "Sanitize" và "Log only" — nhóm cần thảo luận thêm để thống nhất ngưỡng quyết định cụ thể trước khi hiện thực hóa guard logic ở Phase 4–6.
- Toàn bộ 6 metric đánh giá (ASR, Block Rate, FPR, FNR, Latency Overhead, Reason Logging Completeness) hiện chỉ là định nghĩa/công thức — chưa có bất kỳ số liệu đo nào; cần tránh nhầm lẫn đây là kết quả thực tế khi trình bày trong báo cáo LaTeX.
