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

## Trạng thái hiện tại (2026-07-14)

- Phase 12C (RAG pipeline): **DONE** — Code X final re-audit PASS
- Phase 12D (Benchmark V2): **DONE** — manifest FINAL, 3 gate audit đều PASS
- Phase 12E (Evaluation): **12E.1 G1 PASS; 12E.2 CHƯA BẮT ĐẦU**

Cả hai phase chặn 12E đều đã đóng. Kế hoạch tại commit `d82bac7` đã qua
Code X, Gemini và Grok với verdict PASS, không còn Critical hoặc blocking
Major. GuardProfile foundation tại commit
`8b1e485f128d08adc4baeed499363886e8969a18` đã qua Grok Web combined G1 audit
với verdict PASS. 12E.2 vẫn cần task riêng (AGENT_RULES rule 12); kết quả đánh
giá hiện là NONE và holdout chưa được thực thi.

## Operating model Phase 12E

- Planner: **Grok Web trong planning chat riêng**.
- Primary implementer: **Code X**, không được tự approve implementation của mình.
- Mechanical/local preflight: **Qwen2.5-Coder local**; không PASS/REVISE, finding
  phải được người duy trì hoặc Code X kiểm chứng trực tiếp.
- Adversarial candidate generation: **Hermes3 local**; không PASS/REVISE và
  candidate không bao giờ trở thành frozen benchmark ground truth.
- Mechanical verifier: **`scripts/verify_phase.ps1`**.
- Combined technical/security/red-team auditor: **Grok Web trong audit chat
  riêng**, không dùng planning chat.
- Academic/statistical auditor: **Gemini Web**, bắt buộc ở metric/statistical/
  claim gates.
- Final adjudicator và holdout approver: **người duy trì**.

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
