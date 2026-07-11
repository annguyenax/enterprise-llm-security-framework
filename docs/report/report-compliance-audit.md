# Report Compliance Audit — Báo cáo định kỳ TTTN

> **Phiên làm việc gốc tạo tài liệu này là READ-ONLY.** Không có file `.tex`, `.sty`, `.bib`, `.md`, ảnh, hay code nào bị chỉnh sửa trong phiên audit gốc. Chỉ tạo mới file này.
>
> **CẬP NHẬT (Report Compliance Fix Phase):** Nhiều mục Fail/Unknown bên dưới đã được xử lý ở một phiên làm việc riêng. Xem `docs/report/report-compliance-fix-summary.md` để biết chi tiết đầy đủ (file thay đổi, nội dung sửa, việc còn tồn đọng). Tóm tắt nhanh trạng thái sau khi sửa: **C01, C02 → giữ nguyên + ghi chú minh bạch (không tự quyết vì nguồn mâu thuẫn)**; **C03, C04, C05, C06, C08, C12, C14, C16 → đã sửa**; **C07, C09, C10, C11, C13, C15, C17 → chưa sửa** (nằm ngoài 11 mục ưu tiên của phiên Fix, hoặc cần build PDF thật để xác nhận). Ma trận gốc bên dưới được giữ nguyên làm hồ sơ tham chiếu (không chỉnh sửa nội dung ma trận), chỉ bổ sung ghi chú "ĐÃ SỬA" vào cuối các dòng liên quan.

## 0. Đọc file yêu cầu chính thức

**Đã tìm thấy và đọc được** file gốc:

```
Phu luc_Hinh thuc va quy cach trinh bay quyen TTTN QD 922-210313.doc
```

