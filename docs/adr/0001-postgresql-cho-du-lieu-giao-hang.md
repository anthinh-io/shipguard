# ADR-0001: Dùng PostgreSQL làm nơi lưu dữ liệu giao hàng

**Trạng thái:** Đã chấp nhận
**Ngày:** 2026-09-10
**Người quyết định:** Chủ dự án

## Bối cảnh

Bộ dữ liệu Olist gồm khoảng 100 nghìn đơn hàng, đóng băng, không thay đổi. Tính năng đầu tiên được xây — Giám sát hiệu suất — **chỉ đọc**: nó tổng hợp KPI từ dữ liệu lịch sử và không ghi gì trở lại. Xét riêng tính năng này, gần như mọi cách lưu trữ đều đủ nhanh.

Ba lực đang tác động:

- **Quy mô nhỏ.** 100 nghìn dòng nằm gọn trong bộ nhớ của bất kỳ máy nào. Không có sức ép về hiệu năng.
- **Hai quy trình kế tiếp đều cần ghi.** Cùng tài liệu nghiệp vụ mô tả Quản lý đơn hàng lưu ghi chú nội bộ vào đơn (A2.7), và Dự đoán rủi ro lưu nhãn dự đoán kèm trạng thái đã xử lý gắn với từng đơn (A3.6, A3.9). Đây là yêu cầu đã biết, không phải phỏng đoán.
- **Chỉ số ba chặng cần tính phân vị.** Trung vị và phân vị 90 cho ba chặng thời gian, tính lại theo từng tổ hợp bộ lọc.

Đồng thời có một ràng buộc từ `CLAUDE.md`: không dựng thứ chưa ai yêu cầu. Cần cân nhắc thật giữa việc dựng sẵn hạ tầng và việc chỉ làm vừa đủ.

## Quyết định

Dùng PostgreSQL, chạy qua Docker Compose, lược đồ quản lý bằng Alembic. Dữ liệu thô nạp vào bảng thô, rồi dựng một bảng dẫn xuất một dòng mỗi đơn phục vụ truy vấn KPI.

## Các phương án đã cân nhắc

### Phương án A: pandas trong bộ nhớ

| Chiều đánh giá | Nhận định |
| --- | --- |
| Độ phức tạp | Thấp — không có dịch vụ ngoài, không lược đồ, không migration |
| Chi phí vận hành | Thấp nhất |
| Đáp ứng nhu cầu ghi | Không đáp ứng |
| Khả năng mở rộng | Đủ cho quy mô hiện tại |
| Độ quen thuộc | Cao — đã có trong danh sách công nghệ của dự án |

**Ưu:** ít mã nhất, khởi động nhanh nhất, không phải cài đặt gì thêm để chạy dự án.
**Nhược:** không lưu được dữ liệu ghi. Tới Quy trình 2 và 3 phải làm lại toàn bộ tầng dữ liệu, kéo theo viết lại cả tầng truy vấn KPI. Tính phân vị theo nhiều tổ hợp bộ lọc phải tự viết tay.

### Phương án B: SQLite

| Chiều đánh giá | Nhận định |
| --- | --- |
| Độ phức tạp | Thấp — một tệp, không dịch vụ ngoài |
| Chi phí vận hành | Thấp |
| Đáp ứng nhu cầu ghi | Có |
| Khả năng mở rộng | Đủ, nhưng ghi đồng thời bị hạn chế |
| Độ quen thuộc | Cao |

**Ưu:** đáp ứng được nhu cầu ghi mà không phải cài dịch vụ nào. Chạy được ngay trên máy trống.
**Nhược:** không có hàm tính phân vị sẵn, phải tự xoay. Môi trường phát triển khác môi trường triển khai, nên lỗi chỉ lộ ra khi triển khai. Chuyển sang PostgreSQL sau này vẫn là một lần đổi lược đồ và đổi câu truy vấn.

### Phương án C: PostgreSQL

| Chiều đánh giá | Nhận định |
| --- | --- |
| Độ phức tạp | Trung bình — thêm Docker Compose và Alembic |
| Chi phí vận hành | Trung bình — một container phải chạy khi phát triển |
| Đáp ứng nhu cầu ghi | Có |
| Khả năng mở rộng | Dư sức, kể cả khi dữ liệu tăng nhiều lần |
| Độ quen thuộc | Cao |

**Ưu:** đáp ứng nhu cầu ghi; có sẵn `percentile_cont` cho chỉ số ba chặng; môi trường phát triển giống môi trường triển khai; một tầng dữ liệu duy nhất dùng chung cho cả ba quy trình.
**Nhược:** phải cài Docker mới chạy được dự án. Thêm Alembic và một lược đồ phải bảo trì. Với riêng tính năng đầu tiên thì đây là thứ dựng dư.

## Phân tích đánh đổi

Đánh đổi thật nằm giữa **làm vừa đủ cho hôm nay** và **tránh phải làm lại đã biết trước**.

Phương án A rẻ nhất ngay lúc này nhưng chắc chắn phải vứt đi. Nhu cầu ghi của Quy trình 2 và 3 không phải phỏng đoán — nó nằm ngay trong tài liệu nghiệp vụ đã được duyệt, ở các hoạt động có mã số cụ thể. Chọn A nghĩa là cố ý viết một tầng dữ liệu biết trước sẽ bỏ.

Giữa B và C, cả hai đều đáp ứng nhu cầu ghi, nên đánh đổi hẹp lại: SQLite đổi một chút tiện lợi lúc cài đặt lấy sự khác biệt giữa môi trường phát triển và triển khai, cộng với việc phải tự viết hàm phân vị. Chỉ số ba chặng — trung vị và phân vị 90, tính lại theo từng tổ hợp bộ lọc — là phần tính toán nặng nhất của tính năng này, và PostgreSQL làm sẵn phần đó.

Chi phí thật của C so với B chỉ là một tệp Docker Compose. Đó là cái giá nhỏ so với việc tự viết logic phân vị rồi kiểm thử nó.

## Hệ quả

- **Dễ hơn:** Quy trình 2 và 3 có sẵn chỗ ghi, không phải đổi tầng dữ liệu. Chỉ số phân vị là một câu SQL. Lược đồ có lịch sử phiên bản khi thêm cột cho hai quy trình sau.
- **Khó hơn:** phải cài Docker mới chạy được dự án. Test cần một cơ sở dữ liệu thật, chậm hơn test thuần bộ nhớ. Thêm Alembic phải học và bảo trì.
- **Cần xem lại:** nếu Quy trình 2 và 3 bị huỷ khỏi phạm vi dự án, quyết định này mất phần lớn lý do tồn tại và nên quay về phương án A.

## Việc cần làm

1. [ ] Dựng `docker-compose.yml` với PostgreSQL
2. [ ] Khởi tạo Alembic, viết migration cho bảng thô và bảng dẫn xuất
3. [ ] Viết script nạp dữ liệu và script dựng bảng dẫn xuất
4. [ ] Ghi vào `README.md` cách chạy cơ sở dữ liệu ở môi trường phát triển
