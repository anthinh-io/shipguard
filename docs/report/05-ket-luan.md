# CHƯƠNG 5. KẾT LUẬN

## 5.1. Cấu trúc phân chia công việc

Vì đây là đồ án cá nhân, không phải làm việc theo nhóm, bảng đánh giá công việc theo từng thành viên như cấu trúc của báo cáo mẫu không áp dụng được. Thay vào đó, công việc được trình bày theo cấu trúc Hạng mục (Epic) và Sprint — đúng theo phương pháp Agile/Scrum đã áp dụng trong suốt quá trình thực hiện.

**Bảng 5.1.1 — Cấu trúc công việc theo Hạng mục và Sprint**

| STT | Hạng mục | Sprint | Số công việc con | Trạng thái | Ghi chú |
| --- | --- | --- | --- | --- | --- |
| 1 | Giám sát hiệu suất giao hàng — bảng điều khiển KPI | Sprint 1 | 12 | Hoàn thành | |
| 2 | Quản lý đơn hàng — tra cứu, chi tiết, ghi chú nội bộ, xuất CSV, kèm đăng nhập và quản trị người dùng | Sprint 1 | 11 | Hoàn thành | |
| 3 | Dự đoán rủi ro giao trễ — tạo đơn, đánh giá theo mốc, xử lý can thiệp và đối chiếu | Sprint 2 | 10 | Hoàn thành | |
| 4 | Nâng chất lượng mô hình dự đoán rủi ro — đo bằng Accuracy, F1, ROC-AUC | Sprint 2 | 7 | Hoàn thành | |
| 5 | Hoàn thiện phân quyền quản trị tài khoản người dùng theo đối tượng bị tác động | Sprint 2 | 4 | Hoàn thành | Ngoài 4 hạng mục chính, thực hiện sau khi các hạng mục trên đã xong |
| 6 | Hiển thị đúng lý do khi từ chối thao tác quản trị tài khoản | Sprint 2 | — | Chưa thực hiện | Còn tồn đọng, xem mục 5.3 |

Theo kế hoạch ban đầu trong đề cương, khối lượng công việc được ước tính trải dài trong 11 tuần, chia thành 4 giai đoạn. Trên thực tế, cả bốn hạng mục chính đều được hoàn thành trong vòng 2 sprint (2 tuần mỗi sprint) — dồn phần lớn khối lượng thực thi về cuối lịch trình so với kế hoạch ban đầu. Sự lệch này được trình bày chi tiết hơn ở phần Đề cương chi tiết, nơi đối chiếu trực tiếp kế hoạch ban đầu với lịch trình thực tế.

## 5.2. Ưu điểm và nhược điểm

Về ưu điểm, ứng dụng đáp ứng đầy đủ nhu cầu chức năng cốt lõi đã đặt ra ở Chương 1: giám sát và dự báo hiệu suất giao hàng một cách có hệ thống. Việc tách rõ ba chặng trong vòng đời đơn hàng giúp xác định chính xác điểm nghẽn đang nằm ở đâu, thay vì chỉ nhìn thấy một con số thời gian tổng gộp. Giao diện hỗ trợ song ngữ Việt và Anh, phù hợp cho cả nhân viên vận hành lẫn quản lý cấp trung. Toàn bộ bốn hạng mục công việc chính đã được hoàn thành đầy đủ, mang lại một ứng dụng vận hành trọn vẹn từ khâu giám sát, tạo đơn, đánh giá rủi ro đến quản trị người dùng, chứ không dừng lại ở một vài chức năng rời rạc.

Về nhược điểm, điểm F1 của mô hình tại mốc đặt hàng — 19,72% — vẫn còn thấp hơn mục tiêu đã đặt ra là 30%, dù đã có nhiều nỗ lực cải thiện có hệ thống như đã trình bày ở Chương 4. Ứng dụng hiện chỉ hỗ trợ xuất dữ liệu ra định dạng CSV, chưa có khả năng xuất PDF hoặc Excel. Hệ thống cũng chưa có lịch giám sát hoặc cơ chế cảnh báo tự động theo định kỳ, chưa hỗ trợ phân quyền theo khu vực địa lý, và chưa có một quy trình tự động để huấn luyện lại mô hình hoặc cảnh báo khi mô hình bị suy giảm chất lượng theo thời gian. Ngoài ra, trang quản trị tài khoản hiện chưa tự làm mới dữ liệu khi vai trò của một người dùng khác vừa được thay đổi ở một phiên làm việc khác — dẫn đến trường hợp thao tác bị máy chủ từ chối đúng theo quy tắc phân quyền, nhưng giao diện lại chưa giải thích rõ lý do cho người dùng.

## 5.3. Hướng phát triển

Trên cơ sở những hạn chế đã nêu, đề tài có thể phát triển thêm theo một số hướng sau: tối ưu hoá tuyến đường giao hàng; hỗ trợ dự đoán rủi ro theo lô thay vì chỉ từng đơn hàng riêng lẻ; bổ sung khả năng giải thích được mô hình, để người dùng hiểu vì sao một đơn hàng cụ thể bị xếp vào mức rủi ro cao; xây dựng quy trình huấn luyện lại mô hình tự động kèm cảnh báo khi chất lượng mô hình suy giảm theo thời gian; và xem xét quay lại phương án phân loại theo từng mốc nếu điểm F1 tiếp tục không cải thiện được qua các lần thử nghiệm tiếp theo. Về mặt giao diện, cần bổ sung thông báo giải thích rõ lý do khi một thao tác quản trị tài khoản bị từ chối. Về định hướng dài hạn, đúng như đề cương ban đầu đã đặt ra, ứng dụng có tiềm năng mở rộng thành một hệ thống quản lý chuỗi cung ứng hoàn chỉnh hơn, tích hợp thêm các mô-đun thông minh khác.
