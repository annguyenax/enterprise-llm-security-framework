# Review W14 — Muse

- Phạm vi: đọc `review-claude-w14.md`, `w14/w14-implement-notes.md`; xác nhận FIX-01/02 qua `git diff` trên HEAD `bbb78f3` (chưa commit). Không chạy, không push, không mở holdout, không sửa code.
- Verdict: **PASS**

- Ollama chỉ mở khi đồng thời `dev-val` + `validation`; các mode/split khác fail trước I/O.
- Official/holdout vẫn đòi authorization; `VerifiedHoldoutAuthorization` và các gate holdout không bị nới.
- Capability dev-val là class riêng, không mở được cổng holdout; trộn hai capability hoặc hai evidence bị từ chối.
- Analyzer dev-val rẽ sang verifier dev-val, không gọi `verify_frozen_manifest`; đường official giữ verifier cũ.
- Cap validation = 3, ledger append-only hash-chain, claim ghi sau kiểm output; MOCK attempt=0, không tiêu thụ lượt.
- Ngưỡng v6 giữ nguyên (FPR, AOMR C0≥C3, mismatch, coverage, error_rate); AOMR<0.80 hoặc UNKNOWN bật cờ An quyết trước W5, không tự cấp W5.
- FIX-01 đã áp: `_ollama_provider_spec` khôi phục kiểm `llm_provider` + preclaim trước literal descriptor, kèm test trong `test_p2_authorized_ollama_runner.py`.
- FIX-02 đã áp: analyzer in `FAIL [{exc.code}]` cho `RunnerError` thay vì nuốt thành `internal_error`.
- NEW-01/02/03 vẫn là ghi chú runbook/An chốt (purpose W2/W3, MOCK campaign ID, fixture hash holdout cũ), không chặn PASS.
