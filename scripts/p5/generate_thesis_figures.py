"""Generate publication-quality diagrams and empirical evaluation charts (300 DPI)
for the PTIT Graduation Thesis (Đồ án tốt nghiệp Đại học) report in
`report-datn-2026/figures/`.

Figures generated:
1. fig-baseline-comparison.png
   Quantitative comparison (TPR, FPR, F1) of Shield AI (v3 frozen, P5 Rule-Only,
   P5 Rule + Semantic Judge) vs. Meta Llama Guard 3 1B and NVIDIA NeMo Guardrails
   on both `v3_425` (n=425) and external `deepset/prompt-injections` (n=662).
2. fig-latency-breakdown.png
   Per-stage latency percentiles (p50, p95, p99 in ms) across the guarded pipeline
   with Semantic Judge OFF (n=1,275) vs. Semantic Judge ON (n=425), plus SQL Guard
   and Indirect Result Guard.
3. fig-garak-pyrit-redteam.png
   Live red-team prevention rates against NVIDIA `garak v0.17.1` (1,024 probes on
   `POST /v1/rag/query`) and `PyRIT` Converter Matrix (35 obfuscated variants)
   Before vs. After P5 optimization.
4. fig-sql-agent-architecture.png
   Architecture diagram of the P4 × P5 Text-to-SQL & Multi-Tool Company Agent
   defense-in-depth pipeline (Input Guard -> Tool Allowlist -> SQLite EXPLAIN +
   Authorizer AST Guard -> Read-Only Execution -> Indirect Result Guard + DLP ->
   Leader Approval Queue -> Output Guard).
"""
from __future__ import annotations

from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import numpy as np

OUT_DIR = Path(__file__).resolve().parents[2] / "report-datn-2026" / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams["font.family"] = "serif"
plt.rcParams["font.serif"] = ["Times New Roman", "DejaVu Serif"]
plt.rcParams["axes.unicode_minus"] = False


def make_baseline_comparison() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.4), dpi=300)
    fig.patch.set_facecolor("white")

    methods = [
        "Shield AI\n(v3 Regex cũ)",
        "Llama Guard 3\n(1B, Ollama)",
        "NeMo Guardrails\n(self_check_input)",
        "Shield AI P5\n(Rule + Pre-decoder)",
        "Shield AI P5\n(Rule + Judge 2B)",
    ]
    x = np.arange(len(methods))
    w = 0.26

    # Panel A: v3_425 (n=425)
    tpr_v3 = [97.0, 97.0, 93.5, 97.0, 100.0]
    fpr_v3 = [0.0, 7.6, 0.0, 0.0, 0.0]
    f1_v3 = [98.5, 94.4, 96.6, 98.5, 100.0]

    ax = axes[0]
    b1 = ax.bar(x - w, tpr_v3, w, label="TPR / Recall (%)", color="#0d9488", edgecolor="#0f766e")
    b2 = ax.bar(x, f1_v3, w, label="F1-Score (%)", color="#2563eb", edgecolor="#1d4ed8")
    b3 = ax.bar(x + w, fpr_v3, w, label="FPR — Chặn nhầm (%)", color="#ef4444", edgecolor="#b91c1c")
    ax.set_title("(a) Tập kiểm thử nội bộ v3 (n = 425: 200 tấn công, 225 benign)", fontsize=11, fontweight="bold", pad=10)
    ax.set_xticks(x)
    ax.set_xticklabels(methods, fontsize=8.5)
    ax.set_ylim(0, 114)
    ax.set_ylabel("Tỉ lệ (%)", fontsize=9.5)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for bars in (b1, b2, b3):
        for bar in bars:
            h = bar.get_height()
            ax.annotate(
                f"{h:.1f}",
                xy=(bar.get_x() + bar.get_width() / 2, h),
                xytext=(0, 2),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=7.2,
                fontweight="bold",
            )

    # Panel B: External deepset/prompt-injections (n=662)
    tpr_ds = [4.2, 23.2, 29.7, 68.1, 87.5]
    fpr_ds = [0.0, 1.8, 1.0, 0.0, 0.5]
    f1_ds = [8.0, 36.9, 45.2, 81.0, 92.9]

    ax2 = axes[1]
    b4 = ax2.bar(x - w, tpr_ds, w, label="TPR / Recall (%)", color="#0d9488", edgecolor="#0f766e")
    b5 = ax2.bar(x, f1_ds, w, label="F1-Score (%)", color="#2563eb", edgecolor="#1d4ed8")
    b6 = ax2.bar(x + w, fpr_ds, w, label="FPR — Chặn nhầm (%)", color="#ef4444", edgecolor="#b91c1c")
    ax2.set_title("(b) Benchmark độc lập deepset/prompt-injections (n = 662)", fontsize=11, fontweight="bold", pad=10)
    ax2.set_xticks(x)
    ax2.set_xticklabels(methods, fontsize=8.5)
    ax2.set_ylim(0, 114)
    ax2.set_ylabel("Tỉ lệ (%)", fontsize=9.5)
    ax2.grid(axis="y", linestyle="--", alpha=0.4)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    for bars in (b4, b5, b6):
        for bar in bars:
            h = bar.get_height()
            ax2.annotate(
                f"{h:.1f}",
                xy=(bar.get_x() + bar.get_width() / 2, h),
                xytext=(0, 2),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=7.2,
                fontweight="bold",
            )

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, frameon=True, fontsize=9.5, bbox_to_anchor=(0.5, 1.01))
    plt.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig(OUT_DIR / "fig-baseline-comparison.png", dpi=300)
    plt.close(fig)


