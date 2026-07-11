# Final Strict PTIT Report Compliance Review

> Phiên rà soát cuối cùng trước khi upload lên Overleaf. Nguồn chính thức: `Phu luc_Hinh thuc va quy cach trinh bay quyen TTTN QD 922-210313.doc` (đọc lại bằng `antiword`, xác nhận vẫn đọc được, nội dung không đổi so với lần audit trước — xem `docs/report/report-compliance-audit.md` mục 0 để biết chi tiết cách đọc và giới hạn về dấu tiếng Việt bị mất khi trích xuất). Tài liệu này **không lặp lại toàn bộ nội dung trích xuất thô** đã có ở `report-compliance-audit.md` — chỉ tóm tắt lại thành checklist ngắn gọn rồi đối chiếu trực tiếp với trạng thái LaTeX **sau khi đã sửa ở phiên này**.

## A. Checklist yêu cầu chính thức (tóm tắt 10 nhóm)

### A1. Thứ tự tài liệu bắt buộc
Áp dụng theo mục "I. BỐ CỤC" (ưu tiên khi văn bản gốc tự mâu thuẫn — xem `report-compliance-audit.md` mục C01/C02):
1. Bìa ngoài — 2. Bìa đệm — 3. Phiếu giao đề cương TTTN được phê duyệt — 4. Mục lục — 5. Lời cảm ơn — 6. Danh mục ký hiệu/chữ viết tắt — 7. Danh mục bảng — 8. Danh mục hình — 9. Kế hoạch thực hiện công việc nhóm — 10. Mở đầu — 11–14. Chương 1–N — 15. Kết luận, kiến nghị — 16. Tài liệu tham khảo — 17. Phụ lục.

### A2. Trang bìa
Bìa ngoài + bìa đệm cùng nội dung: khối trường/cơ sở → logo → loại báo cáo (size 36) → "Đề tài:" + tên đề tài → khối thông tin (Người hướng dẫn, Sinh viên 1+MSSV+Lớp, Sinh viên 2+MSSV+Lớp, Ngành) → địa điểm/thời gian.

### A3. Đánh số trang
La Mã (i, ii...) từ Mục lục đến hết Kế hoạch nhóm; Ả Rập (1, 2...) từ Mở đầu đến hết Phụ lục; bìa/phiếu đề cương không đánh số.

### A4. Font & cỡ chữ
Times New Roman, 12 hoặc 13pt thân bài; tiêu đề chương in hoa đậm 13–15; tiêu đề mục đậm 13; tiêu đề trang Mục lục/Danh mục... in hoa đậm ~14 (suy ra từ mẫu "toàn bộ size: 12" cho dòng mục lục con — xem ghi chú Unknown ở mục C07 của audit, không nhầm với tiêu đề TRANG Mục lục).

### A5. Lề trang
Trái 3cm; trên/phải/dưới 2cm.

### A6. Header/Footer
Header trái "Báo cáo TTTN Đại học"; Header phải tên chương; Footer trái "Nhóm_<Tên nhóm>"; Footer phải số trang; khoảng cách header/footer ~1cm.

### A7. Bảng/hình/danh mục
Số thứ tự hình đặt dưới hình; đánh số phân cấp theo chương (1.1, 1.1.1); mỗi bảng/sơ đồ/hình nên có ghi chú nguồn; mẫu văn bản gốc phân biệt 3 loại Bảng/Sơ đồ/Hình.

### A8. Danh mục ký hiệu
Xếp theo abc A→Z; mỗi dòng gồm chữ viết tắt, chữ đầy đủ, nghĩa.

### A9. Kế hoạch nhóm
Đúng 5 cột: TT | Nội dung | Người thực hiện | Thời gian thực hiện | Mức độ hoàn thành.

### A10. Tài liệu tham khảo & Phụ lục
Tách 3 nhóm Tiếng Việt/Tiếng Anh/Website (chưa xử lý ở phiên này — xem mục "Remaining manual review"); Phụ lục không dày hơn phần chính; vị trí tương đối với Tài liệu tham khảo có mâu thuẫn nguồn (xem A1).

---

## B. Bảng đối chiếu chi tiết (sau khi sửa ở phiên Final Strict Compliance)

