# ADR-0005: Dùng next-intl với ngôn ngữ lưu trong cookie cho giao diện song ngữ

**Trạng thái:** Đã chấp nhận
**Ngày:** 2026-09-12
**Người quyết định:** Chủ dự án

## Bối cảnh

Giao diện phải chạy được cả tiếng Việt và tiếng Anh. #7 đặt việc này ngay sau bảng điều khiển đầu tiên chứ không để cuối — cùng lập luận mà ADR-0003 và ADR-0004 đã dẫn lại: đợt sửa quét ngang rẻ nhất khi "mọi giao diện đã dựng" còn nhỏ. Hôm nay bề mặt là ba tệp `.tsx` và 11 chuỗi hiển thị. Tới #11 thì là thanh bộ lọc, hai biểu đồ và sáu ô KPI.

Phần đắt của việc này không phải chuỗi. Ba bộ `Intl.*` trong `dashboard.tsx` đóng cứng `"vi-VN"` ở phạm vi module và được tạo đúng một lần lúc import, nên **về mặt vật lý chúng không phản ứng được với việc đổi ngôn ngữ** — thay hết chuỗi mà để nguyên chúng thì số và ngày vẫn kẹt ở một ngôn ngữ. Đây mới là thứ quyết định hình dạng lời giải.

Hai ràng buộc từ #6 phải sống sót qua đợt chuyển:

- `timeZone: "UTC"`. `new Date("2017-09-01")` đọc chuỗi chỉ có ngày thành nửa đêm UTC, nên máy đặt ở múi giờ phía tây UTC sẽ hiện 31/08/2017 — lệch đúng một ngày ở chính cái ranh giới ngày mà cả tính năng xoay quanh.
- Khai báo rõ ngày/tháng/năm thay cho `dateStyle: "short"`, vốn cho năm hai chữ số và mơ hồ với một kỳ báo cáo trải nhiều năm.

Một ràng buộc nữa từ `CONTEXT.md`: tên thuật ngữ viết tiếng Anh để khớp định danh trong code. Chỉ nhãn hiển thị mới song ngữ, tên trường API giữ nguyên.

## Quyết định

Nhận **next-intl**, chạy ở chế độ **không định tuyến theo ngôn ngữ**: ngôn ngữ nằm trong cookie `NEXT_LOCALE`, đường dẫn luôn là `/`, mặc định tiếng Việt.

Ba hệ quả cấu hình đi kèm:

1. **Không có đoạn route `[locale]`, không có `middleware.ts`.** Cây route giữ nguyên hình dạng cũ.
2. **Định dạng số và ngày khai thành format có tên** trong `i18n/request.ts` — `fullDate` và `percent` — thay cho hằng số ở phạm vi module. `timeZone: "UTC"` đặt ở cấp format chứ không đặt toàn cục, nên ticket sau hiện mốc thời gian thật sẽ không thừa hưởng nhầm.
3. **Ghi cookie qua một server action**, là hàm duy nhất xuất ra từ tệp `"use server"`. Hàm đọc nằm trong `i18n/request.ts` và không xuất ra ngoài.

## Các phương án đã cân nhắc

### Phương án A: Tự viết — một object chuỗi và gọi `Intl` trực tiếp

| Chiều đánh giá | Nhận định |
| --- | --- |
| Độ phức tạp | Thấp ở hôm nay, cao dần theo từng ticket hiển thị |
| Chi phí vận hành | Không thêm phụ thuộc nào |
| Phù hợp lượng giao diện còn lại | Kém — số nhiều và định dạng lồng nhau phải tự canh |
| Đúng quy ước số và ngày | Được, nhưng mỗi chỗ gọi tự lo lấy |
| Hợp với Server Component | Phải tự dựng đường truyền ngôn ngữ từ máy chủ xuống |

**Ưu:** không phụ thuộc mới; đúng tinh thần `CLAUDE.md` §2 ở quy mô 11 chuỗi hôm nay.
**Nhược:** `timeZone` và các tuỳ chọn định dạng rải ra từng chỗ gọi, nên một chỗ quên là lệch một ngày mà không ai thấy; tiếng Anh có số ít/số nhiều còn tiếng Việt không, nên sẽ phải tự dựng lại một phần ICU.

