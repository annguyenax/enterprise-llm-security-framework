# Audit Request — Phase 12C Final Read-Only Re-Audit (Code X)

**Trạng thái:** SẴN SÀNG GỬI · Dán khối bên dưới vào Code X.

Đây là gate cuối chặn Phase 12E. Phase 12E đo chính pipeline của 12C, nên 12C
phải `DONE` trước.

---

## Bối cảnh (đã xác minh, không phải claim)

| Sự kiện | Commit | Kết quả |
|---|---|---|
| Pipeline 12C ban đầu | `10e3e97` | — |
| Code X final terminal audit | (review `10e3e97`) | **REVISE** — nested `ProvenanceItemResponse` dựng ngoài block bảo vệ |
| Fix + 5 regression test + báo cáo audit | `56b749a` | — |
| Merge 12C | `ad555c9` | — |
| **`app/` có đổi sau `ad555c9`?** | — | **KHÔNG** (`git log ad555c9..HEAD -- app/` trống) |
| Code X re-audit xác nhận PASS | — | **CHƯA CÓ → đây là blocker** |

Fix đã được xác minh trực tiếp trong code: `app/api/routes.py:349-401` —
`ProvenanceItemResponse`, `StageResultResponse`, và `RagQueryResponse` đều dựng
**bên trong một block `try` duy nhất**; `commit_rag_query_audit` chạy **sau khi**
toàn bộ cây response dựng xong (dòng 400); trên lỗi thì commit event
`mark_response_construction_failed` đã sửa (dòng 394).

---

## Khối dán vào Code X

```
Thực hiện FINAL READ-ONLY re-audit cho Phase 12C (RAG security pipeline).

Repository: enterprise-llm-security-framework
Branch: phase-12-rag-v2
Commit cần review: a460b76ab7225dc605ecae87c20d39bd23ea54cc

Không sửa file. Không commit. Không bắt đầu Phase 12E.

## Lịch sử audit
Vòng trước bạn trả verdict REVISE với finding:
  "ProvenanceItemResponse objects are constructed before the protected
   response-construction try. A failure there bypasses both corrected audit
   commit and safe request-ID error mapping."
Fix đã triển khai ở commit 56b749a. app/ KHÔNG thay đổi kể từ khi merge (ad555c9).

## Nhiệm vụ
Xác minh finding trên đã được sửa ĐÚNG, và không phát sinh lỗi mới.

Kiểm tra cụ thể:
1. app/api/routes.py::rag_query — MỌI response model lồng nhau
   (ProvenanceItemResponse, StageResultResponse, RagQueryResponse) có nằm trong
   cùng MỘT block try bảo vệ không?
2. Terminal-audit contract: mỗi đường kết thúc có commit ĐÚNG MỘT event chính
   xác không? Có đường nào commit "success" trước khi response dựng xong không?
3. run_rag_query_uncommitted / commit_rag_query_audit /
   mark_response_construction_failed — hợp đồng deferred-commit có đúng không?
4. Audit-sink failure có được xử lý an toàn ở mọi đường không?
5. 5 test regression cho lỗi này (test_rag_query_routes.py: test_nested_*,
   test_response_construction_failure_*) có THẬT SỰ chứng minh điều chúng tuyên
   bố, hay chỉ pass vờ?
6. Tài liệu (phase-12c-audit-resolution.md) có mô tả ĐÚNG hành vi thật của code
   không? (Vòng trước bạn đã bắt lỗi tài liệu claim sai — kiểm lại.)
7. Có rò rỉ đường dẫn tuyệt đối / nội dung thô / stack trace ra HTTP response
   hay audit log không?

## Bằng chứng verification (từ scripts/verify_phase.ps1, KHÔNG tự gõ lại)
- branch: phase-12-rag-v2
- base_commit: a460b76ab7225dc605ecae87c20d39bd23ea54cc
- focused_tests (Phase 12D): 255 passed
- full_suite: 578 passed, 1 warning
  (warning = Starlette deprecation về httpx2 — httpx2 là TYPOSQUAT, không bao
   giờ cài; đây là hành vi đã biết và đã ghi nhận)
- compile: PASS
- git_diff_check: PASS
- scope_invariants: PASS (không đụng app/, requirements.txt, redteam/,
  reports/evaluation/, report-latex-template/)

## Định dạng trả lời bắt buộc
# Code X Phase 12C Final Re-Audit

## Reviewed State
- Branch:
- Commit:
- Actual files inspected: yes/no

## Nested Response Construction (finding vòng trước)
- Status: RESOLVED / NOT RESOLVED
- Evidence:
- Blocking: yes/no

## Terminal Audit Contract
## Deferred-Commit Contract
## Test Adequacy
## Documentation Accuracy
## Error/Content Disclosure

## Remaining Critical Issues
None hoặc danh sách

## Remaining Blocking Major Issues
None hoặc danh sách

## Required Actions Before Phase 12C DONE
None hoặc danh sách

## Final Verdict
PASS hoặc REVISE
```

---

## Sau khi có kết quả

- **PASS** → cập nhật `00_PROJECT_STATE.md` (12C: DONE), `TASK_BOARD.md`,
  `tests/README.md`; ghi baseline commit; chạy lại `verify_phase.ps1`; người
  duy trì chấp thuận → mở đường cho Phase 12E.
- **REVISE** → dùng `templates/fix-request.md`, giao Claude sửa, rồi Code X xác
  minh lại.

**Không cần Gemini/Grok audit lại** — code họ đã xem không thay đổi
(`git log ad555c9..HEAD -- app/` trống).
