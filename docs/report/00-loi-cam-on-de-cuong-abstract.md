# LỜI CẢM ƠN

Trên thực tế không có sự thành công nào mà không gắn liền với những sự hỗ trợ, giúp đỡ, dù ít hay nhiều, dù trực tiếp hay gián tiếp của người khác. Trong suốt quá trình thực hiện đồ án môn học này, em đã nhận được rất nhiều sự quan tâm, giúp đỡ từ quý thầy cô.

Với lòng biết ơn sâu sắc nhất, em xin chân thành cảm ơn thầy Mai Xuân Hùng đã tận tâm hướng dẫn em trong suốt quá trình thực hiện đồ án, giải đáp kịp thời các thắc mắc của em. Nếu không có những lời hướng dẫn của thầy thì em nghĩ báo cáo này khó có thể hoàn thành được.

Đồ án được thực hiện trong khoảng 10 tuần (15/07/2026 – 23/09/2026), do đó khó tránh khỏi những thiếu sót. Em rất mong nhận được những ý kiến đóng góp quý báu của thầy để ứng dụng cũng như kiến thức của em được hoàn thiện hơn.

Sau cùng, em kính chúc thầy thật nhiều sức khỏe, tiếp tục thực hiện sứ mệnh cao đẹp của mình là truyền đạt kiến thức cho thế hệ mai sau.

---

# TÓM TẮT ĐỒ ÁN

Các doanh nghiệp giao vận và thương mại điện tử thường thiếu một cách theo dõi hiệu suất giao hàng có hệ thống, và chỉ phát hiện được đơn hàng giao trễ sau khi khách hàng đã phàn nàn. ShipGuard được xây dựng để giải quyết khoảng trống này, gồm hai thành phần kết nối với nhau: một bảng điều khiển vận hành phục vụ theo dõi chỉ số KPI giao hàng, quản lý đơn hàng, và ghi nhận các mốc trong vòng đời đơn hàng; cùng một dịch vụ học máy dự đoán rủi ro giao trễ.

Đề cương ban đầu của đề tài đề xuất một bộ phân loại nhị phân, huấn luyện một lần để gán nhãn đúng hạn hoặc trễ cho từng đơn hàng, đánh giá bằng Accuracy, F1-score và ROC-AUC, với mục tiêu F1 đạt 0,78. Trong quá trình thực hiện, cách tiếp cận này đã được điều chỉnh: mỗi mốc mới trong vòng đời đơn hàng cần một đánh giá rủi ro riêng, dựa trên thời gian thực tế của các chặng đã hoàn thành; đồng thời việc tách riêng một mô hình phân loại và một mô hình xác định nguyên nhân có nguy cơ dẫn đến kết luận không nhất quán. Vì vậy, hệ thống thực tế dự đoán một phân phối rủi ro theo ba chặng của vòng đời đơn hàng — duyệt thanh toán, người bán chuẩn bị hàng, và vận chuyển — và đánh giá lại rủi ro ở mỗi mốc mới. F1 vẫn là chỉ số chính dùng để chọn thuật toán và ngưỡng, với mục tiêu được điều chỉnh xuống còn 0,30 do tỷ lệ trễ nền của bộ dữ liệu khá thấp (khoảng 6,8%); Accuracy và ROC-AUC được bổ sung sau như những chỉ số tham khảo thêm, không thay thế F1.

Xây dựng trên bộ dữ liệu thương mại điện tử Olist của Brazil (khoảng 100.000 đơn hàng), mô hình được chọn đạt điểm F1 là 19,72% tại mốc đặt hàng — thấp hơn mục tiêu 30% dù đã có nhiều nỗ lực cải thiện có hệ thống, bao gồm thay đổi đặc trưng, tinh chỉnh siêu tham số, thử các tỷ lệ chia tập dữ liệu khác nhau, và so sánh với các thuật toán khác. Báo cáo trình bày trung thực kết quả này, song song với bộ chức năng đã hoàn thành: bảng điều khiển hiệu suất, quản lý đơn hàng, đánh giá và xử lý rủi ro, theo dõi độ tin cậy của mô hình, và quản trị tài khoản người dùng theo phân quyền.

---

# ABSTRACT

Logistics and e-commerce businesses often lack a systematic way to monitor delivery performance, discovering late shipments only after customers have already complained. ShipGuard addresses this gap with two connected components: an operations dashboard for tracking delivery KPIs, managing orders, and recording order lifecycle milestones; and a machine learning API that predicts the risk of late delivery.