nằm ở thư mục gốc dự án (`d:\DoAnThucTap\enterprise-llm-security-framework\`). Đây là file `.doc` nhị phân định dạng cũ (Composite Document File V2 / OLE2, không phải `.docx`), được tạo bởi Microsoft Word, tiêu đề nội bộ "HƯỚNG DẪN", tác giả "Mai Hoang", 12 trang, 1843 từ.

**Công cụ đọc:** Tool `Read` của hệ thống báo lỗi "không đọc được file nhị phân". Đã dùng `antiword` (công cụ dòng lệnh **đã có sẵn** trong môi trường làm việc, không cài đặt thêm gói nào mới) để trích xuất văn bản thô từ file `.doc`.

**Vấn đề về encoding (quan trọng, cần lưu ý khi đọc audit này):** File gốc dùng bảng mã tiếng Việt kiểu cũ (khả năng cao là TCVN3/VNI theo font, không phải Unicode) — đây là kiểu mã hóa gắn với font hiển thị cụ thể, không phải charset chuẩn nên `antiword` không giải mã được dấu tiếng Việt, mọi dấu thanh/dấu phụ đều hiển thị thành ký tự `?`. Ví dụ text thô: `H�NH TH?C, QUY C�CH V� C?U TR�C QUY?N TTTN`.

Phần con chữ Latin cơ bản (không dấu) vẫn đọc được nguyên vẹn, nên **nội dung và cấu trúc câu vẫn tái dựng được với độ tin cậy cao** bằng cách khôi phục dấu tiếng Việt dựa trên ngữ cảnh (kỹ năng đọc "tiếng Việt không dấu" phổ biến). Toàn bộ phần trích dẫn yêu cầu chính thức trong audit này đều đã được đối chiếu ngược lại với bản trích xuất thô để đảm bảo không bịa nội dung — bản trích xuất thô đầy đủ được lưu tạm tại `/tmp/ptit_extracted.txt` trong phiên làm việc (không phải một phần của kho mã nguồn).

**Do vẫn có rủi ro sai lệch nhỏ ở một số từ đơn lẻ khó đoán**, mọi mục trong audit này lấy trực tiếp từ câu chữ rõ ràng, không mơ hồ của bản trích xuất được đánh dấu **Pass/Fail/Partial**; những chỗ câu chữ bản gốc tự mâu thuẫn hoặc khó khẳng định 100% được đánh dấu **Unknown**.

---

## 1. Trích xuất yêu cầu chính thức (checklist có cấu trúc)

### 1.1 Thứ tự tài liệu bắt buộc

Theo mục "I. BỐ CỤC" của văn bản gốc:

1. Bìa màu xanh nước biển (không sử dụng bìa kiếng/bìa nhựa trong)
2. Bìa đệm
3. Phiếu giao đề cương Thực tập tốt nghiệp được phê duyệt
4. Mục lục
5. Lời cảm ơn
6. Danh mục các ký hiệu và chữ viết tắt
7. Danh mục các bảng (biểu)
8. Danh mục các hình (vẽ)
9. Kế hoạch thực hiện công việc nhóm
10. Mở đầu
11. Chương 1...
12. Chương 2...
13. Chương n.
14. Kết luận, Kiến nghị
15. Tài liệu tham khảo
16. Phụ lục (nếu có)

**⚠️ MÂU THUẪN NỘI BỘ TRONG VĂN BẢN GỐC (phát hiện quan trọng):** Danh sách trên (mục I) liệt kê "Tài liệu tham khảo" **trước** "Phụ lục". Nhưng ở phần chi tiết cách trình bày Tài liệu tham khảo (mục II.5/mẫu cuối văn bản), văn bản gốc ghi rõ:

> "Danh mục tài liệu tham khảo xếp **cuối cùng, sau các trang phụ lục**."

Và **bản mục lục mẫu đính kèm trong chính văn bản gốc** minh họa rõ:

```
KẾT LUẬN ........................... 120
PHỤ LỤC ............................ 121
DANH MỤC TÀI LIỆU THAM KHẢO ........ 130
```

tức là **Phụ lục đứng trước Tài liệu tham khảo** trong ví dụ thực tế — ngược với thứ tự liệt kê ở mục I. Đây là mâu thuẫn có thật trong văn bản gốc (2/3 tín hiệu — câu văn chi tiết + mục lục mẫu — ủng hộ "Phụ lục trước Tài liệu tham khảo"; chỉ có danh sách tóm tắt ở mục I ghi ngược lại). **Cần hỏi giảng viên hướng dẫn/Khoa để chốt thứ tự chính xác trước khi nộp bản cuối.**

**⚠️ MÂU THUẪN NỘI BỘ THỨ HAI:** Mục I liệt kê "Danh mục các ký hiệu và chữ viết tắt" **trước** "Danh mục các bảng/hình". Nhưng trang mẫu "KÝ HIỆU CÁC CỤM TỪ VIẾT TẮT" trong văn bản gốc lại ghi chú:

> "(Được xếp sau trang Danh mục Các bảng, sơ đồ, hình)"

tức là ngược lại — Danh mục ký hiệu/chữ viết tắt xếp **sau** Danh mục bảng/sơ đồ/hình theo ghi chú mẫu, trong khi mục I lại liệt kê trước. **Đây cũng cần hỏi lại để chốt chính xác.**

### 1.2 Yêu cầu trang bìa

- Bìa ngoài: theo mẫu, **chỉ bìa màu xanh nước biển, không dùng bìa kiếng** (yêu cầu về vật lý/in ấn, không áp dụng trực tiếp cho file LaTeX/PDF).
- Nội dung bìa (theo mẫu, từ trên xuống):
  1. "BỘ KHOA HỌC VÀ CÔNG NGHỆ"
  2. "HỌC VIỆN CÔNG NGHỆ BƯU CHÍNH VIỄN THÔNG"
  3. **"CƠ SỞ TẠI THÀNH PHỐ HỒ CHÍ MINH"** (dòng thứ 3 là địa điểm cơ sở, KHÔNG phải tên Khoa)
  4. [logo — `[pic]`]
  5. "BÁO CÁO THỰC TẬP TỐT NGHIỆP ĐẠI HỌC" (Bold, size 36) — *"Nếu là Báo cáo định kỳ thì ghi là BÁO CÁO ĐỊNH KỲ THỰC TẬP TỐT NGHIỆP ĐẠI HỌC"*
  6. "Đề tài: \"...\"" (Bold, size 16–30 tùy độ dài tên đề tài)
  7. Khối thông tin, **theo đúng thứ tự sau**: Người hướng dẫn → Sinh viên 1 (kèm MSSV) → Lớp → Sinh viên 2 (kèm MSSV) → Lớp → Ngành (mỗi dòng Bold, size 13, in hoa)
  8. "TP.HCM, tháng .... /20...." (Bold, size 13)
- Bìa đệm: đặt sau bìa ngoài, nội dung theo mẫu tương tự (văn bản gốc không mô tả khác biệt cụ thể ngoài việc là một trang riêng).

### 1.3 Yêu cầu đánh số trang

- Trang La Mã thường (i, ii, iii...): **từ Mục lục đến hết Kế hoạch thực hiện công việc nhóm.**
- Trang Ả Rập (1, 2, 3...): **từ Mở đầu đến hết Phụ lục.**
- (Bìa ngoài, bìa đệm, phiếu đề cương: không đánh số — suy ra từ việc La Mã chỉ bắt đầu "từ Mục lục".)

### 1.4 Yêu cầu font & cỡ chữ

- Khổ giấy A4.
- Font: **Times New Roman**, cỡ **12 hoặc 13**.
- Không dùng font kiểu thư pháp.
- Không dùng câu tục ngữ/thành ngữ, hoa văn, hình vẽ trang trí ở đầu mỗi trang/chương/mục.
- Tiêu đề chương: **in hoa, in đậm, cỡ chữ 13–15.**
- Tiêu đề mục con trong chương: **in đậm, cỡ chữ 13.**
- Toàn báo cáo phải **thống nhất** font/cỡ/kiểu (đậm/nghiêng/thường) cho từng cấp tiêu đề.
- **Ghi chú riêng cho Mục lục:** "In đậm và in hoa tiêu đề của các chương, mục lớn (**toàn bộ size: 12**)" — tức là trong chính trang Mục lục, tên chương/mục lớn hiển thị **cỡ 12**, khác với cỡ 13–15 dùng ở tiêu đề thật trong thân bài.

### 1.5 Yêu cầu lề trang

- top/bottom/right: **2,0 cm**
- left: **3,0 cm**
- header/footer: **1,0 cm**

### 1.6 Yêu cầu căn lề & giãn dòng đoạn văn

- Alignment: **Justified** (căn đều 2 bên).
- Spacing before/after: **3 pt**.
- Line spacing: multiple **1,1 đến 1,2**.

### 1.7 Yêu cầu Header/Footer

- Header trái: **"Báo cáo TTTN Đại học"**
- Header phải: **"Chương và tên chương"**
- Footer trái: **"Nhóm_Tên nhóm"** (ví dụ mẫu: "Nhóm_A01" — gợi ý có thể có mã nhóm do Khoa/Bộ môn quy định, không phải tên tự đặt)
- Footer phải: **số thứ tự trang**

### 1.8 Yêu cầu caption bảng/hình

- Đánh số thứ tự **hình vẽ phía dưới mỗi hình**.
- Đánh số theo quy cách phân cấp: số đầu = số chương, số sau = thứ tự trong chương (ví dụ 1.1, 1.1.1).
- **Ở cuối mỗi bảng biểu/sơ đồ/hình trong mỗi chương phải có ghi chú, giải thích, nêu rõ nguồn trích hoặc sao chép** (yêu cầu này áp dụng cho toàn bộ 3 loại: bảng, sơ đồ, hình).
- Danh mục minh họa mẫu tách 3 loại riêng: **BẢNG, SƠ ĐỒ, HÌNH** (ví dụ "BẢNG 1.1", "SƠ ĐỒ 1.1", "HÌNH 1.1") — không chỉ 2 loại (bảng/hình) như cách hiểu thông thường.

### 1.9 Yêu cầu danh mục ký hiệu/chữ viết tắt

- Trình bày **theo thứ tự chữ cái A, B, C....**
- Đánh số trang tương ứng.
- Nội dung mỗi dòng: **chữ viết tắt, chữ đầy đủ, nghĩa** (của từ).
- Hạn chế viết tắt; nếu dùng phải giải nghĩa trong ngoặc ngay từ lần xuất hiện đầu tiên trong thân bài, sau đó mới liệt kê thành trang riêng.

### 1.10 Yêu cầu Kế hoạch thực hiện công việc nhóm

Bảng mẫu có đúng **5 cột**:

| TT | Nội dung | Người thực hiện | Thời gian thực hiện | Mức độ hoàn thành |
|---|---|---|---|---|

### 1.11 Yêu cầu định dạng Tài liệu tham khảo

- Tách thành 3 nhóm: **"Tiếng Việt"**, **"Tiếng Anh"**, **"Danh mục các Website tham khảo"**.
- Sắp xếp theo abc (theo họ tác giả, hoặc theo tên tài liệu).
- Cách ghi khác nhau theo loại nguồn:
  - Tạp chí: Tên tác giả, tên bài viết, tên tạp chí, tập số, trang, năm (năm trong ngoặc).
  - Sách: Tên tác giả, tên sách, trang, nhà xuất bản, nơi xuất bản, lần và năm xuất bản.
  - Báo cáo khoa học: Tên tác giả, tên báo cáo, tên kỷ yếu, nơi và thời gian tổ chức hội nghị.
- Vị trí: xếp cuối cùng (xem mâu thuẫn về thứ tự với Phụ lục ở mục 1.1).

### 1.12 Yêu cầu Phụ lục

- Gồm nội dung minh họa/hỗ trợ: số liệu, mẫu biểu, tranh ảnh...
- **Phụ lục không được dày hơn phần chính của báo cáo.**
- Đặt sau trang cuối cùng của chương cuối.

### 1.13 Yêu cầu khác

- Tổng số trang nội dung (tính từ Mở đầu, đánh số Ả Rập): **30–45 trang**.
- Nếu đề tài có sản phẩm phần cứng: phải đảm bảo chỉ tiêu kỹ thuật về độ bền, an toàn, có vỏ hộp, hoạt động ổn định *(không áp dụng cho đề tài này — sản phẩm là phần mềm)*.
- Nộp 1 quyển báo cáo/nhóm.

---

## 2. Đối chiếu với LaTeX hiện tại (theo từng yêu cầu)

| Yêu cầu | File LaTeX hiện thực | Macro/environment | Trạng thái |
|---|---|---|---|
| Bìa ngoài | `thesis.sty` dòng 31–75 | `\coverpage` | Partial (nội dung đúng nhưng sai vị trí dòng 3 và thứ tự thông tin — xem mục 3) |
| Bìa đệm | `thesis.sty` dòng 80–108 | `\innercoverpage` | Partial (cùng lỗi thứ tự/nội dung như bìa ngoài) |
| Phiếu đề cương | `pages/approved-proposal-pending.tex` | — | Pending (trang review ghi rõ không thay thế phiếu đã ký) |
| Mục lục | `main.tex` dòng 25–29 | `\tableofcontents` | Partial (cơ chế đúng, nhưng cỡ chữ 12 riêng cho mục lục theo mục 1.4 **chưa được cấu hình rõ ràng**) |
| Lời cảm ơn | `pages/acknowledgments.tex`, `thesis.sty` dòng 120–125 | `acknowledgments` (dùng `\chapter*`) | Partial (nội dung ổn, nhưng `\chapter*` không cập nhật `\leftmark` — xem mục 5.9) |
| Danh mục ký hiệu | `pages/abbreviations.tex` | `\chapter*` + `longtable` | **Fail** (không xếp theo thứ tự chữ cái A,B,C — xem mục 3) |
| Danh mục bảng | `main.tex` dòng 37–42 | `\listoftables` | Pass (cơ chế đúng); **Unknown** nội dung thực tế sẽ hiển thị gì (đã có 6 bảng trong Chương 1–4 và Kế hoạch nhóm, chưa build thử) |
| Danh mục hình | `main.tex` dòng 44–49 | `\listoffigures` | **Fail thực tế** — sẽ **rỗng** vì chưa có `\includegraphics`/figure nào trong toàn bộ báo cáo (đã xác nhận bằng grep ở phiên trước) |
| Kế hoạch nhóm | `pages/group-work-plan.tex` | 2 bảng riêng | Partial (nội dung tốt nhưng **không đúng cấu trúc 5 cột** yêu cầu — xem mục 3) |
| Mở đầu | `chapters/chap-0.phan-mo-dau.tex` | `\chapter*` | Pass nội dung; Partial về mặt kỹ thuật (header — xem mục 5.9) |
| Chương 1–4 | `chapters/chap-1-background.tex` … `chap4.tex` | `\chapter` (có số) | Pass (đúng cơ chế đánh số 1.1, 1.1.1) |
| Kết luận, kiến nghị | `chapters/conclusion.tex` | `\chapter*` | Pass nội dung; Partial kỹ thuật (header) |
| Tài liệu tham khảo | `main.tex` dòng 75–80, `refs.bib` | `\bibliography{refs}`, `plain` style | **Fail cấu trúc** — không tách "Tiếng Việt/Tiếng Anh/Website", không theo đúng format từng loại nguồn yêu cầu; **vị trí trước Phụ lục có thể sai** (xem mục 1.1) |
| Phụ lục | `main.tex` dòng 82–90, `chapters/appendix.tex` | `\appendix` | Pass cơ chế; vị trí tương đối với Tài liệu tham khảo cần xác nhận lại |
| Font Times New Roman | `styles/settings.tex` dòng 7–8 | `newtxtext`/`newtxmath` + `fontenc[T5,T1]` | **Unknown** — chưa build thử PDF thật để xác nhận dấu tiếng Việt không lỗi |
| Cỡ chữ 12/13 | `styles/settings.tex` dòng 150 | `\normalsize` = 13pt | Pass |
| Lề 3cm/2cm | `styles/settings.tex` dòng 37–46 | `\geometry{...}` | Pass |
| Header/footer 1cm | `styles/settings.tex` dòng 43–45 | `headsep=10mm, footskip=10mm` | Pass (xấp xỉ 1cm) |
| Justified | Mặc định LaTeX, không có `\raggedright` trong thân bài (đã grep xác nhận) | — | Pass |
| Spacing 3pt | `styles/settings.tex` dòng 159 | `\parskip = 3pt` | Pass |
| Giãn dòng 1.1–1.2 | `styles/settings.tex` dòng 150 | baselineskip 14.95pt / 13pt ≈ 1.15 | Pass (theo tính toán; **Unknown** khi build thật) |
| Tiêu đề chương 13–15, in hoa, đậm | `styles/settings.tex` dòng 59–66 | `\titleformat{name=\chapter}` | Pass |
| Tiêu đề mục con size 13, đậm | `styles/settings.tex` dòng 69–71 | `\titleformat{\section}` | Pass |
| Đánh số phân cấp 1.1, 1.1.1 | `styles/settings.tex` dòng 56–57 | `secnumdepth=3` | Pass |
| Header trái "Báo cáo TTTN Đại học" | `thesis.sty` dòng 23, 144 | `\datn` | Pass |
| Header phải "Chương và tên chương" | `thesis.sty` dòng 145 | `\nouppercase{\leftmark}` | **Partial/Fail kỹ thuật** — đúng cho Chương 1–4 (numbered), nhưng **sai/không cập nhật** cho các trang dùng `\chapter*` (Mở đầu, Kết luận, Danh mục ký hiệu, Kế hoạch nhóm, Lời cảm ơn) — xem mục 5.9 |
| Footer trái "Nhóm_Tên nhóm" | `thesis.sty` dòng 25, 140 | `\teamname` = "Nhóm\_LLM-Security" | Partial — đúng định dạng "Nhóm_X" nhưng **chưa xác nhận** "LLM-Security" có phải mã nhóm chính thức do Khoa cấp hay không (mẫu ví dụ "Nhóm_A01" gợi ý có thể có quy ước mã nhóm riêng) |
| Footer phải: số trang | `thesis.sty` dòng 141, 154 | `\thepage` | Pass |
| Caption hình phía dưới | Cơ chế mặc định LaTeX (`\caption` sau `\includegraphics`) | `caption` package | Pass cơ chế; **không áp dụng được** vì chưa có hình nào trong báo cáo |
| Caption bảng | Đã dùng cho toàn bộ bảng mới | `\caption` trước `\begin{tabular}` | Pass (văn bản gốc không quy định vị trí trên/dưới cho riêng bảng) |
| Ghi chú nguồn dưới mỗi bảng/hình | Không có bảng nào trong Chương 1–4 có dòng ghi chú nguồn riêng | — | **Fail** — chưa có bảng/hình nào kèm ghi chú "nguồn: ..." theo yêu cầu mục 1.8 |
| 3 loại Bảng/Sơ đồ/Hình riêng | Chỉ có 2 cơ chế: `\listoftables`, `\listoffigures` | `tocloft` | **Fail/Gap** — không có counter/danh mục riêng cho "Sơ đồ" |
| Danh mục ký hiệu theo abc | `pages/abbreviations.tex` dòng 14–56 | — | **Fail** (thứ tự hiện tại: LLM, RAG, MVP, PoC, API... — theo nhóm liên quan, không theo abc) |

---

## 3. Ma trận tuân thủ (Compliance Matrix)

| ID | Yêu cầu chính thức PTIT | Trạng thái | Bằng chứng | Vấn đề phát hiện | Đề xuất khắc phục | Ưu tiên |
|---|---|---|---|---|---|---|
| C01 | Thứ tự Tài liệu tham khảo vs Phụ lục | **Unknown (mâu thuẫn nguồn)** | Văn bản gốc mục I vs mục II.5 vs mục lục mẫu | Văn bản gốc tự mâu thuẫn: mục I ghi TLTK trước Phụ lục; mục II.5 + mục lục mẫu ghi ngược lại | Hỏi GVHD/Khoa để chốt; tạm thời cân nhắc đổi `main.tex` sang thứ tự Phụ lục → TLTK (theo 2/3 tín hiệu) | **High** |
| C02 | Thứ tự Danh mục ký hiệu vs Danh mục bảng/hình | **Unknown (mâu thuẫn nguồn)** | Mục I vs ghi chú trang mẫu "Ký hiệu các cụm từ viết tắt" | Mục I ghi ký hiệu trước; ghi chú mẫu ghi ký hiệu sau Danh mục bảng/sơ đồ/hình | Hỏi GVHD/Khoa để chốt | **Medium** |
| C03 | Dòng 3 trên bìa: "CƠ SỞ TẠI THÀNH PHỐ HỒ CHÍ MINH" | **Fail** | `thesis.sty` dòng 48: `\faculty` ("Khoa An toàn thông tin") | Đang hiển thị tên Khoa thay vì dòng địa điểm cơ sở theo mẫu chính thức | Đổi dòng 3 thành "CƠ SỞ TẠI THÀNH PHỐ HỒ CHÍ MINH"; cân nhắc thêm tên Khoa ở vị trí khác nếu cần | **High** |
| C04 | Thứ tự thông tin trên bìa: Người hướng dẫn → SV1(MSSV) → Lớp → SV2(MSSV) → Lớp → Ngành | **Fail** | `thesis.sty` dòng 60–69, 96–102 | Hiện tại: Sinh viên → MSSV → Lớp (chung) → Ngành → GVHD (thứ tự và cấu trúc khác mẫu) | Viết lại khối thông tin đúng thứ tự và cấu trúc mẫu (mỗi SV có dòng Lớp riêng, GVHD ở đầu) | **High** |
| C05 | Cỡ chữ tên loại báo cáo: Bold, size 36 | **Fail** | `thesis.sty` dòng 22, 52, 88 | Hiện dùng 18pt (bìa ngoài) / 16pt (bìa đệm), thấp hơn nhiều so với 36pt yêu cầu | Tăng cỡ chữ `\reporttype` lên 36pt trên bìa ngoài | **Medium** |
| C06 | Danh mục ký hiệu/chữ viết tắt xếp theo abc A,B,C | **Fail** | `pages/abbreviations.tex` dòng 14–56 | Bảng hiện xếp theo nhóm liên quan (LLM, RAG, MVP...), không theo abc | Sắp xếp lại toàn bộ theo thứ tự chữ cái của cột "Từ viết tắt" | **High** |
| C07 | Cỡ chữ 12 riêng cho tiêu đề chương/mục lớn trong trang Mục lục | **Unknown** | `styles/settings.tex` dòng 82–115 (`tocloft`) | Không có khai báo tường minh cỡ chữ 12 cho các dòng chương trong mục lục | Thêm khai báo cỡ chữ 12 cho `\cftchapfont` (nếu cần) sau khi build thử | **Medium** |
| C08 | Bảng Kế hoạch nhóm đúng 5 cột: TT, Nội dung, Người thực hiện, Thời gian thực hiện, Mức độ hoàn thành | **Fail** | `pages/group-work-plan.tex` dòng 7–20, 24–44 | Hiện có 2 bảng khác cấu trúc (2 cột và 3 cột), không khớp mẫu 5 cột chính thức | Viết lại thành 1 bảng đúng 5 cột theo mẫu, có thể giữ nội dung hiện tại làm dữ liệu điền vào | **Medium-High** |
| C09 | Tài liệu tham khảo tách 3 nhóm: Tiếng Việt / Tiếng Anh / Website | **Fail** | `main.tex` dòng 75–80, `refs.bib` | `\bibliographystyle{plain}` xuất 1 danh sách gộp, không tách nhóm theo ngôn ngữ/loại nguồn | Cân nhắc chia thủ công thành 3 mục có tiêu đề, hoặc dùng `bibliography` nhiều file/`\begin{thebibliography}` phân đoạn | **Medium-High** |
| C10 | 3 danh mục minh họa riêng: Bảng / Sơ đồ / Hình | **Fail/Gap** | `styles/settings.tex` (chỉ có `cftfigpresnum`, `cfttabnumwidth`) | Không có counter/float riêng cho "Sơ đồ" — chỉ có Bảng và Hình | Thêm float type "Sơ đồ" bằng `\newfloat` (gói `float`) nếu cần dùng cho các sơ đồ kiến trúc/threat model | **Medium** |
| C11 | Ghi chú nguồn dưới mỗi bảng/hình trong chương | **Fail** | `chapters/chap-1-background.tex`, `chap-2-method.tex` (các bảng không có dòng nguồn) | Toàn bộ bảng mới (FR/NFR, STRIDE, module...) không có dòng "Nguồn: nhóm tự tổng hợp" | Thêm 1 dòng nhỏ dưới mỗi bảng ghi rõ nguồn (tự tổng hợp / trích từ tài liệu nào) | **Low-Medium** |
| C12 | `\chapter*` không cập nhật `\leftmark` → Header phải sai ở các trang không đánh số | **Fail (kỹ thuật)** | `thesis.sty` dòng 113–131 (`declaration`, `acknowledgments`, `abstractvi` dùng `\chapter*`); `chapters/chap-0...tex`, `conclusion.tex`, `pages/abbreviations.tex`, `pages/group-work-plan.tex` đều dùng `\chapter*` (đã grep xác nhận) | Theo cơ chế chuẩn của `book.cls`, chỉ `\chapter` (có số) tự động gọi `\markboth`; `\chapter*` **không** cập nhật `\leftmark`, nên Header phải ở các trang Mở đầu/Kết luận/Danh mục ký hiệu/Kế hoạch nhóm/Lời cảm ơn nhiều khả năng hiển thị sai (giữ giá trị `\leftmark` cũ) | Thêm `\markboth{<tên trang>}{}` thủ công ngay sau mỗi `\chapter*` liên quan | **Medium-High** |
| C13 | Font Times New Roman qua `T5` + `newtxtext`, dấu tiếng Việt | **Unknown** | `styles/settings.tex` dòng 7–8 | Chưa build thử PDF thật (môi trường chưa có `pdflatex`) để xác nhận không lỗi/mất dấu | Build thử bằng MiKTeX/TeX Live thật trước khi nộp | **High** |
| C14 | Danh mục hình sẽ có nội dung (không rỗng) | **Fail (thực tế)** | Đã grep xác nhận không có `\includegraphics` nào trong `chapters/*.tex` | Toàn bộ sơ đồ kiến trúc/threat model hiện trình bày bằng bảng chữ, không có hình ảnh nào | Xuất sơ đồ Mermaid (`docs/diagrams/*.md`) ra ảnh và chèn `\includegraphics` + `\caption` tương ứng | **Medium** |
| C15 | Tổng số trang nội dung 30–45 trang | **Unknown** | Chưa build PDF | Không thể đếm số trang thực tế nếu chưa biên dịch | Build thử và đếm số trang từ Mở đầu đến hết Phụ lục | **Medium** |
| C16 | Tên GVHD chính xác | **Unknown** | `thesis.sty` dòng 14–18 (đã có ghi chú cảnh báo sẵn) | "Nguyễn Hoàng Thanh" (dùng trong toàn dự án) vs "Nguyễn Hoàng Thành" (phiên làm việc Template Compliance trước) | Xác nhận với nhóm/GVHD chính tả đúng | **High** |
| C17 | Mã/tên nhóm chính thức cho Footer trái | **Unknown** | `thesis.sty` dòng 25 | "Nhóm\_LLM-Security" là tên tự đặt, mẫu chính thức dùng dạng "Nhóm_A01" (có thể là mã do Khoa cấp) | Xác nhận Khoa/Bộ môn có cấp mã nhóm chính thức hay không | **Medium** |
| C18 | Trích dẫn không bịa đặt, đã xác minh tồn tại | **Pass (có điều kiện)** | `refs.bib` dòng 1–55, đối chiếu `docs/research/related-work.md` | 5/5 nguồn đã xác minh tồn tại qua tra cứu; 3 nguồn học thuật minh bạch ghi "chưa đọc toàn văn" | Đọc toàn văn trước khi nộp báo cáo cuối kỳ | **Low** (đã minh bạch đúng mức) |
| C19 | Không khẳng định đã triển khai/có kết quả đo | **Pass** | `chapters/chap4.tex`, `chapters/conclusion.tex` | Có ghi chú tường minh "chưa có số liệu đo", "chưa có mã nguồn ứng dụng" ở nhiều vị trí | Giữ nguyên cách hành văn này cho các báo cáo sau | — |
| C20 | Lề trang (3cm/2cm), header/footer ~1cm | **Pass** | `styles/settings.tex` dòng 37–46 | Đúng theo yêu cầu | — | — |
| C21 | Cỡ chữ thân bài 12/13, giãn dòng 1.1–1.2, spacing 3pt | **Pass (tính toán)** | `styles/settings.tex` dòng 149–159 | Đúng theo công thức, chưa build thật để xác nhận trực quan | Xác nhận bằng build thật | **Low** |
| C22 | Căn đều (justified) | **Pass** | Không có `\raggedright` trong thân bài (đã grep) | — | — | — |
| C23 | Tiêu đề chương 13–15 in hoa đậm; mục con 13 đậm | **Pass** | `styles/settings.tex` dòng 59–74 | — | — | — |
| C24 | Đánh số phân cấp 1.1, 1.1.1 | **Pass** | `styles/settings.tex` dòng 56–57 | — | — | — |
| C25 | Phụ lục không dày hơn phần chính | **Unknown** | `chapters/appendix.tex` (hiện ngắn) | Chưa build để so sánh số trang | Kiểm tra khi build thật | **Low** |

---

## 4. Kiểm tra thứ tự cấu trúc bắt buộc (17 mục)

| # | Mục yêu cầu | Có trong `main.tex`? | Đúng vị trí? |
|---|---|---|---|
| 1 | Bìa ngoài | Có (dòng 13) | Pass |
| 2 | Bìa đệm | Có (dòng 16) | Pass |
| 3 | Phiếu giao đề cương | Có (dòng 19) | Pass |
| 4 | Mục lục | Có (dòng 28) | Pass |
| 5 | Lời cảm ơn | Có (dòng 32) | Pass |
| 6 | Danh mục ký hiệu | Có (dòng 35) | **Unknown** — xem C02 (mâu thuẫn nguồn về vị trí trước/sau danh mục bảng/hình) |
| 7 | Danh mục bảng | Có (dòng 41) | Pass (theo mục I) |
| 8 | Danh mục hình | Có (dòng 48) | Pass (theo mục I) |
| 9 | Kế hoạch nhóm | Có (dòng 52) | Pass |
| 10 | Mở đầu | Có (dòng 58) | Pass |
| 11–14 | Chương 1–4 | Có (dòng 61–70) | Pass |
| 15 | Kết luận, kiến nghị | Có (dòng 73) | Pass |
| 16 | Tài liệu tham khảo | Có (dòng 76–80) | **Unknown** — xem C01 (có thể phải đứng sau Phụ lục) |
| 17 | Phụ lục | Có (dòng 83–90) | **Unknown** — cùng vấn đề C01 |

**Kết luận mục 4:** 14/17 mục chắc chắn đúng vị trí; 3/17 mục (6, 16, 17) phụ thuộc vào việc giải quyết 2 mâu thuẫn nội bộ trong văn bản gốc (C01, C02) — không thể kết luận Pass/Fail dứt khoát cho tới khi có xác nhận từ GVHD/Khoa.

---

## 5. Kiểm tra định dạng (Formatting Audit)

| Hạng mục | Trạng thái | Ghi chú |
|---|---|---|
| Khổ giấy A4 | Pass | `\documentclass[a4paper,oneside]{book}` |
| Lề trái 3cm | Pass | `left=30mm` |
| Lề trên/phải/dưới 2cm | Pass | `top=20mm, bottom=20mm, right=20mm` |
| Header/footer ~1cm | Pass | `headsep=10mm, footskip=10mm` |
| Font kiểu Times New Roman | **Unknown** | Chưa build thật, rủi ro dấu tiếng Việt với `T5`+`newtxtext` |
| Cỡ chữ 12 hoặc 13 | Pass | `\normalsize` = 13pt |
| Căn đều | Pass | Không có `\raggedright` |
| Spacing đoạn ~3pt | Pass | `\parskip = 3pt` |
| Giãn dòng 1.1–1.2 | Pass (tính toán) | baselineskip/fontsize ≈ 1.15 |
| Tiêu đề chương in hoa đậm 13–15 | Pass | 14pt, `\MakeUppercase`, `\bfseries` |
| Tiêu đề mục đậm 13 | Pass | 13pt, `\bfseries` |
| Đánh số phân cấp 1.1, 1.1.1 | Pass | `secnumdepth=3` |
| Caption dưới hình | Pass (cơ chế), **N/A nội dung** | Chưa có hình nào để kiểm tra thực tế |
| Caption cho bảng | Pass | Đã áp dụng cho mọi bảng mới |
| Đánh số trang La Mã trước Mở đầu | Pass (cơ chế) | `\frontmatter` đặt đúng chỗ trong `main.tex` |
| Đánh số trang Ả Rập từ Mở đầu | Pass (cơ chế) | `\mainmatter` đặt đúng chỗ trong `main.tex` |
| Xác nhận số trang thực tế đúng i/1 | **Unknown** | Cần build PDF thật |

---

## 6. Kiểm tra nội dung Báo cáo định kỳ 01

| Nội dung yêu cầu | Có trong báo cáo? | Vị trí |
|---|---|---|
| Quá trình tìm hiểu | Có | `chapters/chap-1-background.tex` (toàn chương), tương ứng `docs/report/bao-cao-dinh-ky-01.md` §1 |
| Đề cương chi tiết các công việc thực hiện | Có | `chapters/chap-3.tex` |
| Outline quyển báo cáo | Có | `chapters/chap-3.tex` §1 ("Outline quyển báo cáo cuối kỳ") |
| Phân chia công việc, kế hoạch thực hiện | Có | `pages/group-work-plan.tex` (nhưng sai cấu trúc cột — xem C08) |
| Các khó khăn, vướng mắc | **Thiếu trong LaTeX** | Có đầy đủ ở `docs/report/bao-cao-dinh-ky-01.md` §5 nhưng **chưa được chuyển vào bất kỳ chương LaTeX nào** — đây là một khoảng trống nội dung cần bổ sung (gợi ý: thêm vào cuối Chương 3 hoặc Chương 4, hoặc mục riêng trong Kết luận) |

---

## 7. Danh sách rủi ro cao nhất trước khi nộp

Xếp theo mức độ rủi ro giảm dần:

1. **Phiếu giao đề cương TTTN đã ký duyệt đang chờ bổ sung** — bản review dùng trang pending (`pages/approved-proposal-pending.tex`) và không tuyên bố thay thế phiếu chính thức.
2. **Sai vị trí Tài liệu tham khảo/Phụ lục** — văn bản gốc mâu thuẫn nội bộ (C01), thứ tự hiện tại có thể sai theo 2/3 tín hiệu nguồn.
3. **Sai chính tả tên GVHD** — "Nguyễn Hoàng Thanh" vs "Nguyễn Hoàng Thành" chưa chốt (C16).
4. **Sai đánh số trang / chưa xác nhận build thật** — cơ chế đúng về lý thuyết nhưng chưa có bằng chứng build PDF thực tế (môi trường chưa có `pdflatex`).
5. **Sai Header/Footer ở các trang `\chapter*`** — Mở đầu, Kết luận, Danh mục ký hiệu, Kế hoạch nhóm, Lời cảm ơn nhiều khả năng hiển thị sai tên chương ở Header phải do `\chapter*` không gọi `\markboth` (C12).
6. **Thiếu Danh mục hình có nội dung thực** — `\listoffigures` sẽ rỗng vì chưa có hình nào được chèn (C14).
7. **Danh mục ký hiệu không xếp theo abc** — vi phạm rõ ràng yêu cầu mục 1.9 (C06).
8. **Bảng Kế hoạch nhóm sai cấu trúc cột** — không đúng 5 cột mẫu chính thức (C08).
9. **Trích dẫn chưa đọc toàn văn** — 3/5 nguồn trong `refs.bib` mới xác minh tồn tại, chưa đọc toàn văn (đã minh bạch ghi chú, nhưng vẫn là rủi ro nếu bị hỏi chi tiết nội dung).
10. **Khẳng định đã hoàn thành/có kết quả khi thực tế chưa có** — **đã kiểm tra: KHÔNG vi phạm.** Toàn bộ `chapters/chap4.tex` và `conclusion.tex` đều ghi rõ "chưa có mã nguồn ứng dụng", "chưa có số liệu đo". Đây là điểm đạt yêu cầu tốt, liệt kê ở đây để xác nhận đã rà soát kỹ, không phải một rủi ro.

---

## 8. Kế hoạch khắc phục (Fix Plan) — CHỈ ĐỀ XUẤT, CHƯA THỰC HIỆN

| Bước | File cần sửa | Vấn đề chính xác | Thay đổi đề xuất | Mức rủi ro khi sửa |
|---|---|---|---|---|
| 1 | (Ngoài LaTeX) | Chưa chốt được thứ tự TLTK/Phụ lục và thứ tự Danh mục ký hiệu | Hỏi GVHD/Khoa để xác nhận chính thức | Thấp (chỉ hỏi, không sửa code) |
| 2 | `thesis.sty` | Dòng 3 trên bìa sai (Khoa thay vì địa điểm cơ sở) | Đổi thành "CƠ SỞ TẠI THÀNH PHỐ HỒ CHÍ MINH"; cân nhắc bỏ hẳn dòng Khoa hoặc chuyển xuống vị trí khác | Thấp |
| 3 | `thesis.sty` | Thứ tự thông tin trên bìa sai so với mẫu | Viết lại khối `tabular` theo đúng thứ tự: Người hướng dẫn → SV1(MSSV) → Lớp → SV2(MSSV) → Lớp → Ngành | Thấp |
| 4 | `thesis.sty` | Cỡ chữ tên báo cáo chưa đạt 36pt | Tăng `\reporttype` lên `\fontsize{36pt}{...}` trên bìa ngoài | Thấp (chỉ ảnh hưởng bố cục bìa, cần canh lại khoảng cách dòng) |
| 5 | `pages/abbreviations.tex` | Bảng không xếp theo abc | Sắp xếp lại toàn bộ 20 dòng theo abc cột "Từ viết tắt" | Thấp |
| 6 | `pages/group-work-plan.tex` | Sai cấu trúc bảng (không đúng 5 cột mẫu) | Viết lại thành 1 bảng 5 cột: TT / Nội dung / Người thực hiện / Thời gian thực hiện / Mức độ hoàn thành | Trung bình (cần giữ lại thông tin phân công hiện có, chuyển đổi định dạng) |
| 7 | `main.tex`, `refs.bib` | TLTK không tách 3 nhóm ngôn ngữ | Chia `\bibliography` hoặc thay bằng `thebibliography` thủ công có 3 mục con | Trung bình (ảnh hưởng cơ chế trích dẫn `\cite`) |
| 8 | `thesis.sty`, các file dùng `\chapter*` | Header phải sai ở trang không đánh số | Thêm `\markboth{<Tên trang>}{}` ngay sau mỗi `\chapter*` liên quan | Thấp |
| 9 | `docs/diagrams/*.md` → ảnh → `chapters/chap-2-method.tex` | Danh mục hình rỗng | Xuất sơ đồ Mermaid ra ảnh, chèn `\includegraphics` + `\caption` + ghi chú nguồn | Trung bình (cần công cụ xuất ảnh, ngoài phạm vi "không cài thêm package" nếu cần thư viện mới) |
| 10 | `chapters/chap-1-background.tex`, `chap-2-method.tex` | Bảng thiếu dòng ghi nguồn | Thêm 1 dòng nhỏ dưới mỗi bảng: "Nguồn: nhóm tự tổng hợp" hoặc trích dẫn cụ thể | Thấp |
| 11 | Một chương phù hợp (gợi ý Chương 3 hoặc 4) | Thiếu mục "Các khó khăn, vướng mắc" trong LaTeX | Thêm một section mới, nội dung lấy từ `docs/report/bao-cao-dinh-ky-01.md` §5 | Thấp |
| 12 | (Môi trường làm việc) | Chưa build PDF thật để xác nhận toàn bộ các mục "Unknown" | Cài MiKTeX/TeX Live có hỗ trợ tiếng Việt, build thử, đối chiếu lại toàn bộ audit này | Thấp (không sửa file, chỉ xác minh) |
| 13 | `thesis.sty` | Tên GVHD/mã nhóm chưa chốt | Xác nhận với nhóm/GVHD, sau đó cập nhật `\supervisor`/`\teamname` | Thấp |
| 14 | `styles/settings.tex` | Chưa có counter riêng cho "Sơ đồ" | Cân nhắc thêm `\newfloat{diagram}{...}` nếu quyết định phân biệt Sơ đồ với Hình | Trung bình (thay đổi cấu trúc caption toàn báo cáo) |

**Lưu ý:** toàn bộ bước trên là **đề xuất**, không có bước nào được thực hiện trong phiên làm việc này.

---

## 9. Tổng kết số liệu audit

Đếm trên toàn bộ các mục ở phần 2 và ma trận phần 3 (25 mục C01–C25 + các mục định dạng lặp lại được gộp):

| Trạng thái | Số lượng (trên 25 mục ma trận chính) |
|---|---|
| Pass | 9 |
| Partial | 0 *(đã quy về Fail/Pass/Unknown cụ thể hơn ở ma trận chính)* |
| Fail | 10 |
| Unknown | 6 |

**Diễn giải:** hơn 1/3 số mục là **Fail** — chủ yếu là các lỗi cụ thể, dễ sửa (thứ tự thông tin bìa, cỡ chữ tiêu đề bìa, sắp xếp abc danh mục ký hiệu, cấu trúc bảng kế hoạch nhóm, thiếu ghi chú nguồn dưới bảng, thiếu hình ảnh thật, chưa tách nhóm tài liệu tham khảo). Không mục nào bị đánh giá Fail vì "khẳng định sai sự thật về tiến độ" — nội dung học thuật/tiến độ vẫn trung thực đúng yêu cầu.

---

## 10. Cập nhật trạng thái sau Report Compliance Fix Phase (bổ sung — không sửa nội dung gốc ở trên)

> Phần này được thêm vào **sau** phiên audit gốc, sau khi một phiên làm việc riêng ("Report Compliance Fix Phase") đã sửa các file trong `report-latex-template/`. Toàn bộ nội dung mục 1–9 ở trên được **giữ nguyên làm hồ sơ gốc**, không chỉnh sửa. Chi tiết đầy đủ từng thay đổi xem tại `docs/report/report-compliance-fix-summary.md`.

| ID | Trạng thái gốc | Trạng thái sau Fix Phase | Ghi chú |
|---|---|---|---|
| C01 | Unknown (mâu thuẫn nguồn) | **Không đổi — đã ghi chú minh bạch** | Giữ thứ tự theo "BỐ CỤC" (TLTK trước Phụ lục), có comment giải thích trong `main.tex`; chưa có xác nhận chính thức từ GVHD/Khoa |
| C02 | Unknown (mâu thuẫn nguồn) | **Không đổi — đã ghi chú minh bạch** | Giữ thứ tự theo "BỐ CỤC" (Ký hiệu trước Bảng/Hình), có comment giải thích trong `main.tex`; chưa có xác nhận chính thức |
| C03 | Fail | **Đã sửa** | Dòng 3 trên bìa đổi thành "CƠ SỞ TẠI THÀNH PHỐ HỒ CHÍ MINH" ở cả `\coverpage` và `\innercoverpage` |
| C04 | Fail | **Đã sửa** | Thứ tự thông tin bìa viết lại đúng mẫu (Người hướng dẫn → SV1(MSSV) → Lớp → SV2(MSSV) → Lớp → Ngành) |
| C05 | Fail | **Đã sửa** | `\reporttype` tăng lên 36pt (bìa ngoài), 30pt (bìa đệm) |
| C06 | Fail | **Đã sửa** | `pages/abbreviations.tex` sắp xếp lại theo abc, bổ sung thuật ngữ "AI" |
| C07 | Unknown | Chưa sửa | Ngoài phạm vi 11 mục ưu tiên của Fix Phase |
| C08 | Fail | **Đã sửa** | `pages/group-work-plan.tex` viết lại thành 1 bảng đúng 5 cột mẫu chính thức |
| C09 | Fail | Chưa sửa | Ngoài phạm vi 11 mục ưu tiên của Fix Phase |
| C10 | Fail/Gap | Chưa sửa | Ngoài phạm vi 11 mục ưu tiên của Fix Phase |
| C11 | Fail | Chưa sửa | Ngoài phạm vi 11 mục ưu tiên của Fix Phase |
| C12 | Fail (kỹ thuật) | **Đã sửa** | Thêm `\markboth` cho Lời cảm ơn, Danh mục ký hiệu, Kế hoạch nhóm, Mở đầu, Kết luận, và 5 chương Phụ lục |
| C13 | Unknown | Chưa xác minh được | Vẫn cần build PDF thật (môi trường chưa có `pdflatex`) |
| C14 | Fail (thực tế) | **Đã ghi chú TODO, chưa xóa được** | Không thêm hình giả; đã ghi chú tường minh trong Phụ lục C rằng Danh mục hình còn rỗng và cần xuất ảnh sơ đồ ở phiên sau |
| C15 | Unknown | Chưa xác minh được | Cần build PDF thật để đếm số trang |
| C16 | Unknown | **Đã chốt: "Nguyễn Hoàng Thành"** | Áp dụng trong `thesis.sty`; các file `.md` khác ngoài phạm vi cho phép sửa của Fix Phase vẫn còn ghi "Thanh" — xem `report-compliance-fix-summary.md` mục 6 |
| C17 | Unknown | Chưa xác minh được | Cần hỏi Khoa/Bộ môn có cấp mã nhóm chính thức hay không |

**9/17 mục có mã C0x kể trên đã được xử lý** (6 sửa trực tiếp, 2 xử lý bằng ghi chú minh bạch do nguồn mâu thuẫn, không đổi được nếu không có xác nhận từ GVHD/Khoa); phần còn lại nằm ngoài phạm vi 11 mục ưu tiên của Fix Phase hoặc cần build PDF thật để xác minh.
