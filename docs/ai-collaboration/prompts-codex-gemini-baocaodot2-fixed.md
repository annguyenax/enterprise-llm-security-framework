# Prompt giao Code X + Gemini — đánh giá dự án & báo cáo `baocaodot2_fixed`

**Mục đích:** copy-paste nguyên khối vào chat Code X / Gemini (web).  
**Gói báo cáo:** `baocaodot2_fixed.zip` (hoặc thư mục nguồn `bao_cao_latex_dot2/`).  
**Repo:** Enterprise LLM Security Framework (Shield AI) — lab-scale, synthetic.  
**Ngày soạn prompt:** 2026-08-12.  
**Không** tự adjudicate PASS cấp dự án; maintainer/giảng viên phán quyết cuối.

**Gợi ý đính kèm cho auditor**

| Gói | Nội dung |
|-----|----------|
| Báo cáo | `baocaodot2_fixed.zip` **hoặc** tree `bao_cao_latex_dot2/` (đặc biệt `chapters/chap4.tex`, `conclusion.tex`, `refs.bib`, `main.tex`) |
| Bằng chứng số | `docs/evaluation/phase13-p2-normalize-output-dlp.md`, `docs/evaluation/phase13-wall-optimization-authority-impersonation.md`, `reports/v3/20260812T082413Z-ac64cd5c/`, `reports/v3/20260812T091223Z-49d474bc/`, `reports/demo-ab/` |
| Code guard | `app/guards/` (input, output, semantic, rag, acl, dlp), `scripts/run_v3_evaluation.py`, `scripts/run_demo_ab_paired.py` |
| Luật dự án | `AGENT_RULES.md`, `Claude.md` (tóm tắt) |

**Số liệu cuối (artifact — auditor phải đối chiếu, không tin trí nhớ implementer)**

| Cấu hình | run_id | TPR | FPR | Stop-before-LLM | Ghi chú |
|----------|--------|----:|----:|----------------:|---------|
| Rule + normalize | `20260812T082413Z-ac64cd5c` | 81.5% | 0% | 81.5% | garak 83.8%; injecagent 47.4%; pyrit 100% (template family) |
| qwen3:4b + judge + Output-DLP | `20260812T091223Z-49d474bc` | 100% | 18.7% | **81.5%** | TPR 100% ≠ chặn sớm; 37 case sau provider (canary DLP) |
| Hermes (tham chiếu) | `20260811T151852Z-c848aeac` | 100% | 67.1% | 99.5% | Over-block; trước bước normalize Unicode |

**Ràng buộc cứng cho mọi auditor**

- Không sửa `datasets/v2` (frozen).  
- Holdout 12E.4 **chưa được ủy quyền**.  
- Latency **L2**: không yêu cầu / không chấp nhận p50–p95 báo cáo.  
- AGENT_RULES rule 2–3: không bịa citation; số chỉ từ artifact.  
- Đây là **PoC lab / đồ án**, không production-ready.

---

## A. Prompt cho Code X (artifact integrity + technical/security)

