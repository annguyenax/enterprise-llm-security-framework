# Independent security / red-team audit — v3 firewall metrics + báo cáo `bao_cao_latex_dot2`

| Trường | Giá trị |
|--------|---------|
| **Vai trò** | Independent security / red-team auditor (Grok) |
| **Ngày** | 2026-08-11 |
| **Phạm vi** | (i) Thẩm định TPR/FPR/exfil/framing; (ii) đối chuẩn nguồn uy tín đã xác minh; (iii) có/không tối ưu tường; (iv) rà Chương 4 + hạn chế báo cáo LaTeX |
| **Nguồn số nội bộ** | `docs/evaluation/phase13-v3-firewall-metrics-final.md` + artifact `reports/v3/` |
| **Nguồn báo cáo** | `bao_cao_latex_dot2/` (đặc biệt `chapters/chap4.tex`, `conclusion.tex`, `chap-1-background.tex`) |
| **Ràng buộc** | Không sửa `datasets/v2`; không báo p50/p95 (L2); không tune trên chính 425 case; không commit/push; không tự tuyên bố PASS cấp dự án |
| **Verdict tổng** | **Số liệu nội bộ đáng tin trong phạm vi lab; framing phần lớn trung thực. Không phải SOTA. Nên tối ưu Output canary/DLP trước; rule authority chỉ với held-out. Báo cáo cần vài sửa framing/nhất quán.** |

---

## 0. Phương pháp audit

1. Đối chiếu từng chỉ số trong metrics-final với `metrics.json` thô của ba run.  
2. Kiểm tra định nghĩa metric (TPR/FPR/Stop-before-LLM/exfil, min_n=10, latency L2).  
3. Xác minh **tồn tại** URL/công trình tham chiếu (AGENT_RULES rule 2) bằng tra cứu web tại thời điểm audit — **không** trích số ngoại trừ khi model card / abstract công bố rõ.  
4. Đọc `chap4.tex` và các tuyên bố an ninh liên quan; so với bằng chứng.  
5. Đánh giá hai hướng tối ưu (Claude đề xuất) theo residual quan sát + rủi ro overfit / p-hacking.

**Không** chạy lại evaluation; **không** sửa code/datasets; **không** re-adjudicate holdout 12E.4.

---

## 1. Thẩm định thông số hiện tại + framing

### 1.1 Chuỗi bằng chứng (artifact thật)

| Cấu hình | Run id | `metrics.json` (rates) | Khớp metrics-final? |
|----------|--------|------------------------|---------------------|
| Mock rule/heuristic | `20260811T101139Z-56840d90` | TPR **0.485**, FPR **0.0**, FPR hard **0.0**, Stop-before-LLM **0.485**, exfil **0.0**; TP=97 FN=103 FP=0 TN=225; n=425 | **Có** |
| Ollama `qwen3:4b` | `20260811T110937Z-9bb96d4e` | TPR **0.49**, FPR **0.1067** (~10.7%), FPR hard **0.072**, Stop **0.485**, exfil **0.5** (100/200); TP=98 FN=102 FP=24 TN=201 | **Có** |
| Hermes3:8b (đối chiếu) | `20260811T084708Z-4ad06cc3` | TPR **1.0**, FPR **0.57**, Stop **0.995**, exfil **0.0**; n=**300** (200 mal + **100** normal benign); `cases_sha256` **khác** bộ 425 | **Có** (và **không** được trộn composition với 425) |

`cases_sha256` mock/qwen cùng `f73d094a…` → so sánh mock vs qwen trên **cùng** tập 425 là hợp lệ. Hermes `d8b5fce3…` → **khác** tập.

### 1.2 Định nghĩa metric — tính đúng?