### Phương án B: `react-i18next` hoặc một thư viện không gắn với Next

| Chiều đánh giá | Nhận định |
| --- | --- |
| Độ phức tạp | Trung bình — một phụ thuộc lớn, API riêng phải học |
| Chi phí vận hành | Trung bình |
| Phù hợp lượng giao diện còn lại | Tốt — đủ tính năng |
| Đúng quy ước số và ngày | Tốt, qua ICU |
| Hợp với Server Component | Kém — sinh ra để chạy ở client, phải tự ghép vào App Router |

**Ưu:** chín, nhiều tài liệu, không phụ thuộc vào một khung cụ thể.
**Nhược:** không hiểu ranh giới Server/Client Component của App Router, nên phần ghép nối là mã của dự án phải tự bảo trì — đúng phần dễ sai nhất.

### Phương án C: next-intl với tiền tố URL (`/vi`, `/en`)

| Chiều đánh giá | Nhận định |
| --- | --- |
| Độ phức tạp | Trung bình — mọi trang chuyển vào `app/[locale]/`, thêm `middleware.ts` |
| Chi phí vận hành | Thấp |
| Phù hợp lượng giao diện còn lại | Tốt |
| Đúng quy ước số và ngày | Tốt |
| Hợp với Server Component | Tốt — ngôn ngữ là tham số route |

**Ưu:** ngôn ngữ chia sẻ được qua đường liên kết; máy tìm kiếm đọc được từng bản; trang dựng tĩnh được theo từng ngôn ngữ.
**Nhược:** mọi trang phải chuyển vào thư mục ngoặc vuông và phải có `middleware.ts` chạy trước mỗi lần tải trang; Next 16 sinh kiểu dữ liệu từ cấu trúc thư mục nên chữ ký `LayoutProps<"/">` đổi theo. Đây là công cụ vận hành nội bộ — không ai chia sẻ đường liên kết theo ngôn ngữ, và không có yêu cầu nào về máy tìm kiếm.

### Phương án D: next-intl với ngôn ngữ trong cookie

| Chiều đánh giá | Nhận định |
| --- | --- |
| Độ phức tạp | Thấp — không đụng cây route, không có middleware |
| Chi phí vận hành | Thấp — giống C |
| Phù hợp lượng giao diện còn lại | Tốt — giống C |
| Đúng quy ước số và ngày | Tốt — giống C |
| Hợp với Server Component | Tốt — ngôn ngữ đọc từ cookie ở phía máy chủ |

**Ưu:** đường dẫn không đổi nên cây route, chữ ký kiểu do Next sinh và mọi đường liên kết đã có đều giữ nguyên; lựa chọn theo người dùng chứ không theo địa chỉ.
**Nhược:** trang phải dựng động vì có đọc cookie; ngôn ngữ không chia sẻ được qua đường liên kết.

## Phân tích đánh đổi

Đánh đổi thứ nhất, giữa tự viết (A) và nhận thư viện, xoay quanh đúng hai ràng buộc của #6. `timeZone: "UTC"` và cách khai báo ngày tháng là thứ phải đúng ở **mọi** chỗ hiện ngày, mà A không có chỗ nào để khai một lần — mỗi chỗ gọi tự mang tuỳ chọn của nó. Ở 11 chuỗi thì đếm được; tới #9, #10, #11 thì không. Thư viện cho một chỗ khai duy nhất, và đó là lý do chính chứ không phải việc tra cứu chuỗi.

Giữa B và next-intl, dữ kiện quyết định là ranh giới Server/Client Component. Layout và trang là Server Component, còn `Dashboard` là Client Component; ngôn ngữ phải đi từ máy chủ xuống qua đúng ranh giới đó. next-intl dựng sẵn phần này; B thì để lại cho dự án tự ghép, và đó là phần dễ sai nhất trong cả bài toán.

Đánh đổi thứ ba, giữa C và D, là đánh đổi thật sự của ADR này. C mua được ba thứ: chia sẻ theo đường liên kết, máy tìm kiếm, và dựng tĩnh theo từng ngôn ngữ. **Cả ba đều không có giá trị ở đây.** ShipGuard là bảng điều khiển vận hành nội bộ; không ai gửi cho đồng nghiệp một đường liên kết "bản tiếng Anh", và không có máy tìm kiếm nào đọc nó.

