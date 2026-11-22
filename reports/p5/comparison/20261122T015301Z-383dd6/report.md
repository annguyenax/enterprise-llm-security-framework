# P5 — So sánh định lượng với Baseline chuẩn & Benchmark bên ngoài

Đáp ứng nhận xét của giảng viên:
- **Điểm 1 & 2 (Đánh giá độc lập ngoài tập tự sinh):** Chạy bộ luật đóng băng trên dataset công khai `deepset/prompt-injections` (HuggingFace) mà không sửa bất kỳ regex nào.
- **Điểm 4 & 5 (Đo latency p50/p95/p99 & So sánh với Llama Guard / NeMo Guardrails):** Chạy cùng tập mẫu qua Shield AI, Meta Llama Guard 3 (`llama-guard3:1b`), và mẫu prompt `self_check_input` chuẩn của NVIDIA NeMo Guardrails.

## Tập dữ liệu: `v3_425` (Tập 425 case của đồ án (200 malicious, 225 benign))

- Tổng số mẫu: **425** (Tấn công: **200**, Benign: **225**)
- SHA-256 dataset: `b3127ecd8184fe77f0aef3fa1043722120f2000bad52f5cc7e64991ef77b2e37`

| Giải pháp | TP / Mal | FP / Ben | TPR (Recall) | FPR | Precision | F1 | Latency p50 (ms) | Latency p95 (ms) | Latency p99 (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Shield AI (Rule + Fast Pre-screen, Judge OFF)** | 194/200 | 0/225 | **97.0%** | **0.0%** | 100.0% | 98.5% | 0.20 | 0.35 | 0.40 |
| **Shield AI (Input Regex Guard Only)** | 194/200 | 0/225 | **97.0%** | **0.0%** | 100.0% | 98.5% | 0.12 | 0.35 | 0.38 |
| **Meta Llama Guard 3 (`llama-guard3:1b`)** | 194/200 | 17/225 | **97.0%** | **7.6%** | 91.9% | 94.4% | 58.09 | 83.12 | 90.31 |
| **NeMo Guardrails `self_check_input` (`gemma4:e2b-it-q4_K_M`)** | 187/200 | 0/225 | **93.5%** | **0.0%** | 100.0% | 96.6% | 98.15 | 120.16 | 125.23 |
| **Shield AI (Rule + Semantic Judge `gemma4:e2b-it-q4_K_M`)** | 200/200 | 0/225 | **100.0%** | **0.0%** | 100.0% | 100.0% | 0.45 | 109.15 | 112.83 |

## Tập dữ liệu: `deepset_test` (HuggingFace deepset/prompt-injections (test split, 116 case))

- Tổng số mẫu: **116** (Tấn công: **60**, Benign: **56**)
- SHA-256 dataset: `c09b6f1a2db6cf96dcf3626a6755b1e231adef98b517d567809012d1bad242c5`

| Giải pháp | TP / Mal | FP / Ben | TPR (Recall) | FPR | Precision | F1 | Latency p50 (ms) | Latency p95 (ms) | Latency p99 (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Shield AI (Rule + Fast Pre-screen, Judge OFF)** | 1/60 | 0/56 | **1.7%** | **0.0%** | 100.0% | 3.3% | 0.18 | 0.87 | 1.69 |
| **Shield AI (Input Regex Guard Only)** | 0/60 | 0/56 | **0.0%** | **0.0%** | 0.0% | 0.0% | 0.07 | 0.44 | 0.78 |
| **Meta Llama Guard 3 (`llama-guard3:1b`)** | 8/60 | 2/56 | **13.3%** | **3.6%** | 80.0% | 22.9% | 34.43 | 72.66 | 82.27 |
| **NeMo Guardrails `self_check_input` (`gemma4:e2b-it-q4_K_M`)** | 13/60 | 0/56 | **21.7%** | **0.0%** | 100.0% | 35.6% | 96.97 | 115.91 | 123.66 |
| **Shield AI (Rule + Semantic Judge `gemma4:e2b-it-q4_K_M`)** | 17/60 | 0/56 | **28.3%** | **0.0%** | 100.0% | 44.2% | 91.18 | 110.62 | 112.83 |

## Tập dữ liệu: `deepset_all` (HuggingFace deepset/prompt-injections (full train+test, 662 case))

- Tổng số mẫu: **662** (Tấn công: **263**, Benign: **399**)
- SHA-256 dataset: `4aeab3a7916b8a9089b65f8be56e4c05e31ba5c0c1a77fb13fbe10c59de7cc0b`

| Giải pháp | TP / Mal | FP / Ben | TPR (Recall) | FPR | Precision | F1 | Latency p50 (ms) | Latency p95 (ms) | Latency p99 (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Shield AI (Rule + Fast Pre-screen, Judge OFF)** | 11/263 | 0/399 | **4.2%** | **0.0%** | 100.0% | 8.0% | 0.16 | 0.76 | 1.58 |
| **Shield AI (Input Regex Guard Only)** | 10/263 | 0/399 | **3.8%** | **0.0%** | 100.0% | 7.3% | 0.06 | 0.35 | 0.75 |
| **Meta Llama Guard 3 (`llama-guard3:1b`)** | 61/263 | 7/399 | **23.2%** | **1.8%** | 89.7% | 36.9% | 36.71 | 65.94 | 82.88 |
| **NeMo Guardrails `self_check_input` (`gemma4:e2b-it-q4_K_M`)** | 78/263 | 4/399 | **29.7%** | **1.0%** | 95.1% | 45.2% | 97.73 | 120.74 | 143.60 |
| **Shield AI (Rule + Semantic Judge `gemma4:e2b-it-q4_K_M`)** | 97/263 | 2/399 | **36.9%** | **0.5%** | 98.0% | 53.6% | 89.12 | 115.49 | 126.67 |

