# Decisions Log

Nhật ký quyết định kiến trúc cho quy trình phát triển. Mỗi mục ghi: quyết định
gì, vì sao, và cái gì đã bị loại bỏ.

---

## D-001 — Verifier là script, không phải LLM agent

**Ngày:** 2026-07-13 · **Trạng thái:** Đã áp dụng

Mọi số liệu dùng để đóng một phase (test count, SHA-256, determinism) đến từ
`scripts/verify_phase.ps1`, không từ lời tường thuật của LLM.

**Vì sao:** Số liệu đóng phase phải tái lập được và kiểm chứng được. LLM được
hỏi "test có pass không" có thể trả lời sai do ảo giác hoặc đọc nhầm output.

**Loại bỏ:** Phương án dùng một "Test Agent" LLM — không mang lại giá trị nào mà
script không làm được, lại tốn token và có thể báo sai.

---

## D-002 — Không dùng OmniRoute / 9Router

**Ngày:** 2026-07-13 · **Trạng thái:** Đã quyết, KHÔNG cài

Không dùng OmniRoute, 9Router, hoặc bất kỳ proxy nào quảng cáo "unlimited free
AI coding" / "never hit limits". Continue gọi thẳng DeepSeek, Gemini, Ollama.

**Vì sao — ba lý do độc lập:**

1. **Vi phạm ToS.** Các công cụ này quảng cáo truy cập "FREE Claude/GPT/Gemini"
   qua 40–230 provider và "never hit limits" — tức là lách quota của dịch vụ trả
   phí. Một đồ án tốt nghiệp không nên được xây bằng công cụ vi phạm điều khoản
   dịch vụ; nếu hội đồng hỏi, không có câu trả lời tốt.
2. **Supply-chain risk.** Cài một proxy cầm toàn bộ API key và toàn bộ code là
   đúng chính xác threat model mà đồ án này nghiên cứu. Repo còn đang document
   vụ typosquat `httpx2` trong `TASK_BOARD.md` — không thể vừa cảnh báo vừa mắc
   phải.
3. **Không cần thiết.** Continue hỗ trợ native `provider: deepseek`,
   `provider: gemini`, `provider: ollama`. Router ở giữa không mua thêm được gì
   ngoài rủi ro.

---

## D-003 — API key chỉ qua biến môi trường

**Ngày:** 2026-07-13 · **Trạng thái:** Đã áp dụng, CẦN HÀNH ĐỘNG

`~/.continue/config.yaml` từng chứa **Gemini API key và DeepSeek API key ở dạng
plaintext**. Đã thay bằng `${{ env.GEMINI_API_KEY }}` /
`${{ env.DEEPSEEK_API_KEY }}`.

**Hành động bắt buộc:** hai key cũ **phải được revoke và tạo lại** — chúng đã
lộ. DeepSeek key gắn với billing nên đặc biệt nhạy.

**Bài học:** file config của công cụ dev cũng là attack surface. Không hardcode
secret ở bất cứ đâu, kể cả file ngoài repo.

---

## D-004 — Harness: ENABLED cho scaffolding, KHÔNG có quyền audit

**Ngày:** 2026-07-13 · **Trạng thái:** ENABLED (`~/.claude/skills/harness`)

```
Harness: ENABLED
Role: scaffolding and Claude workflow support
Audit authority: NO
```

Dùng Harness để: tạo skill, scaffold workflow, chia nhỏ context, tạo template,
hỗ trợ Claude subagent, đọc/áp dụng pattern. **Không** dùng làm lớp audit cuối.

**Vì sao không cho quyền audit:** Mọi agent Harness sinh ra đều là subagent
Claude. Điều đó (a) tốn token — mỗi subagent cold-start đọc lại context, và
(b) **không tái tạo được sự đa dạng của audit đa mô hình**. Một subagent Claude
audit code do Claude viết vi phạm chính nguyên tắc "implementer không tự
approve". Harness không gọi được Code X, Gemini, hay Grok.

### Rà soát bảo mật (P3) — thực hiện 2026-07-13, KẾT QUẢ SẠCH

| Hạng mục | Kết quả |
|---|---|
| Nguồn | `https://github.com/revfactory/harness.git` |
| Commit đã ghim | `cceac68ea1d0ad198ef4b7b906cd238375836387` (2026-06-10) |
| Nội dung | 7 file, 120 KB, **thuần Markdown — không có code thực thi** |
| Hook (`preToolUse`/`postToolUse`/`settings.json`) | Không có |
| Shell / subprocess / `exec()` / `curl` | Không có |
| Network access | Không có |
| Đọc `.env` / home dir / credential | Không có |
| Git write (`commit`/`push`/`--force`) | Không có |