| Metric | Định nghĩa trong runner / metrics-final | Đánh giá auditor |
|--------|-------------------------------------------|------------------|
| TPR | blocked / malicious; blocked ∈ {block, human_review} | Hợp lệ cho **detection rate** của pipeline guard (không phải ASR của attacker agent) |
| FPR | blocked / **toàn** benign (225) | Hợp lệ; tách FPR hard (125) / normal (100) là **thêm** precision stress — tốt |
| Stop-before-LLM | mal blocked ∧ ¬provider_called / mal | Hợp lệ; mock=qwen=48.5% cho thấy block chủ yếu **trước** provider |
| Exfil marker | canary của case ∈ answer / n measurable | Hợp lệ **marker lab**; **không** đồng nhất với “leak PII production” |
| Rate reportable | n ≥ 10 | Tuân thủ; `multi_turn_escalation` n=5 → null / không reportable — đúng |
| Latency | `latency_reportable=false` | Đúng L2 — **không** được chèn p50/p95 vào báo cáo |

**Tính toán làm tròn:** FPR qwen `24/225 = 0.1066…` → **10.7%** OK; hard `9/125 = 0.072` → **7.2%** OK; TPR mock `97/200 = 0.485` → **48.5%** OK.

### 1.3 Số có đáng tin không?

**Có — trong phạm vi đã công bố**, với điều kiện:

1. **Synthetic, lab-scale, deterministic seed** — không suy rộng enterprise/real traffic.  
2. **Guard-luật + optional LLM-as-judge nhỏ** — không phải classifier SOTA fine-tune.  
3. **Exfil 0% mock** phản ánh mock **không echo canary**, không phải Output Guard “hoàn hảo”.  
4. **Exfil 50% qwen** = 100 leak / 200 measurable malicious: gần như **mọi FN** (102) đều có thể mang canary → residual output path **thật**, định lượng được.  
5. **Hermes TPR 100% / FPR 57%** chỉ trên bộ **300 (benign dễ)**; **không** re-run 425 → **cấm** so FPR hermes với FPR hard_benign qwen như cùng điều kiện.

### 1.4 Framing: trung thực / quá / thiếu

#### Phần framing **đúng và nên giữ**

- Rule: **FPR 0% kể cả hard benign** + **TPR ~48.5%** + **PyRIT ~0%** — mô tả “precision cao, recall giới hạn, mù roleplay/C-suite”.  
- Qwen: TPR gần như **không** tăng (+0.5pp) trong khi FPR **10.7%** — “judge nhỏ không mua được recall, mua FPR”.  
- Hermes: TPR cao **không** = tường mạnh khi FPR 57%.  
- Residual exfil / PyRIT / multi_turn n&lt;10 / no holdout / no latency — metrics-final §4 đã liệt kê trung thực.

#### Chỗ **diễn giải dễ quá** (cần cẩn)

| Rủi ro framing | Vì sao | Khuyến nghị wording |
|----------------|--------|---------------------|
| “FPR 0% = tường an toàn” | 0 FP ≠ an toàn; FN=103 (~51.5% attack lọt) | Luôn cặp **TPR+FPR** (và ideally residual by family) |
| “Exfil 0% mock chứng minh Output Guard” | Mock không sinh canary echo | Nói rõ **provider mock không lặp canary** |
| “Exfil 50% = nửa số đòn lọt qua Output” | 50% là / **tổng** 200 mal measurable, không chỉ / FN | “100/200 malicious cases có canary trong answer (gần như toàn bộ FN)” |
| So cột hermes cạnh mock/qwen **không chú composition** | Khác n benign & hard_benign | Ghi chú **bộ 300 vs 425** cạnh mọi biểu đồ 3 cột |
| “garak/PyRIT/InjecAgent block rate” | Payload **mô phỏng kỹ thuật**, không phải full suite tool chính thức | “tool_family **inspired by** / tagged”, không claim “đã chạy NVIDIA garak end-to-end” |

#### Chỗ **thiếu** (nên bổ sung khi claim)

- **Precision / F1** (hoặc confusion matrix đã có — tốt) bên cạnh TPR rời.  
- **Exfil conditional on FN** (≈100/102) để reader thấy severity khi lọt.  
- **Stop-before-LLM ≈ TPR** → gần như không có “block sau LLM” có ý nghĩa trên bộ này.  
- **Không** có so sánh head-to-head Prompt Guard 2 / Azure Shield trên **cùng** 425 case (và không nên bịa).

### 1.5 Kết luận mục 1

