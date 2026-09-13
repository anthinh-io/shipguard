# Ship Guard

Hệ thống giám sát hiệu suất giao hàng và dự đoán rủi ro giao trễ, xây trên dữ liệu vòng đời đơn hàng của một sàn thương mại điện tử. Tệp này định nghĩa ngôn ngữ chung của dự án — không chứa chi tiết triển khai.

Tên thuật ngữ viết tiếng Anh để khớp định danh trong code; định nghĩa viết tiếng Việt.

## Đơn hàng và vòng đời

**Order**:
Một lần khách đặt hàng, có thể gồm sản phẩm từ nhiều người bán. Là đơn vị mà mọi chỉ số hiệu suất được tính trên đó.
_Avoid_: Purchase, Transaction

**Delivered Order**:
Đơn đã đến tay khách hàng và có ngày giao thực tế. Đây là tập đơn duy nhất được tính vào KPI hiệu suất.
_Avoid_: Completed Order, Fulfilled Order

**Estimated Delivery Date**:
Ngày giao hàng đã cam kết với khách lúc đặt hàng. Là một ngày, không phải một thời điểm — mọi so sánh với nó đều ở mức ngày lịch.
_Avoid_: Promised Date, ETA, Deadline

**Late Order**:
Đơn có ngày giao thực tế muộn hơn ngày cam kết, so theo ngày lịch. Giao đúng ngày cam kết là đúng hạn, bất kể mấy giờ.
_Avoid_: Delayed Order, Overdue Order

**Multi-Seller Order**:
Đơn có sản phẩm từ nhiều hơn một người bán. Khi lọc theo người bán, đơn này thuộc về mọi người bán tham gia. Không tách được thời gian chuẩn bị hàng theo từng người bán trong một đơn như vậy.
_Avoid_: Split Order, Composite Order

## Ba chặng thời gian

Vòng đời một đơn được chia làm ba chặng liên tiếp, mỗi chặng thuộc về một bên chịu trách nhiệm khác nhau. Việc tách như vậy để biết điểm nghẽn nằm ở đâu, thay vì chỉ nhìn một con số tổng.

**Payment Approval**:
Chặng từ lúc khách đặt hàng đến lúc thanh toán được xác nhận. Thuộc trách nhiệm cổng thanh toán và ngân hàng, không phải người bán.
_Avoid_: Payment Wait, Approval Delay

**Seller Handling**:
Chặng từ lúc thanh toán được xác nhận đến lúc người bán bàn giao hàng cho đơn vị vận chuyển. Thuộc trách nhiệm người bán.
_Avoid_: Processing Time, Preparation Time, Fulfillment Time

**Carrier Transit**:
Chặng từ lúc hàng được bàn giao cho đơn vị vận chuyển đến lúc khách nhận hàng. Thuộc trách nhiệm đơn vị vận chuyển.
_Avoid_: Shipping Time, Delivery Time

## Chỉ số

**On-Time Rate**:
Tỷ lệ đơn đã giao không bị trễ. Chỉ số chính của bảng điều khiển hiệu suất.
_Avoid_: Success Rate, SLA Rate

**Low Review**:
Đánh giá của khách ở mức 1 hoặc 2 sao. Mức 3 sao là trung tính, không tính là thấp.
_Avoid_: Bad Review, Negative Review

**Late-Related Low Review Rate**:
Trong các đơn bị chấm 1–2 sao, tỷ lệ đơn giao trễ. Trả lời câu hỏi giao trễ chiếm bao nhiêu phần trong sự bất mãn của khách — không phải câu hỏi ngược lại.
_Avoid_: Review Impact Rate

**Region**:
Bang của khách hàng nhận hàng. Khi nói phân bố theo vùng, luôn là vùng nhận, không phải vùng gửi.
_Avoid_: Area, Zone, Territory

**Seller State**:
Bang của người bán gửi hàng đi. Chỉ dùng để nhận diện người bán trong ô gợi ý gõ dần — mọi chỉ số theo vùng đều tính trên `Region`, tức bang của khách nhận hàng.
_Avoid_: Origin State, Vendor Region

**Small Sample**:
Tập đơn sau khi lọc có dưới 30 đơn. Ở quy mô này các tỷ lệ phần trăm không đủ tin cậy để kết luận, nên được gắn cảnh báo.
_Avoid_: Low Volume, Insufficient Data

## Kỳ báo cáo

**Reporting Period**:
Khoảng thời gian đang xem trên bảng điều khiển, xác định theo **ngày giao thực tế** của đơn. Một đơn giao trong tháng 1 thuộc kỳ tháng 1 kể cả khi được đặt từ tháng 11.
_Avoid_: Date Range, Time Window

**Full Month**:
Tháng có ít nhất 100 đơn đã giao. Ngưỡng này để loại các tháng ở rìa dải dữ liệu, nơi chỉ còn vài đơn rớt lại — tính chúng vào sẽ cho ra một tỷ lệ dựng trên mẫu quá nhỏ và trông như hệ thống hỏng.
_Avoid_: Complete Month, Valid Month

**Default Reporting Period**:
Kỳ báo cáo khi người dùng chưa chọn gì: 12 tháng gần nhất tính đến `Full Month` cuối cùng. Nếu không tháng nào đạt ngưỡng, lùi về tháng cuối cùng có đơn đã giao. Luôn suy ra từ dữ liệu hiện có, không phải một khoảng ngày cố định.
_Avoid_: Initial Period, Fallback Period

**Comparison Period**:
Kỳ được đem ra đối chiếu với kỳ báo cáo. Có hai lựa chọn: kỳ liền trước có cùng độ dài, hoặc cùng kỳ của năm trước.
_Avoid_: Baseline, Reference Period
