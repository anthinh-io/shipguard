# ADR-0006: Trình duyệt gọi thẳng backend có xác thực — JWT trong bộ nhớ, refresh token trong cookie httpOnly

**Trạng thái:** Đã chấp nhận
**Thay thế:** ADR-0002
**Ngày:** 2026-09-13
**Người quyết định:** Chủ dự án

## Bối cảnh

Quản lý đơn hàng mang tới thao tác ghi đầu tiên cần danh tính: `Internal Note` phải gắn với người viết. Cùng lúc hệ thống không còn một người dùng duy nhất — có ba vai trò (`Operations Staff`, `Logistics Manager`, `Super Admin`) và một trang quản trị `User`. ADR-0002 chọn cho trình duyệt gọi thẳng FastAPI qua CORS với lập luận "không có xác thực nên giấu backend chẳng bảo vệ gì", và tự ghi rằng phải xem lại khi có đăng nhập. ADR này là lần xem lại đó.

Các lực tác động:

- **Đăng nhập bảo vệ toàn bộ ứng dụng**, kể cả bảng điều khiển: dữ liệu đơn chứa thành phố, mã bưu chính và nội dung đánh giá của khách.
- **Khóa tài khoản và đổi vai trò phải có hiệu lực trong thời gian ngắn**, không đợi người bị khóa tự đăng xuất.
- **Không có dịch vụ email**, nên không có luồng quên mật khẩu qua email.
- **Trình duyệt gọi thẳng backend** (ADR-0002); frontend và backend khác cổng nhưng cùng site.

## Quyết định

1. **Access token** là JWT sống 15 phút, chứa định danh `User`, vai trò và các `User Claim` của người đó. Frontend giữ nó trong bộ nhớ và gửi qua header `Authorization: Bearer`. API chỉ xác minh chữ ký, không tra cơ sở dữ liệu.
2. **Refresh token** sống 7 ngày, là chuỗi ngẫu nhiên được băm rồi lưu trong PostgreSQL, gửi qua cookie `httpOnly`, `SameSite=Lax`, `Path=/auth`. Mỗi lần dùng thì xoay vòng: token cũ bị thu hồi, token mới được cấp. Tải lại trang thì frontend gọi `/auth/refresh` để lấy access token mới.
3. **Thu hồi mọi refresh token của một `User`** khi người đó bị khóa, bị đổi vai trò, bị đặt lại mật khẩu, hoặc tự đổi mật khẩu.
4. **CORS** bật `allow_credentials`, mở thêm `POST`, `PATCH` và các header `Authorization`, `Content-Type`.
5. **Giữ nguyên cách gọi thẳng backend của ADR-0002**, chép lại ở đây để ADR này đọc độc lập được. Trình duyệt gọi thẳng FastAPI, không đi qua proxy Next. Frontend đọc địa chỉ backend từ `NEXT_PUBLIC_BACKEND_URL`; backend đọc danh sách origin cho phép từ `CORS_ALLOWED_ORIGINS`.
6. **`Super Admin`** — vai trò riêng của đúng một `User` — được tạo một lần khi backend khởi động, từ `SUPER_ADMIN_EMAIL`, `SUPER_ADMIN_PASSWORD`, `SUPER_ADMIN_NAME`, nếu chưa tồn tại `Super Admin` nào; từ đó biến môi trường bị bỏ qua. Người cài đặt đăng nhập bằng tài khoản này để tạo các `Logistics Manager`. Quên mật khẩu `Super Admin` thì người có quyền vào máy chủ chạy script CLI để đặt lại.

## Các phương án đã cân nhắc

### Phương án A: Session cookie httpOnly lưu trong PostgreSQL

| Chiều đánh giá | Nhận định |
| --- | --- |
| Độ phức tạp | Thấp — một cookie, frontend không phải cầm token |
| Chi phí vận hành | Thấp — thêm một bảng phiên, dọn phiên hết hạn định kỳ |
| Khả năng mở rộng | Trung bình — mọi request tra bảng phiên; chỉ dùng được từ trình duyệt |
| Độ quen thuộc | Cao — mô hình web kinh điển |
| Hiệu lực khi khóa tài khoản | Tức thì |
| Bề mặt khi bị XSS | Nhỏ — JavaScript không đọc được phiên |

**Ưu:** ít mã frontend nhất; khóa tài khoản có hiệu lực ngay.
**Nhược:** mọi request tra bảng phiên; phiên chỉ dùng được từ trình duyệt.

### Phương án B: JWT, cả access lẫn refresh token trong localStorage

| Chiều đánh giá | Nhận định |
| --- | --- |
| Độ phức tạp | Thấp — không đụng CORS credentials |
| Chi phí vận hành | Thấp — không có cookie, không lo cấu hình cùng site |
| Khả năng mở rộng | Tốt — API không tra cơ sở dữ liệu; token dùng được ngoài trình duyệt |
| Độ quen thuộc | Cao — cách làm hay gặp trong hướng dẫn |
| Hiệu lực khi khóa tài khoản | Trễ tới khi access token hết hạn |
| Bề mặt khi bị XSS | Lớn — lấy được refresh token sống 7 ngày |

