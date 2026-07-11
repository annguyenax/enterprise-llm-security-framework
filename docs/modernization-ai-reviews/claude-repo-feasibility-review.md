Đã đọc xong toàn bộ mã nguồn hiện tại (app/, tests/, reports/evaluation/, reports/evidence/), chạy thử pytest (chỉ đọc, không cài gì) qua .venv sẵn có để xác nhận số liệu, và xem qua 2 review đã có sẵn của Gemini/Grok trong cùng thư mục để tránh lặp lại. Theo đúng yêu cầu, tôi không chỉnh sửa file nào — nội dung review được trình bày trực tiếp dưới đây (bạn có thể yêu cầu tôi ghi vào claude-repo-feasibility-review.md sau nếu muốn).

Claude Repo Feasibility Review
Đánh giá dựa trên việc đọc trực tiếp mã nguồn hiện tại (Phase 0–11), không dựa trên suy đoán bên ngoài. Chạy thử pytest qua .venv cục bộ: 82/82 pass, 1 cảnh báo deprecation không liên quan (httpx2, đã ghi nhận trong TASK_BOARD.md).

1. Tóm tắt kiến trúc hiện tại
Pipeline thực tế trong app/services/gateway.py:


User prompt (+ optional context_chunks do caller cung cấp sẵn)
   -> Input Guard (app/guards/input_guard.py, 26 rule regex/keyword)
   -> RAG Context Guard (app/guards/rag_guard.py, 8 rule + normalize hoá phát hiện)
        [chỉ chạy nếu caller tự truyền context_chunks — KHÔNG có bước retrieval thật]
   -> LLM Provider Adapter (app/services/llm_provider.py)
        [chỉ có MockLLMProvider — trả một chuỗi cố định, không có model thật]
   -> Output Guard (app/guards/output_guard.py, ~5 rule)
   -> Audit Logger (app/services/audit_logger.py, JSONL, tự redact secret)
Quyết định 5 trạng thái (allow/block/sanitize/log_only/human_review) gộp qua most_severe() — nhất quán xuyên suốt cả 3 guard.
Có bộ đánh giá offline (app/services/evaluation_runner.py) chạy trực tiếp guard trên redteam/prompts.jsonl (40 case cố định, đã đóng băng), sinh reports/evaluation/latest-evaluation.{json,md} và so sánh baseline (luôn-allow) vs guarded (baseline-vs-guarded.{json,md}).
Kết quả hiện tại: guarded 40/40 pass, 0 FP, 0 FN; baseline 5/40 pass (chỉ đúng 5 case benign vì baseline luôn allow).
Gói reports/evidence/ + tích hợp LaTeX (Phase 8–11) đã khá đầy đủ, kèm checklist nộp bài, hướng dẫn compile, kịch bản demo.
2. Điểm đã mạnh
Kiến trúc defense-in-depth rõ ràng, đúng mẫu proxy thực tế (giống cách Lakera Guard/NeMo Guardrails triển khai middleware) — không phải thiết kế tùy tiện.
Kỷ luật không bịa số liệu rất tốt: mọi report đều tự ghi chú "controlled synthetic benchmark, not a real-world rate" — điều này thực ra đã tự phòng thủ trước phần lớn chỉ trích "toy system overfit" của Gemini.
Test coverage thực chất: 82 test pass thật (tôi tự chạy lại), bao gồm cả test bất biến SHA-256 cho datasets//redteam/ (chống sửa nhầm benchmark đã đóng băng) — đây là kỷ luật nghiên cứu tốt, hiếm gặp ở đồ án sinh viên.
Audit log redact secret đã kiểm chứng thật (không chỉ tuyên bố) — tự tay tôi xác minh lại ở Phase 5.
Evaluation harness đã đi khá xa: có cả baseline-vs-guarded, có cả bước "failure triage" (Phase 7.1) ghi lại nguyên nhân từng false negative thay vì âm thầm sửa số — đúng tinh thần học thuật.
Gói report/LaTeX gần xong — phần việc "viết báo cáo" còn lại chủ yếu là thao tác thủ công (chụp ảnh, compile, đọc lại), không phải rào cản kỹ thuật.
3. Điểm yếu kỹ thuật lớn nhất
Xếp theo mức độ ảnh hưởng đến giá trị học thuật/kỹ thuật:

