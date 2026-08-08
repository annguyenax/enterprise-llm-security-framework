## Confusion Matrix — Phase 13 (v3)

| | Bị chặn | Được trả lời |
|---|---:|---:|
| **Malicious** (n=200) | 98 (TP) | 102 (FN) |
| **Benign** (n=100) | 0 (FP) | 100 (TN) |

### Chỉ số

| Chỉ số | Giá trị | Ghi chú |
|---|---:|---|
| TPR | 49.0% | chặn đúng / tổng malicious |
| FPR | 0.0% | chặn nhầm / tổng benign |
| Stop-before-LLM | 49.0% | malicious bị chặn trước khi gọi provider |
| Exfil marker | 0.0% | canary lọt ra response |

*Latency: không báo cáo (quyết định L2 — `latency_reportable=false`).*
*Rate có mẫu < 10 được báo là "không đủ mẫu".*

### Theo nguồn kỹ thuật (đếm, không phải tỉ lệ)

| Nhóm | Tổng | Bị chặn |
|---|---:|---:|
| garak | 105 | 82 |
| injecagent | 40 | 16 |
| pyrit | 55 | 0 |

### Theo loại tấn công (đếm, không phải tỉ lệ)

| Nhóm | Tổng | Bị chặn |
|---|---:|---:|
| csuite_impersonation | 25 | 0 |
| data_exfiltration | 10 | 3 |
| indirect_prompt_injection | 25 | 16 |
| obfuscated_injection | 30 | 14 |
| payload_splitting | 30 | 30 |
| rag_poisoning | 50 | 35 |
| roleplay_exfiltration | 30 | 0 |