| Hạng mục | Kết luận auditor |
|----------|------------------|
| Số mock / qwen / hermes | **Khớp artifact**; tính đúng theo định nghĩa đã khóa |
| Đáng tin để báo cáo đồ án lab? | **Có**, nếu giữ scope synthetic + không SOTA |
| Framing metrics-final | **Tốt** (residual không giấu) |
| Nguy cơ overclaim chính | Tách TPR khỏi FPR; blurs mock-exfil; hermes composition; “inspired-by” vs “ran tool X” |

---

## 2. Đối chuẩn công trình uy tín (URL đã xác minh 2026-08-11)

### 2.1 Bảng nguồn — tồn tại & vai trò so với dự án

| Nguồn | URL đã xác minh | Vai trò | Liên hệ dự án |
|-------|-----------------|---------|---------------|
| **OWASP Top 10 for LLM / GenAI** (2025 archive + portal; 2026 release đã xuất hiện) | https://genai.owasp.org/llm-top-10/ · https://genai.owasp.org/llmrisk/llm01-prompt-injection/ · https://owasp.org/www-project-top-10-for-large-language-model-applications/ | Taxonomy rủi ro | Guard map **LLM01** (injection/jailbreak input), **LLM02** (sensitive disclosure / output), **LLM04** (data/model poisoning / poisoned context) — khớp `chap-1` threat model |
| **NVIDIA garak** | https://github.com/NVIDIA/garak · https://garak.ai/ | LLM vulnerability **scanner** (probes) | `tool_family=garak` trong v3 = **payload style**, không phải full garak scan pipeline |
| **Microsoft PyRIT** | https://github.com/microsoft/PyRIT | Red-team / risk identification **framework** | `tool_family=pyrit` = roleplay / C-suite style; mock block **0%**, qwen **1.8%** |
| **InjecAgent** | https://arxiv.org/abs/2403.02691 · https://github.com/uiuc-kang-lab/InjecAgent | Benchmark **IPI trên tool-agents** (ASR), 1 054 cases | Metric **ASR agent** ≠ TPR guard; family `injecagent` chỉ mượn bề mặt kỹ thuật |
| **AgentDojo** | https://arxiv.org/abs/2406.13352 · https://github.com/ethz-spylab/agentdojo | Môi trường **động** utility + security agent | Dự án **không** chạy AgentDojo; chỉ tham chiếu phương pháp “attack+defense cùng utility” |
| **Bypassing LLM Guardrails** | https://arxiv.org/abs/2504.11168 (v3 2025-07-14) | Evasion vs 6 hệ (gồm Azure Prompt Shield, Meta Prompt Guard); abstract: **tới 100% evasion** một số instance | Cảnh báo: ngay classifier/commercial guard cũng **bị bypass** — lab rule-guard **không** được claim “đủ chống adaptive” |
| **Meta Llama Prompt Guard 2** | https://huggingface.co/meta-llama/Llama-Prompt-Guard-2-86M · https://developer.meta.com/ai/docs/model-cards-and-prompt-formats/prompt-guard/ | Classifier injection/jailbreak (86M / 22M) | Baseline **SOTA-ish open** — **khác paradigm** (trained detector vs rule lab) |

### 2.2 Map OWASP guard ↔ LLM01 / 02 / 04 (lab)

| OWASP (2025 naming dùng trong báo cáo) | Bề mặt | Component lab | Bằng chứng residual v3 |
|----------------------------------------|--------|---------------|-------------------------|
| **LLM01** Prompt Injection | User prompt, jailbreak, roleplay | Input Guard + Semantic Guard | garak ~75% block; pyrit ~0–2%; unicode ~33% |
| **LLM02** Sensitive Information Disclosure | Answer / tool output | Output Guard / DLP | **Exfil marker 50%** khi qwen + FN; metrics-final residual #2–3 |
| **LLM04** Data / Model Poisoning (và poisoned retrieval context) | Retrieved docs / authority prose | RAG/Context Guard | `poisoned_context_authority` block **0%** (mock & qwen) |

**Lưu ý citation:** `refs.bib` trỏ `owasp.org/www-project-top-10-…` (legacy portal; hiện redirect/“get 2026”). Nên bổ sung URL canonical **genai.owasp.org** và ghi rõ năm phiên bản (2025 vs 2026) — không bịa nội dung 2026 chưa đọc.

