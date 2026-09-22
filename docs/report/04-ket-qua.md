# CHƯƠNG 4. KẾT QUẢ DỰ ÁN

## 4.1. Giới thiệu sản phẩm

ShipGuard là một ứng dụng hỗ trợ quản lý và dự báo hiệu suất giao hàng trong lĩnh vực giao vận, được xây dựng từ hai thành phần kết nối với nhau qua giao diện lập trình ứng dụng dạng REST: một bảng điều khiển vận hành phục vụ theo dõi và quản lý, và một mô hình học máy đóng vai trò dự đoán rủi ro giao trễ.

Về phía bảng điều khiển vận hành, ứng dụng cung cấp đầy đủ các nhóm chức năng chính. Dashboard hiệu suất hiển thị các chỉ số KPI giao hàng, xu hướng biến động theo thời gian, và cho phép so sánh giữa các kỳ báo cáo khác nhau. Chức năng quản lý đơn hàng cho phép tra cứu, lọc, xuất dữ liệu ra tệp CSV, tạo đơn hàng mới, xem chi tiết từng đơn, ghi nhận và chỉnh sửa các mốc trong vòng đời đơn hàng, huỷ đơn khi cần, cũng như ghi chú nội bộ cho từng đơn. Song song đó, chức năng quản lý đánh giá rủi ro cho phép xem lại lịch sử đánh giá của từng đơn, ghi nhận biện pháp can thiệp đã thực hiện, và lọc danh sách đơn theo mức rủi ro hoặc trạng thái xử lý. Một trang chỉ số độ tin cậy mô hình cho phép theo dõi các chỉ số F1, Precision, Recall, Accuracy và ROC-AUC theo từng thuật toán, cùng một bảng đối chiếu tích luỹ dựa trên kết quả giao hàng thật. Cuối cùng, chức năng quản lý tài khoản người dùng cho phép tạo, khoá/mở khoá, đặt lại mật khẩu và đổi vai trò cho từng tài khoản.

Toàn bộ các nhóm chức năng trên đã được hoàn thành đầy đủ, tạo thành một ứng dụng vận hành trọn vẹn từ khâu giám sát hiệu suất, quản lý đơn hàng, dự đoán và xử lý rủi ro, đến quản trị tài khoản người dùng. Cấu trúc công việc và tiến độ hoàn thành cụ thể được trình bày riêng ở Chương 5.1.

## 4.2. Môi trường triển khai

Về cơ sở dữ liệu, hệ thống sử dụng PostgreSQL phiên bản 18, được triển khai thông qua Docker Compose.

Về phía máy chủ, hệ thống được xây dựng trên Python phiên bản 3.12 trở lên, quản lý gói bằng công cụ uv, sử dụng FastAPI (phiên bản từ 0.115) làm framework chính, SQLAlchemy phiên bản 2.0 ở chế độ bất đồng bộ kết hợp với asyncpg để thao tác với cơ sở dữ liệu, và Alembic (từ phiên bản 1.14) để quản lý lược đồ. Mật khẩu người dùng được băm bằng pwdlib với thuật toán Argon2, còn phiên đăng nhập được xác thực bằng token theo chuẩn PyJWT.

Về phần học máy, ba thuật toán ứng viên — scikit-learn, XGBoost và LightGBM — được huấn luyện và so sánh với nhau để chọn ra mô hình dự đoán rủi ro phù hợp nhất, nội dung này được trình bày chi tiết hơn ở mục 4.3.

Về phía giao diện người dùng, hệ thống được xây dựng bằng Next.js phiên bản 16.3.4, React phiên bản 19.2.8 và TypeScript, quản lý gói bằng Bun.

Đây là bộ công nghệ thực tế đã dùng để xây dựng ứng dụng, khác với công nghệ được đề xuất ban đầu trong đề cương — nội dung này được làm rõ hơn ở phần Đề cương chi tiết.

## 4.3. Kết luận kết quả

Về mặt kỹ thuật, hệ thống đã được xây dựng đúng theo thiết kế trình bày ở Chương 2, với đầy đủ tám nhóm chức năng chính, ba vai trò người dùng, và mười hai bảng trong cơ sở dữ liệu. Tuy nhiên, trong quá trình thực hiện, có hai điểm khác biệt đáng chú ý giữa kế hoạch ban đầu và kết quả thực tế, cả hai đều liên quan trực tiếp đến mô hình dự báo rủi ro.

Điểm khác biệt thứ nhất nằm ở cách tiếp cận bài toán học máy. Đề cương ban đầu đề xuất xây dựng một bộ phân loại nhị phân, huấn luyện một lần duy nhất để gán nhãn đúng hạn hoặc trễ cho mỗi đơn hàng, với mục tiêu đạt điểm F1 từ 0,78 trở lên. Trong quá trình thực hiện, cách tiếp cận này đã được điều chỉnh: hệ thống thực tế dự đoán một phân phối rủi ro theo ba chặng của vòng đời đơn hàng — duyệt thanh toán, người bán chuẩn bị hàng, và vận chuyển — đồng thời đánh giá lại rủi ro ở mỗi mốc mới phát sinh, với mục tiêu F1 được điều chỉnh xuống còn 0,30. Sự điều chỉnh này xuất phát từ hai lý do nghiệp vụ cụ thể: mỗi khi có một mốc mới trong vòng đời đơn hàng, hệ thống cần sinh lại một đánh giá rủi ro dựa trên thời gian thực tế của các chặng đã hoàn thành, điều mà một bộ phân loại huấn luyện một lần duy nhất không tự nhiên đáp ứng được; đồng thời, việc tách riêng một mô hình phân loại và một mô hình khác chỉ để xác định nguyên nhân rủi ro có nguy cơ dẫn đến những kết luận không nhất quán giữa xác suất dự đoán và nguyên nhân được đưa ra.

Điểm khác biệt thứ hai là kết quả đánh giá mô hình chưa đạt được mục tiêu đã đặt ra. Cụ thể, điểm F1 tại mốc đặt hàng của mô hình được chọn đạt 19,72%, thấp hơn mục tiêu 30% đã đề ra. Kết quả này được trình bày trung thực trong báo cáo, không che giấu, cùng với bằng chứng cho thấy đã có nhiều nỗ lực cải thiện một cách có hệ thống trước khi đi đến kết luận này — bao gồm việc thử nghiệm các đặc trưng khác nhau, tinh chỉnh siêu tham số, thay đổi tỷ lệ chia tập huấn luyện/kiểm định/kiểm tra, và so sánh với các thuật toán khác. Hai điểm khác biệt này sẽ được bàn tiếp trong phần nhược điểm và hướng phát triển ở Chương 5.

Về mặt quản lý — hiểu theo nghĩa giá trị vận hành mà ứng dụng mang lại cho người dùng cuối, không phải theo nghĩa quản lý tiến độ dự án — ShipGuard giúp doanh nghiệp giao vận theo dõi, phân tích và dự báo hiệu suất giao hàng một cách có hệ thống, thay thế cho quy trình quản lý thủ công. Hệ thống cho phép phát hiện sớm những đơn hàng có nguy cơ giao trễ một cách chủ động, thay vì chỉ nhận biết vấn đề sau khi đã xảy ra như hiện trạng đã nêu ở Chương 1. Giao diện được thiết kế đơn giản và trực quan, phù hợp cho cả nhân viên vận hành trực tiếp lẫn quản lý cấp trung, đồng thời tập trung việc quản lý tài khoản người dùng và phân quyền về một nơi duy nhất, rõ ràng theo từng vai trò.
