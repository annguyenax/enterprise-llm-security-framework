# Template Compliance Checklist — Báo cáo định kỳ TTTN

> Đối tượng: `report-latex-template/`. Đối chiếu với yêu cầu hình thức chính thức của PTIT.

## 0. Về nguồn tham chiếu chính thức

**Không tìm thấy file `Phu luc_Hinh thuc va quy cach trinh bay quyen TTTN QD 922-210313.doc`** ở bất kỳ đâu trong kho mã nguồn hoặc máy làm việc hiện tại (đã tìm kiếm theo tên file, theo mã số quyết định "922", và trong lịch sử git — không có kết quả). Do đó, checklist này được xây dựng dựa trên:

1. Bản tóm tắt hiện có tại `docs/report/latex-format-notes.md`.
2. Các yêu cầu định dạng chi tiết được cung cấp trực tiếp trong chỉ thị của phiên làm việc này (margin, header/footer, đánh số trang, cấu trúc 17 mục bắt buộc...), được xem là đã được trích xuất/tóm tắt từ văn bản gốc.

**Rủi ro:** vì không có file gốc để đối chiếu trực tiếp, không thể loại trừ hoàn toàn khả năng sai lệch tiểu tiết so với văn bản chính thức (ví dụ: cỡ chữ bìa, thứ tự chính xác một vài mục phụ, mẫu bìa đệm chuẩn của Khoa). **Khuyến nghị mạnh:** nhóm cần lấy file `.doc` gốc, đặt vào `docs/report/raw/` (tương tự cách đã làm với nghiên cứu Gemini ở Phase 1), rồi yêu cầu rà soát lại checklist này trong một phiên làm việc riêng.

## 1. Cấu trúc bắt buộc (17 mục)