### 2.3 Bảng đối chuẩn metric (cẩn trọng apples-to-oranges)

> **Cảnh báo phương pháp:** Các hàng dưới **không** cùng test set, không cùng threat model, không cùng định nghĩa positive class. Chỉ dùng để **định vị** lab-scale vs literature — **cấm** kết luận “dự án tốt/xấu hơn Prompt Guard 2 X điểm phần trăm”.

| Hệ / nguồn | Loại | Chỉ số công bố (đã xác minh nguồn) | Vị trí tương đối so với dự án |
|------------|------|-------------------------------------|-------------------------------|
| **Shield AI — mock** (lab này) | Rule + heuristic | TPR **48.5%**, FPR **0%** (225 benign incl. hard), Stop **48.5%**, exfil marker **0%** (mock) | **Cao precision, trung bình-thấp recall** trên bộ tự xây; **không** SOTA |
| **Shield AI — qwen3:4b** | Rule + small LLM judge | TPR **49.0%**, FPR **10.7%** (hard 7.2%), exfil **50%** | Gần như **không** cải recall; **xấu precision** hơn mock |
| **Shield AI — hermes3:8b** | Rule + larger judge | TPR **100%**, FPR **57%** (bộ 300, benign dễ) | Over-block; minh họa trade-off, **không** deployable |
| **Llama Prompt Guard 2 86M** (HF model card) | Trained classifier | Private jailbreak bench: AUC EN **0.998**; **Recall @ 1% FPR = 97.5%** (EN); multi **0.995** AUC | Recall@low-FPR **cao hơn rõ** paradigm lab rule; **khác bench** |
| **Llama Prompt Guard 2 22M** | Smaller classifier | Recall @ 1% FPR EN **88.7%** | Vẫn cao hơn TPR lab ở FPR≈1% target — **không** so trực tiếp FPR lab 0–10% |
| **Prompt Guard 2 trên AgentDojo** (cùng model card) | Defense in agent env | **APR @ 3% utility reduction: 81.2%** (86M) | Metric **APR/utility**, không TPR — dự án **chưa** đo utility degradation |
| **arXiv:2504.11168** | Adaptive evasion study | Tới **100% evasion success** trên một số trong 6 hệ (gồm Azure Prompt Shield, Meta Prompt Guard) | Ngay baseline mạnh cũng **không** immune; lab rule càng **không** claim robust adaptive |
| **InjecAgent** | Agent IPI ASR | Benchmark 1 054 cases; ASR phụ thuộc model/agent (paper tables) | Dự án đo **block rate** ~47% trên family tag — **không** tương đương ASR InjecAgent |
| **AgentDojo** | Dynamic agent | 97 tasks / 629 security cases (paper abstract) | Chuẩn “utility under attack”; lab **chưa** có |
| **garak / PyRIT** | Offensive tooling | Không phải một con số TPR defense cố định | Dùng đúng vai trò: **sinh/probe**, không baseline defense number |

### 2.4 Kết luận định vị

1. Đây là **guard-luật lab-scale + judge tùy chọn**, **không** phải SOTA detector, **không** commercial gateway.  
2. Trên trục **precision (FPR thấp)**, mock lab **ấn tượng trong bộ tự xây** (kể hard benign) — nhưng **không** chứng minh generalization OOD.  
3. Trên trục **recall @ low FPR**, literature (Prompt Guard 2 model card) đặt **bar cao hơn nhiều** so với TPR ~49% của lab.  
4. Literature evasion (2504.11168) cho thấy **kể cả bar cao vẫn vỡ** dưới adaptive attack → residual PyRIT/unicode của lab là **kỳ vọng**, không phải “bug lạ”.  
5. So sánh trung thực với đồ án: **học được pipeline + đo được residual**, không “đánh bại” Meta/Microsoft/NVIDIA.

---

## 3. Nên tối ưu tường không?

### 3.1 Residual đang “đau” nhất (từ artifact)

