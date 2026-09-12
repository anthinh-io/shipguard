# ShipGuard: Delivery Performance Intelligence — Frontend

Bảng điều khiển Next.js hiển thị chỉ số hiệu suất giao hàng lấy từ backend
FastAPI qua HTTP thật (không dữ liệu giả). Style viết bằng Tailwind CSS v4 (lý
do chọn: `docs/adr/0003-tailwind-css-cho-giao-dien.md`), component dựng sẵn lấy
từ shadcn/ui trên nền Radix
(`docs/adr/0004-shadcn-ui-cho-component-giao-dien.md`), biểu đồ về sau dùng
Recharts.

## Yêu cầu

- [Bun](https://bun.sh/)
- Backend đã chạy sẵn (xem `backend/README.md`, mục "Khởi động") — bảng
  điều khiển và bài kiểm thử Playwright đều gọi HTTP thật tới backend.

## Cấu trúc

```
frontend/
  app/
    layout.tsx           metadata (tiêu đề, mô tả), bọc ThemeProvider
    globals.css          nạp Tailwind, bộ token màu shadcn, nhánh sáng/tối
    page.tsx             Server Component: khung trang, gọi <Dashboard />
    components/
      dashboard.tsx      Client Component: gọi GET /dashboard, ba trạng thái
                         (đang tải / lỗi / có số liệu) và hàng ô KPI
      ui/                component do shadcn sinh ra — mã của dự án, sửa trực
                         tiếp được, không phải phụ thuộc trong node_modules
    lib/
      utils.ts           chỗ shadcn trỏ tới cho hàm gộp lớp `cn`
  tests/
    e2e/
      smoke.spec.ts      Playwright: số liệu hiện khi mở trang, đúng một lần
                         gọi máy chủ, trạng thái tải và trạng thái lỗi
  components.json        cấu hình shadcn CLI: thư viện nền và alias đường dẫn
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
trễ của kỳ mặc định, không phải chọn bộ lọc nào trước. Nếu backend chưa chạy,
trang vẫn dựng được và hiện thông báo lỗi thay cho số liệu.

## Thêm component shadcn

Chạy **từ trong `frontend/`**:

```bash
bunx shadcn@latest add <tên>
```

Component rơi vào `app/components/ui/` và thành mã của dự án — sửa thẳng được,
không cần chờ bản phát hành nào. Đường dẫn này do bốn khoá `aliases` trong
`components.json` quyết định; CLI không có cờ nào đặt chúng nên đừng chạy lại
`init`, sửa tệp đó là đủ.

Chế độ tối chạy bằng lớp `.dark` do `next-themes` gắn vào thẻ `<html>`, mặc
định bám theo cài đặt hệ điều hành. Đừng quay lại `prefers-color-scheme`:
component `chart` viết cứng tên lớp `.dark` trong JavaScript, chỗ CSS không với
tới. Cũng đừng thêm mẹo `useState` + `useEffect` để chặn lệch hydrate — quy tắc
`react-hooks/set-state-in-effect` là lỗi trong cấu hình này, và script chặn của
`next-themes` đã lo phần đó rồi.

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
