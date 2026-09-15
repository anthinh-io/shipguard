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

**Order Status**:
Trạng thái vòng đời của đơn do sàn ghi nhận, là một trong tám giá trị: created, approved, invoiced, processing, shipped, delivered, canceled, unavailable. Khác với `Delivery Outcome`. Đơn tạo trong Ship Guard chỉ đi qua created → approved → shipped → delivered, hoặc dừng ở canceled; trạng thái của nó suy ra từ `Order Milestone` mới nhất.
_Avoid_: Order State, Lifecycle Stage

**Order Milestone**:
Một trong ba mốc sau lúc đặt hàng: thanh toán được duyệt, hàng được bàn giao cho đơn vị vận chuyển, khách nhận hàng. Với đơn tạo trong Ship Guard, nhân viên ghi nhận từng mốc theo đúng thứ tự, không mốc nào ở tương lai. Chỉ mốc mới nhất sửa được, và chỉ khi đơn chưa giao.
_Avoid_: Event, Step, Checkpoint

**Delivery Outcome**:
Kết cục giao hàng của một đơn: đúng hạn, trễ, hoặc chưa có kết quả. Chỉ `Delivered Order` mới có đúng hạn hay trễ; mọi đơn khác — đang trên đường, đã hủy, không có hàng, kể cả khi đã quá ngày cam kết — đều là chưa có kết quả.
_Avoid_: Delivery Status, Late Status

**Purchase Date**:
Ngày khách đặt hàng. Là mốc thời gian mặc định khi tra cứu đơn, vì mọi đơn đều có — khác với `Reporting Period` của bảng điều khiển vốn bám theo ngày giao thực tế.
_Avoid_: Order Date, Created Date

**Order Value**:
Tổng giá sản phẩm cộng phí vận chuyển của một đơn. Không phải số tiền khách đã thanh toán, vốn có thể lệch do voucher hay trả góp. Đơn không có sản phẩm nào thì không có giá trị.
_Avoid_: Order Total, Payment Amount, GMV

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

## Tra cứu đơn hàng

**Internal Note**:
Ghi chú nội bộ mà một `User` để lại trên một đơn. Chỉ thêm được, không sửa hay xóa — muốn đính chính thì thêm ghi chú mới.
_Avoid_: Comment, Remark, Annotation

## Dự đoán rủi ro

**Risk Assessment**:
Một lần hệ thống đánh giá khả năng giao trễ của một đơn tại một `Prediction Checkpoint`, gồm `Late Probability`, mức rủi ro, `Risk Cause` và trạng thái xử lý. Mỗi mốc mới sinh thêm một lần đánh giá, các lần cũ giữ nguyên làm lịch sử. Đơn Olist lịch sử không bao giờ có. Chỉ đơn đã có ít nhất một lần đánh giá mới được ghi nhận mốc hay hủy.
_Avoid_: Prediction, Forecast, Risk Score

**Prediction Checkpoint**:
Thời điểm trong vòng đời đơn mà một `Risk Assessment` được tạo: lúc đặt hàng, lúc thanh toán được duyệt, lúc bàn giao cho đơn vị vận chuyển. Càng về sau càng nhiều chặng đã xảy ra thật, nên đánh giá càng đáng tin.
_Avoid_: Stage, Milestone

**Late Probability**:
Khả năng đơn giao sau `Estimated Delivery Date`, tính từ thời gian dự kiến của các chặng chưa xảy ra cộng thời gian thật của các chặng đã xong.
_Avoid_: Risk Score, Confidence

**Risk Threshold**:
Mức `Late Probability` mà từ đó một đơn là `High Risk`. Một con số chung cho mọi mốc, chọn từ kết quả đánh giá mô hình chứ không đặt theo cảm tính.
_Avoid_: Cutoff

**High Risk**:
Mức rủi ro của một `Risk Assessment` có `Late Probability` đạt `Risk Threshold` tại lúc đánh giá; ngược lại là Low Risk. Mức này chốt lúc đánh giá — đổi ngưỡng về sau không xếp lại các lần cũ.
_Avoid_: Critical, Dangerous Order

**Risk Cause**:
Trong các chặng chưa xảy ra, chặng mà thời gian dự kiến vượt mức thường của chính chặng đó nhiều ngày nhất: `Payment Approval`, `Seller Handling` hoặc `Carrier Transit`. Với `Multi-Seller Order`, chặng người bán tính theo người bán chậm nhất, và nguyên nhân nêu tên người bán đó. Chỉ hiển thị với `High Risk`.
_Avoid_: Root Cause, Fault, Blame

**Intervention**:
Biện pháp nhân viên đã thực hiện cho một `Risk Assessment` là `High Risk`, chọn từ danh sách cố định — nhắc người bán, đổi đơn vị vận chuyển, liên hệ về thanh toán, thông báo khách, khác — kèm ghi chú tùy chọn. Ship Guard chỉ ghi nhận, không tự thực thi.
_Avoid_: Action, Fix

**Handled**:
Trạng thái của một `Risk Assessment` là `High Risk` sau khi đã ghi nhận `Intervention`. Chỉ lần đánh giá mới nhất của một đơn còn là việc cần xử lý — lần cũ chưa xử lý bị lần mới thay thế. Đơn đã hủy không còn việc cần xử lý.
_Avoid_: Resolved, Closed, Done

**Reconciliation**:
Việc đối chiếu mọi `Risk Assessment` của một đơn với `Delivery Outcome` thật khi đơn được ghi nhận đã giao. Đánh giá là đúng khi `High Risk` mà đơn trễ, hoặc Low Risk mà đơn đúng hạn.
_Avoid_: Validation, Verification

## Người dùng

**User**:
Một người đăng nhập vào hệ thống, định danh bằng email, có tên hiển thị và đúng một vai trò. Không bao giờ bị xóa, chỉ bị khóa.
_Avoid_: Account, Member

**Operations Staff**:
Vai trò nhân viên vận hành: xem bảng điều khiển, tra cứu đơn, viết `Internal Note`.
_Avoid_: Operator, Agent

**Logistics Manager**:
Vai trò quản lý hậu cần: mọi việc của `Operations Staff`, cộng quyền quản trị các `User` khác trừ `Super Admin`.
_Avoid_: Admin, Supervisor

**Super Admin**:
Vai trò của đúng một `User` duy nhất, sinh ra từ cấu hình lúc cài đặt để có người đầu tiên cấp tài khoản cho các `Logistics Manager`. Làm được mọi việc của `Logistics Manager`, và không ai khóa, đổi vai trò hay đặt lại mật khẩu của nó qua giao diện — để hệ thống luôn còn một lối vào.
_Avoid_: Root, Owner, Admin

**User Claim**:
Một quyền lẻ gán riêng cho một `User`, cộng thêm vào những gì vai trò của họ đã cho phép. Không thay thế vai trò, và không lấy đi quyền nào vai trò đã cho.
_Avoid_: Permission, Grant, Privilege

**Locked User**:
`User` bị khóa: không đăng nhập được, nhưng vẫn là tác giả của mọi `Internal Note` đã viết.
_Avoid_: Disabled User, Deactivated User, Deleted User
