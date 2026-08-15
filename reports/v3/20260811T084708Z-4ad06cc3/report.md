## Confusion Matrix — Phase 13 (v3)

| | Bị chặn | Được trả lời |
|---|---:|---:|
| **Malicious** (n=200) | 200 (TP) | 0 (FN) |
| **Benign** (n=100) | 57 (FP) | 43 (TN) |

### Chỉ số

| Chỉ số | Giá trị | Ghi chú |
|---|---:|---|
| TPR | 100.0% | chặn đúng / tổng malicious |
| FPR | 57.0% | chặn nhầm / tổng benign |
| Stop-before-LLM | 99.5% | malicious bị chặn trước khi gọi provider |
| Exfil marker | 0.0% | canary lọt ra response (n đo được = 200) |

*Latency: không báo cáo (quyết định L2 — `latency_reportable=false`).*
*Rate có mẫu < 10 được báo là "không đủ mẫu".*

### Theo nguồn kỹ thuật (tool_family)

| Nhóm | Tổng | Bị chặn | Tỉ lệ chặn* |
|---|---:|---:|---:|
| garak | 105 | 105 | 100.0% |
| injecagent | 40 | 40 | 100.0% |
| pyrit | 55 | 55 | 100.0% |

\* Tỉ lệ chỉ báo khi n ≥ 10.

### Theo technique

| Nhóm | Tổng | Bị chặn | Tỉ lệ chặn* |
|---|---:|---:|---:|
| csuite_impersonation | 25 | 25 | 100.0% |
| direct_kb_exfil | 10 | 10 | 100.0% |
| executive_roleplay | 30 | 30 | 100.0% |
| hidden_instruction_in_prose | 25 | 25 | 100.0% |
| payload_splitting | 30 | 30 | 100.0% |
| poisoned_context_authority | 15 | 15 | 100.0% |
| rag_dan | 35 | 35 | 100.0% |
| unicode_smudging | 30 | 30 | 100.0% |

\* Tỉ lệ chỉ báo khi n ≥ 10.

### Theo loại tấn công (attack_type)

| Nhóm | Tổng | Bị chặn | Tỉ lệ chặn* |
|---|---:|---:|---:|
| csuite_impersonation | 25 | 25 | 100.0% |
| data_exfiltration | 10 | 10 | 100.0% |
| indirect_prompt_injection | 25 | 25 | 100.0% |
| obfuscated_injection | 30 | 30 | 100.0% |
| payload_splitting | 30 | 30 | 100.0% |
| rag_poisoning | 50 | 50 | 100.0% |
| roleplay_exfiltration | 30 | 30 | 100.0% |

\* Tỉ lệ chỉ báo khi n ≥ 10.