| # | Yêu cầu chính thức | Template trước khi chỉnh | Hành động đã thực hiện | Cần rà soát thủ công |
|---|---|---|---|---|
| 1 | Bìa ngoài | Có `\coverpage`, nhưng nội dung là đề tài mẫu (hệ thống điểm rèn luyện) | Cập nhật toàn bộ biến (`\titlethesis`, `\studentname`...) và `\reporttype` thành "BÁO CÁO ĐỊNH KỲ THỰC TẬP TỐT NGHIỆP ĐẠI HỌC" trong `thesis.sty` | Đối chiếu cỡ chữ/khung trang bìa với mẫu chính thức của Khoa (chưa có file gốc để so) |
| 2 | Bìa đệm | **Không có** — chỉ có 1 loại trang bìa | Thêm macro `\innercoverpage` mới trong `thesis.sty` (không khung trang trí, nội dung tương tự bìa ngoài) | Xác nhận bìa đệm PTIT có yêu cầu khác biệt cụ thể nào (màu giấy, không logo...) không |
| 3 | Phiếu giao đề cương TTTN được phê duyệt | Chờ bản đã ký | Dùng `pages/approved-proposal-pending.tex` trong bản review và ghi rõ trang này không thay thế phiếu đã ký | Thay bằng bản scan/PDF phiếu đã ký khi có |
| 4 | Mục lục | Có (`\tableofcontents`) | Giữ nguyên cơ chế, đổi spacing 1.3 → 1.15 | — |
| 5 | Lời cảm ơn | Có, nội dung đề tài mẫu, giọng số ít "em" | Viết lại nội dung cho đề tài này, giọng "chúng em" nhất quán | Đọc lại văn phong trước khi nộp |
| 6 | Danh mục ký hiệu và chữ viết tắt | Có, bảng thuật ngữ Deep Learning không liên quan (CNN, GRU...) | Thay bằng bảng 20 thuật ngữ của đề tài (LLM, RAG, ASR, STRIDE, OWASP...) | Bổ sung thêm nếu chương sau phát sinh thuật ngữ mới |
| 7 | Danh mục bảng | Có (`\listoftables`) nhưng **đặt sau** Danh mục hình trong bản gốc | Đổi thứ tự: Danh mục bảng (mục 7) đặt **trước** Danh mục hình (mục 8) trong `main.tex` | — |
| 8 | Danh mục hình | Có (`\listoffigures`) | Giữ cơ chế, chỉ đổi vị trí như trên | Danh mục hình hiện sẽ **rỗng** vì chưa có hình nào được chèn (xem mục 7 bên dưới) |
| 9 | Kế hoạch thực hiện công việc nhóm | Không có | Tạo `pages/group-work-plan.tex` mới, nội dung từ `bao-cao-dinh-ky-01.md` §4 và `TASK_BOARD.md` | — |
| 10 | Mở đầu | Có, nội dung đề tài mẫu | Viết lại hoàn toàn cho đề tài LLM security | — |
| 11 | Chương 1: Tổng quan và quá trình tìm hiểu | File `chap-1-background.tex` tồn tại, nội dung không liên quan | Viết lại hoàn toàn: LLM/RAG, 5 dạng tấn công, OWASP mapping, LLMSVS, related work, tool comparison | Bổ sung sau khi đọc toàn văn 3 bài báo (xem Phụ lục B trong `chapters/appendix.tex`) |
| 12 | Chương 2: Phân tích yêu cầu, kiến trúc và threat model | File `chap-2-method.tex` tồn tại (nội dung gốc: giới thiệu IDE), không liên quan | Viết lại hoàn toàn: FR/NFR, kiến trúc, module table, MVP vs future scope, STRIDE, rủi ro | Chèn hình sơ đồ Mermaid thật (hiện đang mô tả bằng bảng/văn bản) |
| 13 | Chương 3: Đề cương chi tiết công việc thực hiện | File `chap-3.tex` tồn tại (nội dung gốc: khảo sát hệ thống điểm rèn luyện), không liên quan | Viết lại hoàn toàn: outline báo cáo cuối kỳ, bảng phase, thiết kế bộ dữ liệu red-team, taxonomy hành vi guard | — |
| 14 | Chương 4: Kế hoạch kiểm thử, đánh giá và hướng triển khai | File `chap4.tex` tồn tại (nội dung gốc: phân tích thiết kế hệ thống điểm rèn luyện), không liên quan | Viết lại hoàn toàn: phương pháp baseline-vs-guarded, 6 metric kèm công thức, ràng buộc, hướng triển khai | — |
| 15 | Kết luận, kiến nghị | File `conclusion.tex` tồn tại nhưng **rỗng nội dung** (chỉ có tiêu đề) | Viết nội dung đầy đủ: tổng kết, hạn chế, kiến nghị | — |
| 16 | Tài liệu tham khảo | Có cơ chế (`\bibliography{refs}`), nhưng `refs.bib` chứa 2 entry không liên quan (Deep Learning) | Thay `refs.bib` bằng 5 nguồn đã xác minh (OWASP LLM Top10, OWASP LLMSVS, PoisonedRAG, PIDP-Attack, MDPI review) | Bổ sung thêm khi đọc toàn văn/tìm thêm nguồn ở Phase 1 tiếp theo |
| 17 | Phụ lục (nếu có) | **Không có cơ chế `\appendix` nào cả** | Thêm `\appendix` + `chapters/appendix.tex` (4 phụ lục: quy ước ID, danh sách nguồn chưa đọc toàn văn, ghi chú môi trường build, 2 mục "chưa có" cho cấu hình/kết quả) + sửa tiền tố tiêu đề chương appendix thành "Phụ lục X" thay vì "Chương X" | — |

**Ghi chú:** "Lời cam đoan" (`pages/declaration.tex`) **không** nằm trong 17 mục bắt buộc của báo cáo định kỳ nên **không** được `\input` trong `main.tex` lần này — file vẫn được cập nhật nội dung để dùng lại cho quyển Đồ án tốt nghiệp đầy đủ sau này.

## 2. Định dạng trang & font