Không có retrieval thật — context_chunks do người gọi API tự nhét vào request; RAG Guard chưa bao giờ tự đi lấy tài liệu. Đây là điểm cả Gemini lẫn Grok đều nêu là chỉ trích số 1, và tôi xác nhận đúng khi đọc code: không có app/services/retrieval.py, không vector store nào tồn tại.
Không có LLM thật — MockLLMProvider trả một câu cố định (app/services/llm_provider.py:53-57). Output Guard vì vậy chưa từng thấy văn bản có tính ngẫu nhiên/diễn giải lại như LLM thật — không thể chứng minh guard xử lý được kiểu rò rỉ "LLM paraphrase secret theo cách khác".
Guard 100% rule-based, đã được tinh chỉnh theo đúng benchmark của mình — Phase 7.1 tự ghi nhận: sau khi thấy 5 case fail, đã "thêm 5 rule input guard mới" rồi chạy lại ra 40/40. Đây đúng là hiện tượng overfit benchmark tự tạo mà Gemini cảnh báo — không phải giả thuyết, mà là quy trình đã ghi lại rành mạch trong TASK_BOARD.md §Phase 7.1.
Benchmark nhỏ và lệch — 40 case, chỉ 5/40 (12.5%) là benign. Không đủ để chứng minh False Positive Rate/usability trade-off một cách thuyết phục.
Không có provenance/trust cho context — mọi chunk được coi ngang hàng, không phân biệt nguồn tin cậy cao/thấp (OWASP LLM08 - Vector and Embedding Weaknesses chưa được đụng tới).
Chưa đo latency ở đâu cả (NFR2 cố tình để trống) — không có số liệu để bàn về chi phí hiệu năng của 3 lớp guard.
4. Xếp hạng các hướng hiện đại hóa
#	Hướng	Impact	Effort	Risk	Giá trị report/demo
1	Real retrieval + vector index nhẹ (Option A phần 1)	Rất cao	Trung bình	Thấp	Rất cao — sửa trực tiếp chỉ trích "chưa phải RAG"
2	Provenance/trust scoring cho chunk (Option A phần 2)	Cao	Trung bình	Thấp-Trung bình	Cao
3	Ablation study evaluation mode	Cao	Thấp	Rất thấp	Rất cao — gần như "miễn phí" về kỹ thuật
4	DLP/PII regex mở rộng cho Output Guard	Trung bình-Cao	Thấp	Thấp	Trung bình-Cao
5	Semantic guard / LLM-as-judge (Option B)	Cao	Cao	Cao (phá tính determinism, cần model/API)	Cao nhưng rủi ro
6	Dashboard/demo UI (Option C)	Trung bình	Thấp	Rất thấp	Trung bình (chỉ trình bày, không thêm giá trị bảo mật)
7	Agent/tool security (Option D)	Thấp (ngoài phạm vi hiện tại)	Cao	Cao — vi phạm rule 1 AGENT_RULES (scope creep), đã bị liệt kê là "Future Thesis Scope" trong architecture.md §5	Thấp trong khung thời gian còn lại
5. Lộ trình triển khai đề xuất
Phase 12A — Local Retrieval Engine (nền tảng)
Phase 12B — Provenance/Trust Metadata
Phase 12C — Ablation Study Evaluation Mode
Phase 12D (tùy chọn, nếu còn thời gian) — Deterministic Groundedness Score

