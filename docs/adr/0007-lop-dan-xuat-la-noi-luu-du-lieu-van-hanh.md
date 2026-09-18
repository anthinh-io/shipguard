# ADR-0007: Lớp dẫn xuất là nơi lưu dữ liệu vận hành, bảng thô chỉ để huấn luyện

**Trạng thái:** Bị thay thế
**Thay bởi:** ADR-0010
**Ngày:** 2026-09-15
**Người quyết định:** Chủ dự án

> ADR-0010 chỉ lật quyết định 1 — bảng `raw_*` không còn là dữ liệu huấn luyện. Các quyết định 2, 3, 4 vẫn còn hiệu lực và được ADR-0010 giữ nguyên tường minh. Chín bảng `raw_*` và lệnh `load_raw_data` **đã bị xoá** ở migration `0010_drop_raw_tables`; bước dựng tự nạp CSV vào bảng tạm. Cả bốn việc cần làm của ADR-0010 đã xong; việc 4 — chốt dừng khi đã có `Risk Assessment` — ở #31.

## Bối cảnh

Tới Quy trình 2, dữ liệu đi một chiều: 9 tệp CSV Olist nạp vào bảng `raw_*`, rồi `build_derived_data` truncate và dựng lại `orders`, `order_sellers`, `sellers` từ bảng thô. Trang chi tiết đơn đọc sản phẩm, thanh toán, đánh giá thẳng từ bảng thô. Dựng lại bao nhiêu lần cũng được, vì không có gì do người dùng tạo nằm trong các bảng đó (ghi chú nội bộ cố ý không có khóa ngoại tới `orders`).

Dự đoán rủi ro phá vỡ giả định này: nhân viên tạo đơn mới thật trong Ship Guard, đơn đó là `Order` đầy đủ — hiện trong danh sách, trang chi tiết, KPI — và được ghi nhận mốc về sau.

Các lực tác động:

- **Bảng thô là dữ liệu huấn luyện.** Mô hình học trên đơn Olist; trộn đơn mới vào đó làm tập huấn luyện đổi theo thao tác người dùng.
- **Truncate đang là bước dựng.** Đơn mới nằm trong `orders` sẽ mất sạch ở lần dựng lại kế tiếp.
- **Đơn mới cần sản phẩm và thanh toán** ở cùng chỗ trang chi tiết đọc.

## Quyết định

1. Bảng `raw_*` chỉ phục vụ huấn luyện mô hình; không ghi đơn mới vào đó.
2. Lớp dẫn xuất có thêm bảng dòng sản phẩm, dòng thanh toán và đánh giá cho mọi đơn. `build_derived_data` đổ dữ liệu Olist vào; đơn mới ghi thẳng sản phẩm và thanh toán vào (đơn mới không có đánh giá). Mọi đường đọc vận hành — trang chi tiết đơn, danh sách, KPI — chỉ đọc lớp dẫn xuất; bảng `raw_*` được giữ trong cơ sở dữ liệu làm nguồn dựng ban đầu và dữ liệu huấn luyện.
3. Lớp dẫn xuất được dựng **một lần** khi cài đặt. Từ đó nó là nơi lưu dữ liệu vận hành, không có cột đánh dấu nguồn.
4. `build_derived_data` tự dừng và báo lỗi nếu đã tồn tại bất kỳ `Risk Assessment` nào — dấu hiệu đã có đơn tạo trong Ship Guard.

## Các phương án đã cân nhắc

### Phương án A: Ghi đơn mới vào bảng thô, dẫn xuất chung một đường

| Chiều đánh giá | Nhận định |
| --- | --- |
| Độ phức tạp | Trung bình — tách hàm dẫn xuất chạy được cho từng đơn |
| Chi phí vận hành | Thấp — dựng lại bao nhiêu lần cũng không mất gì |
| Khả năng mở rộng | Tốt — một đường dữ liệu duy nhất |
| Độ quen thuộc | Cao — giữ nguyên luồng nạp → dựng hiện có |

**Ưu:** một nguồn sự thật; dựng lại vẫn an toàn.
**Nhược:** tập huấn luyện bị trộn đơn mới, đổi theo thao tác người dùng.

### Phương án B: Ghi thẳng lớp dẫn xuất kèm cột nguồn, dựng lại chỉ xóa dòng Olist

| Chiều đánh giá | Nhận định |
| --- | --- |
| Độ phức tạp | Trung bình — mọi bảng dẫn xuất thêm cột nguồn, bước dựng thành xóa có điều kiện |
| Chi phí vận hành | Thấp — vẫn dựng lại được khi đã có đơn mới |
| Khả năng mở rộng | Trung bình — mỗi bảng dẫn xuất mới phải nhớ cột nguồn |
| Độ quen thuộc | Cao |

**Ưu:** giữ khả năng dựng lại; tập huấn luyện tách bạch.
**Nhược:** phân biệt hai loại đơn bằng một cột mà nghiệp vụ đã chốt là không phân biệt.

### Phương án C: Dựng lớp dẫn xuất một lần, sau đó là nơi lưu vận hành, script tự chặn