| Yêu cầu chính thức | Template trước khi chỉnh | Hành động | Cần rà soát thủ công |
|---|---|---|---|
| A4 | `\documentclass[a4paper,oneside]{book}` | Không đổi — đã đúng | — |
| Font kiểu Times, cỡ 12–13 | `newtxtext`/`newtxmath` (giả lập Times) + custom `\normalsize` 13pt | Không đổi họ font; chỉnh baselineskip (xem dòng "Giãn dòng" bên dưới) | **Rủi ro cao nhất:** `fontenc[T5,T1]` + `newtxtext` dưới pdflatex có thể gãy dấu tiếng Việt — cần build thử thật để xác nhận (xem mục 5) |
| Lề trái 3cm | `left=30mm` | Không đổi — đã đúng | — |
| Lề phải/trên/dưới 2cm | `right=20mm, top=20mm, bottom=20mm` | Không đổi — đã đúng | — |
| Header/footer ~1cm | Không khai báo `headsep`/`footskip` tường minh | Thêm `headsep=10mm, footskip=10mm, headheight=18pt` vào `\geometry{...}` trong `settings.tex` | — |
| Căn đều (justified) | Mặc định LaTeX, không có `\raggedright` trong thân bài | Không đổi — đã đúng | — |
| Khoảng cách đoạn trước/sau ~3pt | `\parskip = 6pt` | Đổi thành `\setlength{\parskip}{3pt}` trong `settings.tex` | — |
| Giãn dòng 1.1–1.2 (dùng ~1.15) | `\normalsize` hard-code baselineskip 17.55pt (≈13×1.35, tương đương giãn dòng ~1.35, **không đạt yêu cầu**) | Đổi baselineskip thành 14.95pt (≈13×1.15) trong `settings.tex`; không cộng thêm `\setstretch` để tránh nhân đôi hệ số | Kiểm tra trực quan bằng bản build thật, so khớp cảm giác "1.15" trên trang in |
| Tiêu đề chương: in hoa, đậm, cỡ 13–15 | `\titleformat{name=\chapter}` cỡ 14pt, đậm, `\MakeUppercase` | Không đổi — đã đúng (14pt nằm trong khoảng 13–15) | — |
| Tiêu đề mục: đậm, cỡ ~13 | `\titleformat{\section}` cỡ 13pt, đậm | Không đổi — đã đúng | — |
| Hình có caption bên dưới | Cơ chế `\caption` mặc định LaTeX (dưới hình) | Không đổi cơ chế | Chưa có hình thật nào được chèn ở lần cập nhật này (xem mục 3) |
| Bảng có caption | Cơ chế `\caption` mặc định LaTex (trên bảng theo quy ước) | Đã dùng cho toàn bộ bảng mới trong Chương 1–4 và Kế hoạch nhóm | — |
| Đánh số phân cấp 1.1, 1.1.1 | `secnumdepth=3`, `tocdepth=3` | Không đổi — đã đúng | — |

## 3. Đánh số trang

| Yêu cầu | Cơ chế trước | Hành động | Cần rà soát thủ công |
|---|---|---|---|
| Từ Mục lục → Kế hoạch nhóm: La Mã (i, ii...) | `\frontmatter` gọi **bên trong** `pages/declaration.tex` (file không còn được `\input`) | Chuyển lệnh `\frontmatter` sang `main.tex`, đặt ngay sau Phiếu giao đề cương, trước Mục lục | Build thử để xác nhận số trang La Mã hiển thị đúng từ trang Mục lục |
| Từ Mở đầu → Phụ lục: Ả Rập (1, 2, 3...) | `\mainmatter` đã có trong `main.tex`, đúng vị trí (trước Mở đầu) | Không đổi vị trí, chỉ xác nhận lại thứ tự tổng thể | Build thử để xác nhận số trang Ả Rập bắt đầu đúng từ trang Mở đầu = trang 1 |
| Bìa ngoài/bìa đệm/phiếu đề cương: không đánh số | `\thispagestyle{empty}` đã có sẵn ở `\coverpage` | Áp dụng `\thispagestyle{empty}` tương tự cho `\innercoverpage` và trang phiếu đề cương | — |

## 4. Header/Footer

| Yêu cầu | Trước | Hành động | Cần rà soát thủ công |
|---|---|---|---|
| Header trái: "Báo cáo TTTN Đại học" | `\datn` = "ĐỒ ÁN TỐT NGHIỆP" | Đổi `\datn` thành "Báo cáo TTTN Đại học" | — |
| Header phải: tên chương hiện tại | `\nouppercase{\leftmark}` đã có | Giữ nguyên cơ chế | — |
| Footer trái: "Nhóm_LLM-Security" | **Lỗi cú pháp**: `\fancyfoot[L]{... & \studentname \\ & \studentnametwo \\}` — dấu `&` và `\\` đặt ngoài môi trường bảng, khả năng cao gây lỗi biên dịch ("Misplaced alignment tab character &") | Sửa thành `\fancyfoot[L]{... \teamname}` với `\teamname` = `Nhóm\_LLM-Security` (escape dấu gạch dưới) | — |
| Footer phải: số trang | `\thepage` đã có | Giữ nguyên | — |

## 5. Dọn dẹp template (template cleanup)