```text
Vai trò: Code X — independent technical auditor / artifact & methodology integrity
(KHÔNG implement code; KHÔNG tự phê duyệt phase PASS).

Dự án: Enterprise LLM Security Framework (lab-scale LLM security gateway / RAG
guardrail). Báo cáo nộp: gói baocaodot2_fixed.zip (hoặc bao_cao_latex_dot2/).

BỐI CẢNH NGẮN
- Pipeline: Input Guard → Semantic (optional) → Retrieve+ACL → RAG Context Guard
  → LLM → Output Guard (+ canary DLP).
- Đánh giá v3: 425 case (200 mal + 225 benign, trong đó 125 hard_benign).
- Tối ưu: (1) luật authority-impersonation; (2) chuẩn hoá Unicode input;
  (3) Output-DLP FLAG{...}; (4) demo A/B canary-sạch.
- Semantic judge mặc định OFF sau bằng chứng ROI precision kém.

NHIỆM VỤ (làm đủ, có bằng chứng file/path/hash khi có)

1) ARTIFACT INTEGRITY
   - Đối chiếu từng số chính trong Chương 4 (TPR/FPR/Stop-before-LLM/family/
     ma trận) với metrics.json của run_id được nêu (ít nhất ac64cd5c, 49d474bc,
     và run tối ưu authority nếu Ch4 còn trích 48.5→77).
   - Kiểm tra cases_sha256 / dataset_sha256 / manifest sha nếu có.
   - Exfil: phân biệt (a) metric confounded prompt-canary cũ; (b) clean-canary
     demo; (c) claim Output-DLP 0% marker trên 49d474bc. Chỉ chấp nhận claim khớp
     artifact.
   - Cờ đỏ: số trong báo cáo không có run_id; TPR 100% qwen bị diễn như “input
     recall hoàn hảo” trong khi Stop-before-LLM = 81.5%.

2) TECHNICAL SECURITY (lab-scale)
   - Map guard ↔ LLM01/02/04 (OWASP GenAI) ở mức thiết kế vs residual quan sát.
   - Đánh giá: regex wall, self-service exemption, normalize, Output-DLP, ACL dual
     path. Liệt kê residual (injecagent ~47%, evasion unit tests, FPR judge).
   - Demo A/B: có tái lập được không (script + reports/demo-ab)? Claim có
     oversell không?

3) BÁO CÁO baocaodot2_fixed
   - Ch4 + Kết luận + Hạn chế: claim vs evidence.
   - Provenance: runner có provenance; 3 run cũ có thể thiếu — báo cáo có nói
     đúng không?
   - Citation: chỉ flag entry refs.bib nghi ngờ / chưa verify (rule 2).

4) ĐẦU RA (Markdown)
   - Verdict: PASS | PASS-with-fixes | REVISE | FAIL (artifact) — có lý do.
   - Bảng: claim | evidence path | match? | severity.
   - Danh sách fix ưu tiên (P0/P1/P2), mỗi mục 1–2 câu.
   - KHÔNG bịa số; nếu thiếu artifact → “NOT VERIFIABLE”.
   - KHÔNG declare “dự án DONE/PASS” cấp maintainer.

RÀNG BUỘC: không datasets/v2; không holdout; không latency p50/p95; lab PoC only.
```

---

## B. Prompt cho Gemini (methodology + academic claims)

```text
Vai trò: Gemini — independent methodology / academic claims auditor
(KHÔNG implement; KHÔNG technical red-team sâu; KHÔNG tự phê duyệt đồ án).

Đối tượng: quyển báo cáo thực tập / đồ án trong baocaodot2_fixed.zip
(hoặc bao_cao_latex_dot2/), đặc biệt Chương 4 (kết quả), phần Hạn chế, Kết luận,
và cách trình bày metric bảo mật.

BỐI CẢNH PHƯƠNG PHÁP
- Lab-scale, dữ liệu tổng hợp 425 case; mock + Ollama local (qwen3:4b, hermes tham chiếu).
- Metric: TPR, FPR (kèm hard_benign), Stop-before-LLM, Exfil marker; n≥10 mới
  reportable; latency L2 = không báo p50/p95.
- Tối ưu lũy tiến được báo: baseline 48.5% → authority 77% → normalize 81.5%
  (FPR 0% trên benign synthetic); qwen TPR 100% / FPR 18.7% nhưng Stop-before-LLM
  vẫn 81.5% (phần TPR thêm = chặn sau LLM / Output-DLP).
- PyRIT 100% scoped “họ template ~6 khung”, không claim adaptive.
- Có cite arXiv:2504.11168 (bypass guardrails) — chỉ dùng nếu metadata khớp.

NHIỆM VỤ

1) METRIC HYGIENE (chuẩn học thuật)
   - TPR có luôn đi kèm FPR / confusion matrix không?
   - Có overclaim “precision hoàn hảo / vá mạo danh / SOTA” không?
   - Diễn giải TPR 100% qwen vs Stop-before-LLM 81.5%: có trung thực không?
   - Exfil: confounded vs clean-canary demo vs DLP 0% — framing có tách lớp không?
   - Hard benign + FPR 0% synthetic: có cảnh báo non-generalization không?

2) METHODOLOGY
   - A/B config (rule vs semantic vs hermes) có apples-to-apples không?
   - Held-out / unit boundary tests: báo cáo có nhầm “proof of generalization”
     với “regression probes” không?
   - Overfitting / p-hacking risk trên cùng 425 case: có được thảo luận không?
   - Holdout v2 chưa chạy: hạn chế đã đủ chưa?

3) ACADEMIC FRAMING & LITERATURE
   - Lab PoC vs production claim.
   - “inspired-by” garak/PyRIT/InjecAgent vs “đã chạy full suite tool”.
   - Citation: flag bịa / sai metadata; không yêu cầu đọc full PDF nếu note
     “chưa đọc toàn văn” đã có.
   - Related work / OWASP mapping có thổi phồng không?

4) CẤU TRÚC BÁO CÁO
   - Chương 4 có trả lời được câu hỏi nghiên cứu (nếu có ở Mở đầu) khớp số không?
   - Hạn chế + Kết luận: đủ trung thực cho đồ án đại học không?
   - Lỗi trình bày ảnh hưởng claim (bảng/hình lệch số, caption mâu thuẫn).

5) ĐẦU RA (Markdown, tiếng Việt hoặc Anh — nhất quán một ngôn ngữ)
   - Verdict methodology: PASS | PASS-with-fixes | REVISE.
   - Bảng claim học thuật: claim | vấn đề | mức (Critical/Major/Minor) | sửa đề xuất.
   - 5–10 câu “cách nói lại cho trung thực” (rewrite snippets) cho chỗ overclaim.
   - Điểm mạnh phương pháp (ngắn).
   - KHÔNG bịa số liệu; thiếu bằng chứng → NOT VERIFIABLE.
   - KHÔNG phán “đồ án đạt/không đạt” thay giảng viên; chỉ methodology gate.

RÀNG BUỘC: synthetic lab only; no holdout; no latency percentiles; AGENT_RULES
no fake citations/benchmarks.
```