**Ưu:** đơn giản; không cần cookie.
**Nhược:** một lỗi XSS là đủ chiếm tài khoản cả tuần.

### Phương án C: Proxy qua Next (BFF), cookie thuộc frontend

| Chiều đánh giá | Nhận định |
| --- | --- |
| Độ phức tạp | Cao — viết lại toàn bộ lớp gọi API, một tệp proxy mỗi endpoint |
| Chi phí vận hành | Trung bình — thêm một chặng mạng; backend ẩn sau máy chủ Next |
| Khả năng mở rộng | Trung bình — mỗi endpoint mới kéo theo một tệp proxy |
| Độ quen thuộc | Trung bình — khái niệm Route Handler chưa dùng trong dự án |
| Hiệu lực khi khóa tài khoản | Tuỳ cơ chế phiên phía sau |
| Bề mặt khi bị XSS | Nhỏ |

**Ưu:** bỏ được CORS; backend không phơi ra trình duyệt.
**Nhược:** đảo ngược ADR-0002, và mọi lý do ADR-0002 bác bỏ proxy (tệp proxy mỗi endpoint, đường lỗi test khác đường người dùng gặp) vẫn còn nguyên.

### Phương án D: JWT trong bộ nhớ + refresh token trong cookie httpOnly

| Chiều đánh giá | Nhận định |
| --- | --- |
| Độ phức tạp | Trung bình — frontend phải tự gắn và làm mới token |
| Chi phí vận hành | Trung bình — bảng refresh token; cookie buộc frontend và backend cùng site |
| Khả năng mở rộng | Tốt — API chỉ xác minh chữ ký, chỉ tra cơ sở dữ liệu khi làm mới |
| Độ quen thuộc | Trung bình — mô hình phổ biến với FastAPI, dự án muốn thực hành |
| Hiệu lực khi khóa tài khoản | Trễ tối đa 15 phút |
| Bề mặt khi bị XSS | Vừa — lộ access token 15 phút, không lộ refresh token |

**Ưu:** API không tra cơ sở dữ liệu để biết ai đang gọi; refresh token dài hạn không bị JavaScript chạm tới.
**Nhược:** nhiều mã frontend hơn A; khóa tài khoản không tức thì.

## Phân tích đánh đổi

B rụng vì refresh token 7 ngày nằm trong localStorage. C rụng vì cái giá viết lại lớp gọi API để mua thứ ADR-0002 đã cân và bác.

Đánh đổi thật nằm giữa A và D. A cho khóa tài khoản tức thì với ít mã hơn. D cho API không phải tra cơ sở dữ liệu ở mỗi request, và là mô hình JWT phổ biến với FastAPI mà dự án muốn thực hành. Nói thẳng: ở quy mô dữ liệu và số người dùng hiện tại, một lần tra bảng phiên mỗi request là rẻ, nên lợi thế hiệu năng của D nhỏ; mục tiêu thực hành là lý do có trọng lượng ngang bằng. Cái giá của D — khóa tài khoản trễ tối đa 15 phút — được chấp nhận cho một công cụ nội bộ.

## Hệ quả

- **Dễ hơn:** API xác minh danh tính mà không tra cơ sở dữ liệu; bearer token dùng được cho client ngoài trình duyệt nếu sau này cần.
- **Khó hơn:** frontend phải có một lớp gọi API tự gắn token, gặp 401 thì làm mới một lần rồi thử lại; khi tải lại trang có một nhịp chờ làm mới trước khi biết đã đăng nhập hay chưa; mọi request mang header `Authorization` nên phát sinh preflight CORS; test Playwright phải giả lập `/auth/refresh`.
- **Giới hạn đã chấp nhận:** tài khoản bị khóa hoặc bị hạ vai trò vẫn dùng được access token đang có trong tối đa 15 phút.
- **Ràng buộc triển khai:** cookie `SameSite=Lax` chỉ đi kèm khi frontend và backend cùng site. Triển khai khác site thì phải xem lại (`SameSite=None; Secure`, hoặc phương án C).
- **ADR-0002 chuyển sang "Bị thay thế".** Lập luận "không có xác thực" của nó hết hiệu lực. Quyết định gọi thẳng backend vẫn giữ và đã được chép vào mục Quyết định ở trên. Phần phân tích vì sao không dùng proxy vẫn đọc ở ADR-0002.
- **Cần xem lại:** nếu độ trễ 15 phút khi khóa trở thành vấn đề, thêm bước kiểm tra trạng thái khóa lúc xác minh token — tức là bỏ lợi thế không tra cơ sở dữ liệu, và khi đó phương án A đáng mở lại.

## Việc cần làm

1. [x] Bảng `users`, `refresh_tokens`, `user_claims` qua Alembic
2. [ ] Endpoint `/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/password`, `/me`
3. [x] Dependency xác minh access token, áp cho mọi route trừ `/health` và `/auth/*`
4. [x] Tạo `Super Admin` lúc khởi động; script CLI đặt lại mật khẩu `Super Admin`
5. [x] Mở rộng `CORSMiddleware` và cập nhật test header CORS
6. [x] Lớp gọi API phía frontend: gắn token, làm mới khi 401, chuyển về `/login`
7. [x] Giả lập `/auth/refresh` trong các spec Playwright hiện có
