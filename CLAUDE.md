# CLAUDE.md

Hướng dẫn cho AI agent làm việc trên repo này. Đọc file này trước mọi task.

## Dự án

Enterprise LLM Security Framework — đồ án thực tập đại học. Lab-scale LLM
Security Gateway / Guardrail Proxy đứng trước một ứng dụng RAG, phòng chống
prompt injection, indirect injection, jailbreak, rò rỉ dữ liệu, và data
poisoning. **PoC học thuật, KHÔNG phải production**, dữ liệu tổng hợp hoàn toàn.

## MỤC LỤC BẮT BUỘC ĐỌC CHO AI (AI ONBOARDING)

Nếu bạn là một AI Agent (Claude, Grok, Gemini, v.v...) vừa được giao task mới, BẠN PHẢI ĐỌC các file sau theo thứ tự để hiểu bối cảnh dự án, tránh lặp lại lỗi, và biết file nào cần sửa:

1. `TASK_BOARD.md` — trạng thái hiện tại (phase nào, gate nào đã qua) và roadmap chi tiết.
2. `AGENT_RULES.md` — luật cứng của dự án (KHÔNG dùng API trả phí, KHÔNG tự ý cài thư viện nặng, v.v...) và vai trò/quyền hạn của agent.
3. `PROJECT_PLAN.md` — roadmap tổng thể.
4. `docs/decisions/` (ADR) và `docs/benchmark-v2-methodology.md` — quyết định kiến trúc và phương pháp benchmark.

> Ghi chú: các nhật ký cộng tác/review AI chi tiết (`docs/ai-collaboration/`,
> `docs/modernization-ai-reviews/`) đã được lưu trong lịch sử Git ở các commit
> trước, không còn trong cây làm việc hiện tại.

## Trạng thái hiện tại

Nghĩa trạng thái dùng cho đối chiếu 2026-11-07 là bảng bên dưới. Khối trích
nguyên văn là hồ sơ ngày 2026-07-19, không phải nghĩa hiện tại. Bảng không
chạy lại test, không đổi số benchmark, không mở case/nhãn holdout, và không
ký authorization.

### Nguyên văn khối 2026-07-19 (không còn là nghĩa hiện tại)

> ## Trạng thái hiện tại (2026-07-19)
>
> - Phase 12C (RAG pipeline): **DONE** — Code X final re-audit PASS
> - Phase 12D (Benchmark V2): **DONE** — manifest FINAL, 3 gate audit đều PASS
> - Phase 12E (Evaluation): **12E.1 G1 PASS; 12E.2 G2 PASS; 12E.3 CLOSED PASS;
>   12E.4 PLANNING — HOLDOUT UNAUTHORIZED**
>
> Cả hai phase chặn 12E đều đã đóng. Kế hoạch tại commit `d82bac7` đã qua
> Code X, Gemini và Grok với verdict PASS. GuardProfile foundation tại
> `8b1e485f128d08adc4baeed499363886e8969a18` qua G1 PASS. Development-only runner
> tại `2233002ccf3e067ab932a5a8fa2b6a7bbe350b01` qua G2 PASS.
>
> **Phase 12E.3 đã đóng với verdict PASS** — implementation identity
> `c6d91c78e11009e96a76db08c0dfbb710504c227`; validation artifact closure PASS
> (hồ sơ review lưu trong lịch sử Git);
> không còn Critical hoặc blocking Major. Analyzer tồn tại tại
> `scripts/analyze_v2_results.py`. **Validation đã được quan sát và KHOÁ LẠI —
> không chạy lại** trừ khi có re-adjudication tường minh riêng.
>
> **Phase 12E.4 đang lập kế hoạch.** Kế hoạch ràng buộc (lưu trong lịch sử Git).
> Latency theo **L2**: RQ4
> bị gỡ khỏi research question có thể báo cáo, H5 phân loại lại thành mô tả không
> báo cáo, `latency_reportable=false`, `p50`/`p95` null. **Holdout CHƯA ĐƯỢC THỰC
> THI và CHƯA ĐƯỢC PHÊ DUYỆT.**

