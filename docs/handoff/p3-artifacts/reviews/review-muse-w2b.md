# Review W2b `db791b4` (parent `f47dfec`, feat-p3-rag-opt)

**Verdict: PASS**

**Phạm vi:** [patch W2b](/workspace/deliverables/shield-phase3-rag-opt-20261111/prompts/w2b-db791b4.patch) — không fold clipping budget thành SANITIZE; giữ `Decision` gốc; stage `context_budget` trung lập (`decision=None`); 0011 giữ nguyên.

**Kiểm tra:**

- Truncate/exclude giữ `context_outcomes[...][2]` gốc, chỉ ghi đè `reason_code` budget + thêm stage trung lập. Đúng hướng: containment tài nguyên không phải sanitize bảo mật.
- SANITIZE thật được giữ (test `preserves_real_security_sanitize`); chunk loại hẳn không fold (test `sanitized_empty_chunk`).
- Test bổ sung bao phủ 4 profile × 2 budget + audit log (`final allow`, `stage_reason_codes`, không leak context). Theo báo cáo: 160+79 passed.
- Dev MOCK (báo cáo): C0/C3 AOMR không đổi (8/14, 5/14), FPR 4/12→1/12. 0011 (hits vs no_hits) không sửa. Không val/holdout, đúng phạm vi dev.

**Ghi chú không chặn:**

- `provenance.reason_code` bị ghi đè thành budget reason, mất reason gốc tại provenance; tín hiệu bảo mật còn ở `stage_results` + final fold. Downstream đừng chỉ đọc provenance.
- Chưa val/holdout: cần trước merge/promote, không chặn ở bước dev này.
- Fixture `test_low_relevance` kéo dài ×20 thiếu comment lý do trong trích patch; nên giải thích một dòng.
