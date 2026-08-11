## Confusion Matrix — Phase 13 (v3)

| | Bị chặn | Được trả lời |
|---|---:|---:|
| **Malicious** (n=200) | 155 (TP) | 45 (FN) |
| **Benign** (n=225) | 25 (FP) | 200 (TN) |

### Chỉ số

| Chỉ số | Giá trị | Ghi chú |
|---|---:|---|
| TPR | 77.5% | chặn đúng / tổng malicious |
| FPR (toàn benign) | 11.1% | chặn nhầm / tổng benign |
| FPR hard_benign | 14.4% | chặn nhầm / benign hard (n=125) |
| FPR normal_benign | 7.0% | chặn nhầm / benign thường (n=100) |
| Stop-before-LLM | 77.0% | malicious bị chặn trước khi gọi provider |
| Exfil marker | 21.5% | canary lọt ra response (n đo được = 200) |

*Latency: không báo cáo (quyết định L2 — `latency_reportable=false`).*
*Rate có mẫu < 10 được báo là "không đủ mẫu".*

### Theo nguồn kỹ thuật (tool_family, malicious)

| Nhóm | Tổng | Bị chặn | Tỉ lệ chặn* |
|---|---:|---:|---:|
| garak | 105 | 80 | 76.2% |
| injecagent | 38 | 18 | 47.4% |
| pyrit | 57 | 57 | 100.0% |

\* Tỉ lệ chỉ báo khi n ≥ 10.

### Theo technique (malicious)

| Nhóm | Tổng | Bị chặn | Tỉ lệ chặn* |
|---|---:|---:|---:|
| csuite_impersonation | 24 | 24 | 100.0% |
| direct_kb_exfil | 10 | 4 | 40.0% |
| executive_roleplay | 28 | 28 | 100.0% |
| hidden_instruction_in_prose | 24 | 18 | 75.0% |
| multi_turn_escalation | 5 | 5 | không đủ mẫu |
| payload_splitting | 30 | 30 | 100.0% |
| poisoned_context_authority | 14 | 0 | 0.0% |
| rag_dan | 35 | 35 | 100.0% |
| unicode_smudging | 30 | 11 | 36.7% |

\* Tỉ lệ chỉ báo khi n ≥ 10.

### Theo loại tấn công (attack_type)

| Nhóm | Tổng | Bị chặn | Tỉ lệ chặn* |
|---|---:|---:|---:|
| csuite_impersonation | 24 | 24 | 100.0% |
| data_exfiltration | 10 | 4 | 40.0% |
| indirect_prompt_injection | 24 | 18 | 75.0% |
| multi_turn_escalation | 5 | 5 | không đủ mẫu |
| obfuscated_injection | 30 | 11 | 36.7% |
| payload_splitting | 30 | 30 | 100.0% |
| rag_poisoning | 49 | 35 | 71.4% |
| roleplay_exfiltration | 28 | 28 | 100.0% |

\* Tỉ lệ chỉ báo khi n ≥ 10.

### Theo technique (benign — precision stress)

| Nhóm | Tổng | Bị chặn | Tỉ lệ chặn* |
|---|---:|---:|---:|
| hard_benign_paraphrase | 18 | 6 | 33.3% |
| hard_benign_security_legit | 38 | 3 | 7.9% |
| hard_benign_self_service | 32 | 6 | 18.8% |
| hard_benign_sensitive_keyword | 37 | 3 | 8.1% |
| normal_business_query | 100 | 7 | 7.0% |

\* Tỉ lệ chỉ báo khi n ≥ 10.
