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

## Trạng thái hiện tại (2026-07-13)

- Phase 12C (RAG pipeline): **DONE** — Code X final re-audit PASS
- Phase 12D (Benchmark V2): **DONE** — manifest FINAL, 3 gate audit đều PASS
- Phase 12E (Evaluation): **CHƯA BẮT ĐẦU** — cần go-ahead riêng

Cả hai phase chặn 12E đều đã đóng. 12E vẫn cần go-ahead riêng (AGENT_RULES
rule 12).

## Lệnh

```powershell
.\scripts\verify_phase.ps1              # TOÀN BỘ checklist + evidence block
.\scripts\verify_phase.ps1 -Focused     # nhanh, khi đang lặp fix
.venv\Scripts\python.exe -m pytest -q   # full suite (578 passed, 1 warning)
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

Xem `docs/ai-collaboration/README.md`. Tóm tắt: implement → `verify_phase.ps1`
→ điền handoff YAML → commit → 3 auditor (Code X/Gemini/Grok) chạy song song
trên cùng commit → người adjudicate.
