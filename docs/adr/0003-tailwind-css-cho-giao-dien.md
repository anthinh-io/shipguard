# ADR-0003: Dùng Tailwind CSS cho giao diện bảng điều khiển

**Trạng thái:** Đã chấp nhận
**Ngày:** 2026-09-11
**Người quyết định:** Chủ dự án

## Bối cảnh

Khung frontend dựng ban đầu không chọn hệ thống style nào: `app/globals.css` là bản reset của `create-next-app` cộng vài dòng thêm tay, không Tailwind, không CSS Modules, không thư viện CSS-in-JS. Trang chủ lúc đó chỉ có một dòng chữ trạng thái nên chưa cần quyết định gì.

Bảng điều khiển KPI là màn hình thật đầu tiên, và nó mở đầu một chuỗi ticket giao diện: sáu ô KPI, biểu đồ xu hướng, biểu đồ cột xếp hạng theo bang, thanh bộ lọc, ô gợi ý gõ dần nhiều cột kèm nhãn cảnh báo mẫu nhỏ, mức chênh kèm hướng tăng giảm giữa các kỳ. Đây là lượng bố cục đủ lớn để cách viết style trở thành một quyết định.

Hai lực định hình thời điểm:

- **Đây là lúc rẻ nhất để chọn.** Chuyển hệ thống style ở ticket thứ tư hay thứ năm nghĩa là viết lại mọi thứ đã dựng trước đó. Cùng một lập luận mà #7 dùng để đặt phần song ngữ lên sớm thay vì để cuối.
- **Chưa có prior art để phải tôn trọng.** `globals.css` gần như nguyên trạng bản mẫu, nên không có quy ước sẵn nào bị phá.

Ràng buộc từ `CLAUDE.md` §2: không dựng thứ chưa ai yêu cầu. Thêm một phụ thuộc và một bước trong chuỗi build nằm ngoài phạm vi hẹp của ticket bảng điều khiển.

## Quyết định

Dùng Tailwind CSS v4, nạp qua `@tailwindcss/postcss` khai trong `frontend/postcss.config.mjs` và một dòng `@import "tailwindcss"` ở đầu `app/globals.css`.

Phần reset viết tay trong `globals.css` gỡ đi vì preflight của Tailwind đã lo, giữ lại biến màu và nhánh sáng/tối.

## Các phương án đã cân nhắc

### Phương án A: CSS thuần trong `globals.css`

| Chiều đánh giá | Nhận định |
| --- | --- |
| Độ phức tạp | Thấp nhất — không phụ thuộc, không bước build |
| Chi phí vận hành | Thấp nhất |
| Phù hợp lượng giao diện còn lại | Kém — một tệp chung phình dần qua sáu ticket |
| Khả năng mở rộng | Mọi tên lớp nằm chung một không gian, dễ đụng nhau |
| Độ quen thuộc | Cao nhất |

**Ưu:** không đổi gì; ít thay đổi nhất ở ticket này; đúng tinh thần `CLAUDE.md` §2 và §3.
**Nhược:** `globals.css` thành nơi chứa mọi thứ, và tên lớp phải tự đặt quy ước mà không có gì canh.

### Phương án B: CSS Modules

| Chiều đánh giá | Nhận định |
| --- | --- |
| Độ phức tạp | Thấp — Next hỗ trợ sẵn, không thêm phụ thuộc |
| Chi phí vận hành | Thấp |
| Phù hợp lượng giao diện còn lại | Khá — mỗi component một tệp style |
| Khả năng mở rộng | Tốt — phạm vi tên lớp tách biệt |
| Độ quen thuộc | Cao |

**Ưu:** không thêm phụ thuộc nào; style có phạm vi riêng nên không đụng tên; `globals.css` không phình.
**Nhược:** mỗi component kéo theo một tệp nữa và một lần nhảy qua lại khi đọc; vẫn phải tự đặt quy ước khoảng cách, cỡ chữ, màu.

### Phương án C: Tailwind CSS v4

| Chiều đánh giá | Nhận định |
| --- | --- |
| Độ phức tạp | Trung bình — một phụ thuộc, một tệp cấu hình PostCSS |
| Chi phí vận hành | Thấp — Next 16 coi Tailwind v4 là mặc định, không cấu hình thêm |
| Phù hợp lượng giao diện còn lại | Tốt — phần việc còn lại chủ yếu là bố cục |
| Khả năng mở rộng | Tốt — thang khoảng cách và cỡ chữ có sẵn, không phải tự chế |
| Độ quen thuộc | Cao |

**Ưu:** style nằm ngay trong markup nên đọc một tệp là đủ; có sẵn thang khoảng cách, cỡ chữ, màu nên không phải bịa quy ước; biến thể `dark:` khớp đúng cơ chế `prefers-color-scheme` mà `globals.css` đang dùng; Recharts tạo kiểu qua thuộc tính chứ không qua CSS nên hai bên không giẫm chân.
**Nhược:** thêm một phụ thuộc và một bước PostCSS vào chuỗi build; lớp tiện ích làm markup dài ra; phải gỡ phần reset viết tay để không đá với preflight.

## Phân tích đánh đổi

Đánh đổi nằm giữa **ít thay đổi ở ticket này** và **chi phí dồn lại qua sáu ticket sau**.

A rẻ nhất hôm nay và đắt dần đều: sáu ticket giao diện cùng đổ vào một `globals.css` và một không gian tên lớp chung.

Giữa B và C, cả hai đều giải quyết chuyện phình tệp và đụng tên. Khác biệt là B chỉ cho phạm vi, còn C cho thêm một thang giá trị sẵn có. Với một dự án mà phần lớn giao diện do agent viết theo từng ticket rời nhau, thang sẵn có đáng giá hơn: nó thay chỗ cho một tài liệu quy ước mà không ai viết, và làm các ticket rời nhau ra kết quả nhất quán.

Chi phí thật của C so với B là một phụ thuộc và một tệp cấu hình bốn dòng. Nhỏ so với việc tự đặt và tự canh một hệ quy ước.

Về `CLAUDE.md` §2: thêm Tailwind đúng là nằm ngoài phạm vi hẹp của ticket bảng điều khiển. Nhưng ticket ấy tự nêu rằng hình dạng bộ khung nó dựng quan trọng hơn số chỉ số nó giao, và hệ thống style là một phần của hình dạng đó. Hoãn lại không tiết kiệm được gì, chỉ làm đợt chuyển đổi sau này đắt hơn.

## Hệ quả

- **Dễ hơn:** các ticket giao diện sau viết style ngay trong markup, không phải mở thêm tệp; khoảng cách và cỡ chữ nhất quán mà không cần tài liệu quy ước; chế độ tối dùng biến thể `dark:` có sẵn.
- **Khó hơn:** thêm `tailwindcss` và `@tailwindcss/postcss` vào phụ thuộc, cộng một bước PostCSS khi build; markup dài hơn vì lớp tiện ích; ai chưa quen Tailwind phải tra bảng lớp.
- **Cần xem lại:** nếu dự án về sau lấy một bộ component dựng sẵn có hệ thống style riêng, hai bên sẽ chồng nhau và cần chọn lại.

## Việc cần làm

1. [x] Thêm `tailwindcss` và `@tailwindcss/postcss` vào phụ thuộc phát triển của `frontend`
2. [x] Tạo `frontend/postcss.config.mjs` nạp plugin
3. [x] Thêm `@import "tailwindcss"` vào đầu `app/globals.css`
4. [x] Gỡ phần reset viết tay đã trùng với preflight của Tailwind
5. [x] Ghi Tailwind vào `frontend/README.md`