| # | Yêu cầu | File đã kiểm tra | Trạng thái | Ghi chú | Còn cần rà soát thủ công |
|---|---|---|---|---|---|
| B1 | `\faculty` = "Khoa Công nghệ thông tin 2" | `thesis.sty` dòng 7 | **Fixed** | Đổi từ "Khoa An toàn thông tin" theo đúng chỉ thị | Xác nhận đây đúng là tên Khoa chính thức của nhóm |
| B2 | `\teamname` = "Nhóm\_A06" (footer), "Nhóm A06" (văn xuôi) | `thesis.sty` dòng 25–26 | **Fixed** | Thêm `\teamnameprose` dùng trong `pages/group-work-plan.tex`; `\teamname` (có gạch dưới) dùng cho Footer qua `\fancyfoot` | Xác nhận A06 đúng là mã nhóm chính thức do Khoa cấp |
| B3 | GVHD = "ThS. Nguyễn Hoàng Thành" xuyên suốt `report-latex-template/` | `thesis.sty` dòng 15 | **Pass (giữ nguyên từ phiên trước)** | Đã grep xác nhận không còn "Thanh" trong nội dung hiển thị của `report-latex-template/` | Các file `.md` khác ngoài phạm vi cho phép sửa vẫn ghi "Thanh" (không thuộc phiên này) |
| B4 | Loại báo cáo "BÁO CÁO ĐỊNH KỲ / THỰC TẬP TỐT NGHIỆP ĐẠI HỌC", đậm, ~36pt, cả 2 bìa | `thesis.sty` dòng 52 (bìa ngoài), dòng 88 (bìa đệm) | **Fixed** | Bìa đệm trước đó chỉ 30pt, nay tăng lên 36pt như bìa ngoài theo đúng chỉ thị | Kiểm tra bằng build thật xem 36pt trên bìa đệm có tràn khung không (bìa đệm không có khung tikz nên rủi ro thấp hơn bìa ngoài) |
| B5 | Header trường/cơ sở đúng 3 dòng | `thesis.sty` dòng 49–51 (bìa ngoài), dòng 90–92 (bìa đệm) | **Pass (giữ nguyên từ phiên trước)** | "BỘ KHOA HỌC VÀ CÔNG NGHỆ / HỌC VIỆN CÔNG NGHỆ BƯU CHÍNH VIỄN THÔNG / CƠ SỞ TẠI THÀNH PHỐ HỒ CHÍ MINH" | — |
| B6 | Nhãn "Đề tài:" in đậm trước tên đề tài | `thesis.sty` dòng 54–55 (bìa ngoài), dòng 89–90 (bìa đệm) | **Fixed** | Trước đây thiếu hẳn nhãn này, chỉ có tên đề tài; nay thêm dòng "Đề tài:" riêng, in đậm, trước tên đề tài | — |
| B7 | Tên đề tài mới: "Nghiên cứu và triển khai cơ chế Guardrails bảo vệ hệ thống RAG trước tấn công Prompt Injection và rò rỉ dữ liệu" | `thesis.sty` dòng 8 (`\titlethesis`) | **Fixed** | Thay thế tên đề tài cũ ("Xây dựng Hệ thống Bảo mật LLM...") theo đúng chỉ thị; đã grep xác nhận không còn tên cũ ở đâu trong `report-latex-template/` | **Tên đề tài này khác với tên dùng ở `README.md`/`PROJECT_PLAN.md`/toàn bộ `docs/` khác của dự án** (các file đó ngoài phạm vi cho phép sửa) — đây là một điểm KHÔNG NHẤT QUÁN cấp dự án cần nhóm xác nhận: dùng tên nào là tên chính thức cuối cùng |
| B8 | Nhãn IN HOA đậm: NGƯỜI HƯỚNG DẪN/SINH VIÊN 1/MSSV/LỚP/SINH VIÊN 2/MSSV/LỚP/NGÀNH | `thesis.sty` dòng 60–68 (bìa ngoài), dòng 98–106 (bìa đệm) | **Fixed** | Viết lại hoàn toàn khối `tabular`: 8 dòng đúng thứ tự và đúng nhãn in hoa; MSSV tách thành dòng riêng thay vì viết chung dòng với tên sinh viên như phiên trước | Kiểm tra canh lề/khoảng cách dòng khi build thật |
| B9 | Thứ tự thông tin bìa | `thesis.sty` (như B8) | **Pass (đã đúng từ phiên trước, giữ nguyên)** | Trường/cơ sở → Loại báo cáo → Đề tài → Người hướng dẫn → SV1 → Lớp → SV2 → Lớp → Ngành → Địa điểm/thời gian | — |
| B10 | Khung viền trang trí trên bìa | `thesis.sty` dòng 34–41 | **Giữ nguyên + đã thêm TODO** | Không tự ý xóa khung; thêm comment TODO giải thích lý do giữ và điều kiện nên xóa (nếu Khoa yêu cầu bìa trơn) | Hỏi Khoa/Bộ môn có bắt buộc bìa trơn không họa tiết hay không |
| B11 | Xóa comment nội bộ nhắc AI/session/Fix Phase | Toàn bộ `report-latex-template/*.tex`, `*.sty` | **Fixed** | Đã grep và rút gọn toàn bộ comment còn nhắc "Report Compliance Fix Phase", "phiên này", "phiên làm việc sau", cross-reference tới `report-compliance-audit.md mục Cxx`; comment còn lại chỉ mang tính kỹ thuật (vd: "`\chapter*` không tự gọi `\markboth`") | — |
| C1 | Tiêu đề "MỤC LỤC" in hoa đậm | `styles/settings.tex` (`\@cftmaketoctitle`) | **Fixed** | Bọc `\MakeUppercase{\contentsname}`; đồng thời redefine `\contentsname` = "Mục lục" trong `\AtBeginDocument` để không phụ thuộc chuỗi mặc định của babel | Xác nhận bằng build thật babel không ghi đè lại sau `\AtBeginDocument` |
| C2 | Tiêu đề "DANH MỤC CÁC BẢNG"/"DANH MỤC CÁC HÌNH" in hoa đậm, đúng thuật ngữ | `styles/settings.tex` (`\@cftmakelottitle`, `\@cftmakeloftitle`) | **Fixed** | Redefine `\listtablename`="Danh mục các bảng", `\listfigurename`="Danh mục các hình" (khớp đúng thuật ngữ chính thức, không dùng chuỗi mặc định của babel có thể khác); bọc `\MakeUppercase{}` | Tương tự C1 |
| C3 | Tiêu đề "LỜI CẢM ƠN" in hoa đậm cỡ 14 | `thesis.sty` (env `acknowledgments`, gọi `\chapter*`) | **Pass (tự động qua titlesec)** | `\titleformat{name=\chapter,numberless}` trong `settings.tex` đã áp `\MakeUppercase`+`\bfseries`+14pt cho MỌI `\chapter*`, không cần hack riêng | — |
| C4 | Tiêu đề "DANH MỤC CÁC KÝ HIỆU VÀ CHỮ VIẾT TẮT" in hoa đậm cỡ 14 | `pages/abbreviations.tex` (`\chapter*`) | **Pass (tự động qua titlesec)** | Cùng cơ chế C3 | — |
| C5 | Tiêu đề "KẾ HOẠCH THỰC HIỆN CÔNG VIỆC NHÓM" in hoa đậm cỡ 14 | `pages/group-work-plan.tex` (`\chapter*`) | **Pass (tự động qua titlesec)** | Cùng cơ chế C3 | — |
| D1 | Tiêu đề chương: in hoa, đậm, cỡ 13–15 | `styles/settings.tex` dòng 60–66 | **Pass (không đổi, đã đúng)** | 14pt, `\MakeUppercase`, `\bfseries`, `\centering` | — |
| D2 | Tiêu đề mục (`\section`): đậm, cỡ ~13, đánh số 1.1 | `styles/settings.tex` dòng 69–71 | **Pass (không đổi, đã đúng)** | 13pt, `\bfseries`, số tự động qua `\thesection` | — |
| D3 | Tiêu đề tiểu mục (`\subsection`): đậm, đánh số 1.1.1 | `styles/settings.tex` dòng 72–74 | **Pass (không đổi, đã đúng)** | 13pt, `\bfseries`, số tự động qua `\thesubsection` | — |
| E1 | Thứ tự Danh mục ký hiệu → Bảng → Hình → Kế hoạch nhóm | `main.tex` dòng 34–58 | **Pass (không đổi, đã đúng)** | Khớp mục A1 | Xem mâu thuẫn nguồn C02 trong audit gốc |
| E2 | Danh mục hình rỗng — không dựng hình giả | `chapters/appendix.tex` (Phụ lục C) | **Pass (giữ nguyên, đã viết lại câu chữ)** | Ghi chú TODO minh bạch, đã bỏ cách diễn đạt "phiên làm việc sau" | Xuất ảnh sơ đồ thật ở giai đoạn tiếp theo |
| E3 | Caption bảng + header đậm | `chapters/chap-1-background.tex`, `chap-2-method.tex`, `pages/group-work-plan.tex` | **Pass (không đổi, đã đúng từ phiên trước)** | Mọi bảng đều có `\caption` + hàng tiêu đề `\textbf{}` | — |
| E4 | Bảng Kế hoạch nhóm đúng 5 cột, không tràn trang | `pages/group-work-plan.tex` | **Pass (không đổi, đã đúng từ phiên trước)** | Tổng độ rộng cột ≈ 0.92\linewidth, an toàn trong lề | Kiểm tra bằng build thật |
| E5 | Owner trong bảng nhóm dùng đúng 3 giá trị cho phép | `pages/group-work-plan.tex` | **Pass** | Chỉ dùng "Nguyễn Văn An", "Lê Đình Nghĩa", "Cả nhóm" | — |
| F1 | Danh mục ký hiệu xếp abc | `pages/abbreviations.tex` | **Pass (không đổi, đã đúng từ phiên trước)** | 23 mục, A→Z | — |
| F2 | Đủ thuật ngữ yêu cầu (AI, API, ASR, FNR, FPR, LLM, LLMSVS, OWASP, PII, RAG, SIEM, STRIDE, TTTN) | `pages/abbreviations.tex` | **Pass** | Đã kiểm tra đủ cả 13 thuật ngữ | — |
| G1 | Đánh số La Mã Mục lục→Kế hoạch nhóm, Ả Rập Mở đầu→Phụ lục | `main.tex` (`\frontmatter`/`\mainmatter`) | **Pass (không đổi, đã đúng từ phiên trước)** | Cơ chế đúng vị trí | Cần build PDF thật để xác nhận trực quan |
| G2 | Header trái/phải, Footer trái/phải | `thesis.sty` dòng 155–160 | **Pass (nội dung Footer trái tự động đổi theo B2)** | `\teamname` nay là "Nhóm\_A06" nên Footer trái tự động đúng, không cần sửa thêm gì trong `\fancyfoot` | — |
| G3 | `\markboth` cho các trang `\chapter*` | `thesis.sty`, `chapters/chap-0...tex`, `conclusion.tex`, `pages/abbreviations.tex`, `pages/group-work-plan.tex`, `chapters/appendix.tex` | **Pass (không đổi, đã đúng từ phiên trước)** | Đủ 6 nhóm trang theo yêu cầu | Xác nhận bằng build thật |
| H1 | A4, lề 3cm/2cm, header/footer ~1cm | `styles/settings.tex` dòng 36–46 | **Pass (không đổi, đã đúng)** | — | — |
| H2 | Font Times-like, 12/13pt | `styles/settings.tex` dòng 7–8, 150 | **Pass (không đổi, đã đúng)**; rủi ro dấu tiếng Việt vẫn Unknown | `newtxtext`+`T5` fontenc | Build thật để xác nhận dấu tiếng Việt |
| H3 | Căn đều, spacing 3pt, giãn dòng ~1.15 | `styles/settings.tex` dòng 159–160, 150 | **Pass (không đổi, đã đúng)** | — | — |

