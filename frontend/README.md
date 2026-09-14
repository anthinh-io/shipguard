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
    (app)/               route group của mọi trang cần đăng nhập — không
                         thêm tiền tố nào vào URL
      layout.tsx         bọc các trang trong <AuthGate />, <ProfileProvider /> và
                         khung sidebar; đọc cookie sidebar_state để giữ trạng
                         thái thu gọn
      page.tsx           Server Component: đọc searchParams, gọi <Dashboard />
      orders/
        page.tsx         Server Component: đọc searchParams, gọi <OrderList />
      admin/users/
        page.tsx         Server Component: gọi <UserAdmin />
    login/
      page.tsx           trang đăng nhập, nằm ngoài (app)/ nên không bị chặn
    lib/
      api.ts             access token trong bộ nhớ, apiFetch tự gắn và làm
                         mới token, login, logout, changePassword
      next-path.ts       safeNextPath: chỉ nhận đường dẫn quay lại nội bộ
      search-params.ts   dùng chung khi đọc URL: first, parseDayRange (bỏ cả
                         khoảng nếu thiếu một đầu, sai ngày hay ngược chiều)
      dashboard-filters.ts
                         đọc/ghi bộ lọc bảng điều khiển trên URL
      order-list-params.ts
                         đọc/ghi tìm kiếm, bộ lọc, sắp xếp, trang của /orders
                         trên URL
      users-api.ts       gọi /users: liệt kê, tạo, khóa / đổi vai trò, đặt lại
                         mật khẩu — trả kết quả dạng khóa chuỗi cho giao diện
    components/
      auth-gate.tsx      Client Component: chờ /auth/refresh trước khi vẽ
                         trang, thất bại thì về /login?next=...
      login-form.tsx     Client Component: form đăng nhập
      profile-provider.tsx
                         Client Component: gọi /me một lần cho cả khung,
                         useProfile() trả tên, vai trò, id người đang đăng nhập
      app-sidebar.tsx    Client Component: sidebar chung, NAV_ITEMS là danh
                         sách mục điều hướng; mục có `roles` chỉ hiện với các
                         vai trò đó
      app-header.tsx     Client Component: nút menu và tiêu đề trang hiện tại
      nav-user.tsx       Client Component: menu người dùng ở đáy sidebar —
                         tên, vai trò (từ useProfile), đổi mật khẩu, ngôn ngữ,
                         đăng xuất (chỉ rời phiên khi máy chủ xác nhận đã thu hồi)
      change-password-dialog.tsx
                         Client Component: hộp thoại tự đổi mật khẩu
      user-admin.tsx     Client Component: trang Quản trị — bảng tài khoản, menu
                         "…" mỗi dòng (ẩn ở dòng Super Admin và dòng của chính
                         mình), từ chối khi GET /users trả 403
      create-user-dialog.tsx, lock-user-dialog.tsx, reset-user-password-dialog.tsx
                         Client Component: tạo tài khoản, xác nhận khóa, đặt
                         lại mật khẩu cho người khác
      dashboard.tsx      Client Component: gọi GET /dashboard, ba trạng thái
                         (đang tải / lỗi / có số liệu) và hàng ô KPI; bộ lọc
                         đọc từ và ghi lên URL
      filter-bar.tsx     Client Component: thanh lọc bảng điều khiển
      date-range-picker.tsx, customer-state-select.tsx, seller-combobox.tsx
                         Client Component: ô chọn khoảng ngày, bang, người bán
                         dùng chung cho cả hai thanh lọc
      order-list.tsx     Client Component: gọi GET /orders — ô tìm mã đơn,
                         bảng 8 cột sắp được, phân trang nhảy trang
      order-filter-bar.tsx
                         Client Component: thanh lọc /orders — trạng thái, kết
                         quả giao, ngày đặt, ngày giao, bang (GET /customer-states),
                         người bán, xoá hết
      language-toggle.tsx
                         Client Component: nút đổi ngôn ngữ ở trang đăng nhập
                         và hook useLocaleSwitch dùng chung với menu người dùng
      ui/                component do shadcn sinh ra — mã của dự án, sửa trực
                         tiếp được, không phải phụ thuộc trong node_modules
    hooks/
      use-mobile.ts      useIsMobile cho sidebar (shadcn sinh, đã viết lại
                         bằng useSyncExternalStore)
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
                         gọi máy chủ, trạng thái tải và trạng thái lỗi; trang
                         Đơn hàng với dữ liệu thật
      orders.spec.ts     Playwright: trang Đơn hàng (giả lập máy chủ) — tìm,
                         sắp xếp, nhảy trang, đường liên kết chia sẻ
      order-filters.spec.ts
                         Playwright: thanh lọc /orders (giả lập máy chủ) — từng
                         bộ lọc, nửa khoảng ngày chưa lọc, kết hợp, xoá hết, tải lại
      order-list-params.spec.ts
                         kiểm đọc/ghi tham số URL của /orders, không mở trình duyệt
      url-filters.spec.ts
                         Playwright: bộ lọc bảng điều khiển trên URL (giả lập
                         máy chủ) — đường liên kết chia sẻ, tải lại, Back, nhãn
                         người bán, xoá hết
      dashboard-filters.spec.ts
                         kiểm đọc/ghi bộ lọc bảng điều khiển trên URL, không mở
                         trình duyệt
      i18n.spec.ts       Playwright: đổi ngôn ngữ, giữ lựa chọn sau khi tải
                         lại, và quy ước số/ngày của từng ngôn ngữ
      auth.spec.ts       Playwright: chặn khi chưa đăng nhập, quay lại đúng
                         trang, giữ phiên khi tải lại, làm mới token giữa chừng
      app-shell.spec.ts  Playwright: sidebar, thu gọn giữ sau tải lại, ngăn kéo
                         trên màn hình hẹp, đổi ngôn ngữ từ menu, đăng xuất
      change-password.spec.ts
                         Playwright: hộp thoại đổi mật khẩu (giả lập máy chủ)
      user-admin.spec.ts Playwright: trang Quản trị (giả lập máy chủ) — ẩn và
                         từ chối theo vai trò, tạo, khóa có xác nhận, đổi vai
                         trò, đặt lại mật khẩu, song ngữ
      next-path.spec.ts  kiểm safeNextPath, không mở trình duyệt
      session.ts         mockSession / mockMe / signInForReal / switchLanguage
                         dùng chung cho các spec
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

