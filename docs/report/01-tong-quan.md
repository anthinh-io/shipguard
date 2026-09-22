# CHƯƠNG 1. TỔNG QUAN ĐỀ TÀI NGHIÊN CỨU

## 1.1. Nhu cầu thực tế của đề tài

Trong lĩnh vực giao vận và thương mại điện tử hiện đại, một đơn hàng không đến tay khách hàng ngay lập tức mà phải đi qua nhiều chặng liên tiếp — từ khâu duyệt thanh toán, đến khâu người bán chuẩn bị hàng, rồi mới đến khâu vận chuyển. Rủi ro giao trễ có thể phát sinh ở bất kỳ chặng nào trong chuỗi đó, và một khi đã xảy ra thì hậu quả không chỉ dừng lại ở một đơn hàng bị trễ đơn thuần.

Trên thực tế, các doanh nghiệp quản lý hậu cần hiện nay phần lớn thiếu một công cụ giám sát hiệu suất giao hàng có hệ thống. Vấn đề vì thế chỉ được phát hiện sau khi đã xảy ra — mang tính phản ứng — chứ không có cơ chế cảnh báo sớm để can thiệp kịp thời. Hệ quả là doanh nghiệp phải gánh chi phí đền bù, hoàn tiền, đồng thời uy tín với khách hàng bị ảnh hưởng, trong khi bản thân họ lại thiếu một nguồn dữ liệu có cấu trúc để cải thiện vận hành về lâu dài.

Chính vì vậy, một ứng dụng chuyên biệt là cần thiết, thay vì tiếp tục dựa vào các báo cáo thủ công rời rạc. Hệ thống cần theo dõi tình hình gần với thời gian thực, đồng thời phải có khả năng dự đoán — chứ không chỉ mô tả lại những gì đã xảy ra trong quá khứ. Và hệ thống ấy cần phục vụ được cả hai cấp độ theo dõi: một cái nhìn tổng quan trên toàn hệ thống, và khả năng đi sâu vào từng đơn hàng cụ thể khi cần.

## 1.2. Khảo sát hiện trạng

Trước khi xây dựng ứng dụng, việc khảo sát dựa trên bộ dữ liệu công khai Olist — một bộ dữ liệu thương mại điện tử thực tế tại Brazil — được dùng làm nền để xây dựng và kiểm chứng mô hình dự báo. Số liệu khảo sát cho thấy tỷ lệ trễ nền trên toàn bộ tập dữ liệu ở mức 6,77%, nhưng con số này không ổn định theo thời gian: có giai đoạn tỷ lệ trễ tăng vọt bất thường lên xấp xỉ 19% vào tháng 3 năm 2018, một sự kiện ngoại lai cho thấy rủi ro giao trễ không phân bố đều mà có thể bùng phát cục bộ theo thời điểm.

Đi sâu hơn vào từng chặng của vòng đời đơn hàng — chặng duyệt thanh toán, chặng người bán chuẩn bị hàng, và chặng vận chuyển — dữ liệu cho thấy một đặc điểm chung: phân phối thời gian xử lý lệch đuôi rất mạnh. Phần lớn đơn hàng được xử lý nhanh, trong khi một số ít đơn lại trễ kéo dài bất thường, kéo thời gian xử lý trung bình lên cao hơn nhiều so với thời gian xử lý điển hình của phần lớn đơn hàng.

Đây chính là hạn chế cốt lõi của các báo cáo thủ công hiện có: một báo cáo tĩnh, tổng hợp theo kỳ, không có khả năng bắt được đặc điểm lệch đuôi lẫn những đợt đột biến cục bộ theo thời điểm — trong khi chính hai đặc điểm này lại là nơi rủi ro giao trễ thực sự tập trung, và cũng là nơi cần cảnh báo sớm nhất.

## 1.3. Phát biểu bài toán

Từ những quan sát trên, bài toán đặt ra cho đề tài là: làm thế nào để ShipGuard có thể giúp doanh nghiệp giao vận giám sát, phân tích và dự báo hiệu suất giao hàng một cách có hệ thống, qua đó phát hiện sớm những đơn hàng có nguy cơ giao trễ, thay vì chỉ nhận biết vấn đề sau khi nó đã xảy ra như hiện trạng đã nêu.

Để giải quyết bài toán này, đề tài xây dựng một ứng dụng gồm hai thành phần vận hành song song và kết nối với nhau qua giao diện lập trình ứng dụng dạng REST. Thành phần thứ nhất là một bảng điều khiển vận hành, cho phép xem chỉ số hiệu suất chính, quản lý danh sách đơn hàng, và nhập thông tin đơn hàng mới kèm kết quả dự báo. Thành phần thứ hai là một mô hình học máy dự báo rủi ro giao trễ, được đóng gói thành một dịch vụ REST API riêng để thành phần thứ nhất có thể gọi đến khi cần.

Mục tiêu cuối cùng của đề tài, vì vậy, không chỉ dừng lại ở việc xây dựng một công cụ kỹ thuật, mà hướng đến việc tạo ra một công cụ thực sự hỗ trợ được doanh nghiệp giao vận trong việc theo dõi, phân tích và dự báo hiệu suất giao hàng, thay thế cho quy trình quản lý thủ công vốn thiếu tính hệ thống. Ứng dụng được thiết kế theo hướng đơn giản và trực quan, để phù hợp với cả nhân viên vận hành trực tiếp lẫn quản lý cấp trung — hai nhóm người dùng có nhu cầu sử dụng khác nhau nhưng đều cần một công cụ dễ tiếp cận.