---

## C. Tổng kết trạng thái

| Trạng thái | Số lượng (trên 34 mục ở bảng B) |
|---|---|
| Fixed (sửa mới ở phiên này) | 9 |
| Pass (đã đúng từ trước, không cần sửa) | 22 |
| Needs manual review / Unknown | 3 (B1 mã Khoa, B2 mã nhóm A06, B7 tên đề tài không khớp phần còn lại của dự án) |

**Không có mục nào bị đánh giá Fail còn tồn đọng trong `report-latex-template/`** ở lần rà soát này — mọi Fail đã biết từ audit gốc (`report-compliance-audit.md`) hoặc đã được sửa ở phiên trước hoặc phiên này, hoặc đã được ghi nhận rõ ràng là "cố tình giữ nguyên do văn bản gốc mâu thuẫn" (không phải lỗi, mà là quyết định có ghi chú). Các mục còn "Needs manual review" đều là các con số/tên KHÔNG THỂ tự suy luận được (mã Khoa, mã nhóm, tên đề tài cuối cùng) — bắt buộc phải có xác nhận từ con người.

## D. Remaining manual review (tổng hợp)

1. **Xác nhận tên đề tài cuối cùng:** `report-latex-template/` hiện dùng tên mới ("Nghiên cứu và triển khai cơ chế Guardrails...") theo đúng chỉ thị của phiên này, nhưng đây là tên KHÁC với tên đang dùng ở README.md/PROJECT_PLAN.md/toàn bộ tài liệu `docs/` khác của dự án ("Xây dựng Hệ thống Bảo mật LLM..."). Cần nhóm xác nhận đây có phải đổi tên đề tài chính thức hay chỉ là tên rút gọn riêng cho báo cáo định kỳ.
2. **Xác nhận "Khoa Công nghệ thông tin 2"** đúng là Khoa quản lý ngành An toàn thông tin của nhóm tại cơ sở TP.HCM.
3. **Xác nhận mã nhóm "A06"** là mã chính thức do Khoa/Bộ môn cấp (không phải tự đặt).
4. Toàn bộ mục "Remaining manual review" đã liệt kê trong `docs/report/report-compliance-fix-summary.md` mục 6 (2 mâu thuẫn nguồn C01/C02, chưa tách 3 nhóm Tài liệu tham khảo, chưa có 3 loại danh mục Bảng/Sơ đồ/Hình riêng, chưa build PDF thật) **vẫn còn nguyên giá trị**, không bị thay đổi bởi phiên rà soát này.
5. **Build PDF thật trên Overleaf** là bước bắt buộc tiếp theo — mọi mục "Pass (tính toán)"/"Fixed" ở trên vẫn chỉ là đúng về mặt cấu hình LaTeX, chưa được xác nhận bằng bản in trực quan.