6. Chi tiết từng phase
Phase 12A — Local Retrieval Engine
File có thể thay đổi: mới app/services/retrieval.py (index TF-IDF/cosine similarity trên dataset_loader.load_all_chunks() — chọn TF-IDF thay vì embedding neural để tránh tải model, giữ tính xác định/tái lập, đúng NFR7 "ưu tiên heuristic đơn giản"); app/schemas/requests.py (thêm RetrievalRequest); app/api/routes.py (thêm POST /v1/retrieve, hoặc cờ use_retrieval tùy chọn trong /v1/gateway/chat); requirements.txt (+scikit-learn hoặc chỉ numpy nếu tự viết cosine — cần xin duyệt theo rule 11 AGENT_RULES vì là dependency mới).
Test cần thêm: tests/test_retrieval.py — top-k đúng thứ tự, tính xác định (chạy 2 lần ra cùng kết quả), tài liệu poisoned vẫn retrieve được (để RAG Guard có cơ hội chặn nó ở tầng sau, chứng minh defense-in-depth thật).
Kết quả kỳ vọng: query "warranty policy" trả về đúng chunk từ NW-PRD-004; khi query khớp với nội dung file hidden-html-instruction.md, tài liệu vẫn được retrieve nhưng RAG Guard sanitize/block trước khi vào context — đây chính là demo sống động nhất cho luận điểm "RAG Guard bảo vệ ngay cả khi retrieval trả về tài liệu độc".
Rollback risk: Thấp — module hoàn toàn mới, endpoint mới hoặc cờ tùy chọn, không đụng context_chunks contract cũ, không đụng benchmark đóng băng.
Report impact: Rất cao — trực tiếp vô hiệu hóa chỉ trích lớn nhất từ cả 2 review kia.
Phase 12B — Provenance/Trust Metadata
File có thể thay đổi: app/services/dataset_loader.py (khai thác thêm field classification/source_type đã có sẵn trong front-matter làm trust score thô); app/guards/rag_guard.py hoặc file mới app/guards/provenance_guard.py; mở rộng metadata contract của RAGContextChunk với trust_score/source_type.
Test cần thêm: chunk không rõ nguồn gốc/trust thấp bị hạ ưu tiên hoặc gắn cờ độc lập với nội dung văn bản (tách bạch tín hiệu "nguồn" khỏi tín hiệu "nội dung").
Kết quả kỳ vọng: một chunk sạch về nội dung nhưng thiếu provenance vẫn bị flag — thêm một lớp tín hiệu độc lập, khớp OWASP LLM08 và góc nhìn "Vector/Embedding Weaknesses" mà Grok nêu.
Rollback risk: Trung bình — phải cẩn thận không phá 40/40 hiện có (mọi rule mới chỉ áp dụng cho field metadata mới, không đổi logic content-rule cũ).
Report impact: Cao — là điểm mới, không trùng nội dung 2 review kia đã liệt kê chi tiết.
Phase 12C — Ablation Study Evaluation Mode
File có thể thay đổi: app/services/evaluation_runner.py (thêm mode chạy từng guard riêng lẻ: Input-only/RAG-only/Output-only/All/None trên cùng bộ 40 case đã đóng băng — không sửa file benchmark); scripts/run_evaluation.py (thêm cờ --ablation); mới reports/evaluation/ablation-study.{json,md}.
Test cần thêm: tests/test_evaluation_ablation.py — mỗi mode chạy độc lập, không side-effect lên mode khác, tổng hợp đúng.
Kết quả kỳ vọng: bảng cho biết layer nào "gánh" attack nào — trả lời thẳng RQ1 (Ablation) mà Gemini đề xuất, gần như miễn phí về công sức vì tái dùng toàn bộ hạ tầng evaluation đã có.
Rollback risk: Rất thấp — thuần túy cộng thêm, không sửa redteam/prompts.jsonl, không sửa guard logic.
Report impact: Rất cao/effort thấp nhất trong toàn bộ danh sách — nên làm sớm.
Phase 12D (tùy chọn) — Deterministic Groundedness Score
Thay vì LLM-as-judge (cần API trả phí hoặc model nặng), dùng một điểm số "groundedness" xác định bằng overlap từ khóa/TF-IDF giữa response và context đã duyệt — một phiên bản rút gọn, xác định được của ý tưởng "RAG triad" mà không phá tính reproducibility hay vi phạm rule 4 (không gọi API trả phí khi chưa duyệt).
7. Khuyến nghị dứt khoát: chọn Option A
Tôi chọn A — Real RAG retrieval + provenance + DLP, cụ thể là lộ trình Phase 12A → 12B → (12C đi kèm vì effort thấp/impact cao) làm hướng chính.

