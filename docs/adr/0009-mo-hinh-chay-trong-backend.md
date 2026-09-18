# ADR-0009: Mô hình dự đoán chạy trong backend FastAPI hiện có

**Trạng thái:** Đã chấp nhận
**Ngày:** 2026-09-15
**Người quyết định:** Chủ dự án

## Bối cảnh

Tài liệu nghiệp vụ mô tả "API dự đoán học máy" như một tài nguyên riêng. Backend hiện chưa có thư viện ML nào. Mỗi lần tạo đơn và ghi nhận mốc phải sinh `Risk Assessment` trong cùng thao tác — đơn không bao giờ được tồn tại mà thiếu đánh giá, vì đó là điều kiện để ghi nhận mốc (xem `CONTEXT.md`).

## Quyết định

Mô-đun dự đoán nằm trong backend FastAPI, nạp tệp mô hình từ `RISK_MODEL_DIR` khi khởi động. Tạo đơn, ghi nhận mốc và sinh `Risk Assessment` chạy trong một giao dịch cơ sở dữ liệu. Chưa có tệp mô hình thì API tạo đơn trả lỗi rõ ràng, phần còn lại của ứng dụng vẫn chạy. Script huấn luyện nằm cạnh các script dữ liệu. Thư viện ML (pandas, NumPy, Scikit-learn, XGBoost) vào dependency của backend, đúng ngăn xếp README.

## Các phương án đã cân nhắc

### Phương án A: Trong backend hiện có

| Chiều đánh giá | Nhận định |
| --- | --- |
| Độ phức tạp | Thấp — dùng chung xác thực, cơ sở dữ liệu, test harness |
| Chi phí vận hành | Thấp — một tiến trình, một lần triển khai |
| Khả năng mở rộng | Trung bình — dự đoán và API khác chia chung tài nguyên |
| Độ quen thuộc | Cao — cùng FastAPI, cùng cấu trúc service/route |

**Ưu:** tạo đơn, ghi nhận mốc và sinh `Risk Assessment` nằm trong một giao dịch.
**Nhược:** backend nặng thêm thư viện ML; khởi động chậm hơn vì nạp mô hình.

### Phương án B: Dịch vụ ML riêng, backend gọi nội bộ

| Chiều đánh giá | Nhận định |
| --- | --- |
| Độ phức tạp | Trung bình — thêm hợp đồng HTTP nội bộ |
| Chi phí vận hành | Trung bình — hai tiến trình, phải xử lý khi dịch vụ ML không phản hồi |
| Khả năng mở rộng | Tốt — mở rộng phần dự đoán độc lập |
| Độ quen thuộc | Trung bình — chưa có giao tiếp giữa các dịch vụ trong dự án |

**Ưu:** tách phụ thuộc nặng; triển khai mô hình độc lập với backend.
**Nhược:** giao dịch tạo đơn phải bao quanh một lời gọi mạng.

### Phương án C: Dịch vụ ML riêng, trình duyệt gọi thẳng

| Chiều đánh giá | Nhận định |
| --- | --- |
| Độ phức tạp | Cao — dịch vụ ML tự xác thực JWT, frontend điều phối hai lời gọi |
| Chi phí vận hành | Trung bình — hai tiến trình, thêm một origin cho CORS |
| Khả năng mở rộng | Tốt |
| Độ quen thuộc | Trung bình — theo kiểu gọi thẳng của ADR-0006 nhưng với hai backend |

**Ưu:** backend chính không đụng tới ML.
**Nhược:** đơn và đánh giá lưu ở hai nơi, có thể sinh đơn không có đánh giá.

## Phân tích đánh đổi

C rụng vì có thể sinh đơn không có đánh giá — trái quy tắc chỉ đơn có `Risk Assessment` mới được ghi nhận mốc. B tách được phụ thuộc nặng và triển khai độc lập, nhưng ở quy mô một công cụ nội bộ, cái giá vận hành thêm một dịch vụ và bọc giao dịch quanh lời gọi mạng lớn hơn lợi ích.

## Hệ quả

- **Dễ hơn:** một lần triển khai; test route dùng bộ dự đoán giả qua dependency override.
- **Khó hơn:** backend nặng thêm thư viện ML và khởi động chậm hơn; tài liệu nghiệp vụ đổi "API dự đoán học máy" thành "API (mô-đun dự đoán)".
- **Cần xem lại:** nếu dự đoán làm chậm các API khác hoặc cần mở rộng riêng, tách thành phương án B.

## Việc cần làm

1. [x] Thêm thư viện ML vào `backend/pyproject.toml`
2. [x] `RISK_MODEL_DIR`, `RISK_THRESHOLD` trong cấu hình và `.env.example`
3. [x] Nạp mô hình lúc khởi động; dependency cung cấp bộ dự đoán
