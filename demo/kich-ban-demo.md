# Kịch bản video Demo ShipGuard

Người thực hiện: Nguyễn Thanh Thịnh, MSSV 22730096. Thời lượng dự kiến khoảng 14 phút 15 giây. Video ghép từ các đoạn trong thư mục clips; lời thuyết minh do người thực hiện đọc hoặc dùng công cụ đọc văn bản của Clipchamp.

## Cách dựng video

Các đoạn được quay tự động bằng Playwright ở kích thước 1536x864 (16:9), định dạng .webm, không có tiếng. Mỗi cảnh một tệp, tên tệp nằm ở đầu từng cảnh bên dưới. Cột "Thời điểm" là mốc giây trong đúng đoạn đó, nên đọc lời thuyết minh tới dòng nào thì màn hình đang ở bước đó.

Các bước trong Clipchamp (có sẵn trong Windows 11):

1. Tạo video mới, nhập lần lượt các tệp trong clips theo thứ tự cảnh. Cảnh 1 có phần dòng lệnh chèn giữa hai tệp (xem Cảnh 1).
2. Đặt các đoạn nối tiếp nhau trên dòng thời gian, xuất bản ghi tiếng bằng nút Ghi âm (đọc lời thuyết minh theo từng cảnh) hoặc dán lời thuyết minh vào công cụ chuyển văn bản thành giọng nói, chọn giọng tiếng Việt.
3. Nếu lời thuyết minh dài hơn đoạn video thì kéo dài khung hình cuối của đoạn đó; nếu ngắn hơn thì cắt bớt phần chờ ở cuối đoạn.
4. Xuất MP4 độ phân giải 1080p, lưu vào thư mục Demo của gói nộp.

Ghi chú về hình ảnh: trong video, ô ngày giờ hiển thị ngày/tháng/năm; mốc trong "Dòng thời gian" của đơn hiển thị theo giờ UTC còn "Thời điểm đánh giá" hiển thị theo giờ máy nên lệch 7 giờ ở Việt Nam. Danh mục sản phẩm hiện nhãn tiếng Anh vì dữ liệu Olist đặt tên như vậy.

## Cảnh 1. Mở đầu và chạy một lệnh (1:30)

Vai trò: chưa đăng nhập. Ba tệp và một đoạn tự quay:

- canh-1a-tieu-de.webm (19 giây): thẻ tiêu đề.
- Đoạn dòng lệnh (khoảng 45 giây): bạn tự quay bằng Xbox Game Bar (Win + Alt + R), mở terminal trong thư mục Source, chạy `docker compose up -d --build --wait` rồi `docker compose ps`. Nếu không tự quay, dùng canh-1-terminal-tinh.webm (30 giây), ảnh tĩnh kết quả `docker compose ps` thật của dự án đang chạy.
- canh-1b-dang-nhap.webm (25 giây): trang đăng nhập http://localhost:3000.

| Thời điểm | Thao tác | Lời thuyết minh |
| --- | --- | --- |
| 1a, 0:00 | Thẻ tiêu đề: tên ứng dụng, sinh viên, giảng viên | "Xin chào thầy. Em là Nguyễn Thanh Thịnh, mã số sinh viên 22730096. Đây là phần trình diễn ứng dụng ShipGuard, ứng dụng quản lý và dự đoán hiệu suất giao hàng bằng học máy. Ứng dụng giúp bộ phận hậu cần biết sớm đơn nào có nguy cơ giao trễ để xử lý trước khi khách phải chờ." |
| Dòng lệnh, 0:00 | Chạy `docker compose up -d --build --wait` | "Toàn bộ hệ thống chạy bằng một lệnh duy nhất: docker compose up -d --build --wait. Lệnh này dựng cơ sở dữ liệu PostgreSQL và nạp sẵn chín mươi chín nghìn bốn trăm bốn mươi mốt đơn hàng, dựng máy chủ xử lý FastAPI cùng mô hình dự đoán đã huấn luyện, và dựng giao diện web Next.js." |
| Dòng lệnh, 0:30 | Chạy `docker compose ps`, ba dịch vụ đang chạy | "Kiểm tra lại bằng docker compose ps: cơ sở dữ liệu, máy chủ và giao diện đều đang chạy, ứng dụng sẵn sàng tại cổng 3000." |
| 1b, 0:00 | Trang đăng nhập | "Giờ em mở trình duyệt, vào địa chỉ localhost, cổng 3000. Ứng dụng có ba tài khoản thử tương ứng ba vai trò: Nhân viên vận hành, Quản lý hậu cần và Super Admin. Em sẽ đi qua một ngày làm việc của từng vai trò." |