| Hạng mục | Trạng thái trước | Hành động | Cần rà soát thủ công |
|---|---|---|---|
| Nội dung đề tài mẫu cũ (hệ thống điểm rèn luyện, microservices) | Có ở toàn bộ `chapters/*.tex`, `pages/declaration.tex`, `pages/acknowledgments.tex`, `pages/abbreviations.tex` | Đã thay thế toàn bộ bằng nội dung đề tài LLM security | — |
| `\cite{latex2e}` trơ trọi trong `main.tex` | Có ở dòng giữa các `\input` chương và mục tài liệu tham khảo | Đã loại bỏ khi viết lại `main.tex` | — |
| `refs.bib` | 2 entry không liên quan (Deep Learning, khóa `latex2e` gán sai cho bài LeCun 1998) | Thay bằng 5 entry đã xác minh trong `docs/research/` | — |
| Logo PTIT | `assets/Logo_PTIT_University.png`, được dùng ở `\coverpage` | **Giữ nguyên, không xóa** | — |
| `Mau-De-An-Tot-Nghiep-PTIT-2409/` (bản gốc) | Thư mục tham chiếu gốc | **Không đụng tới** theo đúng yêu cầu | — |
| Ảnh không liên quan (`figure/*.png` cũ, `assets/cnn.jpeg`, `image.png` ở gốc) | Không được `.tex` nào tham chiếu (đã xác nhận bằng `grep` ở phiên trước) | **Giữ nguyên, không xóa** theo đúng yêu cầu ("prefer leaving unused assets alone") | Xóa thủ công sau nếu nhóm xác nhận chắc chắn không cần |
| `\usepackage{algorithm}` bị nạp 2 lần | Có ở `settings.tex` dòng 12 và dòng cũ 119 | Bỏ dòng nạp trùng | — |

## 6. Nội dung — quy tắc hành văn

| Quy tắc | Áp dụng |
|---|---|
| Giọng "chúng em"/"nhóm em", không dùng "em" số ít | Áp dụng trong `declaration.tex`, `acknowledgments.tex`, toàn bộ chương mới |
| "đã tìm hiểu", "đã khảo sát", "đã thiết kế", "dự kiến triển khai" | Dùng nhất quán trong Chương 1–4, Mở đầu, Kết luận |
| Không khẳng định hệ thống đã được triển khai | Có ghi chú tường minh ở đầu Chương 4 và trong Kết luận |
| Không đưa số liệu ASR/FPR/độ trễ như đã đo | Chương 4 chỉ trình bày công thức/định nghĩa, ghi rõ "chưa có số liệu đo" |
| Không tuyên bố "production-ready" | Không xuất hiện ở bất kỳ đâu trong nội dung mới |
| Tách bạch nghiên cứu/thiết kế đã hoàn thành và phần chưa triển khai | Có mục riêng "Lưu ý quan trọng" cuối Chương 4 + phần "Hạn chế" trong Kết luận |
| Không bịa trích dẫn/kết quả đo | `refs.bib` chỉ chứa nguồn đã xác minh; có ghi chú "chưa đọc toàn văn" cho 3 nguồn học thuật |
| Dữ liệu ví dụ chỉ mang tính tổng hợp | Không có ví dụ dữ liệu nào được chèn trực tiếp vào LaTeX lần này (chỉ mô tả tóm tắt, tham chiếu `docs/evaluation/red-team-test-design.md`) |
| Không có PII/secret/dữ liệu tổ chức thật | Không áp dụng trực tiếp (không có ví dụ dữ liệu nhạy cảm nào trong nội dung LaTeX) |

## 7. Rủi ro biên dịch còn tồn tại

1. **Font tiếng Việt (T5 + newtxtext):** chưa build thử bằng TeX thật trong phiên làm việc này (môi trường chưa cài `pdflatex`) — đây là rủi ro cao nhất, cần xác nhận sớm.
2. **`\definecolor` trước `\usepackage{xcolor}` tường minh:** vẫn hoạt động nhờ `tikz` nạp `xcolor` ngầm trước đó, nhưng là phụ thuộc ẩn — không sửa lần này vì không gây lỗi thực tế, chỉ ghi nhận rủi ro tiềm ẩn nếu sau này ai đó bỏ `tikz`.
3. **`\listoffigures` sẽ hiển thị rỗng:** chưa có hình ảnh nào được chèn trong đợt cập nhật này (sơ đồ kiến trúc/threat model hiện trình bày dưới dạng bảng/văn bản thay vì hình Mermaid xuất ra ảnh) — cần một bước riêng để xuất hình từ `docs/diagrams/*.md` và chèn vào báo cáo.
4. **Phiếu giao đề cương là trang placeholder**, chưa phải phiếu đã ký thật.

## 8. Cách biên dịch (chưa xác minh được trong môi trường hiện tại)

