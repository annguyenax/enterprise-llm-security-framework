"""Synthetic business documents used by the workspace proof-of-concept.

The records intentionally exercise every workspace ACL level. They contain no
real employee, payroll, customer, supplier, or contract data.
"""
from __future__ import annotations

from typing import Any

from app.core.decisions import Decision
from app.guards.rag_guard import evaluate_rag_context
from app.schemas.requests import RAGContextChunk
from app.services.upload_scanner import scan_upload
from app.workspace import store


def _document(
    filename: str,
    owner: str,
    scope: str,
    audience: str,
    department: str,
    document_type: str,
    classification: str,
    body: str,
) -> dict[str, str]:
    metadata = (
        "---\n"
        f"document_type: {document_type}\n"
        f"classification: {classification}\n"
        f"scope: {scope}\n"
        f"audience: {audience}\n"
        f"department: {department}\n"
        f"owner: {owner}\n"
        "synthetic_data: true\n"
        "---\n\n"
    )
    return {
        "filename": filename,
        "owner_username": owner,
        "scope": scope,
        "audience": audience,
        "department": department,
        "document_type": document_type,
        "classification": classification,
        "content": metadata + body.strip() + "\n",
    }


BUSINESS_DOCUMENTS: tuple[dict[str, str], ...] = (
    _document(
        "chinh-sach-luong-thuong-2026.md", "superadmin", "global", "member", "WORKSPACE",
        "compensation_policy", "internal",
        """# Chính sách lương thưởng 2026

Đây là dữ liệu mẫu. Lương được rà soát vào tháng 6 và tháng 12. Thưởng hiệu suất
tham khảo kết quả công việc, mức độ hoàn thành mục tiêu và ngân sách đã duyệt.
Nhân viên trao đổi thắc mắc với leader hoặc phòng Nhân sự.""",
    ),
    _document(
        "mau-hop-dong-lao-dong-chung.md", "superadmin", "global", "member", "WORKSPACE",
        "employment_contract_template", "internal",
        """# Mẫu hợp đồng lao động chung

Tài liệu mẫu gồm chức danh, nơi làm việc, thời hạn, quyền lợi, nghĩa vụ, thời giờ
làm việc và điều khoản chấm dứt. Mọi tên, số tiền và mã hợp đồng trong bản mẫu
đều phải được thay bằng dữ liệu đã được phê duyệt trước khi ký.""",
    ),
    _document(
        "huong-dan-phe-duyet-dieu-chinh-luong.md", "superadmin", "global", "leader", "WORKSPACE",
        "salary_approval_workflow", "confidential",
        """# Hướng dẫn phê duyệt điều chỉnh lương

Leader lập đề xuất, nêu căn cứ đánh giá và phạm vi ngân sách. Phòng Nhân sự kiểm
tra tính nhất quán; SuperAdmin phê duyệt cuối cùng. Chỉ thông báo kết quả cho
người có liên quan sau khi quy trình hoàn tất.""",
    ),
    _document(
        "bao-cao-chi-phi-nhan-su-q2-2026.md", "superadmin", "global", "leader", "WORKSPACE",
        "workforce_cost_report", "confidential",
        """# Báo cáo chi phí nhân sự quý 2 năm 2026

Dữ liệu giả lập: tổng quỹ lương kế hoạch là 820 triệu đồng; chi phí thực tế là
798 triệu đồng; chênh lệch còn lại là 22 triệu đồng. Báo cáo chỉ phục vụ minh
họa kiểm thử phân quyền, không phản ánh một doanh nghiệp có thật.""",
    ),
    _document(
        "hop-dong-doi-tac-alpha-cloud-2026.md", "superadmin", "global", "superadmin", "WORKSPACE",
        "vendor_contract", "restricted",
        """# Hợp đồng dịch vụ với đối tác giả lập ALPHA-CLOUD

Mã hợp đồng mẫu: HD-DM-ALPHA-2026-01. Giá trị giả lập: 1,2 tỷ đồng trong 12 tháng.
Phạm vi gồm hạ tầng thử nghiệm, hỗ trợ kỹ thuật và báo cáo mức dịch vụ. Đại diện
hai bên trong tài liệu này đều là danh tính giả lập.""",
    ),
    _document(
        "bien-ban-dam-phan-doi-tac-orion-2026.md", "superadmin", "global", "superadmin", "WORKSPACE",
        "vendor_negotiation", "restricted",
        """# Biên bản đàm phán với đối tác giả lập ORION-LAB

Hai bên thống nhất bản thử nghiệm có thời hạn 90 ngày. Ngân sách trần giả lập là
360 triệu đồng. Điều khoản thương mại chưa có hiệu lực cho đến khi người có
thẩm quyền ký hợp đồng chính thức.""",
    ),
    _document(
        "quy-trinh-onboarding-va-hop-dong-hr.md", "hr.leader", "department", "member", "HR",
        "hr_procedure", "internal",
        """# Quy trình onboarding và hợp đồng của phòng HR

HR kiểm tra hồ sơ mẫu, tạo lịch tiếp nhận, hướng dẫn ký hợp đồng và bàn giao nội
quy. Không đưa bản lương hoặc hợp đồng cá nhân vào thư mục dùng chung của phòng.""",
    ),
    _document(
        "tong-hop-quy-luong-hr-thang-07-2026.md", "hr.leader", "department", "leader", "HR",
        "department_payroll_summary", "confidential",
        """# Tổng hợp quỹ lương phòng HR tháng 07/2026

Dữ liệu giả lập: quỹ lương cơ bản 126 triệu đồng, phụ cấp 14 triệu đồng và thưởng
dự kiến 9 triệu đồng. Báo cáo tổng hợp không chứa số lương của từng cá nhân.""",
    ),
    _document(
        "danh-sach-hop-dong-sap-het-han-hr.md", "hr.leader", "department", "leader", "HR",
        "contract_renewal_register", "confidential",
        """# Danh sách hợp đồng sắp hết hạn của phòng HR

Dữ liệu giả lập: hồ sơ NV-DEMO-HR-01 cần rà soát ngày 20/09/2026; hồ sơ
NV-DEMO-HR-02 cần rà soát ngày 05/10/2026. Leader HR chịu trách nhiệm phân công
kiểm tra và không chia sẻ danh sách ra ngoài phòng.""",
    ),
    _document(
        "chinh-sach-phu-cap-truc-it.md", "it.leader", "department", "member", "IT",
        "allowance_policy", "internal",
        """# Chính sách phụ cấp trực phòng IT

Dữ liệu mẫu: ca trực ngoài giờ được ghi nhận theo lịch đã duyệt. Thành viên xác
nhận ca trực trước ngày khóa công và phản hồi sai lệch cho leader IT.""",
    ),
    _document(
        "du-toan-ngan-sach-ha-tang-it-q3-2026.md", "it.leader", "department", "leader", "IT",
        "department_budget", "confidential",
        """# Dự toán ngân sách hạ tầng IT quý 3 năm 2026

Dữ liệu giả lập: máy chủ thử nghiệm 280 triệu đồng, lưu trữ 95 triệu đồng và dự
phòng vận hành 45 triệu đồng. Tổng dự toán là 420 triệu đồng.""",
    ),
    _document(
        "hop-dong-bao-tri-he-thong-beta-tech.md", "it.leader", "department", "leader", "IT",
        "department_vendor_contract", "confidential",
        """# Hợp đồng bảo trì với đối tác giả lập BETA-TECH

Mã mẫu: HD-BT-IT-2026-03. Giá trị giả lập: 240 triệu đồng một năm. Phạm vi gồm
bảo trì hệ thống lab, hỗ trợ sự cố và báo cáo định kỳ cho leader IT.""",
    ),
    _document(
        "hop-dong-lao-dong-it-user1.md", "it.user1", "user", "member", "IT",
        "employment_contract", "personal_confidential",
        """# Hợp đồng lao động mẫu của it.user1

Mã hợp đồng giả lập: HDLD-DEMO-IT01. Chức danh: Kỹ sư phần mềm. Thời hạn mẫu:
01/01/2026 đến 31/12/2026. Mức lương cơ bản giả lập: 24 triệu đồng mỗi tháng.""",
    ),
    _document(
        "phieu-luong-it-user1-thang-07-2026.md", "it.user1", "user", "member", "IT",
        "payslip", "personal_confidential",
        """# Phiếu lương mẫu của it.user1 tháng 07/2026

Lương cơ bản giả lập: 24 triệu đồng; phụ cấp giả lập: 2 triệu đồng; khấu trừ giả
        lập: 1,8 triệu đồng; thực nhận giả lập: 24,2 triệu đồng.""",
    ),
    _document(
        "hop-dong-lao-dong-it-user2.md", "it.user2", "user", "member", "IT",
        "employment_contract", "personal_confidential",
        """# Hợp đồng lao động mẫu của it.user2

Mã hợp đồng giả lập: HDLD-DEMO-IT02. Chức danh: Kỹ sư kiểm thử. Thời hạn mẫu:
01/03/2026 đến 28/02/2027. Mức lương cơ bản giả lập: 22 triệu đồng mỗi tháng.""",
    ),
    _document(
        "phieu-luong-it-user2-thang-07-2026.md", "it.user2", "user", "member", "IT",
        "payslip", "personal_confidential",
        """# Phiếu lương mẫu của it.user2 tháng 07/2026

Lương cơ bản giả lập: 22 triệu đồng; phụ cấp giả lập: 1,8 triệu đồng; khấu trừ
giả lập: 1,6 triệu đồng; thực nhận giả lập: 22,2 triệu đồng.""",
    ),
    _document(
        "hop-dong-lao-dong-hr-user1.md", "hr.user1", "user", "member", "HR",
        "employment_contract", "personal_confidential",
        """# Hợp đồng lao động mẫu của hr.user1

Mã hợp đồng giả lập: HDLD-DEMO-HR01. Chức danh: Chuyên viên nhân sự. Thời hạn
mẫu: 01/02/2026 đến 31/01/2027. Mức lương cơ bản giả lập: 21 triệu đồng mỗi tháng.""",
    ),
    _document(
        "phieu-luong-hr-user1-thang-07-2026.md", "hr.user1", "user", "member", "HR",
        "payslip", "personal_confidential",
        """# Phiếu lương mẫu của hr.user1 tháng 07/2026

Lương cơ bản giả lập: 21 triệu đồng; phụ cấp giả lập: 1,5 triệu đồng; khấu trừ
        giả lập: 1,4 triệu đồng; thực nhận giả lập: 21,1 triệu đồng.""",
    ),
    _document(
        "hop-dong-lao-dong-hr-user2.md", "hr.user2", "user", "member", "HR",
        "employment_contract", "personal_confidential",
        """# Hợp đồng lao động mẫu của hr.user2

Mã hợp đồng giả lập: HDLD-DEMO-HR02. Chức danh: Chuyên viên tuyển dụng. Thời hạn
mẫu: 01/04/2026 đến 31/03/2027. Mức lương cơ bản giả lập: 20 triệu đồng mỗi tháng.""",
    ),
    _document(
        "phieu-luong-hr-user2-thang-07-2026.md", "hr.user2", "user", "member", "HR",
        "payslip", "personal_confidential",
        """# Phiếu lương mẫu của hr.user2 tháng 07/2026

Lương cơ bản giả lập: 20 triệu đồng; phụ cấp giả lập: 1,2 triệu đồng; khấu trừ
giả lập: 1,3 triệu đồng; thực nhận giả lập: 19,9 triệu đồng.""",
    ),
    _document(
        "hop-dong-lao-dong-hr-leader.md", "hr.leader", "user", "leader", "HR",
        "employment_contract", "personal_confidential",
        """# Hợp đồng lao động mẫu của hr.leader

Mã hợp đồng giả lập: HDLD-DEMO-HRL. Chức danh: Trưởng phòng Nhân sự. Thời hạn
mẫu: 01/01/2026 đến 31/12/2027. Mức lương cơ bản giả lập: 34 triệu đồng mỗi tháng.""",
    ),
    _document(
        "phieu-luong-hr-leader-thang-07-2026.md", "hr.leader", "user", "leader", "HR",
        "payslip", "personal_confidential",
        """# Phiếu lương mẫu của hr.leader tháng 07/2026

Lương cơ bản giả lập: 34 triệu đồng; phụ cấp quản lý giả lập: 4,5 triệu đồng;
khấu trừ giả lập: 2,8 triệu đồng; thực nhận giả lập: 35,7 triệu đồng.""",
    ),
    _document(
        "hop-dong-lao-dong-it-leader.md", "it.leader", "user", "leader", "IT",
        "employment_contract", "personal_confidential",
        """# Hợp đồng lao động mẫu của it.leader

Mã hợp đồng giả lập: HDLD-DEMO-ITL. Chức danh: Trưởng phòng Công nghệ thông tin.
Thời hạn mẫu: 01/01/2026 đến 31/12/2027. Mức lương cơ bản giả lập: 36 triệu đồng mỗi tháng.""",
    ),
    _document(
        "phieu-luong-it-leader-thang-07-2026.md", "it.leader", "user", "leader", "IT",
        "payslip", "personal_confidential",
        """# Phiếu lương mẫu của it.leader tháng 07/2026

Lương cơ bản giả lập: 36 triệu đồng; phụ cấp quản lý giả lập: 5 triệu đồng; khấu
        trừ giả lập: 3 triệu đồng; thực nhận giả lập: 38 triệu đồng.""",
    ),
    _document(
        "hop-dong-lao-dong-superadmin.md", "superadmin", "user", "superadmin", "WORKSPACE",
        "employment_contract", "restricted",
        """# Hợp đồng lao động mẫu của superadmin

Mã hợp đồng giả lập: HDLD-DEMO-SA. Chức danh: Giám đốc điều hành hệ thống mẫu.
Thời hạn mẫu: 01/01/2026 đến 31/12/2028. Mức lương cơ bản giả lập: 48 triệu đồng mỗi tháng.""",
    ),
    _document(
        "phieu-luong-superadmin-thang-07-2026.md", "superadmin", "user", "superadmin", "WORKSPACE",
        "payslip", "restricted",
        """# Phiếu lương mẫu của superadmin tháng 07/2026

Lương cơ bản giả lập: 48 triệu đồng; phụ cấp điều hành giả lập: 8 triệu đồng;
khấu trừ giả lập: 4,5 triệu đồng; thực nhận giả lập: 51,5 triệu đồng.""",
    ),
    _document(
        "phu-luc-thuong-dieu-hanh-2026.md", "superadmin", "user", "superadmin", "WORKSPACE",
        "executive_compensation_appendix", "restricted",
        """# Phụ lục thưởng điều hành năm 2026

Dữ liệu mẫu dành riêng cho SuperAdmin. Mức thưởng giả lập được xác định sau khi
hoàn thành đánh giá cuối năm và không phải là cam kết chi trả thực tế.""",
    ),
)