def make_latency_breakdown() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13.2, 5.2), dpi=300)
    fig.patch.set_facecolor("white")

    # Panel A: Guard stages & SQL Guards (sub-2ms deterministic stages)
    stages = [
        "History Screen",
        "Output / DLP Guard",
        "Semantic Pre-screen\n(Heuristic)",
        "Input Guard\n(Regex + Decoder)",
        "Indirect SQL\nResult Guard",
        "RAG Context Guard",
        "SQLite EXPLAIN +\nAuthorizer SQL Guard",
        "Tổng Guard Overhead\n(Judge OFF, n=1275)",
    ]
    p50 = [0.01, 0.02, 0.12, 0.14, 0.18, 0.37, 0.49, 0.42]
    p95 = [0.01, 0.03, 0.20, 0.35, 0.29, 0.96, 0.64, 1.21]
    p99 = [0.02, 0.04, 0.24, 0.47, 0.42, 1.20, 0.73, 1.39]

    y = np.arange(len(stages))
    h = 0.25
    ax = axes[0]
    b1 = ax.barh(y + h, p50, h, label="p50 (Median)", color="#10b981")
    b2 = ax.barh(y, p95, h, label="p95", color="#3b82f6")
    b3 = ax.barh(y - h, p99, h, label="p99", color="#6366f1")
    ax.set_yticks(y)
    ax.set_yticklabels(stages, fontsize=8.5)
    ax.invert_yaxis()
    ax.set_xlabel("Độ trễ (ms) — Thang tuyến tính", fontsize=9.5)
    ax.set_xlim(0, 1.65)
    ax.set_title("(a) Độ trễ các lớp Guard tất định (Judge OFF, < 1.5 ms)", fontsize=10.8, fontweight="bold", pad=10)
    ax.grid(axis="x", linestyle="--", alpha=0.4)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for bar in b2:
        w_val = bar.get_width()
        ax.annotate(
            f"p95={w_val:.2f}ms",
            xy=(w_val, bar.get_y() + bar.get_height() / 2),
            xytext=(4, 0),
            textcoords="offset points",
            va="center",
            fontsize=7.3,
            color="#1e3a8a",
            fontweight="bold",
        )

    # Panel B: End-to-End & LLM Guard comparison (Log/Grouped)
    configs = [
        "Shield AI\n(Rule-Only\nGuard Overhead)",
        "Hybrid Retrieval\n(SQLite FTS5 +\nNumpy Matrix)",
        "Llama Guard 3 1B\n(Ollama GPU)",
        "Shield AI\n(Rule + Judge 2B\nTổng Overhead)",
        "NeMo Guardrails\n(self_check_input\nOllama GPU)",
    ]
    c_p50 = [0.42, 2.08, 36.71, 0.73, 97.73]
    c_p95 = [1.21, 5.27, 65.94, 110.89, 120.74]
    c_p99 = [1.39, 6.66, 82.88, 121.42, 143.60]

    x2 = np.arange(len(configs))
    w2 = 0.25
    ax2 = axes[1]
    r1 = ax2.bar(x2 - w2, c_p50, w2, label="p50 (Median)", color="#10b981")
    r2 = ax2.bar(x2, c_p95, w2, label="p95", color="#3b82f6")
    r3 = ax2.bar(x2 + w2, c_p99, w2, label="p99", color="#6366f1")
    ax2.set_xticks(x2)
    ax2.set_xticklabels(configs, fontsize=8.3)
    ax2.set_ylabel("Độ trễ (ms)", fontsize=9.5)
    ax2.set_ylim(0, 165)
    ax2.set_title("(b) So sánh độ trễ p50/p95/p99 với Llama Guard 3 & NeMo", fontsize=10.8, fontweight="bold", pad=10)
    ax2.grid(axis="y", linestyle="--", alpha=0.4)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    for bars in (r1, r2, r3):
        for bar in bars:
            val = bar.get_height()
            ax2.annotate(
                f"{val:.1f}",
                xy=(bar.get_x() + bar.get_width() / 2, val),
                xytext=(0, 2),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=7.0,
                fontweight="bold",
            )

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, frameon=True, fontsize=9.5, bbox_to_anchor=(0.5, 1.01))
    plt.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig(OUT_DIR / "fig-latency-breakdown.png", dpi=300)
    plt.close(fig)