Câu “CLOSED PASS” và “chưa được thực thi” trong trích dẫn mô tả hồ sơ tại
`365e9001d566e7faefef67b73106647083330628` (2026-07-19 09:22:19 +0700). Chúng
không phủ nhận bảng: file analyzer có mặt không phải hoàn tất; closure
validation là hồ sơ Git; holdout governance-valid vẫn chưa được ủy quyền;
một lần exploratory sau ngày đó được ghi ở `docs/final/00_FINAL_STATUS.md`
và không phải PASS cuối.

### Document status reconciliation (2026-11-07)

Scope: status meaning only. Base `ff047623a265af3a99fe716b561de7eac3cc830f` (2026-08-16 10:38:56 +0700). This note does not re-run tests, does not change benchmark figures, does not open holdout cases or labels, and does not sign holdout authorization. Analyzer presence is not completion. Missing bytes stay UNKNOWN.

| Layer | What is true | Source and time | This 2026-11-07 pass |
|---|---|---|---|
| Analyzer implementation | `scripts/analyze_v2_results.py` is in the tree. Presence is not completion. | `ff047623:scripts/analyze_v2_results.py:1`. First commit `47bd393d1a7ac9106ce5a64bb8edd736615ad038` (2026-07-14 18:47:44 +0700). Alignment commit `c6d91c78e11009e96a76db08c0dfbb710504c227` (2026-07-14 20:20:37 +0700). | Path observed. Script not executed. |
| 12E.3 validation execution record | Line 6 names implementation `c6d91c78e11009e96a76db08c0dfbb710504c227`. Line 7 records `provider_id=mock` and `split=validation`. Line 16 records attempt 2 as eight complete validation runs and one analysis publication. Line 9 says that audit did not execute the runner or analyzer. Line 70 says the result artifacts are not tracked. Bytes in this worktree: UNKNOWN. | `94eafc686cb03262f77d7bd3572ee6557f7d6a98:docs/modernization-ai-reviews/code-x-phase-12e-3-validation-artifact-closure.md` lines 6, 7, 9, 16, 70. Absent at `ff047623` after `24e70831f077d2430387007a46148c99e5b5dc6d` (2026-08-15 13:42:45 +0700). | Not re-run. Not a new PASS. |
| Historical “12E.3 CLOSED PASS” sentence | The block headed 2026-07-19 records 12E.3 CLOSED PASS and validation artifact closure PASS, with the review dossier kept in git history. This pass does not re-adjudicate that sentence. | `ff047623:CLAUDE.md:29` and `:37-39` | Preserved as history. |
| Holdout at the 12E.3 closure | The same audit records that holdout execution was not authorized and was not executed, and that the audit does not authorize holdout. | `94eafc686cb03262f77d7bd3572ee6557f7d6a98:docs/modernization-ai-reviews/code-x-phase-12e-3-validation-artifact-closure.md` lines 63 and 65 | Preserved. Not an authorization. |
| Later exploratory holdout | Classification is `POST-EXECUTION EXPLORATORY / DIAGNOSTIC EVIDENCE ONLY`. Fully completed human adjudication before execution is recorded as No (governance gap). Final Phase 12E.4 PASS must not be claimed. Attempt bytes were not opened: UNKNOWN. | `ff047623:docs/final/00_FINAL_STATUS.md:63`, `:70`, and `:71`. Package commit `4da5d8ccc9e52da3384f3e8c6982bfdd6ea21857` (2026-07-24 14:23:42 +0700). Last change before this reconciliation: `8a5db083592473c8576090b691104b43b5000a73` (2026-07-25 10:05:14 +0700). | Not re-opened. No metrics added. |
| Authorization | This reconciliation signs no holdout authorization. The base rule says the maintainer is the only person who approves holdout. | `ff047623:CLAUDE.md:63` | Unchanged rule. No signature added. |

