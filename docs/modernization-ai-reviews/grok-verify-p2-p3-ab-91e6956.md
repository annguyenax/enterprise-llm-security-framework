# Independent verify — P2 normalize + P3 semantic default-OFF + demo A/B

| Trường | Giá trị |
|--------|---------|
| **Vai trò** | Independent technical/security auditor (Grok) |
| **Ngày** | 2026-08-12 |
| **Commit** | `91e6956` (HEAD tại audit; package P2 chính tại `e7a945c` / `7e259bd`) |
| **Phạm vi** | `_normalize`; `_llm_enabled`; Output canary; `run_demo_ab_paired.py`; Ch4 |
| **Ràng buộc** | Không datasets/v2; no holdout; no p50/p95; **không commit** |

---

## Verdict

| Hạng | Verdict | Ghi chú |
|------|---------|---------|
| **P2 normalize** | **PASS** (có residual) | De-obfuscation tổng quát; ΔTPR mock **tái lập** offline; FPR synthetic 0 |
| **P3 semantic default OFF** | **PASS** | Opt-in đúng bằng chứng ROI |
| **Demo A/B 12/18 vs 0/18** | **PASS** (artifact khớp; framing system-level) | **Không** phải same-retrieval ablation |
| **qwen 100% TPR framing Ch4** | **PASS** | Stop-before 81.5% + DLP 37 post-provider; FPR 18.7% đi kèm |
| **Tổng kỹ thuật lab (cập nhật)** | **7.6 / 10** | +0.2 vs 7.4 nhờ A/B đo được + normalize locked |

---

## 1. P2 — chuẩn hoá đầu vào

### 1.1 Có “tổng quát” không?

**Có — ở mức de-obfuscation pipeline, không phải rule per-case.**

`input_guard.py` áp dụng **mọi** prompt trước khi match:

1. `unicodedata.normalize("NFKC", …)`  
2. Strip zero-width / soft-hyphen (`U+200B/C/D`, `U+2060`, `U+FEFF`, `U+00AD`)  
3. Fold **bảng homoglyph cố định** (Cyrillic/Latin look-alikes thường gặp)

Không có nhánh “nếu case-id ∈ unicode_smudging thì …”. Unit test smudge (ZW + Cyrillic `е`/`ո`) block được — đúng design.

**Giới hạn “tổng quát” (không chặn PASS):**

- Homoglyph table **hữu hạn** (không cover full confusable Unicode).  
- Không giải HTML/comment hidden, payload split, hay injecagent prose.  
- Normalize **có thể** làm một số chuỗi “trông lạ” trở thành trigger (rủi ro FP lý thuyết) — **không** quan sát trên 225 benign synthetic (xem dưới).

### 1.2 TPR 77%→81.5%, garak 75.2%→83.8%, FPR 0% — tái lập?

| Run | TPR | FPR | garak | unicode | Nguồn |
|-----|----:|----:|------:|--------:|-------|
| Authority only `ada94ea1` | **77.0%** (154/200) | 0% | 75.24% | 33.3% | artifact |
| + normalize `ac64cd5c` | **81.5%** (163/200) | 0% | 83.81% | 63.3% | artifact |
| Offline input-only **code HEAD** trên `all.jsonl` | **163/200**, **0/225 FP** | | | | re-audit |

Δ = +9 TP = gần như unicode (+9: 10→19/30) → garak +9 (79→88). **Mock/tất định: có.**

**Lưu ý provenance:** `ac64cd5c` ghi `git_worktree_dirty=true` trên base `d65f1e3` (normalize chưa trong commit khi chạy). Code **hiện** đã commit (`e7a945c`); offline 163/0 khớp artifact → số **đáng tin**, tái lập *từ commit hiện tại* OK; người ngoài chỉ từ provenance block của run cũ thì **chưa** clean-only.

### 1.3 FP mới trên Unicode hợp lệ?

Probe re-audit (ALLOW hết):

- Tiếng Việt dấu đầy đủ (nghỉ phép, MFA).  
- Self-service “phiếu lương của chính tôi”.  
- `€` trong câu benign.  
- Cyrillic “Документ” + MFA question → ALLOW (norm đổi text nhưng không trigger rule độc).

Trên **225 benign** offline: **FP = 0**.  
**Không** chứng minh zero FP mọi Unicode OOD; trên lab set **không** thấy FP mới do normalize.

---

## 2. P3 — Semantic default OFF

**Đồng ý opt-in đúng.**

`_llm_enabled()`: default `"0"`; chỉ bật với `1/true/yes/on`; mock luôn false.

Bằng chứng:

| | Stop-before-LLM | TPR | FPR |
|--|----------------:|----:|----:|
| Rule (mock P2) | 81.5% | 81.5% | 0% |
| qwen judge ON + DLP | **81.5%** | 100% | 18.7% |

Judge **không** tăng chặn sớm; FPR tăng mạnh. Comment code nhắc ~11% (điểm pre-P2); P2 qwen là **18.7%** — vẫn ủng hộ default OFF (thậm chí mạnh hơn).

---

## 3. Demo A/B — 12/18 vs 0/18

### 3.1 Khớp artifact?