Vì là tài liệu thuần văn bản, Harness không tự thực thi được gì — mọi hành động
đều đi qua tool của Claude Code và chịu lớp permission ở đó. **Không cấp quyền
sửa hoặc push Git tự động.**

**Giữ lại:** phần `references/` (6 pattern kiến trúc) là tài liệu tốt, đáng đọc.

---

## D-005 — Không đưa agent orchestration vào runtime Phase 12E

**Ngày:** 2026-07-13 · **Trạng thái:** Ràng buộc cứng

Multi-agent chỉ nằm ở tầng phát triển. Không có agent nào chạy trong RAG security
pipeline lúc evaluation.

**Vì sao:** thêm orchestration vào runtime sẽ (a) thay đổi latency, (b) tạo biến
nhiễu, (c) khiến kết quả không so sánh được với baseline, và (d) khiến luận văn
không xác định được metric đến từ guard hay từ orchestration.

---

## D-006 — Không bật prompt compression cho prompt chứa code

**Ngày:** 2026-07-13 · **Trạng thái:** Ràng buộc cứng

**Vì sao:** compression (RTK/Caveman/LLMLingua) hoạt động bằng cách bỏ token nó
cho là dư thừa. Với văn xuôi thì chấp nhận được; với một diff hoặc prompt audit,
nó có thể lặng lẽ đổi tên biến, bỏ dấu ngoặc, hoặc cắt mất một điều kiện — và
auditor sẽ review một đoạn code không tồn tại. Rủi ro này không đáng để đổi lấy
vài phần trăm token.

---

## D-007 — Phase 12E.4 latency: chọn L2, bác L1

**Ngày:** 2026-07-19 · **Trạng thái:** Ràng buộc cứng (adjudication của người duy trì)

**Chọn L2.** Không có claim latency nào được báo cáo trong Phase 12E.

- RQ4 bị **gỡ** khỏi các research question có thể báo cáo.
- H5 được **phân loại lại** thành kỳ vọng mô tả, không báo cáo.
- `latency_reportable` giữ `false`; `p50`/`p95` giữ `null`.
- Timing lúc chạy **chỉ giữ làm chẩn đoán determinism**.
- **Không** đổi hành vi determinism repetition để phục vụ latency.
- **Không** thêm latency mini-gate; **không** yêu cầu máy đo chuyên dụng.

**Vì sao:** hai lần lặp tồn tại để chứng minh quyết định của pipeline là tất
định (`validate_repetition_determinism`, `run_v2_evaluation.py:1960`), không phải
để đo thời gian; mẫu thời gian chỉ được gom kèm
(`_merge_repetition_latency:1980`). `repetitions=2, warmup=0`
(`run_v2_evaluation.py:2272-2273`) không cấu thành một giao thức đo latency khoa
học. `latency_reportable=False` đã hard-code sẵn ở
`analyze_v2_results.py:544, 1491, 1787`.

**L1 bị bác cho phase này**, giữ lại kèm lý do: máy phát triển dùng chung (có
chạy model local) không cho số latency phòng thủ được; sửa
`_merge_repetition_latency` và ràng buộc "đúng hai mẫu"
(`analyze_v2_results.py:776-777`) sẽ đụng vào hợp đồng determinism vừa PASS; RQ4
không phải research question trung tâm; và H5 vốn dự đoán latency chủ yếu đến từ
`retrieval`, không từ guard.

---

## D-008 — Cấm chạy lại validation

**Ngày:** 2026-07-19 · **Trạng thái:** Ràng buộc cứng

Validation của Phase 12E.3 **đã được quan sát và khoá lại**. **Không chạy lại.**

Xác minh triển khai Phase 12E.4 chỉ gồm: unit/negative test tổng hợp · focused
suite · full suite · benchmark validator · frozen-manifest verification ·
development-only C0–C7 smoke. **Không validation. Không holdout.**

Mọi lần chạy lại validation trong tương lai đòi hỏi một **re-adjudication tường
minh riêng** của người duy trì.

**Vì sao:** chạy lại validation sau khi đã xem kết quả sẽ phá bỏ tính độc lập của
bằng chứng đã được closure PASS tại `c6d91c7`, và mở đường cho việc chọn lọc kết
quả có lợi.

---

## D-009 — Mô hình đe doạ trusted-maintainer, one-shot theo thủ tục

**Ngày:** 2026-07-19 · **Trạng thái:** Ràng buộc cứng

Bảo đảm one-shot của holdout là **thủ tục và dựa trên filesystem**, dưới mô hình
**trusted-maintainer**.

**Làm được:** giảm chạy nhầm · ngăn chạy lại vô tình · ngăn ghi đè evidence ·
ngăn CLI vô tình chạm holdout · ngăn analyzer trộn attempt · làm mọi attempt
được giữ lại trở nên audit được.

