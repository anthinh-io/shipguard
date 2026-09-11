# ShipGuard: Delivery Performance Intelligence — Frontend

Giao diện Next.js hiển thị trạng thái kết nối tới backend FastAPI qua HTTP thật
(không dữ liệu giả).

## Yêu cầu

- [Bun](https://bun.sh/)
- Backend đã chạy sẵn (xem `backend/README.md`, mục "Khởi động") — trang
  chủ và bài kiểm thử Playwright đều gọi HTTP thật tới backend.

## Cấu trúc

```
frontend/
  app/
    layout.tsx        metadata (tiêu đề, mô tả)
    page.tsx           Server Component: đọc BACKEND_URL, gọi GET /health
  tests/
    e2e/
      smoke.spec.ts     Playwright: kiểm tra trang hiển thị trạng thái backend
  playwright.config.ts
```

Cài đặt qua bun workspace khai ở `package.json` gốc repo — `bun install`
chạy từ gốc, không phải từ `frontend/`.

## Khởi động

Chép tệp môi trường rồi điền `BACKEND_URL` nếu backend chạy ở địa chỉ khác
`http://localhost:8000`:

```bash
cp frontend/.env.example frontend/.env
```

Cài phụ thuộc và khởi động — **từ gốc repo**:

```bash
bun install
bun run dev
```

Mở http://localhost:3000 — trang hiển thị trạng thái backend. Nếu backend
chưa chạy, trang vẫn hiển thị được (nhánh "Backend: unreachable (...)").

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

## Cấu hình

| Biến | Dùng ở đâu |
| --- | --- |
| `BACKEND_URL` | `app/page.tsx` — địa chỉ gốc của backend để gọi `/health`. Chỉ đọc phía máy chủ (Server Component), không có tiền tố `NEXT_PUBLIC_` nên không lộ ra trình duyệt. |