```
cd report-latex-template
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

Cần cài MiKTeX hoặc TeX Live có hỗ trợ tiếng Việt (gói `vntex`/`T5` fontenc) trước khi chạy. Nếu `pdflatex` báo lỗi liên quan tới `T5` hoặc dấu tiếng Việt, cân nhắc chuyển sang `xelatex` + `fontspec` (yêu cầu sửa lại phần khai báo font trong `settings.tex`, chưa thực hiện ở đợt này).

## 9. Tổng kết mức độ hoàn thành

- **17/17 mục cấu trúc bắt buộc:** đã có cơ chế và nội dung (một số ở dạng placeholder có ghi chú rõ ràng).
- **Định dạng trang/font/margin:** đã khớp theo yêu cầu được cung cấp, **chưa xác minh bằng bản build PDF thật**.
- **Đánh số trang La Mã/Ả Rập:** đã cấu trúc đúng cơ chế `\frontmatter`/`\mainmatter`, **chưa xác minh bằng bản build PDF thật**.
- **Nội dung:** đã viết lại toàn bộ theo đúng đề tài, tuân thủ quy tắc hành văn (chưa khẳng định đã triển khai, chưa đưa số liệu).
- **Việc còn thiếu lớn nhất:** (1) chưa build thử PDF thật để xác nhận không lỗi và hiển thị đúng dấu tiếng Việt; (2) chưa có hình ảnh sơ đồ nào được chèn; (3) chưa có file `.doc` gốc để đối chiếu 100%.

## 10. Cập nhật (bổ sung sau — không sửa nội dung mục 1–9 ở trên)

- **File `.doc` gốc đã được tìm thấy và đọc được** ở một phiên làm việc sau (`Phu luc_Hinh thuc va quy cach trinh bay quyen TTTN QD 922-210313.doc`, nằm ở thư mục gốc dự án, đọc bằng `antiword`). Toàn bộ phần "mục 0" ở trên (về việc không tìm thấy file gốc) chỉ còn đúng ở thời điểm checklist này được viết ra — xem `docs/report/report-compliance-audit.md` để có kết quả đối chiếu đầy đủ với văn bản gốc thật, và `docs/report/report-compliance-fix-summary.md` để biết các lỗi đã được sửa.
- **Tên GVHD đã được chốt là "Nguyễn Hoàng Thành"** (áp dụng trong `report-latex-template/thesis.sty`), thay cho "Nguyễn Hoàng Thanh" dùng tạm trước đó trong checklist này. Các file `.md` khác ngoài `report-latex-template/` vẫn còn ghi "Thanh" — xem `report-compliance-fix-summary.md` mục 6 để biết phạm vi chưa đồng bộ.
- Nhiều mục "cần rà soát thủ công" ở mục 1–8 phía trên nay đã có audit chi tiết hơn và một phần đã được sửa — tài liệu này (`template-compliance-checklist.md`) được giữ nguyên làm hồ sơ của phiên làm việc gốc, không cập nhật lại từng dòng.

## 11. Cập nhật lần 2 — Final Strict Compliance Review

Một đợt rà soát cuối cùng, chặt chẽ hơn, đã hoàn tất — xem `docs/report/final-strict-compliance-review.md` để có bảng đối chiếu đầy đủ (34 mục). Các thay đổi metadata đáng chú ý so với checklist này: `\faculty` đổi thành "Khoa Công nghệ thông tin 2"; tên nhóm chuẩn hóa thành "Nhóm A06" / "Nhóm\_A06"; tên đề tài trên bìa đổi thành "Nghiên cứu và triển khai cơ chế Guardrails bảo vệ hệ thống RAG trước tấn công Prompt Injection và rò rỉ dữ liệu" (khác với tên dùng ở các file `.md` khác của dự án — cần xác nhận). Tiêu đề trang Mục lục/Danh mục bảng/Danh mục hình nay được ép in hoa tường minh qua `\MakeUppercase` thay vì phụ thuộc vào chuỗi mặc định của babel.

## 12. Cập nhật lần 3 — Report Title Lock

Tên đề tài "Nghiên cứu và triển khai cơ chế Guardrails bảo vệ hệ thống RAG trước tấn công Prompt Injection và rò rỉ dữ liệu" đã được **xác nhận là tên đề tài đăng ký chính thức** (không còn là điểm "cần xác nhận" như ghi ở mục 11). `\titlethesis` trong `thesis.sty` đã khớp chính xác; đã rà soát toàn bộ `report-latex-template/` và xác nhận không còn tên đề tài cũ/xung đột nào sót lại. README.md/PROJECT_PLAN.md/`docs/` khác của dự án vẫn dùng tên cũ ("Xây dựng Hệ thống Bảo mật LLM...") — nằm ngoài phạm vi cho phép sửa, nên đây vẫn là một điểm không đồng bộ ở cấp toàn dự án, chỉ khác là nay đã được xác nhận có chủ đích thay vì còn bỏ ngỏ.