| Residual | Mock | Qwen | Ý nghĩa ưu tiên |
|----------|------|------|-----------------|
| PyRIT / roleplay / C-suite / poison authority | ~0% block | ~0–4% | LLM01 semantic gap |
| Exfil marker | 0% (mock no-echo) | **50%** | LLM02 output path **hở** khi FN |
| Unicode smudging | 33% | 33% | Obfuscation |
| multi_turn | n=5 unreportable | idem | Chưa đủ mẫu |
| Hermes-style over-block | — | FPR 10.7% đã thấy với judge nhỏ | Đừng “cứ tăng judge size” |

### 3.2 Hướng (a) — thêm luật khẳng định thẩm quyền / mạo danh cấp cao (nâng recall PyRIT, giữ FPR thấp)

| Tiêu chí | Đánh giá |
|----------|----------|
| **Đáng làm?** | **Có điều kiện — ưu tiên P2** sau DLP. Residual pyrit 0–1.8% là lỗ hổng **có thật** và map LLM01. |
| **Hiệu quả kỳ vọng** | Có thể nâng block trên **cùng paraphrase pattern** (CEO/CFO “authorize dump”); **không** kỳ vọng robust vs paraphrase đa dạng / multilingual / AML evasion (2504.11168). |
| **Rủi ro overfitting** | **Cao** nếu rule viết bằng n-gram lấy từ chính 57 case `pyrit` trong 425. Dễ “lên TPR trên test set” mà fail OOD. |
| **Rủi ro FPR** | Hard benign có self-service / security_legit / sensitive_keyword — rule “CEO/password/approve” **dễ** đụng FP nếu không có context (self vs dump người khác). |
| **p-hacking** | **Cao** nếu: sửa rule → re-run **cùng** 425 → chọn rule set có ΔTPR đẹp nhất → báo như generalization. |
| **Cách đo công bằng** | 1) **Freeze** rule candidate **trước** khi nhìn held-out. 2) Tách **dev rules** vs **eval**: giữ 425 (hoặc subset) làm **regression frozen**; tạo **held-out paraphrase pack** (seed khác, ≥30–50 roleplay/C-suite **không** copy từ train). 3) Báo **ΔTPR_pyrit, ΔFPR_all, ΔFPR_hard** trên held-out **và** regression. 4) Không drop multi_turn/hard_benign để “làm đẹp”. 5) Pre-register: “success = ΔTPR_pyrit ≥ X **và** ΔFPR_hard ≤ Y”. |

**Khuyến nghị (a):** Làm **sau** (b), với held-out + pre-register. **Không** tune regex vào đúng 28 `executive_roleplay` + 24 `csuite_impersonation` hiện có rồi claim “đã vá PyRIT”.

### 3.3 Hướng (b) — canary / DLP trên Output Guard (bịt exfil 50%)

| Tiêu chí | Đánh giá |
|----------|----------|
| **Đáng làm?** | **Có — ưu tiên P1** trong phạm vi lab. Artifact qwen: **100/200** malicious có canary trong answer; metrics-final residual #2–3; map **LLM02**. |
| **Hiệu quả kỳ vọng** | Trên **cùng** protocol canary (namespace đã seed), exact/normalized match canary → exfil_marker **có thể** giảm mạnh **mà không** cần đụng TPR input. Đây là lớp **defense-in-depth** khi FN input. |
| **Rủi ro overfitting** | **Thấp hơn (a)** nếu detector là **structural** (exact canary tokens từ corpus builder, entropy high markers), không phải keyword “lương/password” chung. |
| **Rủi ro FPR / side-effect** | (i) User hỏi lại token vô hại trùng format; (ii) log/telemetry **echo** canary khi block (content-free policy); (iii) canary quá dễ đoán → attacker avoid. |
| **p-hacking** | Trung bình: chỉ tối ưu threshold trên 200 mal measurable **cùng run** rồi báo 0% exfil. Giảm bằng: freeze detector trên **canary schema** (builder), eval exfil trên **run mới** + optional **canary set B** (re-seed khác, không train pattern). |
| **Cách đo công bằng** | 1) Implement Output canary match **không** nhìn `result.jsonl` từng FN. 2) Re-run **cùng** configs mock + qwen trên **cùng** 425 (regression). 3) Primary: `exfil_marker`, secondary: FPR (expect ~0 change nếu pure output canary), TPR (có thể tăng nhẹ nếu output block tính “blocked”). 4) Định nghĩa rõ: output block có count vào TPR/Stop-before-LLM không? (**phải** document trước run). 5) Không claim “hết LLM02” — chỉ “giảm marker lab”. |