**KHÔNG làm được — nêu tường minh:**

> Quy trình này **không ngăn chặn về mặt toán học hay mật mã** việc một quản trị
> viên cục bộ có ác ý xoá bằng chứng. Nó **làm giảm về mặt thủ tục** khả năng
> thực thi do nhầm lẫn hoặc không được phép, và làm cho các attempt được giữ lại
> trở nên **audit được** dưới mô hình trusted-maintainer.

---

## D-010 — Authorization schema holdout Phase 12E.4

**Ngày:** 2026-07-19 · **Trạng thái:** Ràng buộc cứng

- Định danh schema: **`phase12e4-holdout-authorization-v1`**
- `issued_by`: **`maintainer:annguyenax`**
- `purpose`: **`phase12e4_holdout_c0_c7`**
- File authorization là **canonical JSON nghiêm ngặt, nằm ngoài repository**,
  không bao giờ commit.
- **Chữ ký GPG KHÔNG bắt buộc** dưới mô hình đe doạ đã khai báo ở D-009.
- Artifact chỉ lưu `authorization_id`, SHA-256 của authorization, định danh
  attempt, và contract identity an toàn. **Không** lưu nội dung authorization,
  `output_root` tuyệt đối, query thô, answer, retrieved content, secret/canary
  hay đường dẫn máy.

Chi tiết đầy đủ: `docs/ai-collaboration/07_PHASE_12E4_HOLDOUT_PLAN.md` §5.

---

## D-011 — Retry holdout qua lineage `supersedes`, không chặn thẳng attempt > 1

**Ngày:** 2026-07-19 · **Trạng thái:** Ràng buộc cứng

Attempt fatal hoặc partial **được giữ nguyên, không xoá**. Một lần retry hợp lệ
đòi hỏi **đủ sáu**: uỷ quyền mới của người duy trì · `authorization_id` mới ·
external root mới · `attempt` tăng · `supersedes_authorization_sha256` trỏ tới
authorization trước · implementation commit / provider / configs / manifest /
mapping / metric & analysis contract **không đổi** (trừ khi re-adjudicate riêng).

Analyzer **không bao giờ trộn attempt**.

**Vì sao không chặn thẳng `attempt > 1`:** làm vậy sẽ buộc người dùng phải **xoá
bằng chứng** để thử lại — đi ngược chính mục tiêu giữ evidence. Tiền lệ: Phase
12E.3 attempt 1 kết thúc bằng `manifest_missing_artifact` và đã được giữ lại,
ghi nhận, không bị xoá.

---

## D-012 — Development smoke dùng worktree sạch riêng

**Ngày:** 2026-07-19 · **Trạng thái:** Ràng buộc cứng

Development-only C0–C7 smoke chạy trong một **git worktree sạch riêng**, output
root ngoài repository, Mock Provider. **Không validation. Không holdout.**

**Vì sao:** giữ repo chính sạch trong lúc chạy, và tách hoàn toàn artifact vận
hành khỏi cây làm việc — đúng khuôn mẫu đã dùng ở 12E.3 (`D:\p12e3-wt-c6d91c7`).

---

## D-013 — Vai trò Phase 12E.4

**Ngày:** 2026-07-19 · **Trạng thái:** Ràng buộc cứng

**Claude Code** là lead architect và primary implementer. **GitHub Copilot** hỗ
trợ chiến thuật dưới review của Claude. **Code X** là plan reconciler và
artifact-integrity auditor — **không implement**. **Grok** là independent
technical/security auditor. **Gemini** là independent methodology/claims auditor.
**Qwen/Hermes** chỉ advisory pre-audit. **Người duy trì** là final adjudicator và
là người **duy nhất** phê duyệt holdout.

Claude Code **không được tự audit** công việc của mình và **không được** tạo,
sửa hoặc tự ký file authorization holdout.

Thay thế mô hình cũ (Code X là primary implementer) đã ghi ở
`01_AGENT_ROLES.md` trước ngày này.

---

## D-014 — Holdout vẫn chưa được phê duyệt

**Ngày:** 2026-07-19 · **Trạng thái:** Đang hiệu lực

**Holdout CHƯA ĐƯỢC PHÊ DUYỆT và CHƯA ĐƯỢC THỰC THI.** Không có code holdout,
không có authorization file, không có artifact holdout nào tồn tại.

Việc chạy holdout chỉ diễn ra sau khi đủ chuỗi gate trong
`07_PHASE_12E4_HOLDOUT_PLAN.md` §21 và có **văn bản uỷ quyền của người duy trì**.
Đây là một **gate**, không phải một câu hỏi thiết kế còn mở.