## Cảnh 2. Nhân viên vận hành đầu ngày: bảng điều khiển và tra cứu đơn (2:15)

Tệp: canh-2-bang-dieu-khien.webm. Vai trò: operations_staff@shipguard.com, tên hiển thị "Operations Staff".

| Thời điểm | Thao tác | Lời thuyết minh |
| --- | --- | --- |
| 0:00 | Gõ email, mật khẩu, bấm "Đăng nhập"; vào Bảng điều khiển | "Đầu ngày, nhân viên vận hành đăng nhập và thấy ngay bảng điều khiển. Dữ liệu Olist là đơn lịch sử nên kỳ báo cáo mặc định là từ một tháng chín năm 2017 đến ba mươi mốt tháng tám năm 2018, đã có sẵn số liệu." |
| 0:20 | Di chuột lần lượt qua sáu thẻ số liệu | "Tỷ lệ giao đúng hạn là 92,23%, trên bảy mươi lăm nghìn năm trăm bốn mươi tám đơn đã giao, và có năm nghìn tám trăm sáu mươi tám đơn giao trễ. Ba thẻ tiếp theo cho biết thời gian từng chặng: duyệt thanh toán, người bán xử lý, vận chuyển. Nhờ đó biết chặng nào đang chậm." |
| 0:50 | Chọn so sánh "Kỳ liền trước", cuộn tới biểu đồ "Xu hướng tỷ lệ trễ" | "Biểu đồ xu hướng cho thấy tỷ lệ trễ theo thời gian, và có thể so sánh với kỳ liền trước để thấy tình hình đang tốt lên hay xấu đi." |
| 1:10 | Cuộn tới "Tỷ lệ trễ theo bang", di chuột lên một cột, bấm vào cột | "Biểu đồ theo bang cho biết bang nào trễ nhiều. Bấm vào một cột, hệ thống mở thẳng danh sách các đơn trễ của bang đó." |
| 1:30 | Trang Quản lý đơn hàng đã lọc: bấm "Xoá hết bộ lọc", cuộn qua các đơn đầu danh sách | "Danh sách có chín mươi chín nghìn bốn trăm năm mươi ba đơn. Mười hai đơn ở đầu là đơn thử em đã chuẩn bị sẵn để có số liệu cho phần đánh giá mô hình, còn lại là đơn Olist, cột Mức rủi ro hiện Chưa đánh giá vì ShipGuard chỉ đánh giá đơn tạo trong ứng dụng." |
| 1:50 | Gõ sáu ký tự đầu mã một đơn Olist đã giao vào ô tìm kiếm, bấm dòng kết quả, xem chi tiết | "Tra cứu một đơn chỉ cần gõ vài ký tự đầu của mã đơn. Trang chi tiết có dòng thời gian các mốc, thời gian từng chặng, sản phẩm, người bán, địa chỉ và đánh giá của khách. Các mốc trên dòng thời gian hiển thị theo giờ UTC." |
| 2:10 | Quay lại danh sách, bấm "Xuất CSV" | "Danh sách đang lọc có thể xuất ra tệp CSV bằng một nút bấm." |

## Cảnh 3. Tạo đơn: hẹn giao gấp và hẹn giao rộng rãi (4:30)

Tệp: canh-3-tao-don.webm. Vai trò: operations_staff@shipguard.com (đã đăng nhập sẵn khi cảnh bắt đầu, vì Cảnh 2 đã cho thấy cách đăng nhập).

Đơn B, hẹn giao gấp, quay trước. Các ô dùng chung cho hai đơn: thời điểm đặt hàng để mặc định (lúc này), bang SP, thành phố "sao paulo", mã bưu chính 01310, người bán gõ 1f50f920 rồi chọn dòng đầu (SP · sao jose do rio preto), danh mục furniture_decor, cân nặng 500, giá 120.5, phí vận chuyển 25.3, thanh toán thẻ tín dụng, số tiền 145.8, trả góp 2 kỳ.