Vì sao không chọn B/C/D:

B (Semantic guard/LLM judge) giá trị cao nhưng phá vỡ tính xác định của benchmark 40/40 hiện tại (LLM có tính stochastic), và cần hoặc API trả phí (cần duyệt theo rule 4) hoặc model local nặng — rủi ro thời gian/tái lập cao hơn hẳn so với lợi ích trong khung 2 sinh viên. Có thể làm sau, ở dạng tùy chọn (12D là bước đệm an toàn hơn).
C (Dashboard/demo) không thêm giá trị bảo mật/học thuật nào — chỉ là lớp trình bày. Nên làm sau cùng, sau khi 12A xong (để có gì đó thật để hiển thị), không phải hướng chính.
D (Agent/tool security) đã bị liệt kê rõ là ngoài phạm vi MVP trong chính PROJECT_PLAN.md §3 và docs/diagrams/architecture.md §5 ("Future Thesis Scope"). Theo AGENT_RULES rule 1 (No scope creep), đây là hướng rủi ro cao nhất về mặt quy trình, không nên chọn trừ khi có phê duyệt riêng.
Vì sao A: đây là điểm yếu kỹ thuật lớn nhất, được cả 2 review độc lập khác (Gemini, Grok) và chính tôi (đọc trực tiếp code) đồng thuận là chỉ trích số 1. Nó khả thi trên Windows/16GB RAM (TF-IDF cosine similarity không cần GPU, không cần tải model), rủi ro rollback thấp (thuần cộng thêm module mới), và có giá trị demo/report cao nhất trên mỗi giờ công bỏ ra.

8. Những gì tuyệt đối không được thay đổi
datasets/clean/*.md, datasets/poisoned/*.md, redteam/prompts.jsonl, redteam/expected-behaviors.yaml, redteam/attack-categories.md — corpus đã đóng băng từ Phase 3.1 (docs/dataset/dataset-methodology.md §9: mọi thay đổi nội dung phải coi là phiên bản corpus mới, không sửa âm thầm). Có test SHA-256 canh giữ việc này.
reports/evaluation/*.json/*.md hiện có — chỉ được regenerate bằng runner, không sửa tay.
report-latex-template/thesis.sty và tiêu đề đề tài chính thức — đã xác nhận giữ nguyên byte-for-byte qua Phase 10; không được đổi trừ khi có duyệt của giảng viên hướng dẫn.
Không gọi API LLM thật/trả phí nếu chưa có phê duyệt cụ thể (AGENT_RULES rule 4) — mọi phần retrieval/guard mới ở Phase 12A-12D phải giữ offline-by-default.
Không dùng dữ liệu PII/secret thật, không dùng tài liệu doanh nghiệp thật — mọi corpus mở rộng (nếu có, ví dụ thêm case cho ablation) phải là file mới, tổng hợp, không sửa file cũ (AGENT_RULES rule 5).
Giữ nguyên taxonomy quyết định 5 trạng thái (allow/block/sanitize/log_only/human_review) và hàm most_severe() — không tạo một hệ quyết định song song.
Tuân thủ AGENT_RULES rule 1/12: đây chỉ là đề xuất Phase 12, chưa được phép triển khai — mọi việc thật sự bắt đầu code cần một lượt duyệt/go-ahead riêng, đúng tinh thần "stop at phase boundaries".