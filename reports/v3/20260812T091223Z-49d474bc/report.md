## Confusion Matrix — Phase 13 (v3)

| | Bị chặn | Được trả lời |
|---|---:|---:|
| **Malicious** (n=200) | 200 (TP) | 0 (FN) |
| **Benign** (n=225) | 42 (FP) | 183 (TN) |

### Chỉ số

| Chỉ số | Giá trị | Ghi chú |
|---|---:|---|
| TPR | 100.0% | chặn đúng / tổng malicious |
| FPR (toàn benign) | 18.7% | chặn nhầm / tổng benign |
| FPR hard_benign | 20.0% | chặn nhầm / benign hard (n=125) |
| FPR normal_benign | 17.0% | chặn nhầm / benign thường (n=100) |
| Stop-before-LLM | 81.5% | malicious bị chặn trước khi gọi provider |
| Exfil marker | 0.0% | canary lọt ra response (n đo được = 200) |

*Latency: không báo cáo (quyết định L2 — `latency_reportable=false`).*
*Rate có mẫu < 10 được báo là "không đủ mẫu".*

### Theo nguồn kỹ thuật (tool_family, malicious)

| Nhóm | Tổng | Bị chặn | Tỉ lệ chặn* |
|---|---:|---:|---:|
| garak | 105 | 105 | 100.0% |
| injecagent | 38 | 38 | 100.0% |
| pyrit | 57 | 57 | 100.0% |

\* Tỉ lệ chỉ báo khi n ≥ 10.

### Theo technique (malicious)

| Nhóm | Tổng | Bị chặn | Tỉ lệ chặn* |
|---|---:|---:|---:|
| csuite_impersonation | 24 | 24 | 100.0% |
| direct_kb_exfil | 10 | 10 | 100.0% |
| executive_roleplay | 28 | 28 | 100.0% |
| hidden_instruction_in_prose | 24 | 24 | 100.0% |
| multi_turn_escalation | 5 | 5 | không đủ mẫu |
| payload_splitting | 30 | 30 | 100.0% |
| poisoned_context_authority | 14 | 14 | 100.0% |
| rag_dan | 35 | 35 | 100.0% |
| unicode_smudging | 30 | 30 | 100.0% |

\* Tỉ lệ chỉ báo khi n ≥ 10.

### Theo loại tấn công (attack_type)

| Nhóm | Tổng | Bị chặn | Tỉ lệ chặn* |
|---|---:|---:|---:|
| csuite_impersonation | 24 | 24 | 100.0% |
| data_exfiltration | 10 | 10 | 100.0% |
| indirect_prompt_injection | 24 | 24 | 100.0% |
| multi_turn_escalation | 5 | 5 | không đủ mẫu |
| obfuscated_injection | 30 | 30 | 100.0% |
| payload_splitting | 30 | 30 | 100.0% |
| rag_poisoning | 49 | 49 | 100.0% |
| roleplay_exfiltration | 28 | 28 | 100.0% |

\* Tỉ lệ chỉ báo khi n ≥ 10.

### Theo technique (benign — precision stress)

| Nhóm | Tổng | Bị chặn | Tỉ lệ chặn* |
|---|---:|---:|---:|
| hard_benign_paraphrase | 18 | 6 | 33.3% |
| hard_benign_security_legit | 38 | 5 | 13.2% |
| hard_benign_self_service | 32 | 6 | 18.8% |
| hard_benign_sensitive_keyword | 37 | 8 | 21.6% |
| normal_business_query | 100 | 17 | 17.0% |

\* Tỉ lệ chỉ báo khi n ≥ 10.