def seed_business_documents() -> dict[str, Any]:
    """Validate and insert missing sample documents without creating duplicates."""
    store.initialize()
    actors = {user["username"]: user for user in store.users()}
    with store.connect() as db:
        existing = {row[0] for row in db.execute("SELECT filename FROM documents")}

    created: list[str] = []
    skipped: list[str] = []
    for spec in BUSINESS_DOCUMENTS:
        filename = spec["filename"]
        if filename in existing:
            skipped.append(filename)
            continue
        actor = actors[spec["owner_username"]]
        content = spec["content"].encode("utf-8")
        scan = scan_upload(filename, content)
        if not scan.allowed:
            raise RuntimeError(f"Seed document {filename} failed upload scan: {scan.reason}")
        guard = evaluate_rag_context(
            [RAGContextChunk(doc_id=f"seed:{filename}", text=spec["content"], metadata={})]
        )
        if guard.decision not in {Decision.ALLOW, Decision.LOG_ONLY}:
            raise RuntimeError(
                f"Seed document {filename} failed RAG guard: {guard.decision.value}"
            )
        store.add_document(
            actor,
            filename,
            content,
            spec["scope"],
            spec["audience"],
            spec["department"],
            guard_decision=guard.decision.value,
            mime_type="text/markdown",
        )
        existing.add(filename)
        created.append(filename)

    return {"created": created, "skipped": skipped, "total": len(BUSINESS_DOCUMENTS)}