The original project outline proposed a one-time binary classifier (on-time vs. late) evaluated by Accuracy, F1-score, and ROC-AUC, targeting an F1 of 0.78. During development this approach was revised: each new order-lifecycle milestone needs its own updated risk assessment using the actual elapsed time of completed stages, and separating a classifier from a root-cause model risked inconsistent conclusions. The system instead predicts a distribution over three delivery stages — payment approval, seller handling, carrier transit — and re-evaluates risk at every milestone. F1 remains the primary metric for selecting the algorithm and threshold, with a revised target of 0.30 given the dataset's low baseline late rate (about 6.8%); Accuracy and ROC-AUC were added later as supplementary context, not replacements.

Built on the Olist Brazilian e-commerce dataset (about 100,000 orders), the selected model (sklearn_quantile) reaches an F1-score of 0.1972 at the order-placed checkpoint — below the 0.30 target despite systematic improvement attempts, including feature changes, hyperparameter tuning, alternative train/validation/test splits, and alternative algorithms (XGBoost, LightGBM). The report documents this result honestly alongside the completed feature set: performance dashboard, order management, risk assessment and intervention tracking, model-confidence monitoring, and role-based user administration.

---

# ĐỀ CƯƠNG CHI TIẾT

| Trường | Nội dung |
| --- | --- |
| Tên đề tài | Xây dựng ứng dụng hỗ trợ quản lý và dự báo hiệu suất giao hàng trong lĩnh vực giao vận |
| Tên đề tài (tiếng Anh) | Developing a web application for managing and predicting delivery performance in logistics |
| Cán bộ hướng dẫn | ThS. Mai Xuân Hùng |
| Thời gian thực hiện | Từ ngày 15/07/2026 đến ngày 23/09/2026 |
| Sinh viên thực hiện | Nguyễn Thanh Thịnh — MSSV 22730096 |
| Công nghệ/mô hình/công cụ | Chưa cố định trong đề cương gốc — công nghệ thực tế được chọn ở Giai đoạn 3 của kế hoạch thực hiện bên dưới, xem Chương 4.2 "Môi trường triển khai" |

## Mô tả chi tiết

Trong lĩnh vực giao vận và chuỗi cung ứng, việc quản lý hiệu suất giao hàng thường dựa trên các quy trình thủ công, thiếu khả năng dự báo và phân tích dữ liệu một cách hệ thống. Điều này dẫn đến khó khăn trong việc phát hiện sớm các đơn hàng có nguy cơ giao trễ, ảnh hưởng đến sự hài lòng của khách hàng và hiệu quả vận hành.

Đề tài xây dựng ứng dụng web tích hợp hai thành phần song song:

**Thành phần 1 — Ứng dụng web quản lý vận hành:**
- Dashboard tổng quan: hiển thị KPI giao hàng (tỉ lệ đúng hạn, phân bổ theo khu vực, xu hướng theo thời gian).
- Quản lý danh sách đơn hàng: tìm kiếm, lọc, xem chi tiết từng đơn.
- Nhập thông tin đơn hàng mới và hiển thị kết quả dự báo.

**Thành phần 2 — Mô hình AI/ML dự báo rủi ro giao trễ:**
- Phân tích và tiền xử lý bộ dữ liệu Olist Brazilian E-Commerce (Kaggle, khoảng 100.000 đơn hàng).
- Trích xuất đặc trưng: địa lý, khối lượng sản phẩm, lịch sử người bán, danh mục hàng hóa.
- Xây dựng mô hình phân loại nhị phân (giao đúng hạn / giao trễ).
- So sánh các thuật toán: Logistic Regression, Random Forest, XGBoost.
- Đánh giá theo chỉ số Accuracy, F1-score, ROC-AUC.
- Triển khai mô hình thành REST API phục vụ ứng dụng web.

Hai thành phần được kết nối qua REST API, cho phép người dùng nhập thông tin đơn hàng và nhận kết quả dự báo nguy cơ giao trễ trực tiếp trên giao diện.

## Phương pháp thực hiện