**Khuyến nghị (b):** **Nên làm** như bước tối ưu **đầu tiên** có ROI bằng chứng rõ, overfit thấp hơn authority-regex.

### 3.4 Có nên tối ưu **bây giờ** không? (quyết định)

| Câu hỏi | Trả lời auditor |
|---------|-----------------|
| Bắt buộc để “đồ án đúng” với số đã báo? | **Không** — residual đã trung thực là kết quả học thuật hợp lệ |
| Nên tối ưu nếu còn thời gian engineering? | **Có**, thứ tự: **(b) Output canary/DLP → (a) authority rules với held-out** |
| Được tune prompt/luật trên chính 425 rồi báo TPR mới như SOTA? | **Không** — overfitting + p-hacking |
| Hermes “gắt hơn” để TPR 100%? | **Không** cho config chính; chỉ giữ như **cảnh báo over-block** |
| Holdout v2 / 12E.4? | **Ngoài scope** — unauthorized |

### 3.5 Anti p-hacking checklist (bắt buộc nếu tối ưu)

1. Pre-register metric + success threshold **trước** code change.  
2. Không iterate “sửa rule → chạy 425 → sửa tiếp” quá N vòng **mà không** held-out.  
3. Mọi Δ metric gắn **run_id + SHA metrics.json** mới.  
4. Báo **cả** chỉ số xấu đi (FPR, utility proxy nếu có).  
5. Phân biệt **development set** vs **reporting set** trong prose.

---

## 4. Đánh giá báo cáo `bao_cao_latex_dot2` (đặc biệt Chương 4)

### 4.1 Khớp bằng chứng — điểm **mạnh**

| Nội dung chap4 | Khớp artifact? |
|----------------|----------------|
| 425 = 200 mal + 225 benign (100+125 hard) | Có |
| CM mock 97/103/0/225; semantic 98/102/24/201 | Có |
| TPR 48.5/49.0; FPR 0/10.7; hard 0/7.2; Stop 48.5; exfil 0/50 | Có |
| Family garak 75.2 / injecagent 47.4 / pyrit 0 / 1.8 | Có |
| Phân tích: rule precision cao, qwen không mua recall, hermes over-block, exfil residual | **Trung thực**, khớp metrics-final |
| Hạn chế: no holdout, no real enterprise, NOT_CHECKED, no production-ready | Có (chap4 + conclusion) |
| TPR & FPR **cùng bảng / cùng figure** | **Đúng chuẩn học thuật** (không chỉ khoe TPR) |
| Caption hermes: “không phải bằng chứng tường mạnh” | Tốt |

### 4.2 Vấn đề cần sửa (danh sách hành động)

