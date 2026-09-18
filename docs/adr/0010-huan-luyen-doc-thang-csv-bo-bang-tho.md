# ADR-0010: Huấn luyện đọc thẳng tệp CSV, bỏ tầng bảng thô

**Trạng thái:** Đã chấp nhận
**Thay thế:** ADR-0007
**Ngày:** 2026-09-16
**Người quyết định:** Chủ dự án

## Bối cảnh

ADR-0007 chốt hai vai cho bảng `raw_*`: nguồn dựng lớp dẫn xuất, và dữ liệu huấn luyện mô hình. Chính nó cũng ghi lại rằng Phương án E — xoá hẳn bảng thô — rẻ hơn lúc bị loại sau khi việc 1 và 2 hoàn thành, và hẹn mở lại câu hỏi sau khi lệnh huấn luyện viết xong.

Bốn điều đã thay đổi kể từ đó:

- **Không đường đọc vận hành nào còn chạm bảng thô.** Việc cần làm số 2 đã xong: 111 lần nhắc tới `raw_` trong backend nằm ở đúng một script ETL, một tệp model, các migration và 6 tệp test. Không route, không service.
- **Danh sách đặc trưng của lệnh huấn luyện đã chốt**, nên không còn phải suy đoán nó chạm cột nào. Lớp dẫn xuất phủ phần lớn nhưng thiếu ba thứ, và cả ba đều cần thật: `raw_order_items.shipping_limit_date` cho đặc trưng "người bán bàn giao quá hạn" — tín hiệu mạnh nhất đã đo được (đơn bàn giao quá hạn trễ 20,8% so với 5,4%); `raw_sellers.seller_zip_code_prefix`, mà bảng `sellers` dẫn xuất không mang; và toàn bộ `raw_geolocation`, không có bảng dẫn xuất nào tương ứng. Hai thứ sau dùng cho đặc trưng khoảng cách người bán → khách.
- **Mã bưu chính trong bảng thô đã mất số 0 đầu.** Ba cột mã bưu chính ở tầng thô là `INTEGER` nên `01310` nạp thành `1310`; `build_derived_data` phải `lpad` lại. Tệp CSV giữ nguyên chuỗi `"01310"`. Đọc thẳng CSV là bỏ hẳn một lớp biến dạng dữ liệu chứ không phải né nó.
- **Bảng thô là một bản sao thứ hai của một tập dữ liệu đã đóng băng.** 9 tệp CSV Olist không bao giờ đổi. Giữ chúng thêm một lần nữa trong lược đồ không mua được gì mà vẫn phải migration, phải nạp, phải giữ đồng bộ.

Lực còn lại theo hướng ngược: ba tệp test đang dùng bảng thô làm nguồn đối chiếu độc lập ngay trong cùng cơ sở dữ liệu, cộng bốn câu SQL dựng lại `edge_case_orders.json`.

## Quyết định

1. **Lệnh huấn luyện và notebook phân tích đọc thẳng tệp CSV trong `datasets/raw/`.** Không qua cơ sở dữ liệu. Tập huấn luyện vì thế đóng băng theo đúng nghĩa đen — nó là tệp trên đĩa, không phải trạng thái của một bảng.
2. **Chín bảng `raw_*` bị xoá khỏi lược đồ.** Lệnh `load_raw_data` biến mất cùng chúng.
3. **`build_derived_data` tự nạp CSV vào bảng TẠM trong cùng giao dịch**, chạy nguyên bảy câu SQL đang có, rồi kết thúc giao dịch — bảng tạm tự biến mất. Bảy câu SQL không viết lại, chỉ đổi tên bảng nguồn.
4. **Test đối chiếu lấy CSV làm nguồn độc lập**, không lấy bảng thô. Đây là khuôn `test_order_value_golden.py` đã dùng, với lý do ghi sẵn trong chính nó: "cùng một lỗi cộng sai ở hai nơi thì so với nhau vẫn xanh".
5. Mọi quyết định khác của ADR-0007 giữ nguyên: lớp dẫn xuất là nơi lưu dữ liệu vận hành, dựng một lần khi cài đặt, không có cột đánh dấu nguồn, và script dựng tự dừng khi đã tồn tại `Risk Assessment`.

## Các phương án đã cân nhắc

### Phương án A: Giữ nguyên ADR-0007 — huấn luyện đọc bảng `raw_*`

| Chiều đánh giá | Nhận định |
| --- | --- |
| Độ phức tạp | Thấp — không đổi gì |
| Chi phí vận hành | Trung bình — hai lệnh nạp, 9 bảng thừa trong lược đồ |
| Khả năng mở rộng | Kém — mọi cột mới cần cho mô hình phải thêm vào cả bảng thô |
| Độ quen thuộc | Cao — đang chạy như vậy |

**Ưu:** không phải đụng gì; test đối chiếu giữ nguyên.
**Nhược:** huấn luyện phụ thuộc cơ sở dữ liệu, nên test của nó cần Postgres; giữ một bản sao thứ hai của tập dữ liệu không bao giờ đổi; mã bưu chính đã mất số 0 đầu ngay ở tầng thô.

### Phương án B: Huấn luyện đọc lớp dẫn xuất, thêm cột còn thiếu

