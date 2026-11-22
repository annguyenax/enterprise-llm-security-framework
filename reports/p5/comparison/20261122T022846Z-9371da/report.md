# P5 — So sánh định lượng với Baseline chuẩn & Benchmark bên ngoài

Đáp ứng nhận xét của giảng viên:
- **Điểm 1 & 2 (Đánh giá độc lập ngoài tập tự sinh):** Chạy bộ luật đóng băng trên dataset công khai `deepset/prompt-injections` (HuggingFace) mà không sửa bất kỳ regex nào.
- **Điểm 4 & 5 (Đo latency p50/p95/p99 & So sánh với Llama Guard / NeMo Guardrails):** Chạy cùng tập mẫu qua Shield AI, Meta Llama Guard 3 (`llama-guard3:1b`), và mẫu prompt `self_check_input` chuẩn của NVIDIA NeMo Guardrails.

## Tập dữ liệu: `v3_425` (Tập 425 case của đồ án (200 malicious, 225 benign))

- Tổng số mẫu: **425** (Tấn công: **200**, Benign: **225**)
- SHA-256 dataset: `b3127ecd8184fe77f0aef3fa1043722120f2000bad52f5cc7e64991ef77b2e37`

| Giải pháp | TP / Mal | FP / Ben | TPR (Recall) | FPR | Precision | F1 | Latency p50 (ms) | Latency p95 (ms) | Latency p99 (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Shield AI (Rule + Fast Pre-screen, Judge OFF)** | 194/200 | 0/225 | **97.0%** | **0.0%** | 100.0% | 98.5% | 0.47 | 1.29 | 1.59 |
| **Shield AI (Input Regex Guard Only)** | 194/200 | 0/225 | **97.0%** | **0.0%** | 100.0% | 98.5% | 0.29 | 1.25 | 1.44 |
| **Shield AI (Rule + Semantic Judge `gemma4:e2b-it-q4_K_M`)** | 200/200 | 0/225 | **100.0%** | **0.0%** | 100.0% | 100.0% | 1.23 | 146.23 | 156.13 |

## Tập dữ liệu: `deepset_test` (HuggingFace deepset/prompt-injections (test split, 116 case))

- Tổng số mẫu: **116** (Tấn công: **60**, Benign: **56**)
- SHA-256 dataset: `c09b6f1a2db6cf96dcf3626a6755b1e231adef98b517d567809012d1bad242c5`

| Giải pháp | TP / Mal | FP / Ben | TPR (Recall) | FPR | Precision | F1 | Latency p50 (ms) | Latency p95 (ms) | Latency p99 (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Shield AI (Rule + Fast Pre-screen, Judge OFF)** | 44/60 | 0/56 | **73.3%** | **0.0%** | 100.0% | 84.6% | 0.26 | 1.17 | 1.47 |
| **Shield AI (Input Regex Guard Only)** | 44/60 | 0/56 | **73.3%** | **0.0%** | 100.0% | 84.6% | 0.13 | 0.75 | 1.05 |
| **Shield AI (Rule + Semantic Judge `gemma4:e2b-it-q4_K_M`)** | 50/60 | 0/56 | **83.3%** | **0.0%** | 100.0% | 90.9% | 118.32 | 146.18 | 148.07 |

## Tập dữ liệu: `deepset_all` (HuggingFace deepset/prompt-injections (full train+test, 662 case))

- Tổng số mẫu: **662** (Tấn công: **263**, Benign: **399**)
- SHA-256 dataset: `4aeab3a7916b8a9089b65f8be56e4c05e31ba5c0c1a77fb13fbe10c59de7cc0b`

| Giải pháp | TP / Mal | FP / Ben | TPR (Recall) | FPR | Precision | F1 | Latency p50 (ms) | Latency p95 (ms) | Latency p99 (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Shield AI (Rule + Fast Pre-screen, Judge OFF)** | 130/263 | 0/399 | **49.4%** | **0.0%** | 100.0% | 66.2% | 0.19 | 0.91 | 2.20 |
| **Shield AI (Input Regex Guard Only)** | 130/263 | 0/399 | **49.4%** | **0.0%** | 100.0% | 66.2% | 0.12 | 0.64 | 1.36 |
| **Shield AI (Rule + Semantic Judge `gemma4:e2b-it-q4_K_M`)** | 210/263 | 2/399 | **79.8%** | **0.5%** | 99.1% | 88.4% | 120.84 | 146.95 | 162.62 |