## Operating model Phase 12E.4

- **Lead architect và primary implementer: Claude Code.**
- Tactical coding support: **GitHub Copilot**, dưới review của Claude Code.
- Plan reconciliation và artifact-integrity audit: **Code X** — **KHÔNG
  implement**.
- Independent technical/security auditor: **Grok Web trong audit chat riêng**.
- Independent methodology/claims auditor: **Gemini Web**, bắt buộc ở
  metric/statistical/claim gates.
- Advisory pre-audit: **Qwen2.5-Coder local** và **Hermes3 local** — không phát
  hành PASS/REVISE; candidate của Hermes không bao giờ trở thành frozen benchmark
  ground truth.
- Mechanical verifier: **`scripts/verify_phase.ps1`** (script, không LLM).
- Final adjudicator và **người duy nhất phê duyệt holdout**: **người duy trì**.

**Claude Code không được tự audit công việc của chính mình và không được phê
duyệt holdout.** Dù là primary implementer, Claude Code vẫn phải qua Grok
(technical/security) và Gemini (methodology/claims) độc lập, rồi mới tới
adjudication của người duy trì. Không agent nào — kể cả Claude Code — được tạo,
sửa hoặc tự ký file authorization holdout.

## Lệnh

```powershell
.\scripts\verify_phase.ps1              # TOÀN BỘ checklist + evidence block
.\scripts\verify_phase.ps1 -Focused     # nhanh, khi đang lặp fix
.venv\Scripts\python.exe -m pytest -q   # full suite; không báo số từ trí nhớ
python scripts/validate_v2_benchmark.py
python scripts/freeze_v2_benchmark.py verify
```

Luôn dùng `.venv\Scripts\python.exe`, không dùng `python` trần.

## Ràng buộc CỨNG

- **`datasets/v2/` — 9 artifact đã FINAL freeze. KHÔNG SỬA.** Đổi một byte =
  benchmark v3 + phải chạy lại toàn bộ audit Gemini/Grok. `verify_phase.ps1`
  kiểm tra hash mỗi lần chạy.
- **KHÔNG cài `httpx2`.** Đó là typosquat/decoy. Starlette báo deprecation
  warning về nó — cứ để nguyên, warning đó là bình thường và đã được ghi nhận.
- **KHÔNG cài gói mới** vào `requirements.txt` nếu không được yêu cầu rõ ràng.
- **KHÔNG commit/push** trừ khi người dùng yêu cầu.
- **KHÔNG tự tuyên bố PASS / APPROVE / DONE.** Bạn là implementer; người duy trì
  là adjudicator duy nhất.
- **KHÔNG báo số liệu test từ trí nhớ.** Chỉ dán từ output của
  `verify_phase.ps1`.
- **KHÔNG bắt đầu phase tiếp theo** khi chưa có go-ahead riêng (AGENT_RULES rule 12).
- **KHÔNG hardcode API key** ở bất cứ đâu. Dùng biến môi trường.

## Quy ước code

- Test đặt trong `tests/`, dùng `importlib.util.spec_from_file_location` để nạp
  script từ `scripts/` (thư mục đó không phải Python package).
- Validator dùng pattern **type-first**: luôn `isinstance` TRƯỚC khi làm
  membership/hash. Lý do: `list`/`dict` không hashable → `x in SET` ném
  `TypeError`; và `bool` là subclass của `int` nên phải loại trừ tường minh.
- Thông báo lỗi: dùng đường dẫn tương đối, không lộ đường dẫn tuyệt đối hay nội
  dung artifact thô.

## Quy trình

Tóm tắt quy trình cộng tác AI: Grok planning chat → Code X implement → Qwen
preflight (advisory) → `verify_phase.ps1` → handoff/commit → Grok audit chat +
Gemini gate tương ứng → người duy trì adjudicate. Grok planning và audit không
dùng chung chat. (Nhật ký cộng tác chi tiết lưu trong lịch sử Git.)
