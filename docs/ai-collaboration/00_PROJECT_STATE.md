# Project State

> **Agent đọc file này ĐẦU TIÊN, trước khi làm bất cứ việc gì.**
> Cập nhật sau mỗi phase gate. Không nhồi lịch sử chat — chỉ trạng thái hiện tại.

**Cập nhật lần cuối:** 2026-07-13

## Trạng thái phase

| Phase | Nội dung | Trạng thái |
|---|---|---|
| 0–10 | Gateway, guards, mock provider, v1 evaluation, báo cáo LaTeX | Done (Phase 10 In Review) |
| 12A | Kế hoạch hiện đại hoá v2 | Done |
| 12B | SQLite FTS5/BM25 retrieval foundation | Done |
| 12C | End-to-end RAG security pipeline | **In Review** — chờ 1 vòng Code X re-audit cuối |
| 12D | Benchmark V2 (thiết kế / sinh / freeze) | **DONE** — manifest FINAL |
| 12E | Đánh giá + ablation trên benchmark v2 | **CHƯA BẮT ĐẦU** |

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