| Thời điểm | Thao tác | Lời thuyết minh |
| --- | --- | --- |
| 0:00 | Bấm "Tạo đơn" ở trang danh sách | "Đây là chức năng chính của ShipGuard: tạo một đơn mới và biết ngay nguy cơ giao trễ. Em thử một đơn hẹn giao gấp trước." |
| 0:15 | Giữ thời điểm đặt hàng mặc định; ngày giao cam kết = hôm nay + 6 ngày | "Thời điểm đặt hàng để mặc định là lúc này. Em hẹn giao chỉ sau sáu ngày." |
| 0:35 | Bang SP; thành phố "sao paulo"; mã bưu chính 01310 | "Khách nhận hàng ở bang SP, thành phố São Paulo, mã bưu chính 01310." |
| 1:00 | Người bán 1f50f920; danh mục furniture_decor; cân nặng 500; giá 120.5; phí vận chuyển 25.3 | "Người bán chọn bằng cách gõ vài ký tự của mã rồi chọn trong danh sách gợi ý. Sản phẩm thuộc danh mục furniture_decor, nặng năm trăm gam, giá 120,5 và phí vận chuyển 25,3. Danh mục hiện nhãn tiếng Anh vì dữ liệu gốc Olist đặt tên như vậy." |
| 1:30 | Thanh toán thẻ tín dụng, số tiền 145.8, trả góp 2 kỳ; bấm "Tạo đơn" | "Thanh toán bằng thẻ tín dụng, số tiền bằng giá cộng phí vận chuyển là 145,8, trả góp hai kỳ. Em bấm tạo đơn." |
| 1:50 | Trang chi tiết: "Xác suất giao trễ" 92,00%, nhãn "Rủi ro cao", nguyên nhân dự kiến ở chặng người bán xử lý, người bán liên quan | "Hệ thống trả về xác suất giao trễ khoảng chín mươi hai phần trăm, nhãn Rủi ro cao, vì ngưỡng rủi ro cao là 18%. Đơn này còn cho biết nguyên nhân dự kiến ở chặng người bán xử lý: hẹn sáu ngày là quá gấp so với thời gian người bán này thường cần. Xác suất được ước lượng bằng mô phỏng nên mỗi lần tạo có thể lệch nhẹ." |
| 2:30 | Bấm "Ghi nhận xử lý", chọn "Nhắc hoặc ưu tiên người bán", ghi chú "Đã nhắc người bán ưu tiên đóng gói đơn này.", bấm "Lưu" | "Vì là đơn rủi ro cao nên có nút Ghi nhận xử lý. Nhân viên chọn biện pháp, ví dụ nhắc người bán ưu tiên, viết thêm ghi chú rồi lưu. ShipGuard chỉ ghi lại việc đã làm, không tự nhắc người bán hay đổi đơn vị vận chuyển." |
| 3:10 | Ở khối "Mốc vòng đời" bấm "Lưu" cho mốc "Duyệt thanh toán"; hiện lần đánh giá mới và mục "Các lần đánh giá trước" | "Khi đơn đi qua từng mốc, nhân viên ghi nhận mốc đó. Em ghi nhận Duyệt thanh toán. Mỗi mốc sinh thêm một lần đánh giá rủi ro mới với thông tin mới hơn, các lần trước được xếp xuống mục Các lần đánh giá trước. Thời điểm đánh giá hiển thị theo giờ máy nên lệch bảy giờ so với dòng thời gian, vì dòng thời gian dùng giờ UTC." |
| 3:40 | Ô "Ghi chú nội bộ": gõ "Đã liên hệ người bán, hẹn bàn giao vận chuyển trong ngày mai.", bấm "Gửi ghi chú" | "Cuối cùng là ghi chú nội bộ. Ghi chú hiện kèm tên người viết, vai trò và thời điểm, không sửa hay xóa được." |

Đơn A, hẹn giao rộng rãi, quay sau, chỉ khác ngày giao cam kết:

| Thời điểm | Thao tác | Lời thuyết minh |
| --- | --- | --- |
| 3:55 | Tạo đơn thứ hai với các ô như đơn B, ngày giao cam kết = hôm nay + 25 ngày (điền nhanh) | "Bây giờ em tạo đơn thứ hai, cùng người bán, cùng sản phẩm, chỉ khác một điểm: hẹn giao trong hai mươi lăm ngày." |
| 4:15 | Trang chi tiết: xác suất 3,90%, nhãn "Rủi ro thấp", không có nút Ghi nhận xử lý | "Kết quả khoảng bốn phần trăm, Rủi ro thấp, và không có nguyên nhân hay nút xử lý. Cùng một đơn hàng, chỉ đổi cam kết giao, mô hình cho hai kết luận trái ngược." |

