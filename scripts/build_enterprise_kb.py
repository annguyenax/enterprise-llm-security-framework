"""Deterministically build datasets/enterprise-kb/ from this file.

`.gitignore` excludes `*.jsonl` repository-wide, deliberately: the frozen
benchmark's holdout split must not become git-visible as a side effect of
packaging, and that file says in so many words not to add a blanket
un-ignore rule. Corpus artifacts in this project are therefore **not tracked
by git** -- they are reproduced from a committed builder and verified
against a manifest SHA-256. This script is the enterprise KB's builder, the
same role `scripts/build_v2_benchmark.py` plays for the evaluation
benchmark.

Consequences worth stating plainly:

- The document contents below are the **source of truth**. Editing
  `datasets/enterprise-kb/corpus/documents.jsonl` by hand is pointless: the
  next build overwrites it, and the manifest hash would flag the drift
  first.
- Output is canonical (`sort_keys=True`, `ensure_ascii=False`, LF endings,
  sorted arrays), so two builds on two machines produce byte-identical
  files and the manifest hash is meaningful.

Run:
    .venv\\Scripts\\python.exe scripts/build_enterprise_kb.py
    .venv\\Scripts\\python.exe scripts/build_enterprise_kb.py --check

`--check` rebuilds in memory and compares against what is on disk without
writing anything, exiting non-zero on drift. That is what the test suite
uses, so a hand-edit or a half-finished build cannot pass unnoticed.

All content is 100% fictional (Northwind Retail Group, the same invented
company the Phase 3 datasets use). No real personal data, no real secrets.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
KB_ROOT = REPO_ROOT / "datasets" / "enterprise-kb"
CORPUS_RELATIVE = "corpus/documents.jsonl"
MANIFEST_RELATIVE = "manifests/enterprise-kb-manifest.json"

SCHEMA_VERSION = "enterprise-kb-1"
SOURCE_KEY = "enterprise_kb"
LANGUAGE = "vi"

ALL_ROLES = ("leader", "member", "superadmin")
LEADERSHIP = ("leader", "superadmin")
ADMIN_ONLY = ("superadmin",)

# (index, title, content, sensitivity, roles, departments, owner, valid_from, valid_to)
#
# Coverage is intentional, not incidental: every branch of
# `app.retrieval.acl.evaluate_acl` has at least one document that exercises
# it -- all four sensitivity tiers, department-scoped and organisation-wide
# access, all three role subsets, and validity windows that are absent,
# already expired, not yet in force, and currently open.
DOCUMENTS: tuple[tuple, ...] = (
    (
        1,
        "Chính sách nghỉ phép thường niên",
        "Nhân viên toàn thời gian của Northwind Retail Group được nghỉ phép 12 ngày mỗi năm, "
        "tích lũy theo tháng. Đơn nghỉ phải được quản lý trực tiếp phê duyệt trước ít nhất 3 ngày làm việc.",
        "public",
        ALL_ROLES,
        ("*",),
        "hr",
        None,
        None,
    ),
    (
        2,
        "Cam kết thời gian xử lý của bộ phận IT",
        "Yêu cầu đặt lại mật khẩu được xử lý trong vòng 4 giờ làm việc. Sự cố mất kết nối mạng "
        "toàn phòng ban được xếp mức ưu tiên cao và xử lý trong vòng 2 giờ làm việc.",
        "internal",
        ALL_ROLES,
        ("*",),
        "it",
        None,
        None,
    ),
    (
        3,
        "Khung bậc lương phòng Nhân sự 2026",
        "Bậc lương P1 đến P5 áp dụng cho nhân viên phòng Nhân sự trong năm 2026. Khoảng lương từng bậc "
        "và hệ số điều chỉnh theo thâm niên được nêu trong bảng đính kèm nội bộ.",
        "confidential",
        LEADERSHIP,
        ("hr", "workspace"),
        "hr",
        "2026-01-01T00:00:00+00:00",
        None,
    ),
    (
        4,
        "Báo cáo hậu sự cố hệ thống kho ngày 2026-03-14",
        "Sự cố gián đoạn hệ thống quản lý kho kéo dài 47 phút do lỗi cấu hình cân bằng tải. "
        "Báo cáo nêu trình tự sự kiện, tác động và các hành động khắc phục đã hoàn tất.",
        "confidential",
        LEADERSHIP,
        ("it", "workspace"),
        "it",
        "2026-03-20T00:00:00+00:00",
        None,
    ),
    (
        5,
        "Cơ cấu thù lao ban điều hành",
        "Tài liệu mô tả cơ cấu thù lao và tiêu chí thưởng theo hiệu quả của ban điều hành "
        "Northwind Retail Group. Chỉ dành cho cấp quản trị cao nhất.",
        "restricted",
        ADMIN_ONLY,
        ("*",),
        "workspace",
        None,
        None,
    ),
    (
        6,
        "Danh mục kiểm tra khi tiếp nhận nhân sự IT mới",
        "Danh mục gồm cấp phát thiết bị, tạo tài khoản nội bộ, ký cam kết bảo mật và "
        "hoàn thành khóa đào tạo an toàn thông tin trong tuần đầu tiên.",
        "internal",
        ALL_ROLES,
        ("it",),
        "it",
        None,
        None,
    ),
    (
        7,
        "Kế hoạch tuyển dụng năm 2027",
        "Kế hoạch tuyển dụng dự kiến cho năm tài chính 2027, gồm số lượng vị trí theo phòng ban "
        "và ngân sách tuyển dụng đề xuất. Chưa có hiệu lực công bố.",
        "confidential",
        LEADERSHIP,
        ("hr", "workspace"),
        "hr",
        "2027-01-01T00:00:00+00:00",
        None,
    ),
    (
        8,
        "Quy định truy cập VPN (phiên bản cũ)",
        "Quy định truy cập VPN áp dụng đến hết năm 2025, yêu cầu kết nối qua cổng tập trung "
        "và xác thực hai yếu tố. Đã được thay thế bởi hướng dẫn an toàn thông tin hiện hành.",
        "internal",
        ALL_ROLES,
        ("*",),
        "it",
        "2024-01-01T00:00:00+00:00",
        "2026-01-01T00:00:00+00:00",
    ),
    (
        9,
        "Hướng dẫn an toàn thông tin hiện hành",
        "Hướng dẫn yêu cầu xác thực hai yếu tố cho mọi tài khoản nội bộ, khóa màn hình sau 10 phút "
        "không hoạt động, và báo cáo sự cố nghi ngờ trong vòng 1 giờ.",
        "internal",
        ALL_ROLES,
        ("*",),
        "it",
        "2026-01-01T00:00:00+00:00",
        "2027-01-01T00:00:00+00:00",
    ),
    (
        10,
        "Quy trình hoàn ứng chi phí công tác",
        "Chi phí công tác được hoàn ứng khi có hóa đơn hợp lệ và phê duyệt của quản lý trực tiếp. "
        "Hạn mức ăn uống là 350.000 đồng mỗi ngày công tác.",
        "internal",
        ALL_ROLES,
        ("*",),
        "workspace",
        None,
        None,
    ),
    (
        11,
        "Quy trình xử lý kỷ luật lao động",
        "Quy trình mô tả các bước xác minh, lập biên bản và ra quyết định kỷ luật, "
        "kèm yêu cầu lưu trữ hồ sơ. Nội dung chứa thông tin nhân sự nhạy cảm.",
        "restricted",
        ADMIN_ONLY,
        ("hr", "workspace"),
        "hr",
        None,
        None,
    ),
    (
        12,
        "Điều khoản hợp đồng nhà cung cấp hạ tầng",
        "Hợp đồng với nhà cung cấp hạ tầng máy chủ gồm cam kết mức dịch vụ, điều khoản phạt "
        "và lịch thanh toán theo quý.",
        "confidential",
        LEADERSHIP,
        ("it", "workspace"),
        "it",
        "2026-02-01T00:00:00+00:00",
        None,
    ),
)


def build_rows() -> list[dict]:
    """Build every corpus row in canonical shape (arrays sorted)."""
    rows: list[dict] = []
    for (
        index,
        title,
        content,
        sensitivity,
        roles,
        departments,
        owner,
        valid_from,
        valid_to,
    ) in DOCUMENTS:
        document_id = f"ekb-doc-{index:04d}"
        rows.append(
            {
                "access_departments": sorted(departments),
                "access_roles": sorted(roles),
                "content": content,
                "document_id": document_id,
                "external_id": document_id,
                "language": LANGUAGE,
                "owner_department": owner,
                "sensitivity": sensitivity,
                "source_key": SOURCE_KEY,
                "title": title,
                "valid_from": valid_from,
                "valid_to": valid_to,
            }
        )
    return rows


def render_corpus(rows: list[dict]) -> str:
    lines = [json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows]
    return "\n".join(lines) + "\n"


def render_manifest(rows: list[dict], corpus_text: str) -> str:
    payload = corpus_text.encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    counts: dict[str, int] = {}
    for row in rows:
        key = row["sensitivity"]
        counts[key] = counts.get(key, 0) + 1
    manifest = {
        "corpus_sha256": digest,
        "document_count": len(rows),
        "files": [
            {
                "path": CORPUS_RELATIVE,
                "sha256": digest,
                "size_bytes": len(payload),
            }
        ],
        # Never "final" from a builder. A FINAL freeze in this project is an
        # adjudicated outcome of independent audit, not something a script
        # may award itself.
        "manifest_status": "draft",
        "schema_version": SCHEMA_VERSION,
        "sensitivity_counts": dict(sorted(counts.items())),
        "source_key": SOURCE_KEY,
    }
    return json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def build(kb_root: Path) -> tuple[str, str]:
    rows = build_rows()
    corpus_text = render_corpus(rows)
    return corpus_text, render_manifest(rows, corpus_text)


def write(kb_root: Path) -> str:
    corpus_text, manifest_text = build(kb_root)
    corpus_path = kb_root / CORPUS_RELATIVE
    manifest_path = kb_root / MANIFEST_RELATIVE
    corpus_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    corpus_path.write_text(corpus_text, encoding="utf-8", newline="\n")
    manifest_path.write_text(manifest_text, encoding="utf-8", newline="\n")
    return hashlib.sha256(corpus_text.encode("utf-8")).hexdigest()


def check(kb_root: Path) -> list[str]:
    """Compare an in-memory build against what is on disk. Returns a list of
    drift descriptions (empty means identical)."""
    corpus_text, manifest_text = build(kb_root)
    problems: list[str] = []
    for relative, expected in (
        (CORPUS_RELATIVE, corpus_text),
        (MANIFEST_RELATIVE, manifest_text),
    ):
        path = kb_root / relative
        if not path.is_file():
            problems.append(f"{relative}: chua duoc sinh ra")
            continue
        if path.read_text(encoding="utf-8") != expected:
            problems.append(f"{relative}: khac voi ban dung lai tu builder")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the enterprise knowledge base.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="So sanh voi noi dung tren dia, khong ghi gi. Thoat khac 0 neu lech.",
    )
    args = parser.parse_args()

    if args.check:
        problems = check(KB_ROOT)
        if not problems:
            print("OK: enterprise-kb tren dia trung khop voi builder.")
            return 0
        print(f"FAIL: {len(problems)} sai lech:")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    digest = write(KB_ROOT)
    print(f"Da sinh {len(DOCUMENTS)} tai lieu.")
    print(f"corpus_sha256: {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
