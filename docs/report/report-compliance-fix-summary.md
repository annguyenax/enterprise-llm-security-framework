# Report Compliance Fix Summary — Báo cáo định kỳ TTTN

> Phiên làm việc: **Report Compliance Fix Phase**. Chỉ sửa các vấn đề đã được xác định trong `docs/report/report-compliance-audit.md`. Không viết lại toàn bộ báo cáo, không đổi ý nghĩa học thuật/nghiên cứu, không thêm kết quả/số liệu giả, không bịa trích dẫn.

## 1–4. Bảng tổng hợp: Vấn đề đã sửa / File thay đổi / Nội dung thay đổi / Còn cần rà soát thủ công

| # | Vấn đề đã sửa (mã audit) | File thay đổi | Nội dung đã thay đổi | Còn cần rà soát thủ công |
|---|---|---|---|---|
| 1 | C16 — Sai chính tả tên GVHD | `thesis.sty` | Đổi `\supervisor` từ "Nguyễn Hoàng Thanh" → **"Nguyễn Hoàng Thành"**, theo đúng chỉ thị của phiên này | Các file `.md` khác ngoài phạm vi cho phép sửa (README.md, PROJECT_PLAN.md, AGENT_RULES.md, TASK_BOARD.md, `docs/report/bao-cao-dinh-ky-01.md`, `docs/weekly-notes/`) **vẫn còn ghi "Nguyễn Hoàng Thanh"** — xem mục 6 bên dưới |
| 2 | C03 — Dòng 3 trên bìa sai (Khoa thay vì địa điểm) | `thesis.sty` (`\coverpage`, `\innercoverpage`) | Đổi dòng 3 từ `\faculty` thành literal **"CƠ SỞ TẠI THÀNH PHỐ HỒ CHÍ MINH"** ở cả 2 macro bìa | Xác nhận với GVHD/Khoa xem có cần thêm dòng tên Khoa ở vị trí khác không |
| 3 | C04 — Sai thứ tự thông tin trên bìa | `thesis.sty` (`\coverpage`, `\innercoverpage`) | Viết lại khối `tabular` theo đúng thứ tự mẫu: **Người hướng dẫn → Sinh viên 1 (MSSV) → Lớp → Sinh viên 2 (MSSV) → Lớp → Ngành** | Kiểm tra bố cục thị giác thực tế sau khi build (khoảng cách dòng, canh giữa) |
| 4 | C05 — Cỡ chữ tên loại báo cáo chưa đạt 36pt | `thesis.sty` (`\coverpage`) | Tăng cỡ chữ `\reporttype` trên bìa ngoài từ 18pt → **36pt** (bìa đệm tăng lên 30pt, nhỏ hơn một chút để phân biệt 2 lớp bìa — quyết định diễn giải riêng, xem mục 6) | Kiểm tra 36pt có làm vỡ bố cục bìa (tràn trang) khi build thật hay không, đặc biệt với dòng 2 chữ "THỰC TẬP TỐT NGHIỆP ĐẠI HỌC" |
| 5 | C06 — Danh mục ký hiệu không xếp theo abc | `pages/abbreviations.tex` | Sắp xếp lại toàn bộ theo thứ tự chữ cái A→Z của cột "Từ viết tắt"; **thêm thuật ngữ "AI"** còn thiếu; giữ nguyên 3 cột (Từ viết tắt / Nghĩa tiếng Anh / Nghĩa tiếng Việt) | Xác nhận danh sách 23 thuật ngữ đã đủ, không thiếu thuật ngữ nào dùng trong thân báo cáo |
| 6 | C08 — Bảng Kế hoạch nhóm sai cấu trúc | `pages/group-work-plan.tex` | Gộp 2 bảng cũ (2 cột + 3 cột) thành **1 bảng đúng 5 cột chính thức**: TT / Nội dung / Người thực hiện / Thời gian thực hiện / Mức độ hoàn thành, điền theo Phase 0 → Phase 2.5 → chuẩn bị báo cáo → MVP tương lai | Xác nhận nội dung từng dòng có phản ánh đúng thực tế phân công của nhóm hay không |
| 7 | C12 — `\chapter*` không cập nhật `\leftmark` (Header phải sai) | `thesis.sty` (env `acknowledgments`), `chapters/chap-0.phan-mo-dau.tex`, `chapters/conclusion.tex`, `pages/abbreviations.tex`, `pages/group-work-plan.tex`, `chapters/appendix.tex` | Thêm `\markboth{<TÊN TRANG>}{}` thủ công ngay sau mỗi `\chapter*`/`\chapter` liên quan cho: Lời cảm ơn, Danh mục ký hiệu, Kế hoạch nhóm, Mở đầu, Kết luận-kiến nghị, và cả 5 chương Phụ lục (A–E, dùng `\Alph{chapter}` động) | Xác nhận bằng build thật rằng Header phải hiển thị đúng tiêu đề ở từng trang này (không thể test nếu chưa có `pdflatex`) |
| 8 | C14 — Danh mục hình sẽ rỗng | `chapters/appendix.tex` (Phụ lục C — Ghi chú môi trường biên dịch) | Thêm đoạn ghi chú tường minh: Danh mục hình hiện rỗng vì chưa chèn hình nào; liệt kê rõ đây là **TODO cho phiên sau** (xuất sơ đồ Mermaid → ảnh → chèn vào Chương 2); **không** thêm hình ảnh giả để "lấp chỗ trống" | Thực hiện việc xuất sơ đồ thật ở một phiên làm việc riêng (cần công cụ xuất ảnh, ngoài phạm vi phiên này) |
| 9 | C01 — Xung đột thứ tự Tài liệu tham khảo / Phụ lục | `main.tex` | Thêm khối comment giải thích rõ mâu thuẫn trong văn bản gốc (mục I vs mục II.5 + mục lục mẫu) và lý do giữ thứ tự **Tài liệu tham khảo trước Phụ lục** (theo ưu tiên "BỐ CỤC" như chỉ thị yêu cầu) | Hỏi GVHD/Khoa xác nhận thứ tự chính thức; nếu cần đảo ngược chỉ cần hoán đổi 2 khối lệnh trong `main.tex` |
| 10 | C02 — Xung đột thứ tự Danh mục ký hiệu / Danh mục bảng-hình | `main.tex` | Thêm khối comment giải thích mâu thuẫn tương tự (mục I vs ghi chú trang mẫu) và lý do giữ nguyên thứ tự Danh mục ký hiệu trước Danh mục bảng/hình | Hỏi GVHD/Khoa xác nhận thứ tự chính thức |
| 11 | Mục 10 chỉ thị — Rà soát văn phong | Không cần sửa file nào | Đã kiểm tra bằng `grep`: không có "em" số ít sai ngữ cảnh, không có khẳng định "đã triển khai hệ thống"/"production-ready" nào bị hiểu sai — toàn bộ đã đúng chuẩn "chúng em"/"nhóm em" và "dự kiến triển khai" | Đọc lại toàn văn một lần cuối trước khi nộp (rà soát bằng mắt, không chỉ bằng grep) |