Xác suất là ước lượng bằng mô phỏng, mỗi lần quay lại có thể lệch nhẹ (lần quay này: 92,00% và 3,90%). Nếu quay lại, đọc lại số trên màn hình.

## Cảnh 4. Hủy đơn (0:45)

Tệp: canh-4-huy-don.webm. Vai trò: operations_staff@shipguard.com (đã đăng nhập sẵn). Bắt đầu từ trang chi tiết đơn A của Cảnh 3.

| Thời điểm | Thao tác | Lời thuyết minh |
| --- | --- | --- |
| 0:00 | Khối "Mốc vòng đời", bấm "Hủy đơn", hiện hộp thoại "Hủy đơn này?" | "Khách đổi ý thì nhân viên hủy đơn. Hệ thống hỏi lại vì thao tác này không hoàn tác được." |
| 0:15 | Bấm "Giữ đơn", mở lại hộp thoại, bấm "Xác nhận hủy đơn"; trạng thái thành "Đã hủy" | "Nếu chọn Giữ đơn thì đơn không đổi. Xác nhận thì đơn chuyển sang Đã hủy và không ghi nhận thêm mốc nào nữa. Đơn hủy không tính vào phần đối chiếu dự đoán." |

## Cảnh 5. Quản lý hậu cần xem Chỉ số mô hình (2:00)

Tệp: canh-5-chi-so-mo-hinh.webm. Vai trò: logistics_manager@shipguard.com, tên hiển thị "Logistics Manager".

| Thời điểm | Thao tác | Lời thuyết minh |
| --- | --- | --- |
| 0:00 | Đăng nhập bằng Quản lý hậu cần, mở "Chỉ số mô hình" | "Giờ em đăng nhập bằng Quản lý hậu cần, người cần biết mô hình có đáng tin để dựa vào hay không. Ba vai trò đều xem được trang Chỉ số mô hình." |
| 0:15 | Chỉ vào phiên bản mô hình, thuật toán đang dùng, ngưỡng 18% | "Trang cho biết phiên bản mô hình, thuật toán đang dùng và ngưỡng rủi ro cao đang áp dụng là 18%." |
| 0:30 | Dừng ở thẻ "F1 ở mốc đặt hàng" và nhãn "Chưa đạt" | "Em nói thẳng kết quả này: F1 ở mốc đặt hàng là 19,72%, trong khi mục tiêu đề ra là 30%, nên nhãn hiện Chưa đạt. Đây là kết quả thật của mô hình, không phải lỗi ứng dụng. Nguyên nhân đã được phân tích ở Chương 4 báo cáo. Em không chỉnh số liệu để đẹp hơn." |
| 1:00 | Cuộn tới bảng "So sánh thuật toán ứng viên" | "Bảng này so sánh các thuật toán đã thử trên cùng tập kiểm tra cố định khi huấn luyện, thuật toán được chọn có nhãn Đang dùng." |
| 1:20 | Bảng "Đối chiếu tích lũy trên đơn thật": 12 lần đối chiếu, 8 đúng, 4 sai, cảnh báo mẫu nhỏ | "Bảng dưới so dự đoán với kết quả giao hàng thật. Mỗi khi nhân viên ghi nhận Khách nhận hàng cho một đơn tạo trong ứng dụng, hệ thống đối chiếu dự đoán với kết quả thực rồi cộng vào đây. Bảng này ban đầu trống. Trước khi quay, em đã tạo mười hai đơn đặt lùi bốn mươi ngày và ghi nhận đủ ba mốc, nên bảng có mười hai lần đối chiếu ở mỗi điểm đánh giá, tám đúng và bốn sai. Số lần còn ít, trang cũng cảnh báo chưa đủ để kết luận chắc." |

## Cảnh 6. Super Admin quản trị tài khoản và phân quyền (2:30)

Tệp: canh-6-quan-tri.webm. Vai trò lần lượt: admin@shipguard.local (Super Admin), logistics_manager@shipguard.com, operations_staff@shipguard.com.