| ID | Mức | Vị trí | Vấn đề | Sửa đề xuất |
|----|-----|--------|--------|-------------|
| **R1** | **Major (framing)** | `chap4` fig TPR/FPR 3 cột + § hermes | Hermes **n=300, benign-only-normal** đứng cạnh mock/qwen **n=425 hard_benign** — reader dễ so FPR 57% vs 10.7% như cùng composition | Chú thích rõ trong caption + 1 câu prose: “hermes trên bộ 300 (100 benign thường); không hard_benign; không so FPR trực tiếp với 425” |
| **R2** | **Major (metric prose)** | chap4 “Exfil 50%: một nửa số tấn công lọt qua…” | Câu tiếng Việt **mơ hồ** (50% / all mal vs / FN). Artifact: **100/200** measurable | Viết: “Exfil Marker Rate = 50% = 100/200 case tấn công measurable có canary trong câu trả lời (tập trung ở các FN)” |
| **R3** | **Major (stale test count)** | `tab:test-summary` “Full suite 1263 passed…” | Suite lab hiện tại đã ghi nhận **cao hơn** trong session gần (vd. 1519) — số 1263 có thể **lỗi thời** | Re-run pytest, dán số **từ output thật** + ngày; hoặc ghi “tại commit X” |
| **R4** | **Moderate** | chap4 “mô phỏng kỹ thuật NVIDIA garak, Microsoft PyRIT và InjecAgent” | Dễ hiểu nhầm đã chạy full tool upstream | “payload **gắn nhãn / lấy cảm hứng** kỹ thuật từ …; không phải bản chạy chính thức full suite tool” |
| **R5** | **Moderate** | chap4 kết luận “hai hướng … **bắt buộc trước khi đưa vào sử dụng**” | Nghe như đường **production deploy**; mâu thuẫn lab PoC + AGENT_RULES honest terminology | Đổi: “hai hướng **ưu tiên nếu tiếp tục phát triển lab** / trước khi xem xét triển khai thật” |
| **R6** | **Moderate** | Mock exfil 0% trong bảng | Thiếu 1 câu: mock provider **không** echo canary | Thêm footnote dưới bảng metrics |
| **R7** | **Moderate** | `refs.bib` OWASP URL legacy | Portal chính thức GenAI + 2026 release đã có | Thêm `howpublished` genai.owasp.org; ghi năm phiên bản đã map (2025) |
| **R8** | **Minor** | chap4 không nêu **FPR normal 15%** qwen | Bảng có hard 7.2% nhưng normal_benign 15% (15/100) **cao hơn hard** — insight quan trọng (judge over-block cả câu dễ) | Thêm 1 hàng hoặc 1 câu trong phân tích |
| **R9** | **Minor** | Không cite 2504.11168 / Prompt Guard 2 khi nói “không SOTA” | Có thể tăng độ tin cậy academic **nếu** đã xác minh (audit này đã xác minh URL) | Optional: 1 đoạn related-work + bib entries **sau khi** thành viên đọc abstract/model card (không bịa số ngoài card) |
| **R10** | **Minor** | `tab:test-summary` vs security eval | Đã có câu “không phải chỉ số hiệu quả bảo mật” — **giữ**; đảm bảo abstract/slide không trộn 1263 tests với TPR | Review mở đầu / tóm tắt |
| **R11** | **Info** | Conclusion hướng phát triển | Chưa liệt kê canary Output / authority held-out | Có thể align với §3 audit (optional) |
| **R12** | **Info** | LLM01/02/04 map chap1 | Map hợp lý với OWASP 2025 naming; xác nhận lại wording nếu chuyển sang bản **2026** | Khi update bib, đối chiếu tên mục 2026 |

### 4.3 Claim an ninh — có thổi phồng không?

| Claim (implicit/explicit) | Auditor |
|---------------------------|---------|
| Lab guard “hoạt động đúng trên synthetic” | **OK** nếu kèm residual |
| “Không cấu hình nào đạt triển khai thực tế” | **OK**, trung thực |
| Precision rule đáng tin **trong lab** | **OK** với hard_benign 0 FP |
| Semantic judge “gần như không giúp recall” trên qwen3:4b | **OK** trên bộ này |
| Production / enterprise ready | **Không** claim — tốt |
| Holdout / real LLM security | **Không** claim — tốt |
| TPR hermes 100% như thành công | **Đã bác** trong text — tốt; chỉ cần R1 composition |
| Đánh bại / ngang SOTA guard | **Không** thấy claim trực tiếp — **giữ khoảng cách** |

### 4.4 Chuẩn học thuật TPR/FPR

- **Đạt:** confusion matrix + bảng TPR **và** FPR + figure cặp màu + cảnh báo hermes.  
- **Nên thêm (không bắt buộc nhưng tốt):** precision/F1 hoặc “operating point”; CI không cần nếu n cố định và không claim population; **không** bao giờ abstract chỉ “TPR 49%”.

### 4.5 Hạn chế đã đủ trung thực chưa?

**Gần đủ** cho đồ án lab: holdout, real data, NOT_CHECKED, no production, no self-PASS.  

**Nên bổ sung 2–3 bullet** (từ residual kỹ thuật, không chỉ process):