Mở http://localhost:3000 — lần đầu sẽ được đưa tới trang đăng nhập; đăng nhập
bằng tài khoản Super Admin khai trong `.env` gốc (xem `backend/README.md`). Sau
đó bảng điều khiển hiện tỷ lệ giao đúng hạn và số đơn trễ của kỳ mặc định,
không phải chọn bộ lọc nào trước. Giao diện lên tiếng Việt; đổi sang tiếng Anh,
đổi mật khẩu và đăng xuất nằm trong menu người dùng ở đáy sidebar. Nếu backend
chưa chạy, trang không xác nhận được phiên nên cũng dừng ở trang đăng nhập, và
bấm đăng nhập sẽ báo không kết nối được máy chủ.

## Đăng nhập và gọi backend

Access token chỉ nằm trong bộ nhớ trình duyệt, refresh token nằm trong cookie
httpOnly (`docs/adr/0006-goi-thang-backend-kem-xac-thuc-jwt.md`). Máy chủ Next
không thấy token, nên việc chặn nằm ở client, trong `(app)/layout.tsx` — **không
có `middleware.ts` / `proxy.ts`**.

- Trang mới cần đăng nhập đặt trong `app/(app)/`; nó tự đi qua cổng chặn và tự
  có sidebar. Thêm mục điều hướng cho nó vào `NAV_ITEMS` trong `app-sidebar.tsx`
  (tiêu đề trên thanh đầu trang cũng lấy từ đó) cùng khoá `nav.*` trong
  `messages/`; trang chỉ dành cho một số vai trò thì khai `roles` cho mục đó —
  đó chỉ là ẩn mục, máy chủ vẫn phải tự trả 403.
- Mọi lời gọi backend đi qua `apiFetch` trong `app/lib/api.ts`, **đừng gọi
  `fetch` trần**: thiếu header `Authorization` là 401, và chỉ `apiFetch` biết làm
  mới token rồi thử lại.
- Đừng tự gọi `/auth/refresh` ở chỗ khác. Refresh token chỉ dùng được một lần;
  `refreshAccessToken` gộp mọi lần làm mới đồng thời vào một lời gọi, gọi riêng
  là tự đá người dùng ra trang đăng nhập.

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