## 5. Hướng dẫn biên dịch

Môi trường làm việc hiện tại **chưa có sẵn `pdflatex`/`xelatex`** nên các thay đổi trong phiên này **chưa được build thử để xác nhận trực quan**. Khi có môi trường TeX (khuyến nghị: Overleaf, hoặc MiKTeX/TeX Live cài đặt cục bộ có hỗ trợ tiếng Việt):

```
cd report-latex-template
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

**Lưu ý khi build trên Overleaf:**
- Tải lên toàn bộ thư mục `report-latex-template/` (bao gồm `assets/`, `figure/`, `chapters/`, `pages/`, `styles/`, `main.tex`, `thesis.sty`, `refs.bib`).
- Đặt `main.tex` làm file biên dịch chính (Overleaf thường tự nhận diện qua tên `main.tex`).
- Compiler nên chọn **pdfLaTeX**. Nếu gặp lỗi liên quan `T5`/dấu tiếng Việt (rủi ro đã ghi trong audit mục C13), thử đổi sang **XeLaTeX** — nhưng lưu ý phần khai báo font trong `styles/settings.tex` hiện được viết cho pdfLaTeX (`fontenc[T5,T1]` + `newtxtext`), **chưa được điều chỉnh cho XeLaTeX** (sẽ cần thay bằng `fontspec` + `\setmainfont{Times New Roman}` nếu chuyển compiler — việc này **chưa được thực hiện** trong phiên này vì nằm ngoài danh sách vấn đề ưu tiên).
- Overleaf tự động chạy đủ số vòng `pdflatex`/`bibtex` cần thiết khi nhấn "Recompile" — không cần chạy tay 3 lệnh trên, chỉ áp dụng cho biên dịch dòng lệnh cục bộ.

## 6. Xung đột/vấn đề còn tồn tại chưa giải quyết được

1. **Xung đột thứ tự Tài liệu tham khảo vs Phụ lục (C01):** văn bản gốc tự mâu thuẫn. Đã chọn giữ thứ tự theo mục "BỐ CỤC" (Tài liệu tham khảo trước Phụ lục) theo đúng chỉ thị ưu tiên của phiên này, và đã ghi chú rõ trong `main.tex`. **Chưa được GVHD/Khoa xác nhận chính thức.**
2. **Xung đột thứ tự Danh mục ký hiệu vs Danh mục bảng/hình (C02):** tương tự mục 1, giữ theo "BỐ CỤC", đã ghi chú trong `main.tex`, **chưa được xác nhận chính thức.**
3. **Tên GVHD không nhất quán toàn dự án:** `report-latex-template/` nay dùng "Nguyễn Hoàng Thành" (theo chỉ thị phiên này), nhưng các file sau **vẫn còn ghi "Nguyễn Hoàng Thanh"** vì nằm ngoài phạm vi cho phép sửa của phiên Fix này: `README.md`, `PROJECT_PLAN.md`, `AGENT_RULES.md`, `TASK_BOARD.md`, `docs/report/bao-cao-dinh-ky-01.md`, `docs/weekly-notes/week-01.md`. **Cần một phiên làm việc riêng, được phép sửa các file đó, để đồng bộ toàn dự án** sau khi chốt chính tả chính xác.
4. **Chưa build PDF thật:** mọi khẳng định "Pass" về font/dấu tiếng Việt/độ dài trang/bố cục bìa trong audit và trong bảng ở mục 1–4 vẫn ở mức "đúng về mặt cấu hình LaTeX", **chưa được xác nhận bằng bản build PDF thực tế** (môi trường làm việc không có `pdflatex`). Khuyến nghị build trên Overleaf ngay khi có thể.
5. **Danh mục hình vẫn sẽ rỗng cho tới khi có ảnh sơ đồ thật** — đã ghi TODO rõ ràng trong Phụ lục, chưa xuất ảnh (nằm ngoài phạm vi phiên này vì không được cài thêm công cụ/package).
6. **Tài liệu tham khảo chưa tách 3 nhóm Tiếng Việt/Tiếng Anh/Website (C09):** phát hiện này có trong audit nhưng **không nằm trong danh sách 11 mục ưu tiên sửa của phiên này**, nên chưa được xử lý. Vẫn dùng `\bibliographystyle{plain}` với 1 danh sách gộp.
7. **Cỡ chữ 12pt riêng cho tiêu đề trong trang Mục lục (C07):** chưa được cấu hình tường minh (không nằm trong 11 mục ưu tiên của phiên này); `tocloft` hiện dùng cỡ chữ mặc định.
8. **3 loại danh mục Bảng/Sơ đồ/Hình riêng biệt (C10):** chưa thêm counter/float type riêng cho "Sơ đồ" (không nằm trong 11 mục ưu tiên); hiện chỉ có Bảng và Hình.
9. **Ghi chú nguồn dưới mỗi bảng trong Chương 1–4 (C11):** chưa thêm (không nằm trong 11 mục ưu tiên).

## Tổng kết mức độ hoàn thành

- **10/11 mục ưu tiên** trong chỉ thị của phiên này đã được xử lý trực tiếp bằng thay đổi file (mục 1–9 ở bảng trên, cộng rà soát văn phong ở mục 11 không cần sửa file).
- Mục còn lại liên quan tới **định dạng cơ bản (margin/font/spacing)** không cần sửa vì đã đúng từ phiên Report Template Compliance trước đó (đã xác nhận lại qua audit, không có Fail nào ở nhóm này).
- **2 xung đột nguồn** (C01, C02) được xử lý bằng cách **giữ nguyên theo "BỐ CỤC"** kèm ghi chú minh bạch trong code, đúng theo chỉ thị ưu tiên — không tự ý "đoán" câu trả lời đúng.