---

## C. Prompt ngắn (nếu chỉ paste 1 lần, cả hai)

Dùng khi cửa sổ context hẹp — vẫn tách vai trò trong cùng tin:

```text
Bạn là auditor độc lập. Đọc baocaodot2_fixed (báo cáo) + nếu có:
docs/evaluation/phase13-p2-normalize-output-dlp.md và metrics.json
(ac64cd5c, 49d474bc).

Code X focus: artifact match, security residual, demo tái lập.
Gemini focus: metric hygiene (TPR+FPR), overclaim, methodology, citations.

Số neo (phải verify): rule TPR 81.5%/FPR 0%; qwen TPR 100%/FPR 18.7% nhưng
Stop-before-LLM cả hai 81.5% (TPR 100% qwen ≠ input recall); injecagent rule
47.4%; PyRIT 100% = template family. Lab PoC, no holdout, no p50/p95.

Output: verdict PASS|PASS-with-fixes|REVISE + bảng claim/evidence + fix list.
Không bịa số; không self-approve dự án.
```

---

## D. Checklist người gửi (trước khi paste)

- [ ] Đính `baocaodot2_fixed.zip` (bản in/PDF nếu có, hoặc cả folder tex).  
- [ ] Nếu Code X: đính thêm 2–3 `metrics.json` + `phase13-p2-normalize-output-dlp.md`.  
- [ ] Nêu rõ: worktree có thể dirty (normalize) so với zip build lúc `3:13 PM` —  
      **nếu zip cũ hơn P2 numbers trong chap4 worktree, bảo auditor dùng zip làm source of truth
      cho “báo cáo nộp” và flag lệch với artifact mới.**  
- [ ] Yêu cầu ghi file kết quả:  
  `docs/reviews/codex-baocaodot2-fixed-audit.md`  
  `docs/reviews/gemini-baocaodot2-fixed-methodology-audit.md`  
  (hoặc paste vào chat rồi bạn lưu).

### Cảnh báo đồng bộ zip

`baocaodot2_fixed.zip` (LastWrite ~ 2026-08-12 15:13) có thể **chưa** chứa bản Ch4
P2 mới nhất trong worktree. Khi giao audit:

1. **Hoặc** rebuild zip từ `bao_cao_latex_dot2/` hiện tại rồi gửi lại;  
2. **Hoặc** ghi rõ trong prompt: “Audit đúng **file zip đính kèm**; liệt kê chỗ
   zip lệch artifact P2 nếu có.”
