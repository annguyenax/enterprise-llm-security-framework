# Tóm tắt kết quả phục vụ báo cáo thực tập

> **Phạm vi diễn giải:** Toàn bộ kết quả định lượng dưới đây chỉ áp dụng cho bộ
> benchmark tổng hợp có kiểm soát của dự án. Hệ thống là proof-of-concept dựa
> trên rule, không phải sản phẩm sẵn sàng triển khai; LLM thực, vector database,
> embedding và pipeline retrieval hoàn chỉnh nằm ngoài phạm vi. Kết quả 40/40
> không được diễn giải thành tỷ lệ phát hiện trong môi trường thực tế.

## Mục tiêu hệ thống

Đề tài xây dựng một mô hình thử nghiệm quy mô phòng lab cho cổng bảo mật ứng
dụng mô hình ngôn ngữ lớn. Mục tiêu của hệ thống là kiểm tra dữ liệu đầu vào,
ngữ cảnh được cung cấp cho quy trình RAG và dữ liệu đầu ra nhằm minh họa cơ chế
phòng vệ nhiều lớp trước một số dạng prompt injection, jailbreak, trích xuất
thông tin nhạy cảm và đầu độc tài liệu. Hệ thống phục vụ nghiên cứu và thực
nghiệm trong phạm vi thực tập, không phải sản phẩm bảo mật sẵn sàng triển khai.

## Phạm vi đã triển khai

Hệ thống đã triển khai API bằng FastAPI, Input Guard, RAG Context Guard, Output
Guard, bộ điều phối gateway, ghi nhật ký JSONL có che giấu chuỗi nhạy cảm, bộ
nạp tài liệu tổng hợp, giao diện nhà cung cấp LLM và nhà cung cấp giả lập cục
bộ. Ngoài ra, đề tài có bộ chạy đánh giá ngoại tuyến, phân tích lỗi, hiệu chỉnh
rule và báo cáo so sánh giữa chế độ không guard với chế độ có guard.

Phạm vi hiện tại không bao gồm LLM thực, API trả phí, vector database,
embedding, truy hồi tương đồng hay một pipeline RAG hoàn chỉnh. Các context
chunk trong demo được truyền trực tiếp bởi phía gọi API.

## Kiến trúc tổng quát

Luồng xử lý đã triển khai có thứ tự: Input Guard, RAG Context Guard tùy chọn,
Mock LLM Provider, Output Guard và Audit Logger. Quyết định bảo mật sử dụng năm
trạng thái `allow`, `log_only`, `sanitize`, `human_review` và `block`, với thứ
tự ưu tiên từ `block` đến `allow`. Khi Input Guard hoặc RAG Guard trả về
`block`/`human_review`, pipeline dừng trước bước provider. Khi có quyết định
`sanitize`, dữ liệu đã làm sạch được chuyển sang bước tiếp theo.

## Dữ liệu thử nghiệm

Bộ dữ liệu được xây dựng hoàn toàn bằng dữ liệu tổng hợp, gồm 5 tài liệu sạch,
5 tài liệu bị đầu độc và 40 prompt red-team thuộc 8 nhóm. Báo cáo kiểm tra dữ
liệu xác nhận cấu trúc JSONL hợp lệ, ID không trùng lặp và không phát hiện PII
hoặc khóa bí mật thực theo các mẫu đã kiểm tra. Tuy nhiên, việc kiểm tra tự động
không thay thế đánh giá thủ công đầy đủ; chất lượng và độ đại diện của corpus
vẫn là một giới hạn của nghiên cứu.

## Phương pháp đánh giá

Bộ chạy đánh giá đọc 40 prompt cố định, kiểm tra schema, chạy trực tiếp guard
được chỉ định và so sánh quyết định thực tế với nhãn mong đợi. Các chỉ số gồm
tỷ lệ khớp quyết định, số lượng false positive, false negative, phân bố quyết
định và attack-success proxy dựa trên quyết định. Phương pháp này có tính tái
lập và không gọi LLM hoặc dịch vụ mạng.

## Kết quả chính

Lần chạy đầu tiên ghi nhận 35/40 trường hợp khớp nhãn, với 5 false negative và
0 false positive. Quá trình Phase 7.1 phân tích nguyên nhân của từng lỗi và bổ
sung năm rule hẹp kèm biến thể lân cận và trường hợp lành tính đối chứng. Sau
hiệu chỉnh, cùng bộ 40 prompt không thay đổi đạt 40/40 quyết định khớp nhãn, 0
false positive và 0 false negative. Bộ kiểm thử cục bộ hiện ghi nhận 82 test
pass; có một cảnh báo deprecation từ Starlette nhưng không làm thất bại test.

Các con số trên chỉ phản ánh độ khớp nhãn trên benchmark tổng hợp có kiểm soát.
Chúng không phải tỷ lệ phát hiện trong môi trường thực tế, không chứng minh khả
năng tổng quát hóa và không tạo ra bảo đảm an toàn cho hệ thống sản xuất.

## So sánh baseline

Baseline được định nghĩa là hệ thống không có guard và luôn trả về quyết định
`allow`. Trên cùng benchmark, baseline khớp 5/40 trường hợp, có 35 false
negative và attack-success proxy bằng 1,0000. Chế độ guarded khớp 40/40, có 0
false negative và proxy bằng 0,0000. So sánh này minh họa tác động của tầng
quyết định guard trên bộ nhãn cố định; baseline không sinh câu trả lời bằng LLM
và do đó không phải baseline đánh giá chất lượng mô hình ngôn ngữ.

## Hạn chế

Các guard dựa trên biểu thức chính quy và từ khóa nên có thể bỏ sót biến thể ngữ
nghĩa, mã hóa, hội thoại nhiều lượt hoặc kỹ thuật ngoài corpus hiện tại. Bộ dữ
liệu nhỏ và tổng hợp nên không đại diện cho phân bố tấn công thực tế. Phạm vi
đánh giá không đo chất lượng câu trả lời của LLM, chất lượng retrieval, độ trễ
trong pipeline thực hoặc tác động bảo mật trên dữ liệu doanh nghiệp. Kết quả
40/40 có thể chịu ảnh hưởng của quá trình hiệu chỉnh theo benchmark hiện hữu.

## Hướng phát triển

Các hướng tiếp theo gồm hoàn thiện đánh giá thủ công corpus, mở rộng tập kiểm
thử độc lập không dùng để hiệu chỉnh, nghiên cứu bộ phân loại ngữ nghĩa, tích hợp
provider thực với quản lý khóa và phê duyệt chi phí, thử nghiệm embedding/vector
store, đánh giá retrieval, đo độ trễ và thực hiện kiểm thử trên dữ liệu tổng hợp
đa dạng hơn. Mọi tích hợp dịch vụ bên ngoài cần tuân thủ nguyên tắc không sử
dụng dữ liệu thật và không gọi API trả phí khi chưa được phê duyệt.