**Có — đếm lại từ `reports/demo-ab/20260812T095917Z/ab_result.json`:**

| Field | Artifact | Re-count |
|-------|----------|----------|
| unguarded_canary_leak_total | 12 | 12/18 attacks |
| guarded_canary_leak_total | 0 | 0/18 |
| per-rep unguarded | 3, 4, 5 | khớp |
| `canary_in_prompt` | false | — |
| `response` in keys | present trên unguarded rows | script prefers `response` |

Script hiện tại: `_extract_unguarded_answer` ưu tiên `response` — đúng schema `/v1/unguarded/chat`.

### 3.2 Paired hợp lệ?

| Tiêu chí | Đánh giá |
|----------|----------|
| Cùng prompt set | **Có** |
| Canary **chỉ trong KB** (seed cả hai store) | **Có** (design + `canary_in_prompt: false`) |
| Cùng model tag | **Có** (`qwen3:4b`) |
| Cùng retrieval implementation | **Không** — artifact `framing` ghi rõ system-level |
| Chỉ khác “bật/tắt guard” | **Không** |

**Kết luận:** A/B **hợp lệ** như thí nghiệm **system-level lab** (có tường vs unguarded path) với canary-sạch. **Không** hợp lệ như ablation guard-only / ACL-only. Ch4 hiện đã ghi system-level + số 12/18 & 0/18 — **khớp**.

---

## 4. qwen 100% TPR / 18.7% FPR — thổi phồng?

### 4.1 Phân rã (artifact `49d474bc`)

| Layer | Quan sát |
|-------|----------|
| Block pre-provider | **163/200** (= Stop-before-LLM 81.5%) |
| Block post-provider | **37/200** |
| Allow | 0 |
| Exfil marker final answer | **0/200** |

→ TPR 100% = **rule+normalize (input) + (judge có thể) + Output-DLP canary** cộng dồn, **không** = “input detection 100%”.  
Exfil 0% = **final answer sau Output Guard** (exact `FLAG{…}`), không = “hết injection”.

### 4.2 Framing Ch4

Ch4 nêu rõ:

- Stop-before qwen = rule = 81.5%.  
- 37 đòn TPR thêm = chặn **sau** provider / canary DLP.  
- FPR 18.7% / hard 20% đi kèm.  
- TPR 100% **không** = input recall 100%.  

**Đủ khiêm tốn cho lab report.** Còn residual: artifact không ghi `blocked_stage` → 37 post-provider là suy từ `provider_called` (hợp lý, chưa rule-id cứng).

---

## 5. Lỗ hổng / claim còn lại + điểm

### 5.1 Còn mở (không chặn verdict verify này)

| ID | Mức | Nội dung |
|----|-----|----------|
| R1 | Moderate | P2/qwen runs `dirty=true` trên `d65f1e3`; nên note “measured with normalize; locked later at e7a945c” hoặc re-run clean |
| R2 | Moderate | injecagent **47.4%** rule; 11/30 unicode vẫn lọt |
| R3 | Moderate | Output DLP = exact FLAG pattern; mutation/encoding chưa đo |
| R4 | Low | A/B system-level ≠ same-chunk; không suy ACL |
| R5 | Low | Homoglyph table hẹp; adversarial Unicode còn |
| R6 | Info | Full suite exact “passed” không khóa trong Ch4 (inventory 1533) — đúng hướng |

### 5.2 Điểm an ninh cập nhật (cùng thang lab 0–10)

| Trục | Trước (1b53635) | Nay | Ghi chú |
|------|----------------:|----:|---------|
| A Kiến trúc | 8.0 | 8.0 | — |
| B Luật / normalize | 7.2 | **7.5** | +unicode partial |
| C ACL | 8.0 | 8.0 | — |
| D Output/exfil | 5.5 | **6.2** | DLP + A/B measured leak |
| E Đo lường | 8.3 | **8.5** | A/B fixed detector |
| F Honesty | 8.5 | **8.7** | Ch4 Stop-before/TPR split |
| **Tổng** | **7.4** | **7.6** | |

### 5.3 Hướng còn lại (ưu tiên)

1. **Injecagent / hidden prose** (recall rule) — held-out, không p-hack 425.  
2. **Clean re-run 425** từ commit sạch + optional `blocked_stage`.  
3. **DLP hardening** (normalize output, non-marker leak) + FPR corpus.  
4. **Same-path A/B** (optional research) nếu muốn claim guard-only.

---

## 6. Checklist xác minh (re-audit)

| Kiểm tra | Kết quả |
|----------|---------|
| Mock TPR 81.5 / FPR 0 / garak 83.8 | Khớp `ac64cd5c` |
| Offline code HEAD input TP/FP | 163/200, 0/225 |
| qwen TPR 100 / FPR 18.7 / Stop 81.5 / pre163 post37 | Khớp `49d474bc` |
| A/B 12/18 vs 0/18 | Khớp `095917Z` |
| Script reads `response` | Có |
| Semantic default OFF | Có |
| Ch4 overclaim TPR 100 as input | **Không** (đã tách) |

---

*Auditor: Grok. Không commit/push. Không adjudicate project PASS.*