| Thời điểm | Thao tác | Lời thuyết minh |
| --- | --- | --- |
| 0:00 | Đăng nhập Super Admin, mở "Quản trị" | "Cuối cùng là quản trị. Em đăng nhập bằng Super Admin. Mục Quản trị liệt kê tài khoản với vai trò và trạng thái." |
| 0:15 | Bấm "Tạo tài khoản": tên "Nguyễn Văn An", email an.nguyen@congty.com, vai trò "Nhân viên vận hành", mật khẩu ban đầu; bấm "Tạo" | "Super Admin tạo tài khoản mới. Người mới đăng nhập được ngay." |
| 0:45 | Menu "..." của dòng An: mở "Đổi vai trò" (không chọn), rồi "Khóa tài khoản" và "Khóa" | "Menu thao tác có đổi vai trò, khóa tài khoản và đặt lại mật khẩu. Khóa thì tài khoản không đăng nhập được nữa, các phiên đang mở bị đăng xuất chậm nhất sau mười lăm phút." |
| 1:10 | Menu "..." rồi "Mở khóa"; menu rồi "Đặt lại mật khẩu", gõ hai lần, bấm "Hủy" | "Mở khóa thì đăng nhập lại được. Đặt lại mật khẩu thì nhập mật khẩu mới hai lần; ở đây em hủy để không đổi." |
| 1:35 | Đăng xuất, đăng nhập Quản lý hậu cần, mở Quản trị; dấu "..." chỉ có ở hai dòng Nhân viên vận hành; mở "Tạo tài khoản" rồi mở ô Vai trò, chỉ thấy Nhân viên vận hành; đóng hộp thoại | "Quản lý hậu cần cũng vào được Quản trị, nhưng chỉ quản lý tài khoản của Nhân viên vận hành: dấu ba chấm không hiện ở các dòng khác, và khi tạo tài khoản chỉ chọn được Nhân viên vận hành. Đổi vai trò chỉ Super Admin làm được." |
| 2:00 | Đăng xuất, đăng nhập Nhân viên vận hành; thanh bên chỉ có ba mục; truy cập thẳng địa chỉ trang quản trị, hiện "Bạn không có quyền truy cập trang quản trị." | "Nhân viên vận hành không có mục Quản trị trên thanh bên. Nếu truy cập thẳng địa chỉ trang quản trị thì bị chặn với thông báo không có quyền. Mọi thao tác nghiệp vụ còn lại đều giống nhau giữa ba vai trò." |

## Cảnh 7. Kết (0:45)

Tệp: canh-7-ket.webm. Thẻ tóm tắt, không cần đăng nhập.

| Thời điểm | Thao tác | Lời thuyết minh |
| --- | --- | --- |
| 0:00 | Thẻ tóm tắt: các việc đã trình diễn, giới hạn, lệnh chạy | "Tóm lại, ShipGuard chạy bằng một lệnh, giúp nhân viên vận hành theo dõi giao hàng, thấy sớm đơn rủi ro cao kèm nguyên nhân dự kiến, ghi nhận xử lý và mốc vòng đời, đồng thời cho quản lý biết mô hình đáng tin đến đâu và cho Super Admin phân quyền theo vai trò." |
| 0:25 | Cuối thẻ: "Cảm ơn thầy đã xem" | "Hạn chế lớn nhất em đã nói thẳng ở phần chỉ số: F1 ở mốc đặt hàng chưa đạt mục tiêu, và bảng đối chiếu trên đơn thật mới ở mức thử nghiệm. Em xin cảm ơn thầy đã xem." |

## Các đoạn trong thư mục clips

| Tệp | Thời lượng |
| --- | --- |
| canh-1a-tieu-de.webm | 0:19 |
| (đoạn dòng lệnh tự quay, hoặc canh-1-terminal-tinh.webm) | khoảng 0:45 (ảnh tĩnh 0:30) |
| canh-1b-dang-nhap.webm | 0:25 |
| canh-2-bang-dieu-khien.webm | 2:15 |
| canh-3-tao-don.webm | 4:30 |
| canh-4-huy-don.webm | 0:45 |
| canh-5-chi-so-mo-hinh.webm | 2:00 |
| canh-6-quan-tri.webm | 2:30 |
| canh-7-ket.webm | 0:45 |

## Lồng tiếng và dựng bằng Remotion

