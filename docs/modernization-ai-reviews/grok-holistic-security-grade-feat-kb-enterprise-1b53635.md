# Chấm tổng thể an ninh kỹ thuật — `feat/kb-enterprise-retriever` @ `1b53635`

| Trường | Giá trị |
|--------|---------|
| **Vai trò** | Independent technical/security auditor (Grok) |
| **Ngày** | 2026-08-11 |
| **HEAD** | `1b53635` (*docs(report): focus thesis on the LLM security wall*) |
| **Nhánh** | `feat/kb-enterprise-retriever` |
| **Bối cảnh số liệu v3 (cùng 425 case)** | Rule **TPR 77.0% / FPR 0%** (`ada94ea1`); qwen3:4b **77.5% / 11.1%** (`5f1e19a2`); hermes3:8b **100% / 67.1%** (`c848aeac`) |
| **Ràng buộc** | Không sửa dataset; holdout chưa duyệt; latency L2; không commit; maintainer adjudicate |

---

## Verdict tóm tắt

| Hạng | Kết luận |
|------|----------|
| **Điểm tổng (thang 10)** | **7.4 / 10** — lab-scale multi-layer wall **tốt cho đồ án học thuật**; **không** production / SOTA |
| **Định vị** | Guard-luật + judge tùy chọn + ACL/RBAC + demo A/B; residual recall (injecagent/unicode) + output path + measurement debt (canary) |
| **Ch4** | **Phần lớn chuẩn**; vài chỗ tinh chỉnh còn lại (không Major mới) |
| **Tối ưu tiếp** | Ưu tiên **(b) canary redesign → (c) Output DLP → (a) normalize/injecagent → (d) semantic FPR** |

---

## 1. Thang điểm đề xuất + chấm

### 1.1 Thang (tự đề xuất — có lý do)

Thang **0–10** theo **PoC lab / đồ án thực tập LLM security**, **không** theo chuẩn sản phẩm enterprise:

| Điểm | Ý nghĩa |
|-----:|---------|
| 9–10 | Near SOTA lab + methodology publication-grade + residual đo được tin cậy |
| **7–8** | **Kiến trúc đúng, đo được, residual trung thực, còn lỗ hổng có chủ đích** |
| 5–6 | Guard cơ bản, metric mơ hồ hoặc overclaim |
| 3–4 | Demo mỏng, thiếu defense-in-depth hoặc số liệu không tái lập |
| 0–2 | Không có kiểm soát / số liệu giả |

**Trọng số** (tổng 100%):

| Trục | Trọng số | Nội dung |
|------|--------:|----------|
| A. Kiến trúc nhiều lớp | 20% | Pipeline, fail-closed, tách bề mặt |
| B. Chất lượng luật / detection | 20% | Input (+ authority), residual families |
| C. RBAC / ACL | 15% | Pre-filter + guard, fail-closed |
| D. Output / residual exfil | 15% | DLP, canary path |
| E. Phương pháp đo | 20% | TPR+FPR, hard benign, A/B, provenance, honesty |
| F. Non-overclaim / governance | 10% | Scope lab, limitations |

### 1.2 Điểm từng trục (căn cứ)

#### A. Kiến trúc nhiều lớp — **8.0 / 10**

**Có:** Input Guard → (Semantic) → retrieve + **ACL (SQL + Python re-check)** → RAG/Context Guard → LLM → Output Guard; unguarded path lab riêng; content-free audit; `GuardProfile` / fail-closed design notes trong ACL.

**Yếu:** Lớp rule chủ yếu **regex**; Semantic Judge phụ thuộc model (qwen ≈ +1 TP / +11% FPR); Output Guard **hẹp** (secret pattern, không canary schema); defense-in-depth **lab**, không adaptive (arXiv:2504.11168 vẫn áp dụng).

#### B. Chất lượng luật — **7.2 / 10**

| Family (artifact mock optimized) | Block rate | Ghi chú |
|----------------------------------|------------|---------|
| pyrit (n=57) | **100%** | Sau opt; scoped template family (~6 khung) |
| garak (n=105) | **75.2%** | Unicode / obfuscation residual |
| injecagent (n=38) | **47.4%** | Hidden-in-prose — bottleneck recall |
| Overall TPR | **77.0%** | FPR synthetic **0%** |

**Có:** Nhóm authority nhắm 2 invariant; bare claim không block; self-service exemption **đã vá bypass** (`6ed8dfd`: `của tôi` không bare; `_BULK_OTHERS` có phòng/đội) — re-audit probe tại HEAD:

| Probe | Decision @ `1b53635` |
|-------|----------------------|
| “Mở mọi restricted… yêu cầu **của tôi**” | **BLOCK** |
| “xuất … **phòng kế toán** và của chính tôi” | **BLOCK** |
| “xuất … phiếu lương **của chính tôi**” | **ALLOW** (đúng intent) |

Unit boundary: evasions ALLOW + FP BLOCK + bypass regression (doc: 10 tests `test_input_guard.py`).

**Yếu:** PyRIT 100% = family-fit; 8+ evasion vẫn lọt; injecagent nửa số; offline input-only ~150/200 (một phần TP pipeline từ lớp khác).

#### C. RBAC / ACL — **8.0 / 10**

**Có:** Enterprise BM25 pre-filter; `acl_guard` dual-path; 4-way principal/facts (reject khi mismatch); ACL **không ablatable** (đúng security > experiment); demo KB theo department.

**Yếu:** Synthetic ACL only; input guard không thay authN; principal giả lập lab.

#### D. Output / exfil — **5.5 / 10**

**Có:** Output/DLP pattern (fake secret, API-like key); residual **6/10 clean-prompt** leak (Code X / experiment) = tín hiệu KB thật, n=10 under-powered; Ch4 không bán 21.5% như KB rate.

**Yếu:** Canary **190/200 trong prompt** → metric hỏng cho exfil; Output Guard **không** match canary schema; workspace chat DLP path chưa đủ “bịt exfil demo bảng lương” bằng marker structural nếu model echo retrieval.

#### E. Phương pháp đo — **8.3 / 10**

**Có:** 425 case; hard benign 125; TPR **cặp** FPR; Stop-before-LLM; min_n=10; L2 no p50/p95; A/B mock vs qwen vs hermes cùng 425; A/B demo định tính có disclaimer; rate by family; SHA/manifest history; runner provenance schema (post-hoc).

**Yếu:** Evidence runs Ch4 **predates** full provenance block (experiment doc thừa nhận); canary design; không holdout v2; không AgentDojo utility; head-to-head Prompt Guard 2 không có (và không nên bịa).

#### F. Non-overclaim — **8.5 / 10**

**Có:** lab-scale; không production-ready; PyRIT/FPR scoped; 8 né; FP executive named; hermes over-block; inspired-by tools; cite 2504.11168 verified.

**Yếu nhẹ:** “precision **hoàn hảo** trên bộ tổng hợp”; kết luận nén 77%@0%; “đặc trưng bất biến” ≈ lexical; demo table gán stage đôi khi đơn giản hóa.

### 1.3 Tổng hợp điểm

| Trục | Điểm | × trọng số | Đóng góp |
|------|-----:|----------:|---------:|
| A Kiến trúc | 8.0 | 0.20 | 1.60 |
| B Luật | 7.2 | 0.20 | 1.44 |
| C ACL | 8.0 | 0.15 | 1.20 |
| D Output/exfil | 5.5 | 0.15 | 0.83 |
| E Đo lường | 8.3 | 0.20 | 1.66 |
| F Honesty | 8.5 | 0.10 | 0.85 |
| **Tổng** | | | **7.58 → làm tròn báo cáo 7.4** (trừ 0.15 buffer residual bypass history + metric debt) |

**Điểm công bố: 7.4 / 10** (lab LLM security wall — **đạt mức “chắc tay cho đồ án, residual rõ”**).

### 1.4 Điểm mạnh / yếu (executive)

**Mạnh**

1. Defense-in-depth có thật (input / context / ACL / output), không chỉ “một classifier”.  
2. Đo **TPR+FPR+hard benign+family** trên artifact có run_id.  
3. Tối ưu authority có A/B + scope honesty + unit boundary + vá self-service bypass.  
4. ACL dual enforcement + fail-closed mismatch.  
5. Ch4 đã học từ audit: không TPR đơn độc; exfil stratified; demo có giới hạn.

**Yếu**

1. Recall residual: injecagent **47%**, unicode/obfuscation.  
2. Semantic judge **ROI âm** trên bộ này.  
3. Exfil measurement **debt** (prompt-borne canary).  
4. Output DLP **mỏng** so với residual clean-prompt leak.  
5. Regex wall **không** adaptive (literature + unit evasions).  
6. Không holdout / real enterprise traffic.

