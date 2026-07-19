# CLAUDE.md

Hướng dẫn cho AI agent làm việc trên repo này. Đọc file này trước mọi task.

## Dự án

Enterprise LLM Security Framework — đồ án thực tập đại học. Lab-scale LLM
Security Gateway / Guardrail Proxy đứng trước một ứng dụng RAG, phòng chống
prompt injection, indirect injection, jailbreak, rò rỉ dữ liệu, và data
poisoning. **PoC học thuật, KHÔNG phải production**, dữ liệu tổng hợp hoàn toàn.

## Đọc trước khi làm bất cứ việc gì

1. `docs/ai-collaboration/00_PROJECT_STATE.md` — phase nào, commit nào, gate nào đã qua
2. `AGENT_RULES.md` — luật cứng của dự án
3. `docs/ai-collaboration/01_AGENT_ROLES.md` — vai của bạn và giới hạn quyền

## Trạng thái hiện tại (2026-07-19)

- Phase 12C (RAG pipeline): **DONE** — Code X final re-audit PASS
- Phase 12D (Benchmark V2): **DONE** — manifest FINAL, 3 gate audit đều PASS
- Phase 12E (Evaluation): **12E.1 G1 PASS; 12E.2 G2 PASS; 12E.3 CLOSED PASS;
  12E.4 PLANNING — HOLDOUT UNAUTHORIZED**

Cả hai phase chặn 12E đều đã đóng. Kế hoạch tại commit `d82bac7` đã qua
Code X, Gemini và Grok với verdict PASS. GuardProfile foundation tại
`8b1e485f128d08adc4baeed499363886e8969a18` qua G1 PASS. Development-only runner
tại `2233002ccf3e067ab932a5a8fa2b6a7bbe350b01` qua G2 PASS.

**Phase 12E.3 đã đóng với verdict PASS** — implementation identity
`c6d91c78e11009e96a76db08c0dfbb710504c227`; validation artifact closure PASS
(`docs/modernization-ai-reviews/code-x-phase-12e-3-validation-artifact-closure.md`);
không còn Critical hoặc blocking Major. Analyzer tồn tại tại
`scripts/analyze_v2_results.py`. **Validation đã được quan sát và KHOÁ LẠI —
không chạy lại** trừ khi có re-adjudication tường minh riêng.

**Phase 12E.4 đang lập kế hoạch.** Kế hoạch ràng buộc:
`docs/ai-collaboration/07_PHASE_12E4_HOLDOUT_PLAN.md`. Latency theo **L2**: RQ4
bị gỡ khỏi research question có thể báo cáo, H5 phân loại lại thành mô tả không
báo cáo, `latency_reportable=false`, `p50`/`p95` null. **Holdout CHƯA ĐƯỢC THỰC
THI và CHƯA ĐƯỢC PHÊ DUYỆT.**

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

Xem `docs/ai-collaboration/README.md`. Tóm tắt: Grok planning chat → Code X
implement → Qwen preflight (advisory) → `verify_phase.ps1` → handoff/commit →
Grok audit chat + Gemini gate tương ứng → người duy trì adjudicate. Grok
planning và audit không dùng chung chat.
