"""Calibrate OFF_TOPIC_THRESHOLD against this deployment's own corpus.

Why this script exists
----------------------
Cosine similarity has no absolute meaning across embedding models. A score
of 0.3 can be "clearly unrelated" for one model and "closer than most real
matches" for another -- `nomic-embed-text`, which the retrieval path
special-cases, routinely scores unrelated text well above 0.3. Picking a
threshold by intuition therefore produces a gate that either blocks nothing
or blocks legitimate work, and in both cases looks implemented.

This script measures the actual distribution instead: it scores a set of
on-topic probes and a set of off-topic probes against the real knowledge
base, then reports where the two populations sit and whether any threshold
separates them at all.

Run:
    .venv\\Scripts\\python.exe scripts/calibrate_off_topic.py

Output is a report, not a config change. Deciding the threshold -- and
accepting the false-positive rate that comes with it -- is a human call.
The suggested value is the midpoint of the observed gap, which is only
meaningful when a gap exists; the script says so explicitly when it does
not.

All probes below are synthetic and fictional, consistent with the rest of
this project's datasets.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.config import settings  # noqa: E402
from app.workspace import store  # noqa: E402
from app.workspace.hybrid_retrieval import max_score, semantic_rank  # noqa: E402

# Questions a real employee would ask this knowledge base.
ON_TOPIC = (
    "Chính sách nghỉ phép thường niên là bao nhiêu ngày?",
    "Tôi quên mật khẩu nội bộ thì bao lâu được xử lý?",
    "Quy trình hoàn ứng chi phí công tác thế nào?",
    "Hạn mức ăn uống khi đi công tác là bao nhiêu?",
    "Yêu cầu xác thực hai yếu tố áp dụng cho tài khoản nào?",
    "Khi tiếp nhận nhân sự IT mới cần chuẩn bị những gì?",
)

# Questions the gateway exists to refuse cheaply: personal, entertainment,
# or general-purpose coding help that has nothing to do with the corpus.
OFF_TOPIC = (
    "Viết cho tôi một bài thơ về mùa thu Hà Nội",
    "Cách nấu phở bò ngon tại nhà?",
    "Giải thích thuật toán quicksort bằng Python cho bài tập cá nhân",
    "Kết quả trận đấu bóng đá tối qua thế nào?",
    "Gợi ý phim hay để xem cuối tuần",
    "Dịch câu này sang tiếng Nhật giúp tôi",
)


def _score(query: str, documents: list[dict]) -> float | None:
    ranked = semantic_rank(
        query,
        documents,
        model=settings.workspace_embedding_model,
        base_url=settings.ollama_embedding_base_url,
        connect_factory=store.connect,
        limit=5,
    )
    return max_score(ranked)


def main() -> int:
    model = settings.workspace_embedding_model.strip()
    if not model:
        print("WORKSPACE_EMBEDDING_MODEL chua duoc cau hinh; khong the hieu chuan.")
        return 1

    admin = store.authenticate("superadmin", "SuperAdmin#2026")
    if admin is None:
        print("Khong dang nhap duoc tai khoan superadmin de doc toan bo corpus.")
        return 1
    documents = store.accessible_documents(admin[1])
    if not documents:
        print("Khong co tai lieu nao trong workspace; hay nap corpus truoc.")
        return 1

    print(f"Model: {model}")
    print(f"So tai lieu: {len(documents)}\n")

    results: dict[str, list[float]] = {"on": [], "off": []}
    for label, queries in (("on", ON_TOPIC), ("off", OFF_TOPIC)):
        heading = "ON-TOPIC" if label == "on" else "OFF-TOPIC"
        print(f"--- {heading} ---")
        for query in queries:
            score = _score(query, documents)
            if score is None:
                print(f"  [khong co diem]  {query}")
                continue
            results[label].append(score)
            print(f"  {score:.4f}  {query}")
        print()

    if not results["on"] or not results["off"]:
        print("Khong du du lieu de de xuat nguong.")
        return 1

    lowest_on = min(results["on"])
    highest_off = max(results["off"])
    print("=== KET QUA ===")
    print(f"On-topic  : min={lowest_on:.4f}  max={max(results['on']):.4f}")
    print(f"Off-topic : min={min(results['off']):.4f}  max={highest_off:.4f}")

    if lowest_on > highest_off:
        suggestion = (lowest_on + highest_off) / 2
        print(f"\nHai nhom TACH BIET. Nguong de xuat: {suggestion:.4f}")
        print("Ap dung bang bien moi truong OFF_TOPIC_THRESHOLD.")
        print(
            "Luu y: nguong nam giua hai nhom tren dung tap probe nay. Hay mo rong "
            "tap probe truoc khi tin vao con so."
        )
        return 0

    print(
        f"\nHai nhom CHONG LAN (on-topic thap nhat {lowest_on:.4f} <= off-topic cao "
        f"nhat {highest_off:.4f})."
    )
    print("KHONG co nguong nao tach duoc hai nhom voi model hien tai.")
    print("Lua chon: doi model embedding, hoac bo cong off-topic dua tren cosine.")
    print("Dat mot nguong bat ky luc nay se chan nham cong viec that.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