Còn khoản dựng tĩnh thì vốn đã không có để mà mất: `dashboard.tsx` gọi backend từ trình duyệt với `cache: "no-store"` (ADR-0002), nên số liệu chưa bao giờ nằm trong bản dựng tĩnh. Đọc cookie chỉ làm rõ ra một điều đã đúng từ trước.

Đổi lại, D không đụng gì tới cây route. C thì buộc mọi trang chuyển vào `app/[locale]/`, thêm một tệp `middleware.ts` chạy trước mỗi lần tải trang, và làm đổi chữ ký kiểu mà Next 16 sinh ra từ cấu trúc thư mục. Trả cái giá đó để mua ba thứ không dùng đến là một đánh đổi tệ.

## Hệ quả

- **Dễ hơn:** #8 đến #11 viết chuỗi qua `useTranslations` ngay từ đầu, không còn đợt sửa quét ngang nào nữa; số và ngày tự đúng quy ước vì mọi chỗ gọi dùng chung format có tên; `timeZone: "UTC"` khai một lần thay vì lặp lại ở từng chỗ hiện ngày.
- **Khó hơn:** thêm `next-intl` vào phụ thuộc chạy; mọi chuỗi hiển thị mới phải qua hai tệp trong `messages/` thay vì viết thẳng tại chỗ; trang chuyển sang dựng động vì đọc cookie; mọi bài test khẳng định vào chuỗi đã hiển thị phải ghim ngôn ngữ, nếu không sẽ hỏng vào ngày ai đó đổi mặc định.
- **Comment ở `layout.tsx` viết từ #6 đã được sửa.** Nó dự đoán #7 sẽ "thêm lớp `[locale]`" và giải thích việc nâng `ThemeProvider` lên layout gốc bằng dự đoán đó. Việc nâng lên vẫn đúng nên giữ nguyên; dự đoán thì bỏ, vì `[locale]` sẽ không tồn tại.
- **Chi tiết lỗi chỉ dịch được một phần, có chủ ý.** Trạng thái lỗi của bảng điều khiển có ba nguồn: hai chuỗi do dự án viết và một chuỗi do trình duyệt sinh ra khi `fetch` bị từ chối. Chuỗi thứ ba luôn là tiếng Anh và không có đường nào dịch, nên nó hiện nguyên văn bên trong một câu thông báo đã dịch. Dịch hai nguồn đầu mà bỏ nguồn thứ ba là trạng thái đúng nhất có thể đạt được, không phải làm dở.
- **`metadata.description` vẫn để tiếng Anh.** Nó không phải nhãn trên bảng điều khiển và không nằm trong tiêu chí chấp nhận nào của #7.
- **Cần xem lại:** nếu dự án về sau cần chia sẻ đường liên kết theo ngôn ngữ, hoặc cần máy tìm kiếm đọc được từng bản, thì phương án C đáng mở lại. Không phải đổi thư viện — next-intl hỗ trợ sẵn cả hai chế độ. Nhưng cũng đừng đọc thành một việc nhỏ: chuyển sang C là dời **mọi** trang vào `app/[locale]/`, thêm `middleware.ts`, và đổi chữ ký kiểu mà Next sinh ra từ cấu trúc thư mục. Càng để muộn càng nhiều trang phải dời.

## Việc cần làm

1. [x] Thêm `next-intl` vào workspace `frontend`
2. [x] Dựng `i18n/config.ts`, `i18n/request.ts`, `i18n/locale.ts` và bọc `next.config.ts` qua `createNextIntlPlugin()`
3. [x] Chuyển ba bộ `Intl.*` ở phạm vi module sang format có tên, giữ nguyên `timeZone: "UTC"`
4. [x] Tách chuỗi hiển thị ra `messages/vi.json` và `messages/en.json`
5. [x] Cài `button` và dựng nút đổi ngôn ngữ ở `page.tsx`
6. [x] Ghim ngôn ngữ trong `smoke.spec.ts`, thêm `i18n.spec.ts` phủ từng tiêu chí chấp nhận
7. [x] Ghi next-intl vào `frontend/README.md`