1. **Khảo sát và phân tích bài toán** — Mục tiêu dự kiến: nắm vững bài toán, dữ liệu và yêu cầu hệ thống. Phương pháp: đọc tài liệu, ghi chú, viết báo cáo nội dung tìm hiểu; phân tích khám phá dataset của Olist, đặc tả yêu cầu chức năng và phi chức năng, thiết kế wireframe giao diện.
2. **Xây dựng mô hình AI/ML** — Mục tiêu dự kiến: có mô hình dự báo rủi ro giao trễ đạt F1-score ≥ 0,78 và REST API hoạt động ổn định. Phương pháp: tiền xử lý dữ liệu, trích xuất đặc trưng, huấn luyện và so sánh các mô hình phân loại, đóng gói mô hình tốt nhất thành API.
3. **Phát triển ứng dụng sản phẩm** — Mục tiêu dự kiến: ứng dụng hoàn chỉnh với đầy đủ chức năng dashboard, quản lý đơn hàng và tích hợp mô đun dự báo. Phương pháp: triển khai sản phẩm trên công nghệ đã tìm hiểu.
4. **Kiểm thử, đánh giá và hoàn thiện sản phẩm** — Mục tiêu dự kiến: sản phẩm hoàn thiện, tài liệu sản phẩm đầy đủ. Phương pháp: kiểm thử chức năng, đánh giá hiệu năng mô hình, tinh chỉnh giao diện, viết báo cáo kỹ thuật cho sản phẩm.

## Kết quả mong đợi của đề tài

Xây dựng ứng dụng trở thành một công cụ hỗ trợ đắc lực cho các doanh nghiệp giao vận trong việc theo dõi, phân tích và dự báo hiệu suất giao hàng, giúp thay thế các quy trình quản lý thủ công vốn thiếu tính hệ thống và khó phát hiện sớm rủi ro vận hành.

Không những thế, trong bối cảnh chuyển đổi số đang diễn ra mạnh mẽ ở thời đại công nghiệp 4.0, ứng dụng còn có tiềm năng mở rộng và tích hợp thêm các mô đun thông minh — từ tối ưu hóa tuyến đường đến trợ lý AI hỗ trợ nghiệp vụ — tạo nền tảng để phát triển thành hệ thống quản lý chuỗi cung ứng hoàn chỉnh trong khóa luận tốt nghiệp.

Ứng dụng được thiết kế đơn giản, trực quan và dễ sử dụng, phù hợp cho cả nhân viên vận hành lẫn quản lý cấp trung, giúp mở rộng khả năng tiếp cận và ứng dụng thực tế của sản phẩm trong môi trường doanh nghiệp.

## Kế hoạch thực hiện

Đây là kế hoạch **dự kiến ban đầu**, khác với lịch trình **thực tế** đã trình bày ở Chương 5.1 — sự chênh lệch giữa hai bảng này là một phần nội dung "kế hoạch so với thực tế" của báo cáo.

| STT | Thời gian | Nội dung |
| --- | --- | --- |
| 1 | 07/07 – 15/07 | Đăng ký đề tài môn học, viết đề cương khoá luận |
| 2 | 16/07 – 29/07 | Nghiên cứu bài toán quản lý giao hàng; phân tích khám phá dữ liệu Olist; xác định yêu cầu chức năng/phi chức năng; thiết kế wireframe |
| 3 | 30/07 – 12/08 | Tìm hiểu thuật toán phân loại; nghiên cứu kỹ thuật trích xuất đặc trưng; viết báo cáo tổng kết Giai đoạn 1 |
| 4 | 13/08 – 24/08 | Tiền xử lý dữ liệu và trích xuất đặc trưng; huấn luyện/so sánh mô hình; đóng gói mô hình tốt nhất thành REST API |
| 5 | 25/08 – 03/09 | Xây dựng cấu trúc phía máy chủ và API endpoints; phát triển giao diện phía máy khách cơ bản; viết báo cáo tổng kết Giai đoạn 2 |
| 6 | 04/09 – 13/09 | Phát triển dashboard và biểu đồ phân tích hiệu suất; tích hợp mô đun AI dự báo; hoàn thiện chức năng quản lý đơn hàng |
| 7 | 14/09 – 18/09 | Kiểm thử chức năng toàn bộ hệ thống; đánh giá hiệu năng mô hình; viết báo cáo tổng kết Giai đoạn 3 |
| 8 | 19/09 – 23/09 | Tinh chỉnh giao diện, sửa lỗi sau kiểm thử; viết báo cáo hoàn chỉnh |
