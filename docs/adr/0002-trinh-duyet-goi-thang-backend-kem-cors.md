# ADR-0002: Trình duyệt gọi thẳng backend, mở CORS thay vì proxy qua Next

**Trạng thái:** Đã chấp nhận
**Ngày:** 2026-09-11
**Người quyết định:** Chủ dự án

## Bối cảnh

Bảng điều khiển KPI là màn hình đầu tiên phải lấy dữ liệu thật từ FastAPI. Cho tới giờ, trang chủ là một Server Component đọc biến `BACKEND_URL` chỉ tồn tại phía máy chủ và gọi `/health`. `frontend/README.md` ghi rõ lựa chọn đó là có chủ ý: không đặt tiền tố `NEXT_PUBLIC_` để địa chỉ backend không lộ ra trình duyệt.

Ba lực buộc phải xem lại quyết định ấy:

- **Hai tiêu chí của bảng điều khiển chỉ quan sát được từ trình duyệt.** "Một lần đổi bộ lọc chỉ sinh đúng một lần gọi máy chủ" và "hiện thông báo lỗi khi máy chủ không phản hồi" đều cần lần gọi đó xuất phát từ trình duyệt. Khi `fetch` chạy phía máy chủ thì không có request nào để đếm, và không có đường lỗi nào để chặn.
- **Bộ lọc người bán bắt buộc phải ở client.** Ô gợi ý gõ dần gọi endpoint phụ theo từng phím gõ. Không có cách nào làm việc đó bằng Server Component.
- **Không có xác thực.** Đăng nhập và phân quyền nằm ngoài phạm vi tính năng này. Backend vốn không kiểm danh tính, nên giấu địa chỉ của nó không mang lại sự bảo vệ nào.

Ràng buộc từ `CLAUDE.md` §2: không dựng thứ chưa ai yêu cầu, và nếu 200 dòng có thể là 50 thì viết lại.

## Quyết định

Trình duyệt gọi thẳng FastAPI. Thêm `CORSMiddleware` vào backend với danh sách origin đọc từ biến môi trường `CORS_ALLOWED_ORIGINS`, và frontend đọc địa chỉ backend từ `NEXT_PUBLIC_BACKEND_URL`.

Quyết định này **thay thế** ghi chú trong `frontend/README.md` rằng địa chỉ backend chỉ đọc phía máy chủ.

## Các phương án đã cân nhắc

### Phương án A: Giữ Server Component

| Chiều đánh giá | Nhận định |
| --- | --- |
| Độ phức tạp | Thấp nhất — không thêm tệp nào, không sửa backend |
| Chi phí vận hành | Thấp — một biến môi trường, chỉ phía máy chủ |
| Đáp ứng tiêu chí | Không đáp ứng hai tiêu chí |
| Khả năng mở rộng | Bế tắc ở bộ lọc người bán |
| Độ quen thuộc | Cao nhất — đúng mã đang chạy |

**Ưu:** không đổi gì cả; địa chỉ backend không lộ; ít chặng mạng nhất.
**Nhược:** trạng thái tải và trạng thái lỗi không kiểm chứng được từ Playwright, vì trình duyệt không hề phát sinh request. Bộ lọc người bán vẫn phải chuyển sang client, nên đây là hoãn chứ không phải tránh.

### Phương án B: Proxy qua Route Handler của Next

| Chiều đánh giá | Nhận định |
| --- | --- |
| Độ phức tạp | Trung bình — một tệp proxy cho mỗi endpoint backend |
| Chi phí vận hành | Thấp — giữ một bộ biến môi trường cho mọi môi trường |
| Đáp ứng tiêu chí | Đáp ứng đủ |
| Khả năng mở rộng | Tốt — thêm endpoint là thêm một tệp proxy |
| Độ quen thuộc | Trung bình — thêm một khái niệm Next chưa dùng tới |

**Ưu:** `BACKEND_URL` ở nguyên phía máy chủ nên không phải build lại theo môi trường; backend không đổi dòng nào; FastAPI chỉ cần máy chủ Next gọi được, không phải phơi ra Internet.
**Nhược:** phải tự viết hợp đồng khi backend không phản hồi — `fetch` ném, `response.json()` ném khi thân không phải JSON, và không bắt thì Next trả 500 kèm lớp phủ lỗi chứ không phải JSON lỗi của mình. Thêm một chặng mạng mỗi lần gọi. Đường lỗi mà test đi qua không phải đường người dùng thật gặp.

