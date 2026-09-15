# ADR-0008: Dự đoán phân phối thời gian ba chặng thay vì phân loại trễ trực tiếp

**Trạng thái:** Đã chấp nhận
**Ngày:** 2026-09-15
**Người quyết định:** Chủ dự án

## Bối cảnh

README đặt mục tiêu F1 ≥ 0,30 cho bài toán phân loại giao trễ. Nghiệp vụ đòi thêm ba thứ mà một bộ phân loại trễ/đúng hạn không tự cho:

- **Nhiều mốc dự đoán.** Mỗi `Order Milestone` mới sinh một `Risk Assessment`, dùng thời gian thật của chặng đã xong.
- **`Risk Cause`.** Dữ liệu không có nhãn "trễ do ai", nên nguyên nhân phải suy ra được chứ không học trực tiếp được.
- **Xác suất nhất quán với nguyên nhân.** Không thể có đánh giá "rủi ro cao" mà cả ba chặng đều bình thường.

Dữ liệu: tỷ lệ trễ 6,77%, tăng vọt theo mùa (19% ở 2018-03); `Payment Approval` trung vị 0,01 ngày, `Seller Handling` 1,82, `Carrier Transit` 7,10, cả ba lệch đuôi mạnh; khoảng cam kết trung vị 24 ngày.

## Quyết định

1. Mỗi chặng một mô hình dự đoán **phân phối** thời gian từ thông tin có lúc đặt hàng. `Seller Handling` dự đoán cho từng người bán; đơn chờ người chậm nhất.
2. `Late Probability` = khả năng tổng thời gian (chặng đã xong lấy số thật, chặng chưa xong lấy mẫu từ phân phối) vượt `Estimated Delivery Date`, so theo ngày lịch.
3. `Risk Cause` = chặng chưa xong có trung vị dự kiến trừ trung vị lịch sử của chặng đó lớn nhất.
4. Huấn luyện ba bộ ứng viên, mỗi bộ một thuật toán cho cả ba chặng: XGBoost hồi quy phân vị; XGBoost phân phối log-normal (AFT); Scikit-learn HistGradientBoosting hồi quy phân vị. Chia dữ liệu theo thời gian đặt hàng thành huấn luyện / kiểm định / kiểm tra.
5. Giữ bộ có F1 cao nhất ở mốc đặt hàng trên tập kiểm tra. `Risk Threshold` là ngưỡng cho F1 cao nhất trên tập kiểm định, đặt trong cấu hình. F1 dưới 0,30 vẫn triển khai, báo cáo ghi rõ là chưa đạt.

## Các phương án đã cân nhắc

### Phương án A: Bộ phân loại trễ cho mỗi mốc, thêm mô hình chặng chỉ để chỉ nguyên nhân

| Chiều đánh giá | Nhận định |
| --- | --- |
| Độ phức tạp | Cao — ba bộ phân loại theo mốc cộng ba mô hình chặng |
| Chi phí vận hành | Cao — sáu mô hình phải huấn luyện, đánh giá và nạp |
| Khả năng mở rộng | Kém — thêm mốc là thêm một bộ phân loại |
| Độ quen thuộc | Cao — phân loại nhị phân là bài toán quen thuộc nhất |

**Ưu:** tối ưu thẳng mục tiêu F1 của README.
**Nhược:** xác suất và nguyên nhân đến từ hai nguồn, có thể mâu thuẫn trước mắt nhân viên.

### Phương án B: Phân phối thời gian ba chặng, xác suất suy ra

| Chiều đánh giá | Nhận định |
| --- | --- |
| Độ phức tạp | Trung bình — dự đoán phân phối và lấy mẫu Monte Carlo |
| Chi phí vận hành | Trung bình — ba mô hình mỗi thuật toán, chín mô hình khi so ba ứng viên |
| Khả năng mở rộng | Tốt — một bộ mô hình phục vụ mọi mốc |
| Độ quen thuộc | Trung bình — hồi quy phân vị và AFT ít gặp hơn phân loại |

**Ưu:** nguyên nhân và xác suất cùng một nguồn; nguyên nhân giải thích được bằng số ngày.
**Nhược:** giả định các chặng độc lập khi đã biết đặc trưng; F1 có thể thấp hơn bộ phân loại chuyên biệt.

### Phương án C: Dự đoán điểm thời gian từng chặng, so với ngày cam kết

| Chiều đánh giá | Nhận định |
| --- | --- |
| Độ phức tạp | Thấp — ba mô hình hồi quy thường |
| Chi phí vận hành | Thấp |
| Khả năng mở rộng | Tốt — dùng được cho mọi mốc |
| Độ quen thuộc | Cao |

**Ưu:** đơn giản nhất.
**Nhược:** không có xác suất, không có ngưỡng để chỉnh theo dữ liệu lệch 6,77%.

## Phân tích đánh đổi

C rụng vì bỏ xác suất mà nghiệp vụ cần. Giữa A và B, A có thể nhỉnh F1 nhưng trả bằng mâu thuẫn giữa con số và nguyên nhân mà nhân viên nhìn thấy cùng lúc, cộng một bộ phân loại cho mỗi mốc. B đổi một phần F1 lấy tính nhất quán; phần F1 được bù bằng việc chọn thuật toán và ngưỡng theo chính F1.

## Hệ quả

- **Dễ hơn:** thêm mốc không cần mô hình mới; nguyên nhân giải thích được bằng số ngày dự kiến so với mức thường.
- **Khó hơn:** dự đoán cần lấy mẫu Monte Carlo với hạt giống cố định để kết quả lặp lại được; mỗi lần huấn luyện dựng chín mô hình; chấp nhận giả định các chặng độc lập và không huấn luyện lại tự động.
- **Cần xem lại:** nếu F1 ở mốc đặt hàng dưới 0,30 kéo dài, mở lại phương án A.

## Việc cần làm

1. [ ] Script huấn luyện ba bộ ứng viên và báo cáo đánh giá
2. [ ] Mô-đun dự đoán: phân phối, `Late Probability`, `Risk Cause`
3. [ ] `Risk Threshold` trong cấu hình