def make_garak_pyrit_chart() -> None:
    fig, ax = plt.subplots(figsize=(11.5, 5.0), dpi=300)
    fig.patch.set_facecolor("white")

    categories = [
        "Garak\nHijackHateHumans\n(256 probes)",
        "Garak\nLatentJailbreak\n(256 probes)",
        "Garak\nInjectBase64\n(256 probes)",
        "Garak\nDanInTheWild\n(256 probes)",
        "Tổng 1.024 Probes\nGarak trên\n/v1/rag/query",
        "PyRIT Converter\nMatrix (Rule-Only)\n(35 biến thể)",
        "PyRIT Converter\nMatrix (Rule+Judge)\n(35 biến thể)",
    ]
    before = [80.1, 0.0, 0.0, 50.4, 32.6, 48.6, 80.0]
    after_r1 = [79.7, 14.1, 57.4, 61.3, 53.1, 85.7, 100.0]
    after_r2 = [100.0, 100.0, 97.7, 73.4, 92.8, 85.7, 100.0]

    x = np.arange(len(categories))
    w = 0.25
    b1 = ax.bar(x - w, before, w, label="Trước tối ưu P5 (v3 Frozen)", color="#94a3b8", edgecolor="#64748b")
    b2 = ax.bar(x, after_r1, w, label="Sau tối ưu P5 — Vòng 1 (Pre-decoder + Multilingual)", color="#38bdf8", edgecolor="#0284c7")
    b3 = ax.bar(x + w, after_r2, w, label="Sau tối ưu P5 — Vòng 2 (Structural + Bare-Base64 + Latent)", color="#0d9488", edgecolor="#0f766e")

    ax.set_title("Kết quả kiểm thử đối kháng trực tiếp bằng NVIDIA Garak (v0.17.1) & PyRIT Converter qua API", fontsize=11.5, fontweight="bold", pad=26)
    ax.set_xticks(x)
    ax.set_xticklabels(categories, fontsize=8.5)
    ax.set_ylabel("Tỉ lệ ngăn chặn trước Retrieval / LLM (%)", fontsize=9.5)
    ax.set_ylim(0, 114)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.13), ncol=3, frameon=True, fontsize=8.4)

    for bars in (b1, b2, b3):
        for bar in bars:
            h = bar.get_height()
            ax.annotate(
                f"{h:.1f}%",
                xy=(bar.get_x() + bar.get_width() / 2, h),
                xytext=(0, 2),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=7.3,
                fontweight="bold",
            )

    plt.tight_layout()
    fig.savefig(OUT_DIR / "fig-garak-pyrit-redteam.png", dpi=300)
    plt.close(fig)