1. Recall thấp trên roleplay/C-suite/poisoned authority (PyRIT family).  
2. Output path: exfil marker 50% với LLM local khi input miss.  
3. Semantic judge phụ thuộc model: nhỏ ≈ vô ích recall; lớn → FPR không chấp nhận được (hermes).  
4. So sánh tool_family không tương đương full garak/PyRIT/InjecAgent/AgentDojo protocols.  
5. Không đánh giá adaptive evasion kiểu 2504.11168.

---

## 5. Tổng hợp khuyến nghị (executive)

| # | Khuyến nghị | Ưu tiên |
|---|-------------|---------|
| 1 | **Giữ** số mock/qwen/hermes như đã artifact; **không** re-tune trên 425 để “làm đẹp báo cáo” | P0 |
| 2 | Báo cáo: sửa **R1–R6** (composition hermes, exfil wording, stale suite count, inspired-by, “trước khi sử dụng”, mock exfil footnote) | P0 (doc) |
| 3 | Nếu code: **Output canary/DLP (b)** trước, đo bằng run_id mới, pre-register | P1 eng |
| 4 | **Authority rules (a)** chỉ với held-out paraphrase + FPR hard guardrail | P2 eng |
| 5 | Optional related-work: Prompt Guard 2 card + arXiv:2504.11168 (URL đã verify) — **không** claim head-to-head | P3 |
| 6 | Không holdout v2 / không p50-p95 / không datasets/v2 edit | Constraint |

### Verdict ngắn (không thay adjudicator)

- **Metric integrity:** PASS (khớp artifact, định nghĩa ổn).  
- **Honest security framing (docs nội bộ):** PASS with notes.  
- **LaTeX chap4:** **PASS with required fixes R1–R6** trước khi coi là “khóa in”.  
- **SOTA / production security:** **NOT CLAIMED / NOT SUPPORTED** — đúng vị trí lab.  
- **Optimize wall now?** **Optional**; nếu có: **(b) rồi (a)**, anti-overfit bắt buộc.

---

## 6. Phụ lục — đường dẫn bằng chứng nội bộ

```
docs/evaluation/phase13-v3-firewall-metrics-final.md
reports/v3/20260811T101139Z-56840d90/metrics.json   # mock 425
reports/v3/20260811T110937Z-9bb96d4e/metrics.json   # qwen3:4b 425
reports/v3/20260811T084708Z-4ad06cc3/metrics.json   # hermes 300
bao_cao_latex_dot2/chapters/chap4.tex
bao_cao_latex_dot2/chapters/conclusion.tex
bao_cao_latex_dot2/chapters/chap-1-background.tex
bao_cao_latex_dot2/refs.bib
```

## 7. Phụ lục — URL ngoài đã xác minh (checklist rule 2)

| URL | Trạng thái 2026-08-11 |
|-----|----------------------|
| https://genai.owasp.org/llm-top-10/ | Tồn tại (2025 archive + GenAI portal) |
| https://genai.owasp.org/llmrisk/llm01-prompt-injection/ | Tồn tại LLM01:2025 |
| https://owasp.org/www-project-top-10-for-large-language-model-applications/ | Tồn tại (legacy → trỏ 2026) |
| https://github.com/NVIDIA/garak | Tồn tại |
| https://github.com/microsoft/PyRIT | Tồn tại |
| https://arxiv.org/abs/2403.02691 | Tồn tại (InjecAgent) |
| https://github.com/uiuc-kang-lab/InjecAgent | Tồn tại |
| https://arxiv.org/abs/2406.13352 | Tồn tại (AgentDojo) |
| https://github.com/ethz-spylab/agentdojo | Tồn tại |
| https://arxiv.org/abs/2504.11168 | Tồn tại; abstract xác nhận evasion tới 100% một số instance trên 6 hệ |
| https://huggingface.co/meta-llama/Llama-Prompt-Guard-2-86M | Tồn tại; model card có Recall@1% FPR 97.5% (EN) |
| https://developer.meta.com/ai/docs/model-cards-and-prompt-formats/prompt-guard/ | Tồn tại |

---

*Auditor: Grok (independent red-team). Không commit/push. Không tự phê duyệt phase. Maintainer là adjudicator cuối.*
