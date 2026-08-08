"""Build a full, realistic enterprise knowledge base from the skeleton.

`Kho-tri-thuc-doanh-nghiep.zip` is a well-designed *skeleton*: 28 of its 29
files are `README.md` placeholders describing what each folder should hold,
with a genuine RBAC policy in `04-Quan-tri/access-control.yaml`. It has no
actual documents, so a chatbot loaded from it retrieves nothing and answers
"I have no information".

This script fills that skeleton with deterministic synthetic documents --
payroll, contracts, financial reports, runbooks, policies -- each carrying
YAML front-matter in the `Mau-bieu/MAU-METADATA.md` shape, written into a
real directory tree that mirrors the skeleton's layout. The companion
`scripts/seed_enterprise_knowledge_base.py` then loads that tree into the
workspace so the chatbot works on it.

Design decisions
----------------
- **Deterministic.** A fixed seed drives every generated name, amount and
  credential, so two builds are byte-identical and the manifest hash is
  meaningful. Reruns do not churn the corpus.

- **One sensitivity vocabulary.** Documents carry the code's four-tier
  scale (`public/internal/confidential/restricted`, in
  `app/retrieval/acl.py`) *and* the skeleton's equivalent label
  (`PUBLIC_INTERNAL`...`STRICTLY_CONFIDENTIAL`) in front-matter, so the
  folder's own policy names are preserved while the seeder has a single
  field to map from.

- **Realistic-shaped secrets, all fictional.** Credentials match the
  *shape* the DLP detectors look for (`sk-`, `AKIA`, `ghp_`) and payroll
  rows carry bank-account-shaped numbers, because a knowledge base with
  nothing worth protecting cannot demonstrate protection. Every value is
  invented and authenticates to nothing (AGENT_RULES rule 5).

- **No poisoned documents here.** The indirect-injection payload lives in
  `datasets/demo-leak/` for attack demos. A knowledge base the business
  actually uses must be clean; mixing an attack document into it would
  corrupt normal operation.

Run:
    .venv\\Scripts\\python.exe scripts/build_enterprise_knowledge_base.py
    .venv\\Scripts\\python.exe scripts/build_enterprise_knowledge_base.py --check
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
KB_ROOT = REPO_ROOT / "datasets" / "enterprise-kb-full"
MANIFEST_PATH = KB_ROOT / "MANIFEST.json"

SEED = 20260808
COMPANY = "Northwind Retail Group"

# code sensitivity -> skeleton (zip) classification label
ZIP_CLASSIFICATION = {
    "public": "PUBLIC_INTERNAL",
    "internal": "DEPARTMENT_INTERNAL",
    "confidential": "CONFIDENTIAL",
    "restricted": "STRICTLY_CONFIDENTIAL",
}

FIRST = ("Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Vũ", "Đặng", "Bùi", "Đỗ", "Ngô")
MID = ("Văn", "Thị", "Minh", "Quốc", "Thu", "Hải", "Thanh", "Xuân")
LAST = ("An", "Bình", "Cường", "Dung", "Giang", "Hà", "Khanh", "Linh", "Nam", "Phúc", "Quân", "Trang")


@dataclass(frozen=True)
class Doc:
    # Folder path relative to KB_ROOT, e.g. "03-Nhan-su/Luong".
    folder: str
    filename: str
    department: str  # workspace department code: SHARED | KETOAN | IT | HR | WORKSPACE
    sensitivity: str  # public | internal | confidential | restricted
    title: str
    owner: str
    body: str
    related_employee_id: str | None = None


def _rng() -> random.Random:
    return random.Random(SEED)


def _person(rng: random.Random) -> str:
    return f"{rng.choice(FIRST)} {rng.choice(MID)} {rng.choice(LAST)}"


def _sk(rng: random.Random) -> str:
    return "sk-" + "".join(rng.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789", k=32))


def _aws(rng: random.Random) -> str:
    return "AKIA" + "".join(rng.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=16))


def _ghp(rng: random.Random) -> str:
    return "ghp_" + "".join(rng.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789", k=36))


def build_docs() -> list[Doc]:
    rng = _rng()
    docs: list[Doc] = []

    # === 00-Dung-chung — company-wide, everyone reads =====================
    docs.append(Doc(
        "00-Dung-chung", "noi-quy-lao-dong.md", "SHARED", "public",
        "Nội quy lao động", "hr.leader",
        body=(
            f"Nội quy lao động của {COMPANY} áp dụng cho toàn thể nhân viên.\n\n"
            "## Giờ làm việc\n"
            "- Giờ hành chính: 08:30–17:30, nghỉ trưa 12:00–13:00, từ thứ Hai đến thứ Sáu.\n"
            "- Nhân viên chấm công bằng thẻ từ hoặc ứng dụng nội bộ khi vào và ra.\n\n"
            "## Trang phục và ứng xử\n"
            "- Lịch sự, phù hợp môi trường công sở; giữ gìn tài sản chung.\n\n"
            "## Kỷ luật\n"
            "- Vi phạm được xử lý theo quy trình trong tài liệu Nhân sự, có biên bản và quyền giải trình.\n"
        ),
    ))
    docs.append(Doc(
        "00-Dung-chung", "chinh-sach-nghi-phep.md", "SHARED", "public",
        "Chính sách nghỉ phép thường niên", "hr.leader",
        body=(
            "Nhân viên toàn thời gian được nghỉ phép 12 ngày mỗi năm, tích lũy theo tháng.\n\n"
            "## Cách sử dụng\n"
            "- Đơn nghỉ phải được quản lý trực tiếp phê duyệt trước ít nhất 3 ngày làm việc.\n"
            "- Ngày phép chưa dùng được chuyển tối đa 5 ngày sang năm kế tiếp.\n"
            "- Nghỉ ốm có xác nhận y tế không trừ vào phép năm.\n"
        ),
    ))
    docs.append(Doc(
        "00-Dung-chung", "quy-dinh-an-toan-thong-tin.md", "SHARED", "public",
        "Hướng dẫn an toàn thông tin", "it.leader",
        body=(
            "Hướng dẫn áp dụng cho mọi tài khoản nội bộ.\n\n"
            "- Bật xác thực hai yếu tố cho mọi hệ thống nội bộ.\n"
            "- Khóa màn hình sau 10 phút không hoạt động.\n"
            "- Không chia sẻ mật khẩu; không lưu bí mật trong tài liệu dùng chung.\n"
            "- Báo cáo sự cố nghi ngờ cho đội IT trong vòng 1 giờ.\n"
        ),
    ))

    # === 01-Ke-toan =======================================================
    q1_rows = "\n".join(
        f"| {name} | {rng.randrange(180, 920)} triệu | {rng.randrange(120, 780)} triệu | {rng.randrange(-40, 160)} triệu |"
        for name in ("Doanh thu bán lẻ", "Doanh thu bán buôn", "Chi phí vận hành", "Chi phí nhân sự")
    )
    docs.append(Doc(
        "01-Ke-toan/Bao-cao-tai-chinh", "bao-cao-tai-chinh-Q1-2026.md", "KETOAN", "confidential",
        "Báo cáo tài chính Quý 1/2026", "ketoan.leader",
        body=(
            f"# {COMPANY} — Báo cáo tài chính Quý 1/2026\n"
            "Phân loại: MẬT — phòng Kế toán và Ban điều hành.\n\n"
            "| Khoản mục | Kế hoạch | Thực hiện | Chênh lệch |\n|---|---:|---:|---:|\n" + q1_rows + "\n\n"
            "Nhận xét: doanh thu bán lẻ vượt kế hoạch; chi phí vận hành cao hơn dự toán do mở rộng kho miền Bắc.\n"
        ),
    ))
    docs.append(Doc(
        "01-Ke-toan/Hoa-don", "danh-muc-hoa-don-thang-06-2026.md", "KETOAN", "internal",
        "Danh mục hóa đơn tháng 06/2026", "ketoan.user1",
        body=(
            "Danh mục hóa đơn đầu vào/đầu ra tháng 06/2026 phục vụ đối soát nội bộ.\n\n"
            "| Số HĐ | Nhà cung cấp/Khách | Loại | Giá trị (VND) |\n|---|---|---|---:|\n"
            + "\n".join(
                f"| HD-{rng.randrange(20260600, 20260699)} | {rng.choice(('Công ty Beta Tech','Nhà cung cấp Minh Long','Khách sỉ Hòa Phát'))} | {rng.choice(('đầu vào','đầu ra'))} | {rng.randrange(5, 240) * 1_000_000:,} |"
                for _ in range(6)
            )
            + "\n\nGhi chú: không lưu khóa ký số hay mật khẩu trong thư mục này.\n"
        ),
    ))
    docs.append(Doc(
        "01-Ke-toan/Thue", "quyet-toan-thue-TNDN-2025.md", "KETOAN", "confidential",
        "Quyết toán thuế TNDN năm 2025", "ketoan.leader",
        body=(
            f"# {COMPANY} — Quyết toán thuế thu nhập doanh nghiệp 2025\n"
            "Phân loại: MẬT — phòng Kế toán.\n\n"
            f"- Tổng thu nhập chịu thuế: {rng.randrange(28, 64)} tỷ VND.\n"
            f"- Thuế suất áp dụng: 20%.\n"
            f"- Số thuế phải nộp: {rng.randrange(5, 13)} tỷ VND.\n"
            "- Hồ sơ kèm theo: tờ khai quyết toán, phụ lục điều chỉnh, biên bản đối chiếu.\n"
        ),
    ))

    # === 02-IT ============================================================
    docs.append(Doc(
        "02-IT/Huong-dan", "huong-dan-dat-lai-mat-khau.md", "IT", "internal",
        "Hướng dẫn đặt lại mật khẩu", "it.user1",
        body=(
            "Quy trình đặt lại mật khẩu cho nhân viên.\n\n"
            "1. Gửi yêu cầu qua cổng trợ giúp IT nội bộ.\n"
            "2. Xác minh danh tính qua email công ty hoặc xác thực hai yếu tố.\n"
            "3. Thời gian xử lý dự kiến trong vòng 4 giờ làm việc.\n"
            "4. Sự cố mất kết nối toàn phòng ban được ưu tiên cao, xử lý trong 2 giờ.\n"
        ),
    ))
    docs.append(Doc(
        "02-IT/Tai-lieu-ky-thuat", "kien-truc-he-thong-kho.md", "IT", "confidential",
        "Kiến trúc hệ thống quản lý kho", "it.leader",
        body=(
            f"# {COMPANY} — Kiến trúc hệ thống quản lý kho\n"
            "Phân loại: MẬT — phòng IT.\n\n"
            "- Tầng ứng dụng: dịch vụ đơn hàng, tồn kho, báo cáo, sau cân bằng tải khu vực.\n"
            "- Tầng dữ liệu: cơ sở dữ liệu chính + bản sao đọc; snapshot theo giờ.\n"
            "- Tích hợp: cổng thanh toán, hệ thống kế toán qua hàng đợi tin cậy.\n"
        ),
    ))
    docs.append(Doc(
        "02-IT/Cau-hinh", "runbook-khoi-phuc-he-thong-kho.md", "IT", "restricted",
        "Runbook khôi phục hệ thống kho", "it.leader",
        body=(
            f"# {COMPANY} — Runbook khôi phục hệ thống kho\n"
            "Phân loại: TỐI MẬT — chỉ đội vận hành hạ tầng.\n\n"
            "## Biến môi trường bắt buộc\n\n```\n"
            f"WAREHOUSE_AWS_ACCESS_KEY_ID={_aws(rng)}\n"
            f"WAREHOUSE_LLM_API_KEY={_sk(rng)}\n"
            f"WAREHOUSE_DEPLOY_TOKEN={_ghp(rng)}\n"
            f"WAREHOUSE_DB_PASSWORD=Nw!{rng.randrange(100000, 999999)}#kho2026\n"
            "```\n\n## Trình tự khôi phục\n"
            "1. Tạm dừng cân bằng tải khu vực miền Bắc.\n"
            "2. Khôi phục snapshot gần nhất, xác minh checksum.\n"
            "3. Bật lại dịch vụ theo thứ tự: tồn kho → đơn hàng → báo cáo.\n"
        ),
    ))

    # === 03-Nhan-su =======================================================
    payroll = "\n".join(
        f"| NV-2019-{4400 + i:04d} | {_person(rng)} | "
        f"{rng.choice(('Kỹ sư hạ tầng','Chuyên viên HR','Kế toán viên','Trưởng nhóm IT','Nhân viên kho'))} | "
        f"{rng.randrange(14, 58) * 1_000_000:,} | {rng.randrange(2, 9) * 1_000_000:,} | "
        f"VCB {rng.randrange(1000, 9999)}{rng.randrange(100000, 999999)} |"
        for i in range(1, 10)
    )
    docs.append(Doc(
        "03-Nhan-su/Luong", "bang-luong-thang-07-2026.md", "HR", "restricted",
        "Bảng lương chi tiết tháng 07/2026", "hr.leader",
        body=(
            f"# {COMPANY} — Bảng lương chi tiết tháng 07/2026\n"
            "Phân loại: TỐI MẬT — chỉ Trưởng phòng Nhân sự và Kế toán tiền lương.\n\n"
            "| Mã NV | Họ tên | Chức danh | Lương cơ bản (VND) | Phụ cấp (VND) | Tài khoản nhận lương |\n"
            "|---|---|---|---:|---:|---|\n" + payroll + "\n\n"
            "Bảng này không được sao chép ra ngoài hệ thống nhân sự.\n"
        ),
    ))
    docs.append(Doc(
        "03-Nhan-su/Hop-dong-lao-dong", "hop-dong-lao-dong-mau.md", "HR", "confidential",
        "Hợp đồng lao động (mẫu)", "hr.leader",
        body=(
            "Mẫu hợp đồng lao động không xác định thời hạn.\n\n"
            "- Các bên: người sử dụng lao động và người lao động.\n"
            "- Nội dung: vị trí, mức lương, thời giờ làm việc, bảo hiểm, cam kết bảo mật.\n"
            "- Sau khi ký, bản gốc không được sửa đè; thay đổi phải lập phụ lục.\n"
            "- Quy ước tên tệp: HDLD-MaNhanVien-NgayHieuLuc-PhienBan.pdf.\n"
        ),
    ))
    docs.append(Doc(
        "03-Nhan-su/Tuyen-dung", "ke-hoach-tuyen-dung-2027.md", "HR", "confidential",
        "Kế hoạch tuyển dụng năm 2027", "hr.leader",
        body=(
            "Kế hoạch tuyển dụng dự kiến năm tài chính 2027 (chưa công bố).\n\n"
            f"- Tổng số vị trí đề xuất: {rng.randrange(18, 46)}.\n"
            "- Ưu tiên: kỹ sư hạ tầng, chuyên viên phân tích dữ liệu, nhân viên kho khu vực.\n"
            f"- Ngân sách tuyển dụng đề xuất: {rng.randrange(3, 9)} tỷ VND.\n"
        ),
    ))
    docs.append(Doc(
        "03-Nhan-su/Cham-cong", "quy-dinh-cham-cong.md", "HR", "internal",
        "Quy định chấm công", "hr.user1",
        body=(
            "Quy định chấm công áp dụng cho toàn công ty.\n\n"
            "- Chấm công vào/ra bằng thẻ từ hoặc ứng dụng.\n"
            "- Đi muộn quá 3 lần/tháng nhắc nhở; quá 6 lần xem xét kỷ luật.\n"
            "- Làm thêm giờ phải được duyệt trước và ghi nhận vào bảng công.\n"
        ),
    ))

    # === 04-Quan-tri — company strategic, superadmin-only =================
    docs.append(Doc(
        "04-Quan-tri", "du-an-hai-au-tom-tat.md", "WORKSPACE", "restricted",
        "Dự án HẢI ÂU (chưa công bố)", "superadmin",
        body=(
            f"# {COMPANY} — Dự án HẢI ÂU (chưa công bố)\n"
            "Phân loại: TỐI MẬT — Ban điều hành.\n\n"
            "- Mục tiêu thâu tóm: chuỗi bán lẻ Minh Phát (giả định).\n"
            f"- Định giá đề xuất: {rng.randrange(680, 940)} tỷ VND.\n"
            "- Ngày ký dự kiến: 2026-11-14. Chưa công bố ra thị trường.\n"
            "- Rủi ro: rò rỉ trước ngày ký có thể khiến giao dịch đổ vỡ.\n"
        ),
    ))

    return docs


def _frontmatter(doc: Doc, index: int) -> str:
    fields = {
        "document_id": f"DOC-2026-{index:04d}",
        "title": doc.title,
        "department": {"SHARED": "shared", "KETOAN": "accounting", "IT": "it", "HR": "hr", "WORKSPACE": "shared"}[doc.department],
        "owner": doc.owner,
        "classification": ZIP_CLASSIFICATION[doc.sensitivity],
        "sensitivity": doc.sensitivity,
        "workspace_department": doc.department,
        "status": "APPROVED",
        "effective_date": "2026-07-01",
        "retention_until": "2031-07-01",
        "related_employee_id": doc.related_employee_id or "null",
        "approved_by": doc.owner,
        "version": "1.0",
    }
    lines = ["---"]
    lines += [f"{key}: {value}" for key, value in fields.items()]
    lines.append("---")
    return "\n".join(lines)


def render(doc: Doc, index: int) -> str:
    return _frontmatter(doc, index) + "\n\n" + doc.body.rstrip() + "\n"


def build_tree() -> dict[str, str]:
    """Return {relative_path: file_text} for the whole KB, deterministically."""
    tree: dict[str, str] = {}
    for index, doc in enumerate(build_docs(), start=1):
        tree[f"{doc.folder}/{doc.filename}"] = render(doc, index)
    return tree


def render_manifest(tree: dict[str, str]) -> str:
    files = []
    counts: dict[str, int] = {}
    for path in sorted(tree):
        payload = tree[path].encode("utf-8")
        files.append({"path": path, "sha256": hashlib.sha256(payload).hexdigest(), "size_bytes": len(payload)})
    for doc in build_docs():
        counts[doc.sensitivity] = counts.get(doc.sensitivity, 0) + 1
    manifest = {
        "company": COMPANY,
        "document_count": len(tree),
        "files": files,
        "manifest_status": "draft",
        "schema_version": "enterprise-kb-full-1",
        "sensitivity_counts": dict(sorted(counts.items())),
    }
    return json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write() -> tuple[int, str]:
    tree = build_tree()
    for relative, text in tree.items():
        path = KB_ROOT / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    manifest = render_manifest(tree)
    MANIFEST_PATH.write_text(manifest, encoding="utf-8", newline="\n")
    digest = hashlib.sha256(manifest.encode("utf-8")).hexdigest()
    return len(tree), digest


def check() -> list[str]:
    tree = build_tree()
    problems: list[str] = []
    for relative, expected in tree.items():
        path = KB_ROOT / relative
        if not path.is_file():
            problems.append(f"{relative}: chua duoc sinh ra")
        elif path.read_text(encoding="utf-8") != expected:
            problems.append(f"{relative}: khac voi ban dung lai tu builder")
    if MANIFEST_PATH.is_file() and MANIFEST_PATH.read_text(encoding="utf-8") != render_manifest(tree):
        problems.append("MANIFEST.json: khac voi ban dung lai tu builder")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the full enterprise knowledge base.")
    parser.add_argument("--check", action="store_true", help="So sanh voi noi dung tren dia")
    args = parser.parse_args()
    if args.check:
        problems = check()
        if not problems:
            print("OK: enterprise-kb-full tren dia trung khop voi builder.")
            return 0
        for problem in problems:
            print(f"  - {problem}")
        return 1
    count, digest = write()
    print(f"Da sinh {count} tai lieu -> {KB_ROOT.relative_to(REPO_ROOT).as_posix()}/")
    print(f"manifest_sha256: {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