### Phương án C: Gọi thẳng kèm CORS

| Chiều đánh giá | Nhận định |
| --- | --- |
| Độ phức tạp | Thấp — không tệp proxy; backend thêm một middleware một lần |
| Chi phí vận hành | Trung bình — danh sách origin phải khớp từng môi trường |
| Đáp ứng tiêu chí | Đáp ứng đủ |
| Khả năng mở rộng | Tốt — thêm endpoint không thêm gì phía frontend |
| Độ quen thuộc | Cao — CORS là thứ quen thuộc với mọi người |

**Ưu:** ít mã nhất trong ba phương án đáp ứng được tiêu chí; một chặng mạng; lỗi backend không phản hồi đi đúng đường người dùng thật gặp nên test trung thực hơn; không phát sinh preflight vì mọi lời gọi đều là `GET` không header tuỳ biến.
**Nhược:** `NEXT_PUBLIC_BACKEND_URL` nhúng cứng lúc build nên mỗi môi trường phải build lại. Danh sách origin lệch giữa các môi trường là lỗi kinh điển kiểu "chạy tốt ở máy mình, hỏng trên máy chủ". FastAPI phải phơi ra cho trình duyệt của người dùng.

## Phân tích đánh đổi

Phương án A rụng sớm: nó không hoãn được chi phí mà chỉ dời sang ticket bộ lọc người bán, và trong lúc đó làm hai tiêu chí của bảng điều khiển không kiểm chứng được.

Giữa B và C, đánh đổi thật nằm giữa **chi phí trong mã** và **chi phí lúc triển khai**.

B đẩy chi phí vào mã: mỗi endpoint backend kéo theo một tệp proxy, và tệp đó phải mang hợp đồng lỗi riêng. Đổi lại, triển khai đơn giản hơn — một bộ biến môi trường, không danh sách origin, FastAPI nằm sau máy chủ Next.

C đẩy chi phí ra lúc triển khai: build lại theo môi trường, danh sách origin phải đúng, backend phải phơi ra. Đổi lại mã ít hơn hẳn.

Ba điều nghiêng cán cân về C. **Một**, `CLAUDE.md` §2 nói thẳng là chọn phương án ít mã hơn. **Hai**, rủi ro "lộ địa chỉ backend" mà B bảo vệ không tồn tại ở dự án này, vì xác thực nằm ngoài phạm vi — backend không kiểm danh tính thì giấu địa chỉ chẳng bảo vệ được gì. **Ba**, ở B, test trạng thái lỗi phải chặn ở tầng proxy chứ không đi qua đường người dùng thật gặp; ở C hai đường đó là một.

Nhược điểm nặng nhất của C — danh sách origin lệch môi trường — là thứ canh được bằng test, và bộ test của bảng điều khiển có một bài khẳng định header CORS có mặt cho origin được phép.

## Hệ quả

- **Dễ hơn:** thêm endpoint backend mà không thêm tệp nào phía frontend. Test trạng thái lỗi đi đúng đường người dùng gặp. Một chặng mạng ít hơn mỗi lần gọi.
- **Khó hơn:** mỗi môi trường phải build lại frontend vì địa chỉ backend nhúng cứng lúc build. Phải giữ `CORS_ALLOWED_ORIGINS` khớp giữa các môi trường. FastAPI phải cho trình duyệt người dùng gọi được, không chỉ máy chủ Next.
- **Cần xem lại:** nếu dự án thêm đăng nhập và phân quyền — hiện nằm ngoài phạm vi — thì việc phơi backend ra trình duyệt trở thành bề mặt tấn công thật, và phương án B đáng cân nhắc lại.

## Việc cần làm

1. [x] Thêm `CORSMiddleware` vào `backend/app/main.py`, origin đọc từ cấu hình
2. [x] Thêm `CORS_ALLOWED_ORIGINS` vào `backend/app/core/config.py`, `.env` và `.env.example`
3. [x] Đổi `BACKEND_URL` thành `NEXT_PUBLIC_BACKEND_URL` ở `frontend/.env` và `.env.example`
4. [x] Viết test khẳng định header CORS có mặt cho origin được phép
5. [x] Sửa `frontend/README.md`: gỡ ghi chú "chỉ đọc phía máy chủ", trỏ sang ADR này
