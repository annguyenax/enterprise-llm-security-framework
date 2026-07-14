# Project State

> **Agent đọc file này ĐẦU TIÊN, trước khi làm bất cứ việc gì.**
> Cập nhật sau mỗi phase gate. Không nhồi lịch sử chat — chỉ trạng thái hiện tại.

**Cập nhật lần cuối:** 2026-07-14

## Trạng thái phase

| Phase | Nội dung | Trạng thái |
|---|---|---|
| 0–10 | Gateway, guards, mock provider, v1 evaluation, báo cáo LaTeX | Done (Phase 10 In Review) |
| 12A | Kế hoạch hiện đại hoá v2 | Done |
| 12B | SQLite FTS5/BM25 retrieval foundation | Done |
| 12C | End-to-end RAG security pipeline | **DONE** — Code X final re-audit PASS |
| 12D | Benchmark V2 (thiết kế / sinh / freeze) | **DONE** — manifest FINAL |
| 12E | Đánh giá + ablation trên benchmark v2 | **G0 PASS — APPROVED FOR IMPLEMENTATION; triển khai CHƯA BẮT ĐẦU** |

**Cả hai phase chặn 12E (12C và 12D) đều đã đóng bằng audit độc lập PASS.**
G0 của Phase 12E cũng đã đóng bằng triple PASS trên plan commit
`d82bac7828e2e54520e0aa29271e820a52ec6f47`. Việc triển khai không tự bắt đầu;
vẫn cần một task/go-ahead triển khai riêng theo `AGENT_RULES.md` rule 12.

## Phase 12E — trạng thái planning gate G0

- Ba audit kế hoạch tại baseline `a5afcea` đều trả **REVISE**:
  Code X technical · Gemini academic · Grok red-team.
- Adjudication: `docs/modernization-ai-reviews/phase-12e-plan-audit-resolution.md`.
- Master plan đã sửa về execution seam in-process duy nhất, thuật toán từng
  `evaluation_scope`, hạ tầng safety luôn bật, C4/C5 provider caveat, safe stage
  telemetry, case-error/partial policy, run/config/result integrity và C6 checklist.
- Plan commit được audit: `d82bac7828e2e54520e0aa29271e820a52ec6f47`.
- Code X final technical verification: **PASS**.
- Gemini final academic re-audit: **PASS**.
- Grok final red-team re-audit: **PASS**.
- Remaining Critical issues: **None**. Remaining blocking Major issues:
  **None**. Required corrections before implementation: **None**.
- **G0 PASS. Master plan APPROVED FOR IMPLEMENTATION.**
- Chưa có `GuardProfile`, runner, analyzer, test Phase 12E, result artifact hoặc
  generated evaluation output nào.
- Phase 12E implementation: **NOT STARTED**. Evaluation results: **NONE**.
  Holdout executed: **NO**.

## Phase 12C — đã đóng

- **Code X final technical re-audit: PASS.**
  Báo cáo: `docs/modernization-ai-reviews/codex-phase-12c-final-reaudit.md`
- Reviewed HEAD: `9fed074481f46ce5e3ae2bfa20abcec3e36661fb`
- Phase 12C implementation baseline: `ad555c95f01601b8eeeba92106b132ad88d7be00`
- Final implementation commit: `56b749a47501ab9686503ca007c5197d8a6b47b0`
- `app/` drift sau baseline: **không có**
- Critical còn lại: **không có**. Blocking Major còn lại: **không có**.
  Required actions before DONE: **không có**.
- Code X **đã đọc code thật** và **tự chạy test** (không chỉ đọc số liệu ta báo).
- Test: focused Phase 12C **172 passed, 1 warning**; targeted Critical/Major
  probes **24 passed, 1 warning**; full suite **578 passed, 0 failed,
  0 skipped, 1 warning**; `compileall` PASS.
- Finding chặn trước đó (nested `ProvenanceItemResponse` dựng ngoài block bảo
  vệ) — **RESOLVED**: mọi model response lồng nhau giờ dựng trong một block
  `try` duy nhất; success audit chỉ commit sau khi toàn bộ cây response dựng
  xong.
- **3 Minor, đều non-blocking (ghi lại, không bỏ qua):**
  1. Cách đếm regression test: **4 test nested-response mới**; con số 5 chỉ
     đúng khi tính thêm regression outer-response atomicity trước đó. Handoff
     của ta ghi "5" là thiếu chính xác.
  2. `retrieval_score` phi hữu hạn sẽ serialize thành JSON `null` thay vì lỗi.
     SQLite BM25 hiện chỉ sinh giá trị hữu hạn → đây là **schema hardening
     tương lai (tuỳ chọn)**, không phải lỗi sống.
  3. Thư mục `__pycache__` bị ignore có sẵn từ trước — không do audit tạo,
     không track.

## Phase 12D — đã đóng

- **Ba gate đều PASS** tại commit `4e10a2e`:
  Code X (kỹ thuật) PASS · Gemini (học thuật) PASS · Grok (red-team) PASS
- Critical còn lại: **không có**. Blocking Major còn lại: **không có**.
- **Manifest: FINAL**, phủ 9 artifact, SHA-256 khoá cứng.
- Test: focused **255 passed**; full suite **578 passed, 1 warning**
  (warning là `httpx2` deprecation có sẵn — `httpx2` là typosquat, KHÔNG cài).
- Benchmark: 120 case / 23 family / 172 document, split 30-30-60.

## Ràng buộc mang sang Phase 12E

1. **Chín artifact trong `datasets/v2/` là BẤT BIẾN.** Đổi một byte = benchmark
   v3 + phải chạy lại toàn bộ audit Gemini/Grok. `verify_phase.ps1` kiểm tra
   điều này mỗi lần chạy.
2. **Giới hạn báo cáo thống kê (Gemini, đã chấp nhận):** chỉ báo cáo phần trăm ở
   mức tổng hợp hoặc nhóm family lớn đã khai báo trước. Kết quả theo từng family
   riêng lẻ chỉ được mô tả định tính — 2–8 case/family là quá nhỏ để có ý nghĩa
   thống kê.
3. **Probe Grok đề xuất cho 12E** (chưa làm): budget-exact multi-chunk Vietnamese
   splits; trusted-source authority + canary mixes; homoglyph + benign trigger
   combos. Đây là probe lúc evaluation, KHÔNG phải case mới trong benchmark.
4. **Không đưa agent orchestration vào runtime pipeline** — sẽ làm nhiễu đo
   latency và phá tính so sánh với baseline.

## Giới hạn đã ghi nhận (giữ nguyên, không được che giấu)

Corpus tổng hợp · guard dựa trên luật · Mock LLM Provider · phát hiện nhiễm
chéo bằng từ vựng (không ngữ nghĩa) · lexicon song ngữ ~40 mục · không có
retrieval ngữ nghĩa · người viết benchmark trùng người viết guard · mẫu nhỏ
theo family.

## Lệnh chạy nhanh

```powershell
.\scripts\verify_phase.ps1              # toàn bộ checklist + evidence block
.\scripts\verify_phase.ps1 -Focused     # nhanh, dùng khi đang lặp fix
python scripts/validate_v2_benchmark.py
python scripts/freeze_v2_benchmark.py verify
```