| Chiều đánh giá | Nhận định |
| --- | --- |
| Độ phức tạp | Trung bình — một migration, một lần dựng lại |
| Chi phí vận hành | Thấp — một nguồn duy nhất cho cả vận hành lẫn huấn luyện |
| Khả năng mở rộng | Tốt — thêm cột là thêm vào một chỗ |
| Độ quen thuộc | Cao — cùng SQLAlchemy như phần còn lại |

**Ưu:** một nguồn duy nhất; không phải đọc CSV trong mã ứng dụng.
**Nhược:** **hỏng ngay từ gốc.** Quyết định 3 của ADR-0007 chốt lớp dẫn xuất không có cột đánh dấu nguồn, còn đơn tạo trong Ship Guard ghi thẳng vào đó. Từ đơn đầu tiên, tập huấn luyện âm thầm đổi theo thao tác người dùng mà không có cách nào lọc ra. Ngoài ra còn phải thêm một bảng toạ độ mới chỉ để phục vụ huấn luyện.

### Phương án C: Huấn luyện đọc thẳng CSV, bỏ bảng thô

| Chiều đánh giá | Nhận định |
| --- | --- |
| Độ phức tạp | Trung bình — một migration xoá bảng, sửa 6 tệp test |
| Chi phí vận hành | Thấp — một lệnh nạp thay vì hai, lược đồ bớt 9 bảng |
| Khả năng mở rộng | Tốt — thêm đặc trưng chỉ là đọc thêm cột CSV |
| Độ quen thuộc | Trung bình — pandas đọc CSV là chuyện thường của ML, mới với repo này |

**Ưu:** tập huấn luyện đóng băng theo đúng nghĩa đen; huấn luyện không cần cơ sở dữ liệu nên test của nó chạy không cần Postgres; test đối chiếu mạnh lên vì nguồn so sánh nằm ngoài cơ sở dữ liệu thay vì cùng trong đó; dùng được cả `raw_geolocation` và mã bưu chính người bán, hai thứ lớp dẫn xuất không mang, mà không phải thêm bảng nào.
**Nhược:** hai đường đọc CSV trong mã (huấn luyện và bước dựng dẫn xuất); phải sửa 6 tệp test và công thức dựng lại `edge_case_orders.json`.

## Phân tích đánh đổi

B rụng dứt khoát, và không phải vì giá: nó làm tập huấn luyện đổi theo thao tác người dùng, đúng cái ranh giới ADR-0007 dựng lên để chặn.

Đánh đổi thật nằm giữa A và C. A không tốn gì hôm nay nhưng giữ mãi một bản sao thứ hai của dữ liệu đóng băng và buộc mọi test huấn luyện phải có Postgres chạy. C trả một lần chi phí sửa 6 tệp test, đổi lấy một tầng ít đi, một lệnh ít đi, và các test đối chiếu mạnh hơn chính cái chúng đang có. Với tập dữ liệu Olist đã đóng và chỉ nạp một lần, C đúng hướng.

Bảng tạm được chọn thay vì viết lại bước dựng bằng pandas vì bảy câu SQL dựng dẫn xuất đang có test số vàng canh từng con số — trong đó phép đánh số thứ tự đánh giá và phép gộp `Order Value` là hai chỗ đã từng sai. Viết lại chúng bằng pandas là mở lại hai lỗi đã đóng, để đổi lấy sự đồng nhất về công cụ mà không ai đang cần.

## Hệ quả

- **Dễ hơn:** test của dữ liệu huấn luyện, đặc trưng và lệnh huấn luyện chạy không cần Postgres; lược đồ bớt 9 bảng; cài đặt bớt một lệnh; tập huấn luyện đóng băng nên không thể vô tình lẫn đơn mới.
- **Khó hơn:** phải sửa 6 tệp test và công thức dựng lại `edge_case_orders.json`; bước dựng dẫn xuất gánh thêm phần đọc CSV vốn nằm ở lệnh riêng; mất khả năng truy vấn SQL thẳng lên dữ liệu thô khi soi lỗi, phải mở tệp CSV.
- **Cần xem lại:** nếu về sau có huấn luyện lại định kỳ trên đơn mới đã giao, CSV không còn đủ và cần một đường đưa đơn từ lớp dẫn xuất sang dữ liệu huấn luyện — đúng mục "Cần xem lại" mà ADR-0007 đã nêu và ADR này không giải quyết.

## Việc cần làm

1. [x] Lệnh huấn luyện và notebook đọc thẳng CSV
2. [x] Xoá 9 bảng `raw_*`, gộp `load_raw_data` vào `build_derived_data` bằng bảng tạm
3. [x] Sáu tệp test chuyển sang lấy CSV làm nguồn đối chiếu
4. [x] `build_derived_data` dừng khi đã có `Risk Assessment` (chuyển từ ADR-0007)

Ghi chú khi làm việc 2: bảng tạm được đặt **đúng tên chín bảng thô cũ** chứ không đổi
thành `tmp_*` như câu chữ quyết định 3 gợi ý. Postgres tra `pg_temp` trước cho tên bảng
không kèm schema, nên bảy câu SQL dựng không phải sửa một ký tự nào — đúng tinh thần
"bảy câu SQL không viết lại", ở dạng mạnh nhất có thể.
