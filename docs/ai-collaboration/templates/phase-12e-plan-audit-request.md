# Template: Phase 12E Plan Audit Request (Gate G0)

Audit **kế hoạch** `docs/ai-collaboration/06_PHASE_12E_MASTER_PLAN.md`, **không**
audit code (chưa có code 12E). Ba auditor chạy **song song** trên **cùng một
commit**. Cả ba phải PASS trước khi viết dòng code 12E đầu tiên.

> Đây là audit thiết kế nghiên cứu. Auditor không sửa file, không commit, không
> bắt đầu triển khai.

---

## Phần chung (điền một lần, dùng cho cả ba)

```
Repository: enterprise-llm-security-framework
Branch: phase-12e-planning
Commit cần review: <full sha>

Tài liệu chính cần review:
- docs/ai-collaboration/06_PHASE_12E_MASTER_PLAN.md

Ngữ cảnh (đọc để đối chiếu):
- docs/ai-collaboration/00_PROJECT_STATE.md
- docs/benchmark-v2-methodology.md
- docs/decisions/ADR-003-v2-benchmark.md
- app/core/pipeline.py            (GuardProfile CHƯA tồn tại — xác nhận)
- app/core/config.py              (không có guard toggle — xác nhận)
- app/services/rag_query.py       (seam provider=, latency_ms — xác nhận)
- app/services/llm_provider.py    (Mock không echo context — xác nhận §15)

Không sửa file. Không commit. Không bắt đầu triển khai 12E.

MỖI auditor PHẢI mở đầu bằng khối này:
- Branch inspected:
- Exact commit inspected:
- Repository files directly inspected: yes/no  (liệt kê file đã mở thật)

Và PHẢI kết thúc bằng:
- Critical findings: None hoặc danh sách
- Major findings: None hoặc danh sách
- Minor findings: None hoặc danh sách
- Deferrable recommendations: None hoặc danh sách
- Final Verdict: PASS hoặc REVISE
```

---

## Phần A — Code X: Technical & Reproducibility Audit

```
Đánh giá kế hoạch về tính đúng đắn kỹ thuật và khả năng tái lập. Kiểm tra:

1. Bằng chứng nền (§0) có KHỚP với code thật không? Đặc biệt:
   - GuardProfile thật sự CHƯA tồn tại?
   - Seam provider=/retriever= thật sự injectable như §0 tuyên bố?
   - 8 khoá latency_ms và khoá "total" đúng như liệt kê?
   - Mock Provider thật sự không echo context (⇒ §15 đúng)?
2. Thiết kế guard-toggle (§7) có thực sự BẤT KHẢ THI từ đường public không (§8)?
   Có kẽ hở nào để env var / request field / route tắt được guard không?
3. Cổng manifest (§11) + abort-trên-dirty (§22,§25) có đủ chặt theo ADR-003 không?
4. Kiểm tra tính tất định (§21) có đúng là điều kiện dừng-cứng không?
5. Chống so-sánh-khác-commit (§29) có được cưỡng chế ở tầng analyzer không?
6. Công thức p50/p95 (§18), marginal contribution (§19) có đúng toán học không?
7. Schema artifact (§23) có rò rỉ nội dung thô không?
8. Quy trình tái lập (§26) có thực sự tái lập được không?
9. Mọi chỗ "VERIFY DURING IMPLEMENTATION" có phải thật sự chưa chứng minh được
   không, hay kế hoạch đang giấu một giả định sai dưới nhãn đó?

Nêu rõ mọi chỗ kế hoạch TUYÊN BỐ code hiện có hỗ trợ một tính năng mà thực tế
code KHÔNG chứng minh.
```

## Phần B — Gemini: Academic & Methodology Audit

```
Đánh giá kế hoạch về tính hợp lệ học thuật cho luận văn đại học. Kiểm tra:

1. Câu hỏi nghiên cứu (§2) và giả thuyết (§3) có kiểm chứng/bác bỏ được không?
2. Đơn vị phân tích (§4) có nhất quán không?
3. Metric (§12-15) có đo đúng thứ nó tuyên bố không? Định nghĩa "correct" dùng
   allowed_* thay vì expected_* — có tránh được vòng tròn không?
4. Giới hạn rò rỉ (§15) — kế hoạch có TRUNG THỰC về việc Mock Provider không cho
   đo rò rỉ end-to-end không? Cách xử lý bằng provider double có hợp lệ không?
5. Báo cáo theo nhóm (§20) có tuân thủ đúng ràng buộc "không phần trăm theo
   family" mà bạn đã nêu ở audit 12D không?
6. Giới hạn thống kê (§27) có thành thật về cỡ mẫu nhỏ không?
7. Rủi ro construct/internal/external validity (§28-30) có đầy đủ không?
8. Danh sách claim bị cấm (§31) có bao phủ mọi cách luận văn có thể nói quá không?
9. Định nghĩa DONE (§40) có đủ chặt để ngăn kết luận non không?

Nêu mọi chỗ kế hoạch có thể dẫn tới overclaim trong luận văn.
Ghi rõ nếu bạn KHÔNG truy cập được file thật ("CANNOT VERIFY").
```

## Phần C — Grok: Adversarial & Red-Team Audit

```
Đánh giá kế hoạch theo góc nhìn attacker và an toàn. Kiểm tra:

1. Ma trận ablation (§6) có bỏ sót cấu hình nào quan trọng về mặt tấn công không?
2. §8/§32: thêm khả năng tắt guard cho evaluation có VÔ TÌNH mở đường cho client
   tắt guard qua API không? Đây là rủi ro số một — soi kỹ.
3. C6_none (no-guard baseline) có được cô lập đủ an toàn không (§5 điều kiện 1-4)?
4. Kế hoạch có ngăn được việc dùng candidate của Hermes làm ground truth tự động
   không (§32)?
5. Các probe red-team bạn đề xuất ở 12D (budget-exact VN splits, trusted-source
   canary, homoglyph+benign) được xử lý đúng là "exploratory, tách khỏi metric"
   chứ không lẫn vào benchmark đã freeze chứ?
6. Có đường nào để "peek" holdout hoặc chạy lại holdout cho đẹp không (§10,§38)?
7. Residual-risk case (§28) có bị lợi dụng để giấu điểm yếu không?
8. Artifact kết quả (§23) có thể rò rỉ payload tấn công không?

Đề xuất thêm probe/ràng buộc nếu cần — nhưng KHÔNG phải case mới cho benchmark
đã FINAL freeze.
```

---

## Sau khi có 3 verdict

- **Cả 3 PASS** → cập nhật `00_PROJECT_STATE.md`; người duy trì phê duyệt bắt đầu
  12E.1. Chỉ khi đó mới viết dòng code 12E đầu tiên.
- **Bất kỳ REVISE nào** → sửa kế hoạch theo `templates/fix-request.md` (nhưng là
  sửa TÀI LIỆU, không phải code), rồi audit lại.
