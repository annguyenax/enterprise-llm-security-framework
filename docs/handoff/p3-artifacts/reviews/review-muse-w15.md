# Review Muse — W15 (canonical LF ledger I/O)

Phạm vi: Codex implement, Claude review chéo PASS-WITH-FIXES, coordinator không đổi code sau Claude. Đọc `review-claude-w15.md`, `w15/w15-implement-notes.md` (kèm follow-up coordinator) và diff uncommitted tại HEAD `796ae25` (`M scripts/v2_validation_ledger.py`, `?? tests/test_w15_canonical_io.py`). Không chạy pytest/self-check, không chạy trên máy An, không push, không mở holdout, không sửa code, không commit.

Verdict: **PASS**

- Writer ledger: `claim_validation_slot` thêm `getattr(os, "O_BINARY", 0)` vào descriptor append; payload vẫn từ `canonical(record)` (UTF-8, LF duy nhất). Receipt/`xb` và các artifact binary khác giữ nguyên.
- `read_claims` không nới: diff không chạm reader/canonical/hash-chain/lock/cap; không có auto-repair hay rollback; ledger CRLF cũ vẫn fail closed, bytes cũ giữ nguyên.
- Test tái hiện đúng cặp đối chứng: `_append_like_796ae25` (flags cũ thiếu `O_BINARY`) ra CRLF và bị production `read_claims` từ chối `malformed`; production writer mới dưới cùng fixture `windows_newlines` cho bytes đúng `canonical(record)`, không CR, lượt thứ tư bị chặn.
- Self-check tạm, không tiêu cap: `self_check_canonical_io()` không nhận path, chỉ tạo ledger synthetic dưới `TemporaryDirectory` bằng `xb`, gọi production claim/read, cấm CR, dọn sau khi xong; test phủ cả hai nhánh `break_binary` False/True.
- FIX-01 (Claude P3W15-FIX-01): đồng ý theo hướng coordinator — thẻ preflight bắt buộc trong runbook VAL2, FAIL thì dừng trước claim thật và giữ output làm evidence; không đổi runner trong W15.
- FIX-02 (chỉ tài liệu): `audit_logger` text mode `"a"` có thể ra CRLF trên Windows nhưng chỉ quét substring, nằm trong temp `_execute_config`, không phải official evidence; không đổi app logger/guard trong W15.
- NEW-01: không nhúng `self_check_canonical_io()` vào official claim path trong W15; cần go-ahead riêng vì đổi đường official.
- Holdout/gate/cap 3 không đổi: diff chỉ chạm ledger script + test W15 mới; không sửa runner/analyzer/holdout gate/manifest/freeze loader.