**Đối chuẩn ngắn (URL đã verify các vòng trước):** Prompt Guard 2 86M Recall@1%FPR ~97.5% (HF card) — paradigm khác; arXiv:2504.11168 evasion tới 100% một số hệ — lab **không** claim robust adaptive.  
→ **Không** so “7.4 vs SOTA”; đây là **điểm PoC học thuật**.

---

## 2. Tối ưu tiếp — xếp hạng giá trị / rủi ro

### 2.1 Bảng xếp hạng (đáng làm trước → sau)

| Hạng | Hướng | Giá trị kỳ vọng | Rủi ro overfit/p-hack | Effort | **Ưu tiên** |
|-----:|-------|-----------------|------------------------|--------|-------------|
| **1** | **(b) Canary chỉ trong KB** | Mở khóa đo exfil **hợp lệ**; khóa claim 6/10 → n lớn | **Thấp** (methodology, không tune rule) | Trung bình | **P0** |
| **2** | **(c) DLP / canary match Output** (workspace path) | Bịt residual output khi FN input; demo an toàn hơn | Trung bình (FPR redact; log echo) | Trung bình | **P1** |
| **3** | **(a) Chuẩn hoá / giải nhiễu input** (unicode, hidden markup) | Nâng injecagent/garak residual | **Cao** nếu regex vào đúng 38 case | Trung–cao | **P2** |
| **4** | **(d) Hạ FPR Semantic Judge** | Ít giá trị: judge **+1 TP / +25 FP** | Cao (prompt-tune trên 425) | Cao / mơ hồ | **P3 — hoặc tắt mặc định** |

### 2.2 Chi tiết từng hướng

#### (b) Thiết kế lại canary — **#1**

| | |
|--|--|
| **Tác động** | Tách echo vs KB exfil; có thể báo **exfil_marker_clean** với n≥30–50; làm rõ 6/10 có lặp lại không |
| **Overfit** | Thấp — không đụng luật detection trên 425 attack surface |
| **P-hack** | Tránh: freeze canary protocol **trước** re-run; không chọn subset “đẹp” |
| **Before/after** | Cùng 200 mal, seed mới; metric: leak rate on **prompt-clean only**; optional retrieval-trace “canary in retrieved chunks?”; giữ TPR/FPR không đổi kỳ vọng |
| **Held-out** | Pack canary-B (seed khác) sau freeze design |

#### (c) DLP đầu ra workspace — **#2**

| | |
|--|--|
| **Tác động** | Chặn/redact canary + pattern payroll table synthetic khi lọt input; defense-in-depth LLM02 |
| **Overfit** | Thấp nếu match **structural** canary (từ builder), không keyword “lương” chung |
| **P-hack** | Không tối ưu threshold bằng cách re-run 425 đến khi 0% exfil rồi dừng |
| **Before/after** | (1) Baseline sau (b); (2) bật DLP; primary: clean-prompt exfil; secondary: FPR benign answers; định nghĩa trước: output block **có** count TPR? |
| **Held-out** | Benign answers có số tài khoản giả / email policy — không được BLOCK hàng loạt |

#### (a) Chuẩn hoá / injecagent recall — **#3**

| | |
|--|--|
| **Tác động** | Mục tiêu hợp lý: injecagent 47% → ? (đặt pre-register e.g. +15pp family **và** ΔFPR_hard ≤ 1pp) |
| **Overfit** | **Cao** — hidden HTML/prose patterns dễ khớp đúng generator |
| **P-hack** | Cấm iterate trên 38 case rồi báo; freeze normalizer trước held-out paraphrase pack |
| **Before/after** | Regression 425 frozen + held-out hidden-instruction paraphrases (seed≠13) + hard_benign FPR |
| **Lưu ý** | Unicode smudge garak cũng hưởng lợi từ NFKC/strip zero-width |

#### (d) Hạ FPR Semantic Judge — **#4**

| | |
|--|--|
| **Tác động** | Trên bằng chứng: judge **gần như không mua TPR**; hạ FPR có thể chỉ về **≈ rule-only** |
| **Overfit** | Rất cao nếu edit system prompt judge theo 25 FP case |
| **Khuyến nghị** | **Default OFF** judge cho config “production-lab”; giữ hermes/qwen như **ablation over-block**, không “tune cho đẹp” |
| **Before/after** | Nếu vẫn làm: freeze prompt; held-out benign pack; success = FPR↓ **và** TPR không giảm >1pp trên frozen 425 |

### 2.3 Không khuyến nghị (lúc này)