| Chiều đánh giá | Nhận định |
| --- | --- |
| Độ phức tạp | Thấp — một bước kiểm tra trước khi truncate |
| Chi phí vận hành | Trung bình — sửa lỗi dữ liệu dẫn xuất sau khi vận hành phải viết migration dữ liệu |
| Khả năng mở rộng | Tốt — đơn mới và đơn Olist chung một mô hình dữ liệu |
| Độ quen thuộc | Cao |

**Ưu:** đơn giản nhất; không có khái niệm "nguồn đơn"; tập huấn luyện tách bạch.
**Nhược:** mất khả năng dựng lại lớp dẫn xuất sau khi đã có đơn mới.

### Phương án D: Bảng riêng cho đơn mới, UNION khi truy vấn

| Chiều đánh giá | Nhận định |
| --- | --- |
| Độ phức tạp | Cao — mọi truy vấn KPI và danh sách phải sửa |
| Chi phí vận hành | Thấp — dựng lại không đụng đơn mới |
| Khả năng mở rộng | Kém — mỗi truy vấn mới phải nhớ gộp hai nguồn |
| Độ quen thuộc | Trung bình |

**Ưu:** không đụng dữ liệu và truy vấn cũ khi ghi.
**Nhược:** hai cách đọc một đơn ở mọi nơi.

### Phương án E: Xóa hẳn bảng thô khỏi cơ sở dữ liệu, huấn luyện và dựng ban đầu đọc thẳng CSV

| Chiều đánh giá | Nhận định |
| --- | --- |
| Độ phức tạp | Cao — viết lại bước nạp, bước dựng và các test đang đối chiếu với bảng thô |
| Chi phí vận hành | Thấp — cơ sở dữ liệu gọn hơn |
| Khả năng mở rộng | Trung bình — huấn luyện phụ thuộc tệp trên đĩa |
| Độ quen thuộc | Trung bình |

**Ưu:** ranh giới vận hành / huấn luyện rõ nhất về mặt vật lý.
**Nhược:** đảo một phần công việc đã đóng để đổi lấy dung lượng mà nghiệp vụ không cần.

## Phân tích đánh đổi

A rụng vì làm bẩn tập huấn luyện. D rụng vì cái giá sửa mọi truy vấn hiện có. E rụng vì chi phí viết lại lớn trong khi ranh giới "vận hành chỉ đọc lớp dẫn xuất" đạt được rẻ hơn — chuyển nốt đánh giá của khách sang lớp dẫn xuất. Đánh đổi thật giữa B và C: B giữ khả năng dựng lại bằng một cột nguồn mà nghiệp vụ không cần; C bỏ khả năng đó đổi lấy mô hình dữ liệu không phân biệt đơn. Với dữ liệu Olist đã đóng băng và chỉ nạp một lần, dựng lại sau khi vận hành là tình huống hiếm; chặn nó bằng lỗi rõ ràng là đủ an toàn.

## Hệ quả

- **Dễ hơn:** đơn mới dùng lại nguyên danh sách đơn, trang chi tiết, KPI; mô hình huấn luyện trên tập cố định; mọi đường đọc vận hành chỉ nhìn lớp dẫn xuất.
- **Khó hơn:** sửa lỗi dữ liệu dẫn xuất sau khi đã có đơn mới phải viết migration dữ liệu; đơn mới đã giao không quay lại làm dữ liệu huấn luyện, và lịch sử người bán dùng làm đặc trưng dừng ở dữ liệu Olist.
- **Cần xem lại:** nếu có huấn luyện lại định kỳ trên đơn mới, cần một đường đưa đơn đã giao từ lớp dẫn xuất sang dữ liệu huấn luyện.
- **Cần xem lại:** sau khi việc 1 và 2 xong, lớp dẫn xuất phủ đủ danh sách đặc trưng mà lệnh huấn luyện dự kiến dùng, nên **Phương án E** (xoá hẳn bảng thô) rẻ hơn lúc bị loại. Mở lại câu hỏi **sau khi lệnh huấn luyện đã viết xong**, khi đã đọc được nó thật sự chạm bảng và cột nào thay vì suy đoán. Hai biến thể đóng cửa khác nhau: "huấn luyện đọc lớp dẫn xuất" chỉ khả thi **trước khi có đơn tạo trong Ship Guard** — từ đó lớp dẫn xuất hết là tập cố định, và quyết định 3 đã chốt không có cột đánh dấu nguồn; còn "huấn luyện đọc thẳng CSV" thì bỏ lúc nào cũng được. Cái giá phải cân: ba tệp test đang dùng bảng thô làm nguồn đối chiếu độc lập ngay trong cùng cơ sở dữ liệu, cộng bốn câu SQL dựng lại `edge_case_orders.json`.

## Việc cần làm

1. [x] Bảng dẫn xuất dòng sản phẩm, dòng thanh toán và đánh giá, đổ dữ liệu từ `build_derived_data`
2. [x] Trang chi tiết đơn đọc sản phẩm, thanh toán và đánh giá từ lớp dẫn xuất
3. [x] `build_derived_data` dừng khi đã có `Risk Assessment`
