# ShipGuard: Delivery Performance Intelligence — Frontend

Bảng điều khiển Next.js hiển thị chỉ số hiệu suất giao hàng lấy từ backend
FastAPI qua HTTP thật (không dữ liệu giả). Style viết bằng Tailwind CSS v4 (lý
do chọn: `docs/adr/0003-tailwind-css-cho-giao-dien.md`), component dựng sẵn lấy
từ shadcn/ui trên nền Radix
(`docs/adr/0004-shadcn-ui-cho-component-giao-dien.md`), giao diện song ngữ Việt
/ Anh chạy bằng next-intl
(`docs/adr/0005-next-intl-cho-giao-dien-song-ngu.md`), biểu đồ về sau dùng
Recharts.

## Yêu cầu

- [Bun](https://bun.sh/)
- Backend đã chạy sẵn (xem `backend/README.md`, mục "Khởi động") — bảng
  điều khiển và bài kiểm thử Playwright đều gọi HTTP thật tới backend.

## Cấu trúc

```
frontend/
  app/
    layout.tsx           metadata (tiêu đề, mô tả), thẻ lang theo ngôn ngữ
                         đang chọn, bọc NextIntlClientProvider và ThemeProvider
    globals.css          nạp Tailwind, bộ token màu shadcn, nhánh sáng/tối
    page.tsx             Server Component: khung trang, nút đổi ngôn ngữ,
                         gọi <Dashboard />
    components/
      dashboard.tsx      Client Component: gọi GET /dashboard, ba trạng thái
                         (đang tải / lỗi / có số liệu) và hàng ô KPI
      language-toggle.tsx
                         Client Component: nút đổi ngôn ngữ, gọi server action
                         ghi cookie
      ui/                component do shadcn sinh ra — mã của dự án, sửa trực
                         tiếp được, không phải phụ thuộc trong node_modules
  i18n/
    config.ts            danh sách ngôn ngữ, mặc định, tên cookie
    request.ts           đọc cookie mỗi lần dựng trang, nạp bộ chuỗi, khai các
                         format số và ngày dùng chung
    locale.ts            server action ghi cookie
  messages/
    vi.json, en.json     toàn bộ chuỗi hiển thị
  tests/
    e2e/
      smoke.spec.ts      Playwright: số liệu hiện khi mở trang, đúng một lần
                         gọi máy chủ, trạng thái tải và trạng thái lỗi
      i18n.spec.ts       Playwright: đổi ngôn ngữ, giữ lựa chọn sau khi tải
                         lại, và quy ước số/ngày của từng ngôn ngữ
  components.json        cấu hình shadcn CLI: thư viện nền và alias đường dẫn
  next.config.ts         bọc qua plugin của next-intl
  playwright.config.ts
  postcss.config.mjs
```

Cài đặt qua bun workspace khai ở `package.json` gốc repo — `bun install`
chạy từ gốc, không phải từ `frontend/`.

## Khởi động

Chép tệp môi trường rồi điền `NEXT_PUBLIC_BACKEND_URL` nếu backend chạy ở địa
chỉ khác `http://localhost:8000`:

```bash
cp frontend/.env.example frontend/.env
```

Cài phụ thuộc và khởi động — **từ gốc repo**:

```bash
bun install
bun run dev
```

Mở http://localhost:3000 — bảng điều khiển hiện tỷ lệ giao đúng hạn và số đơn
trễ của kỳ mặc định, không phải chọn bộ lọc nào trước. Giao diện lên tiếng Việt,
nút ở góc trên bên phải đổi sang tiếng Anh. Nếu backend chưa chạy, trang vẫn
dựng được và hiện thông báo lỗi thay cho số liệu.

## Thêm component shadcn

Chạy **từ trong `frontend/`**:

```bash
bunx shadcn@latest add <tên>
```

Component rơi vào `app/components/ui/` và thành mã của dự án — sửa thẳng được,
không cần chờ bản phát hành nào. Đường dẫn này do các khoá `aliases` trong
`components.json` quyết định; CLI không có cờ nào đặt chúng nên đừng chạy lại
`init`, sửa tệp đó là đủ.

Registry hiện nhập hàm gộp lớp `cn` thẳng từ gói `cn`, nên dự án **không** có
`app/lib/utils.ts`. Nếu một component về sau nhập `@/app/lib/utils` và `tsc`
báo thiếu, tạo lại tệp đó với đúng một dòng `export { cn } from "cn"` —
`components.json` đã trỏ sẵn `utils` vào đường dẫn này.

Chế độ tối chạy bằng lớp `.dark` do `next-themes` gắn vào thẻ `<html>`, mặc
định bám theo cài đặt hệ điều hành. Đừng quay lại `prefers-color-scheme`:
component `chart` viết cứng tên lớp `.dark` trong JavaScript, chỗ CSS không với
tới. Cũng đừng thêm mẹo `useState` + `useEffect` để chặn lệch hydrate — quy tắc
`react-hooks/set-state-in-effect` là lỗi trong cấu hình này, và script chặn của
`next-themes` đã lo phần đó rồi.

## Thêm chuỗi hiển thị

Mọi nhãn người dùng đọc được nằm trong `messages/vi.json` và `messages/en.json`,
lấy ra bằng `useTranslations`. Đừng viết chuỗi thẳng vào component — thêm một
khoá vào **cả hai** tệp, thiếu một bên thì bản đó hiện ra tên khoá.

Số và ngày lấy qua `useFormatter`, dùng format có tên khai trong
`i18n/request.ts`:

```tsx
format.number(value, "percent")
format.dateTime(date, "fullDate")
```

Đừng dựng `Intl.NumberFormat` hay `Intl.DateTimeFormat` tại chỗ. Không chỉ vì
lặp: một bộ định dạng tạo ở phạm vi module sẽ đóng cứng ngôn ngữ lúc import và
không bao giờ đổi theo nút chuyển ngữ. Và `fullDate` mang theo `timeZone: "UTC"`
— thiếu nó thì máy đặt ở múi giờ phía tây UTC hiện ranh giới kỳ báo cáo lệch
đúng một ngày.

Ngôn ngữ nằm trong cookie `NEXT_LOCALE`, không nằm trong đường dẫn, nên **không
có thư mục `app/[locale]/` và không có `middleware.ts`** — đừng thêm vào, phần
lớn tài liệu next-intl ngoài kia dạy kiểu có tiền tố URL. Lý do chọn cách này:
`docs/adr/0005-next-intl-cho-giao-dien-song-ngu.md`.

Bài test nào khẳng định vào chuỗi đã hiển thị thì phải ghim ngôn ngữ trước, bằng
cách gieo cookie `NEXT_LOCALE` như `smoke.spec.ts` đang làm. Tiếng Việt dùng dấu
phẩy thập phân còn tiếng Anh dùng dấu chấm, nên một bài không ghim sẽ hỏng vào
ngày ai đó đổi mặc định.

## Chạy Playwright (kiểm thử smoke)

Cài trình duyệt cho Playwright (một lần duy nhất trên máy):

```bash
cd frontend && bunx playwright install chromium
```

**Backend phải đang chạy trước khi chạy bài test này** (xem
`backend/README.md`, mục "Khởi động"). Bài test gọi HTTP thật tới backend,
không giả lập — nếu backend chưa sẵn sàng, test sẽ trượt thay vì âm thầm qua.

```bash
bun run test
```

Playwright tự khởi động `bun run dev` ở cổng 3000 trước khi chạy test (xem
`playwright.config.ts`) và tận dụng lại tiến trình dev đang mở sẵn nếu có.

Bài test không khẳng định vào giá trị KPI cụ thể: dữ liệu nạp lại được và kỳ
mặc định tính động từ dữ liệu, nên con số đổi mà hành vi vẫn đúng. Bộ số vàng
được khẳng định ở tầng tính toán phía backend.

## Cấu hình

| Biến | Dùng ở đâu |
| --- | --- |
| `NEXT_PUBLIC_BACKEND_URL` | `app/components/dashboard.tsx` — địa chỉ gốc của backend. Trình duyệt gọi thẳng FastAPI nên biến này có tiền tố `NEXT_PUBLIC_` và được nhúng vào gói JavaScript lúc build; đổi địa chỉ là phải build lại. Backend phải khai origin của frontend trong `CORS_ALLOWED_ORIGINS`. Lý do chọn cách này thay vì proxy qua Next: xem `docs/adr/0002-trinh-duyet-goi-thang-backend-kem-cors.md`. |