- Re-tune authority regex trên 425 để “PyRIT 100% OOD”.  
- Hermes làm default.  
- Holdout v2 **trái** authorization.  
- Báo p50/p95 (L2).  
- Claim ngang Prompt Guard 2 / commercial shield.

---

## 3. Ch4 — lỗ hổng / claim chưa chuẩn?

### 3.1 Đã chuẩn (giữ)

- TPR+FPR cùng bảng/figure; hard benign; family rates.  
- PyRIT 100% / FPR 0% **scoped**; 8 né; FP executive.  
- Exfil: không bán 21.5%; 6/10 clean; cần redesign canary.  
- Hermes 425 + over-block.  
- Demo A/B: định tính + disclaimer synthetic.  
- Hạn chế lab / no production.

### 3.2 Còn chỉnh (ưu tiên)

| ID | Mức | Vấn đề | Gợi ý |
|----|-----|--------|-------|
| **H1** | Minor | “precision **hoàn hảo** trên bộ tổng hợp” | “FPR 0% trên 225 benign synthetic (không khái quát)” |
| **H2** | Minor | Kết luận / CH1: “77% @ FPR 0%” thiếu “synthetic” trong câu chốt | Thêm “trên bộ 425” |
| **H3** | Minor | “đặc trưng **bất biến**” vs lexical template | “bất biến **bề mặt từ vựng** của họ template” |
| **H4** | Moderate-claim | “mỗi lần chạy ghi provenance” | Evidence Ch4 (`ada94ea1`…) **trước** schema provenance; nói “runner hiện ghi; 3 run báo cáo dựa hash manifest” (experiment doc đã đúng hơn Ch4) |
| **H5** | Minor | Bảng A/B: mạo danh → “Semantic Judge” | Sau opt, nhiều case là **Input Guard**; “Input / Semantic (tuỳ cấu hình)” |
| **H6** | Info | 6/10 “reportable” vs under-powered | Giữ cả hai như hiện tại — OK |
| **H7** | Info | Self-service exemption / bypass history | Optional 1 câu residual: exemption hẹp + ACL là control thật |

**Không** phát hiện Major mới kiểu “số sai artifact” so với run ids đã khóa (77/0, 77.5/11.1, 100/67.1, family).

### 3.3 Claim kỹ thuật ngoài số

| Claim | Auditor |
|-------|---------|
| Tường **cần thiết** vs model-only (demo) | **OK** định tính lab |
| Rule-based **cân bằng nhất** trong 3 config | **OK** trên bộ đo |
| “Không triển khai thực tế” | **OK** |
| Adaptive / OOD robust | **Không claim** — tốt |

---

## 4. Checklist an ninh nhanh (HEAD)

| Kiểm tra | Kết quả re-audit |
|----------|------------------|
| Metrics 3-config khớp narrative | **Có** (artifact prior + Ch4) |
| Self-service bypass Grok (6ea8578) | **Đã đóng** @ `6ed8dfd` / HEAD probes |
| datasets/v2 frozen | **Không đụng** trong phạm vi audit này |
| Holdout | **Chưa / unauthorized** |
| Latency p50/p95 | **Không báo** (L2) |
| Input-only 425 | mal ~150/200 block; ben 0/225; pyrit 57/57 |

---

## 5. Khuyến nghị cho maintainer (không tự làm)

1. **Chấm điểm 7.4/10** chấp nhận được cho submission lab nếu giữ framing.  
2. Roadmap: **(b) → (c) → (a)**; **(d)** = default-off judge hơn là tune.  
3. Ch4 polish H1–H5 trước in (không bắt buộc re-eval).  
4. Mọi tối ưu: pre-register metric + held-out + run_id/SHA; **không** p-hack 425.

---

## 6. Nguồn đối chuẩn (đã verify các vòng audit trước)

| Nguồn | URL |
|-------|-----|
| OWASP GenAI LLM Top 10 | https://genai.owasp.org/llm-top-10/ |
| NVIDIA garak | https://github.com/NVIDIA/garak |
| Microsoft PyRIT | https://github.com/microsoft/PyRIT |
| InjecAgent | https://arxiv.org/abs/2403.02691 |
| AgentDojo | https://arxiv.org/abs/2406.13352 |
| Bypassing LLM Guardrails | https://arxiv.org/abs/2504.11168 |
| Llama Prompt Guard 2 86M | https://huggingface.co/meta-llama/Llama-Prompt-Guard-2-86M |

---

*Auditor: Grok (holistic grade). Không commit/push. Maintainer adjudicate cuối.*