def make_sql_agent_architecture() -> None:
    fig, ax = plt.subplots(figsize=(13.5, 5.2), dpi=300)
    fig.patch.set_facecolor("#f8fafc")
    ax.set_facecolor("#f8fafc")
    ax.set_xlim(0, 13.5)
    ax.set_ylim(0, 5.2)
    ax.axis("off")

    def draw_box(x, y, w, h, title, subtitle, bg="#ffffff", border="#0d9488", title_color="#0f172a"):
        patch = FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0.08,rounding_size=0.18",
            facecolor=bg, edgecolor=border, linewidth=1.8,
        )
        ax.add_patch(patch)
        ax.text(x + w / 2, y + h * 0.64, title, ha="center", va="center", fontsize=9.5, fontweight="bold", color=title_color)
        ax.text(x + w / 2, y + h * 0.28, subtitle, ha="center", va="center", fontsize=7.8, color="#475569")

    def arrow(x1, y1, x2, y2, label=""):
        ax.annotate(
            "", xy=(x2, y2), xytext=(x1, y1),
            arrowprops=dict(arrowstyle="->,head_width=0.25,head_length=0.25", color="#334155", lw=1.6),
        )
        if label:
            ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.15, label, ha="center", va="bottom", fontsize=7.5, color="#0f766e", fontweight="bold")

    ax.text(6.75, 4.85, "KIẾN TRÚC PHÒNG THỦ CHIỀU SÂU CHO MULTI-TOOL AGENT & TEXT-TO-SQL (SHIELD AI P4 × P5)", ha="center", va="center", fontsize=11.5, fontweight="bold", color="#0f172a")

    # Top row: User -> Input Guard + Pre-decoder -> Agent Router / Tool Allowlist -> SQL Guard / RAG Guard
    draw_box(0.3, 3.0, 1.9, 1.2, "1. Người dùng\n(Role / Dept)", "Câu hỏi tự nhiên\nhoặc yêu cầu Tool", bg="#ffffff", border="#334155")
    arrow(2.2, 3.6, 2.7, 3.6)

    draw_box(2.7, 3.0, 2.3, 1.2, "2. Input Guard + P5\nPre-Decoder & Judge", "Giải mã Base64/ROT13/Leet\n+ Regex & Judge (0.42 ms)", bg="#ecfdf5", border="#0d9488")
    arrow(5.0, 3.6, 5.5, 3.6, "Allow")

    draw_box(5.5, 3.0, 2.3, 1.2, "3. Agent Tool Router\n& RBAC Allowlist", "Kiểm tra quyền gọi Tool\ntheo Phòng ban + JSON Schema", bg="#eff6ff", border="#2563eb")
    arrow(7.8, 3.6, 8.3, 3.6, "SQL / Tool")

    draw_box(8.3, 3.0, 2.5, 1.2, "4. SQLite EXPLAIN +\nAuthorizer AST Guard", "Phân tích bảng/cột đọc thật\nChặn secrets, ép LIMIT<=50\n(TPR 100%, p50=0.49 ms)", bg="#fef3c7", border="#d97706")
    arrow(10.8, 3.6, 11.3, 3.6, "Read-Only")

    draw_box(11.3, 3.0, 1.9, 1.2, "5. Thực thi CSDL\n& Kho RAG", "SQLite mode=ro\n+ Hybrid BM25/BLOB", bg="#ffffff", border="#334155")

    # Bottom row: return path through Indirect Result Guard -> Approval Queue -> Output/DLP Guard -> Safe Answer
    arrow(12.25, 3.0, 12.25, 1.9)

    draw_box(9.8, 0.7, 3.4, 1.2, "6. Indirect Result Guard + DLP", "Quét từng ô dữ liệu DB & đoạn RAG\nBắt [INST], gạch nối, đổi STK, ảnh Markdown\n(Holdout TPR 100%, FPR 0%, p50=0.18 ms)", bg="#ecfdf5", border="#0d9488")
    arrow(9.8, 1.3, 9.1, 1.3)

    draw_box(6.2, 0.7, 2.9, 1.2, "7. Hàng chờ Phê duyệt\n(Leader Approval Queue)", "Gửi email / tạo ticket nhạy cảm\nbị giữ lại chờ Leader duyệt", bg="#fef2f2", border="#dc2626")
    arrow(6.2, 1.3, 5.5, 1.3)

    draw_box(2.8, 0.7, 2.7, 1.2, "8. Output Guard & DLP\n+ Link/Image Sanitizer", "Chặn rò rỉ Canary, API Key, PII\nXoá link/ảnh exfiltration ngoài tên miền", bg="#ecfdf5", border="#0d9488")
    arrow(2.8, 1.3, 2.2, 1.3)

    draw_box(0.3, 0.7, 1.9, 1.2, "9. Phản hồi an toàn\n& Audit Log", "JSON Content-Free\n(0/18 rò rỉ trên Qwen3)", bg="#f0fdf4", border="#16a34a", title_color="#15803d")

    plt.tight_layout()
    fig.savefig(OUT_DIR / "fig-sql-agent-architecture.png", dpi=300)
    plt.close(fig)


if __name__ == "__main__":
    make_baseline_comparison()
    make_latency_breakdown()
    make_garak_pyrit_chart()
    make_sql_agent_architecture()
    print("Generated 4 thesis figures in", OUT_DIR)
