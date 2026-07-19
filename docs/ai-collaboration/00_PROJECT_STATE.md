# Project State

> **Agent đọc file này ĐẦU TIÊN, trước khi làm bất cứ việc gì.**
> Cập nhật sau mỗi phase gate. Không nhồi lịch sử chat — chỉ trạng thái hiện tại.

**Cập nhật lần cuối:** 2026-07-19

## Trạng thái phase

| Phase | Nội dung | Trạng thái |
|---|---|---|
| 0–10 | Gateway, guards, mock provider, v1 evaluation, báo cáo LaTeX | Done (Phase 10 In Review) |
| 12A | Kế hoạch hiện đại hoá v2 | Done |
| 12B | SQLite FTS5/BM25 retrieval foundation | Done |
| 12C | End-to-end RAG security pipeline | **DONE** — Code X final re-audit PASS |
| 12D | Benchmark V2 (thiết kế / sinh / freeze) | **DONE** — manifest FINAL |
| 12E | Đánh giá + ablation trên benchmark v2 | **12E.1 G1 PASS; 12E.2 G2 PASS; 12E.3 CLOSED PASS; 12E.4 PLANNING — HOLDOUT UNAUTHORIZED** |

**Cả hai phase chặn 12E (12C và 12D) đều đã đóng bằng audit độc lập PASS.**
G0 của Phase 12E đã đóng bằng triple PASS trên plan commit
`d82bac7828e2e54520e0aa29271e820a52ec6f47`. Foundation 12E.1 sau đó được
triển khai tại `8b1e485f128d08adc4baeed499363886e8969a18` và đã qua G1 audit độc lập.
Runner development-only của 12E.2 được triển khai tại
`2233002ccf3e067ab932a5a8fa2b6a7bbe350b01` và đã qua G2 audit độc lập.
**12E.3 đã đóng với verdict PASS** (chi tiết bên dưới). **12E.4 đang ở giai đoạn
lập kế hoạch; holdout vẫn CHƯA ĐƯỢC PHÊ DUYỆT** và vẫn cần văn bản uỷ quyền riêng
của người duy trì theo `AGENT_RULES.md` rule 12.

## Phase 12E.3 — ĐÃ ĐÓNG (CLOSED, PASS)

- **Implementation identity:** `c6d91c78e11009e96a76db08c0dfbb710504c227`
  (`fix: align Phase 12E.3 runner and analyzer contracts`).
- **Validation artifact closure: PASS.** Báo cáo:
  `docs/modernization-ai-reviews/code-x-phase-12e-3-validation-artifact-closure.md`.
- Critical issues: **None**. Blocking Major issues: **None**. Required
  corrections: **None**.
- Matrix hoàn chỉnh: đúng tám `result.json` + tám `result-manifest.json`, C0–C7,
  mọi run và mọi case record đều `complete`; error/timeout/skipped bằng 0.
- Analyzer artifact: `analysis.json`, `analysis-table.csv`,
  `analysis-manifest.json` — hash, kích thước và identity đều tái lập độc lập và
  khớp.
- Chính sách metric được xác nhận nguyên vẹn: không có khoá `abr`, không macro,
  không family rate, không family percentage; `RATE_REPORTING_MIN_N=10` được tuân
  thủ; latency non-reportable với `p50=null`, `p95=null`.
- Quét đệ quy toàn bộ result/analysis JSON cùng 208 dòng CSV: **không** có trường
  thô, canary/secret, retrieved content, answer hay đường dẫn máy tuyệt đối.
- **Validation đã được quan sát và KHOÁ LẠI. Không chạy lại** trừ khi có
  re-adjudication tường minh riêng của người duy trì.
- Holdout: **NOT EXECUTED**, không được uỷ quyền, và closure này **không** cấp
  quyền chạy holdout.

## Phase 12E.4 — PLANNING / HOLDOUT UNAUTHORIZED

- Kế hoạch ràng buộc: `docs/ai-collaboration/07_PHASE_12E4_HOLDOUT_PLAN.md`.
- Baseline lập kế hoạch: `c0b8f6d6fb9fb5faa24f58610368fdc50ca41b62` trên branch
  `phase-12e-4-holdout-planning`.
- **Latency: chọn L2.** RQ4 bị gỡ khỏi các research question có thể báo cáo; H5
  được phân loại lại thành kỳ vọng mô tả, không báo cáo; `latency_reportable`
  giữ `false`; `p50`/`p95` giữ `null`.
- **Chưa triển khai gì.** Không có code holdout, không có authorization file,
  không có artifact holdout.
- **Holdout vẫn CHƯA ĐƯỢC PHÊ DUYỆT.** Chỉ người duy trì mới cấp được uỷ quyền,
  sau khi đủ chuỗi gate trong kế hoạch 12E.4.

## Phase 12E — trạng thái gate hiện tại

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
- `GuardProfile`, internal pipeline parameterization và regression/public-isolation
  tests đã được triển khai tại commit
  `8b1e485f128d08adc4baeed499363886e8969a18`.
- Grok Web combined technical/security/red-team G1 audit: **PASS**. Báo cáo:
  `docs/modernization-ai-reviews/grok-phase-12e-1-g1-audit.md`.
- G1 remaining Critical issues: **None**. Major issues: **None**. Required
  corrections: **None**.
- **12E.1 G1 PASS. 12E.2 G2 PASS.** Runner implementation commit:
  `2233002ccf3e067ab932a5a8fa2b6a7bbe350b01`. Grok Web combined G2 audit
  xác nhận **PASS**, không có Critical, Major, Minor hoặc required correction.
- Runner chỉ hỗ trợ split `development`. Một C0 smoke development do người duy
  trì thực hiện ngoài repository đã hoàn tất với `run_status=complete`, result
  SHA-256 `3da58e32b8ae0c1d72ccd0dd2aed0f8092a56624a1614967c9661920c3d49ef2`
  và kích thước `84995` byte.
- Smoke trên chỉ là bằng chứng vận hành development, không phải validation hay
  kết quả thí nghiệm cuối. Không có aggregate metric nào được tính. Validation:
  **NOT EXECUTED**. Holdout: **NOT EXECUTED**.
- ~~Analyzer chưa tồn tại và 12E.3 NOT STARTED.~~ **Đã lỗi thời** — analyzer tồn
  tại tại `scripts/analyze_v2_results.py` và 12E.3 đã đóng PASS (xem mục
  "Phase 12E.3 — ĐÃ ĐÓNG" ở trên). Các giới hạn và khuyến nghị deferred đã phê
  duyệt vẫn giữ nguyên.
- **Operating model từ 12E.4 trở đi** (thay thế mô hình 12E.2–12E.3): **Claude
  Code là lead architect và primary implementer**; GitHub Copilot hỗ trợ chiến
  thuật dưới review của Claude; **Code X là plan reconciler và
  artifact-integrity auditor, KHÔNG implement**; Grok Web là independent
  technical/security auditor; Gemini Web là independent methodology/claims
  auditor; Qwen2.5-Coder và Hermes3 local chỉ là advisory pre-audit;
  `scripts/verify_phase.ps1` là mechanical verifier; **người duy trì là final
  adjudicator và là người duy nhất phê duyệt holdout**. Chi tiết:
  `docs/ai-collaboration/01_AGENT_ROLES.md`.

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