Dự án Remotion nằm trong thư mục demo/video của repo, tách khỏi gói nộp để không đưa node_modules vào tệp ZIP. Dự án đọc các đoạn trong demo/clips và lời thuyết minh ở các bảng trên (cột "Lời thuyết minh"), tổng hợp giọng nam vi-VN-NamMinhNeural bằng msedge-tts (Edge TTS, không cần khóa API), đặt từng câu đúng mốc của bước tương ứng và xuất demo/ShipGuard-Demo.mp4 (1920x1080, H.264, AAC). Nếu lời đọc dài hơn thao tác thì khung hình cuối của bước đó được giữ cho tới khi đọc xong. Nếu lời đọc ngắn hơn thao tác thì video được rút ngắn cho gần bằng lời đọc, theo cấu hình ở src\data\fit.json. Chế độ mặc định `smart` chỉ cắt thời gian chờ (màn hình đứng yên): `npm run motion` đo chuyển động của từng clip vào src\data\motion.json, mỗi đoạn giữa hai mốc được cắt bỏ phần đuôi đứng yên; nếu phần có thao tác vẫn dài hơn lời đọc thì tăng tốc tối đa `maxSpeed` lần (không cắt thao tác nào, nên video có thể dài hơn lời đọc một ít, phần dư im lặng). Các tham số: `slack` là số giây video được phép dài hơn lời đọc, `tailPad` là số giây giữ lại sau thao tác cuối để người xem kịp thấy kết quả, `motionThreshold` là ngưỡng số điểm ảnh đổi coi là có chuyển động. Chế độ khác: `cut` (cắt đuôi cứng theo độ dài lời đọc), `speed` (tăng tốc rồi cắt), `keep` (giữ nguyên video). `overrides` đổi riêng từng câu, ví dụ `{"canh-3-4": "keep"}` hoặc `{"canh-6-2": {"mode": "smart", "maxSpeed": 3}}`. `npm run verify` kiểm tra độc lập rằng mọi phần bị cắt chỉ là thời gian chờ. Tổng độ dài với `keep` khoảng 14 phút; với cấu hình mặc định khoảng 8 phút (chạy `npm run check` để xem số thật theo từng cảnh).

Trong thư mục demo/video, chạy lần lượt: `npm install`; `npm run sync` (chép các đoạn video sang dự án và đo thời lượng); `npm run narration` (chép lời thuyết minh từ tệp này sang src\data\narration.json); `npm run tts` (tạo âm thanh vào public\audio; thêm `-- --force` để tạo lại tất cả, hoặc thêm id câu như `-- canh-3-6 --force` để tạo lại một câu); `npm run check` (in bảng thời gian, báo câu nào thiếu âm thanh, lệch nguyên văn hoặc phải giữ hình lâu); `npm run studio` (xem trước từng cảnh trong trình duyệt); `npm run render:full` (xuất video cuối). Xuất riêng một cảnh bằng `npm run render:canh -- Canh3 out/canh-3.mp4`.

Các câu có từ tiếng Anh hoặc dãy số (17 câu) được tạo hai bản âm thanh: `<id>.mp3` đọc theo bản phiên âm (quy tắc trong src\data\phien-am.json) và `<id>.raw.mp3` đọc nguyên văn. Nghe cả hai, câu nào bản nguyên văn tự nhiên hơn thì ghi vào src\data\chon.json, ví dụ `{"canh-1t-1": "raw"}`. Sửa lời thuyết minh thì sửa tệp này, chạy lại `narration`, `tts`, `check` rồi `render`. Nếu Edge TTS ngừng hoạt động thì dùng dịch vụ Azure Speech với khóa API, hoặc tự thu âm từng câu vào public\audio với đúng tên tệp mà `check` in ra. Phương án dựng bằng Clipchamp ở đầu tài liệu vẫn dùng được thay thế.

## Quay lại

Trong thư mục scripts: `dung-lai-du-lieu.sh` dựng lại dữ liệu sạch của dự án shipverify và nạp 12 đơn đối chiếu; `node run-all.cjs` quay lại cả bảy cảnh, hoặc `node run-all.cjs 3 4` để quay riêng một số cảnh. Cảnh 4 dùng đơn A do Cảnh 3 tạo (ghi trong state.json), nên quay lại Cảnh 3 thì nên quay lại Cảnh 4 sau đó. Quay lại từng cảnh riêng lẻ trên dữ liệu đã dùng thì số đơn trong danh sách ở Cảnh 2 và tài khoản An ở Cảnh 6 không còn khớp; muốn khớp lại thì dựng lại dữ liệu sạch trước.