Ngoại lệ duy nhất: `Order Value` trong `order-list.tsx` luôn hiện kiểu Brazil
(`R$ 13.664,08`) ở cả hai ngôn ngữ, nên bộ định dạng `pt-BR` ở đó cố ý đóng cứng
ở phạm vi module. Dấu thời gian backend trả không kèm múi giờ
(`"2018-10-17T02:30:18"`) phải cắt lấy 10 ký tự ngày trước khi đưa vào `new
Date()` — đọc nguyên chuỗi thì trình duyệt hiểu theo giờ máy, và `fullDate` hiện
lệch một ngày ở máy phía đông UTC.

## Trạng thái trang trên URL

Trang nào cần giữ tìm kiếm, sắp xếp hay số trang trên URL (để gửi đường liên kết
cho người khác) thì làm như `app/(app)/orders/page.tsx` hay `app/(app)/page.tsx`:
Server Component đọc prop `searchParams`, chuẩn hoá rồi truyền xuống Client
Component; client đổi URL bằng `router.push` / `router.replace` và Next dựng lại
trang với tham số mới. Đừng dùng `useSearchParams` — nó bắt buộc bọc
`<Suspense>`, thiếu thì `next build` hỏng.

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
`backend/README.md`, mục "Khởi động"). `smoke.spec.ts` và `i18n.spec.ts` gọi
HTTP thật tới backend, không giả lập — nếu backend chưa sẵn sàng, test sẽ trượt
thay vì âm thầm qua. Hai tệp này đăng nhập thật bằng `SUPER_ADMIN_EMAIL` /
`SUPER_ADMIN_PASSWORD` đọc từ `.env` gốc (`signInForReal`), nên nếu đã đổi mật
khẩu Super Admin bằng script đặt lại thì phải sửa `.env` theo.

Spec giả lập `/dashboard` thì giả lập luôn `/auth/refresh` và `/me` bằng
`mockSession` trong `beforeEach`; thiếu nó thì cổng chặn (hoặc lời gọi `/me` của
khung ứng dụng mang token giả) đưa trang về `/login` và bài test không thấy bảng
điều khiển. Spec tự giả lập `/auth/refresh` thì gọi `mockMe`. Cả hai mặc định là
một nhân viên vận hành; truyền thêm hồ sơ (`mockSession(context, { role:
"logistics_manager" })`) khi cần vai trò khác. Đừng viết bài Playwright đổi mật
khẩu thật: `signInForReal` sẽ hỏng ở mọi lần chạy sau. Trang Quản trị cũng luôn
giả lập `/users`: tài khoản không xóa được, tạo thật là để lại rác sau mỗi lần chạy.

```bash
bun run test
```

Playwright tự khởi động `bun run dev` ở cổng 3000 trước khi chạy test (xem
`playwright.config.ts`) và tận dụng lại tiến trình dev đang mở sẵn nếu có.

Bài test không khẳng định vào giá trị KPI cụ thể: dữ liệu nạp lại được và kỳ
mặc định tính động từ dữ liệu, nên con số đổi mà hành vi vẫn đúng. Bộ số vàng
được khẳng định ở tầng tính toán phía backend. Ngoại lệ là bài trang Đơn hàng:
tổng 99.441 đơn, đơn giá trị lớn nhất và mã `e481f5` không phụ thuộc kỳ nào mà là
bất biến của bộ CSV.

## Cấu hình

| Biến | Dùng ở đâu |
| --- | --- |
| `NEXT_PUBLIC_BACKEND_URL` | `app/lib/api.ts`, `app/components/dashboard.tsx`, `app/components/order-list.tsx`, `app/components/order-filter-bar.tsx`, `app/components/seller-combobox.tsx`, `app/components/profile-provider.tsx`, `app/lib/users-api.ts` — địa chỉ gốc của backend. Trình duyệt gọi thẳng FastAPI nên biến này có tiền tố `NEXT_PUBLIC_` và được nhúng vào gói JavaScript lúc build; đổi địa chỉ là phải build lại. Backend phải khai origin của frontend trong `CORS_ALLOWED_ORIGINS`; cookie refresh token chỉ đi kèm khi frontend và backend cùng site. Cơ chế token: `docs/adr/0006-goi-thang-backend-kem-xac-thuc-jwt.md`; lý do không proxy qua Next vẫn đọc ở `docs/adr/0002-trinh-duyet-goi-thang-backend-kem-cors.md`. |
