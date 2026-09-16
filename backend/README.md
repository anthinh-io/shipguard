# ShipGuard: Delivery Performance Intelligence — Backend

Máy chủ FastAPI và cơ sở dữ liệu PostgreSQL cho hệ thống giám sát hiệu suất giao hàng.

## Yêu cầu

- Docker (kèm Docker Compose)
- [uv](https://docs.astral.sh/uv/) — tự tải Python 3.12 về, không cần cài Python sẵn

Toàn bộ lệnh dưới đây chạy **từ gốc repo**. Dự án dùng uv workspace: một môi
trường ảo duy nhất ở gốc, `backend/` là một thành viên.

## Cấu trúc

```
backend/
  app/
    main.py        khởi tạo FastAPI, gắn router, tạo Super Admin lúc khởi động
    core/          cấu hình, kết nối cơ sở dữ liệu, bảo mật
      config.py    đọc .env ở gốc repo
      db.py        engine, session, lớp Base của model
      security.py  băm mật khẩu, ký và xác minh access token
    api/
      deps.py      SessionDep, CurrentUserDep, UserAdminDep — phụ thuộc dùng chung
                   cho các endpoint
      routes/      mỗi tệp một nhóm endpoint (auth.py: /auth/*, users.py: /me và
                   /users, orders.py: /orders, /orders/export,
                   /orders/{order_id}/notes, /customer-states)
    services/      logic nghiệp vụ; route chỉ đọc tham số và gọi vào đây
      auth.py      đăng nhập, cấp và xoay vòng refresh token
      users.py     tạo User, Super Admin, quản trị User (khóa, đổi vai trò, đặt
                   lại mật khẩu), tự đổi mật khẩu
      order_notes.py
                   Internal Note: đọc, thêm; không sửa, không xóa
      orders.py    danh sách đơn: tìm tiền tố mã đơn, sắp xếp, phân trang
      queries.py   mảnh truy vấn dùng chung: DELIVERED, like_prefix, within_days,
                   sold_by
    scripts/       lệnh chạy tay: nạp dữ liệu, đặt lại mật khẩu Super Admin
    alembic/       migration
  tests/
  alembic.ini
  pyproject.toml   phụ thuộc riêng của backend
```

Bố cục theo `fastapi/full-stack-fastapi-template`.

## Khởi động

Chép tệp môi trường rồi điền `POSTGRES_USER`, `POSTGRES_PASSWORD`, `JWT_SECRET_KEY`
và ba biến `SUPER_ADMIN_*` của bạn:

```bash
cp .env.example .env
```

Dựng cơ sở dữ liệu, cài phụ thuộc, chạy migration, khởi động máy chủ:

```bash
docker compose up -d --wait postgres
uv sync
uv run alembic -c backend/alembic.ini upgrade head
uv run python -m app.scripts.build_derived_data
uv run python -m app.scripts.train_risk_model
uv run fastapi dev backend/app/main.py
```

`--wait` chặn cho tới khi Postgres nhận kết nối. Thiếu nó thì lệnh migration
ngay sau đó có thể chạy trong lúc cơ sở dữ liệu còn đang khởi tạo và bị từ chối.

Lệnh `build_derived_data` làm trọn một lượt trong **một giao dịch duy nhất**: nạp 9 tệp
CSV Olist trong `datasets/raw/` vào 9 bảng TẠM nguyên trạng, chạy bảy câu `INSERT ...
SELECT` dựng bảy bảng dẫn xuất từ chúng, rồi kết thúc giao dịch — bảng tạm tự biến mất
(`ON COMMIT DROP`). Chạy lại an toàn: bảy bảng dẫn xuất được xoá sạch (`TRUNCATE`) rồi
dựng lại trong cùng giao dịch ấy, nên không bao giờ bị nhân đôi dữ liệu, và giao dịch
hỏng giữa chừng không để lại bảng tạm nào. Xem mục [Lớp dẫn xuất](#lớp-dẫn-xuất) bên dưới.

Lệnh `train_risk_model` huấn luyện bộ mô hình dự đoán rủi ro. Nó **không đụng cơ sở
dữ liệu** — đọc thẳng tệp CSV trong `datasets/raw/` (ADR-0010) — nên không phụ thuộc
hai lệnh trên và chạy được cả khi Postgres đang tắt. Xếp ở vị trí này vì backend cần
tệp mô hình thì mới dự đoán được. Xem
[Huấn luyện mô hình rủi ro](#huấn-luyện-mô-hình-rủi-ro) bên dưới.

Kiểm tra: `curl http://localhost:8000/health` trả về
`{"status":"ok","database":"connected"}`. Nếu cơ sở dữ liệu không kết nối được,
endpoint trả mã 503 kèm `{"status":"degraded","database":"disconnected"}`.

Kiểm tra tiếp: `curl http://localhost:8000/dashboard -H 'Authorization: Bearer
<access_token>'` (lấy token ở mục [Đăng nhập](#đăng-nhập)) trả về kỳ báo cáo mặc
định kèm khối KPI; thiếu token thì 401. Truyền `?start_date=...&end_date=...` để chọn kỳ khác — hai tham
số phải đi cùng nhau, thiếu một bên thì endpoint trả mã 422.

Mỗi điểm của `late_rate_trend.points` có `bucket_start` (mốc `date_trunc`, có thể trước
ngày đầu kỳ; tuần tính từ thứ Hai), cùng `bucket_from` / `bucket_to` là khoảng thật của
điểm đó, đã kẹp vào kỳ báo cáo và tính cả hai đầu. Drill-down chép nguyên hai giá trị
này vào `delivered_from` / `delivered_to` của `/orders`, cộng `delivery_outcome=late`.
`total` nhận về đúng bằng `late_orders` của điểm.

`GET /orders` (cũng đòi token) trả một trang 50 đơn: `{"items", "total", "page",
"page_size"}`. Tham số, đều không bắt buộc:

| Tham số | Giá trị | Mặc định |
| --- | --- | --- |
| `order_id` | Tiền tố mã đơn, không phân biệt hoa thường; `%` và `_` là ký tự thường | không lọc |
| `order_status` | Một trong tám `Order Status`: `created`, `approved`, `invoiced`, `processing`, `shipped`, `delivered`, `canceled`, `unavailable` | không lọc |
| `delivery_outcome` | `on_time`, `late`, `no_outcome` — cùng định nghĩa với cột `delivery_outcome` của từng dòng | không lọc |
| `purchased_from`, `purchased_to` | Khoảng ngày đặt `YYYY-MM-DD`, tính cả hai đầu; phải đi cùng nhau | không lọc |
| `delivered_from`, `delivered_to` | Khoảng ngày giao thực tế, cùng luật; độc lập với khoảng ngày đặt | không lọc |
| `customer_state` | Bang của khách nhận hàng (`Region`), không phải bang người bán | không lọc |
| `seller_id` | Mã người bán; `Multi-Seller Order` thuộc về mọi người bán tham gia, vẫn một dòng mỗi đơn | không lọc |
| `sort` | `purchased_at`, `estimated_delivery_date`, `delivered_at`, `order_value` | `purchased_at` |
| `direction` | `asc`, `desc` | `desc` |
| `page` | Số nguyên từ 1; vượt quá trang cuối thì `items` rỗng, `total` giữ nguyên (chỉ số lớn tới mức tràn `OFFSET` bigint mới nhận 422) | `1` |

Giá trị ngoài danh sách nhận 422, và chỉ một đầu của một khoảng ngày cũng nhận 422
kèm lý do trong `detail` — cùng luật với `start_date` / `end_date` của `/dashboard`.
Các bộ lọc kết hợp với nhau bằng AND. Khoảng ngày xét nửa mở trên dấu thời gian (`>=`
nửa đêm ngày đầu, `<` nửa đêm sau ngày cuối) để còn dùng được chỉ mục, nên đơn đặt lúc
02:30 ngày cuối vẫn được tính. Bộ lọc `late` ra 6.534 đơn; nếu thấy 6.535 là đã tính
nhầm đơn đã hủy có ngày giao, 7.826 là đã so theo giờ thay vì theo ngày.

`GET /orders/export` (đòi token) nhận đúng bộ tham số lọc và sắp xếp của `GET /orders`,
không có `page`, và stream **mọi** đơn khớp dưới dạng `text/csv` UTF-8 có BOM. Thiếu
BOM thì Excel đọc sai dấu. Dòng đầu là tên trường của một dòng `/orders`. Ô trống là
giá trị `null`. `order_id` đủ 32 ký tự. Hai endpoint đọc tham số qua cùng một
dependency `order_query`, nên không bao giờ lệch nhau. Route này phải khai báo trước
`/orders/{order_id}`, không thì `export` bị hiểu là một mã đơn. Trình duyệt tải bằng
`fetch` kèm token rồi lưu blob, vì một thẻ `<a href>` không mang được header
`Authorization`.

`GET /customer-states` (đòi token) trả mảng mọi bang có đơn, sắp tăng dần, không áp bộ
lọc nào — tuỳ chọn cho ô chọn bang của trang đơn hàng. Khác danh sách bang trong
`/dashboard`, vốn chỉ tính đơn đã giao. Cùng lý do, ô gợi ý người bán của trang đơn
hàng gọi `GET /sellers?q=...&delivered_only=false`: mặc định `/sellers` chỉ gợi ý người
bán có đơn đã giao (đúng cho bảng điều khiển), còn `false` gợi ý cả 125 người bán chưa
giao xong đơn nào. Số `delivered_orders` trên gợi ý vẫn luôn là số đơn đã giao.

Ô trống (`delivered_at` của đơn chưa giao,
`order_value` của đơn không có sản phẩm) luôn nằm cuối, cả khi sắp tăng lẫn giảm.
Đơn trùng giá trị sắp xếp được xếp tiếp theo `order_id`, nên lật trang không trả
trùng hay bỏ sót đơn. Mỗi dòng mang `delivery_outcome`: `on_time` / `late` chỉ với
`Delivered Order`, mọi đơn khác là `no_outcome` — kể cả đơn đã hủy lỡ có ngày giao.
`order_value` là số thực, không phải chuỗi thập phân.

`GET /orders/{order_id}` (đòi token) trả mọi thứ về một đơn cho trang chi tiết; mã
không tồn tại nhận 404 `{"detail": "Order not found"}`.

| Khối | Nội dung |
| --- | --- |
| `order_id`, `order_status`, `delivery_outcome`, `order_value` | Như một dòng của `GET /orders` |
| `timeline` | Bốn mốc `purchased_at`, `payment_approved_at`, `handed_to_carrier_at`, `delivered_at` kèm `estimated_delivery_date`, và ba chặng `payment_approval_days`, `seller_handling_days`, `carrier_transit_days` (số ngày, đọc từ cột sinh). Mốc hay chặng chưa có là `null`; chặng có thể âm vì dữ liệu gốc có đơn bàn giao vận chuyển trước lúc duyệt |
| `address` | `customer_city`, `customer_state`, `customer_zip_code_prefix` (chuỗi đủ 5 chữ số) |
| `items` | Từng sản phẩm theo `order_item_id`: `product_id`, `category` (tên tiếng Anh; chưa có bản dịch thì tên gốc; không có danh mục thì `null`), `price`, `freight_value`, `seller_id` |
| `sellers` | Người bán tham gia: `seller_id`, `seller_city`, `seller_state` (bang gửi đi) |
| `payments` | Theo `payment_sequential`: `payment_type`, `payment_installments`, `payment_value` |
| `reviews` | Theo `review_sequential`, cũ nhất trước: `review_score`, `comment_title`, `comment_message`, `created_at` |

Danh sách rỗng nghĩa là đơn không có phần đó (775 đơn không có sản phẩm, nhiều đơn
không có đánh giá), không phải lỗi. Sản phẩm, thanh toán và đánh giá tra trên ba bảng
dẫn xuất tương ứng, qua khoá chính ghép mở đầu bằng `order_id` (migration
`0009_derived_order_lines`); không bảng thô nào còn nằm trên đường đọc này.

Thứ tự đánh giá đọc theo `review_sequential` chứ không theo thời điểm tạo: 547 đơn Olist
có nhiều hơn một đánh giá, và 157 cặp (đơn, thời điểm tạo) trùng nhau, nên sắp theo riêng
thời điểm tạo cho thứ tự bất định giữa các lần chạy.

`GET /orders/{order_id}/notes` (đòi token) trả các `Internal Note` của đơn, mới nhất trên
cùng: `{"id", "body", "created_at", "author": {"display_name", "role"}}`. `POST` cùng
đường dẫn với `{"body": "..."}` thêm một ghi chú mang tên người đang đăng nhập và trả 201.
Nội dung cắt khoảng trắng hai đầu, còn 1–2.000 ký tự, ngoài khoảng đó trả 422. Mã đơn
không tồn tại trả 404 ở cả hai phương thức. Không có PATCH hay DELETE: ghi nhầm thì thêm
ghi chú đính chính. `created_at` là mốc thật có múi giờ, không theo quy ước UTC của dữ liệu
Olist. Tác giả `Locked User` vẫn hiện tên.

### Tạo đơn và Risk Assessment

`POST /orders` (đòi token) ghi một đơn thật cùng lần `Risk Assessment` đầu tiên **trong
một giao dịch** (ADR-0009) — đơn không bao giờ được tồn tại mà thiếu đánh giá
(CONTEXT.md, mục `Risk Assessment`). Thân yêu cầu:

| Trường | Ghi chú |
| --- | --- |
| `purchased_at` | ISO 8601 kèm offset, không ở tương lai |
| `estimated_delivery_date` | Ngày (`YYYY-MM-DD`), không sớm hơn ngày của `purchased_at` |
| `customer_state`, `customer_city`, `customer_zip_code_prefix` | Địa chỉ giao; `customer_state` phải là một trong các bang đã có đơn |
| `items[]` | `seller_id` (phải tồn tại), `product_category_name` (phải tồn tại), `product_weight_g` (tuỳ chọn), `price`, `freight_value` — tối thiểu một dòng |
| `payments[]` | `payment_type` (`credit_card` / `boleto` / `voucher` / `debit_card`), `payment_installments`, `payment_value` — tối thiểu một dòng; chỉ `credit_card` mới nhận số kỳ trả góp lớn hơn 1 |

Trả 201 kèm `{"order_id", "risk_assessment"}`; `risk_assessment` gồm `id`, `checkpoint`
(luôn `order_placed` ở đây), `late_probability`, `is_high_risk`, `threshold_used`,
`model_version` và `risk_cause: {stage, seller_id, median_days, historical_median_days,
excess_days}` — chặng gây rủi ro nhất trong các chặng chưa xảy ra, kèm tên người bán nếu
nguyên nhân là khâu người bán.

Dữ liệu sai một trường (thiếu dòng sản phẩm/thanh toán, người bán hay danh mục không tồn
tại, bang ngoài danh sách, trả góp nhiều kỳ mà không phải thẻ tín dụng, thời điểm ở tương
lai, ngày cam kết trước ngày đặt, số âm) trả 422 kèm `detail` dạng danh sách
`[{"type", "loc", "msg"}]` chỉ đúng trường sai — cùng hình dạng lỗi Pydantic tự sinh, kể
cả với các lỗi cần tra cơ sở dữ liệu (người bán, danh mục, bang) mà Pydantic không tự
kiểm được. Không có gì được lưu khi có lỗi. Chưa có tệp mô hình thì trả 503 và không tạo
đơn nào.

`GET /orders/{order_id}/risk-assessments` (đòi token) trả lịch sử đánh giá của một đơn,
mới nhất trên cùng. Đơn Olist lịch sử không bao giờ có đánh giá nên trả mảng rỗng; mã đơn
không tồn tại trả 404.

`GET /product-categories` (đòi token, **cấp gốc**) trả danh mục sản phẩm kèm nhãn hiển
thị — `[{"name", "label"}]` — cho ô chọn danh mục của biểu mẫu tạo đơn. Cùng lý do với
`/customer-states`: mẫu chặn `${BACKEND_URL}/orders**` của Playwright vượt cả dấu gạch
chéo, nên đường dẫn không nằm dưới `/orders`.

## Đăng nhập

Cơ chế token theo `docs/adr/0006-goi-thang-backend-kem-xac-thuc-jwt.md`: access
token JWT sống 15 phút gửi qua header `Authorization: Bearer`, refresh token sống
7 ngày trong cookie `httpOnly` chỉ đi kèm `/auth/*`.

Lần khởi động đầu tiên tạo `Super Admin` từ `SUPER_ADMIN_EMAIL`,
`SUPER_ADMIN_PASSWORD`, `SUPER_ADMIN_NAME`. Từ đó các biến này bị bỏ qua — đổi
chúng rồi khởi động lại không tạo thêm hay sửa tài khoản nào. Backend **không
khởi động** nếu chưa chạy migration, hoặc nếu `SUPER_ADMIN_EMAIL` trùng một
`User` thường đã có; thông báo lỗi nêu rõ lý do.

```bash
curl -i -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"..."}'
curl http://localhost:8000/me -H 'Authorization: Bearer <access_token>'
```

| Endpoint | Việc |
| --- | --- |
| `POST /auth/login` | Trả access token, đặt cookie refresh token. Sai mật khẩu, email không tồn tại và tài khoản bị khóa đều nhận cùng một 401 |
| `POST /auth/refresh` | Đổi cookie hiện có lấy access token và cookie mới; cookie cũ bị thu hồi, dùng lại nhận 401 |
| `POST /auth/logout` | Thu hồi cookie hiện có và xóa nó khỏi trình duyệt |
| `POST /auth/password` | Tự đổi mật khẩu, cần access token; body `{"current_password", "new_password"}`. Thu hồi mọi refresh token của người đó rồi trả access token và cookie mới cho phiên đang dùng — mọi phiên khác bị đăng xuất. Sai mật khẩu cũ nhận 400, mật khẩu mới dưới 8 ký tự nhận 422 (không phải 401: frontend hiểu 401 là phiên hết hạn) |
| `GET /me` | Người đang đăng nhập: email, tên, vai trò, claim. Thiếu token hợp lệ thì 401 |

Mọi route khác đều đòi access token hợp lệ, thiếu thì 401 — trừ `/health` và
`/auth/*` (`/auth/logout` chỉ cần cookie; `/auth/password` là ngoại lệ, vẫn đòi
access token).

Cookie refresh token chưa đặt cờ `Secure` vì môi trường phát triển chạy http.
Triển khai qua HTTPS thì phải bật lại.

### Quản trị User

Bốn endpoint dưới đây chỉ dành cho `logistics_manager` và `super_admin`; vai trò
khác nhận 403, thiếu token nhận 401. Vai trò người gọi đọc từ access token, nên
người vừa bị hạ vai trò vẫn gọi được tối đa 15 phút.

| Endpoint | Việc |
| --- | --- |
| `GET /users` | Mọi `User`, theo thứ tự tạo: `id`, `email`, `display_name`, `role`, `is_locked` |
| `POST /users` | Tạo `User`; body `{"display_name", "email", "role", "password"}`, trả 201 kèm dòng vừa tạo. Email trùng (không phân biệt hoa thường) nhận 409; tên trống, email sai định dạng, mật khẩu dưới 8 ký tự hay `role` ngoài `operations_staff` / `logistics_manager` nhận 422 |
| `PATCH /users/{id}` | Đổi vai trò hoặc khóa / mở khóa; body `{"role"?, "is_locked"?}`, trả dòng sau khi đổi. Đổi vai trò và khóa thu hồi mọi refresh token của người đó |
| `POST /users/{id}/password` | Đặt lại mật khẩu; body `{"new_password"}`, trả 204. Thu hồi mọi refresh token của người đó |

Quy tắc bảo vệ kiểm ở backend: thao tác lên `Super Admin` hay lên chính người gọi
nhận 403 (tự đổi mật khẩu dùng `POST /auth/password`), id không tồn tại nhận 404,
và không có endpoint xóa `User`. Email kiểm bằng `EmailStr`, vốn từ chối tên miền
dành riêng như `.local`, `.test`, `.localhost` — tài khoản tạo qua API phải dùng
tên miền thật.

### Đặt lại mật khẩu Super Admin

Không có luồng quên mật khẩu qua email. Người có quyền vào máy chủ chạy:

```bash
uv run python -m app.scripts.reset_super_admin_password
```

Lệnh hỏi mật khẩu mới hai lần (tối thiểu 8 ký tự, không hiện khi gõ). Đặt lại
xong, mọi phiên cũ của Super Admin bị đăng xuất.

## Lớp dẫn xuất

Dữ liệu Olist chỉ tồn tại ở hai nơi: tệp CSV trên đĩa và lớp dẫn xuất trong cơ sở dữ
liệu. Không còn bảng thô nào nằm lại trong lược đồ — chín bảng `raw_*` cũ đã bị xoá ở
migration `0010_drop_raw_tables`, và bước dựng tự nạp CSV vào bảng tạm cùng tên trong
giao dịch của nó (ADR-0010).

| Bảng | Nội dung |
| --- | --- |
| `orders` | Một dòng mỗi đơn — bốn mốc thời gian, ba khoảng thời gian, cờ trễ, bang, thành phố và mã bưu chính của khách, điểm đánh giá thấp nhất, trạng thái đơn, giá trị đơn |
| `order_sellers` | Bảng nối đơn với người bán, dùng khi lọc theo người bán |
| `order_items` | Dòng sản phẩm: thứ tự dòng, mã sản phẩm, tên danh mục gốc, cân nặng, giá, phí vận chuyển, người bán |
| `order_payments` | Dòng thanh toán: thứ tự, hình thức, số kỳ trả góp, số tiền |
| `order_reviews` | Đánh giá của khách: thứ tự trong đơn, số sao, tiêu đề, nội dung, thời điểm tạo |
| `product_categories` | Bảng tra danh mục: tên danh mục gốc và nhãn tiếng Anh tương ứng |
| `sellers` | Người bán: `seller_id`, `seller_city`, `seller_state`, `seller_zip_code_prefix` (mã bưu chính, mô hình dự đoán dùng để tính khoảng cách người bán → khách) |
| `order_notes` | Internal Note — bảng nghiệp vụ, không phải bảng dẫn xuất |
| `risk_assessments` | `Risk Assessment` — bảng nghiệp vụ, không phải bảng dẫn xuất |

Ba bảng dòng sản phẩm, dòng thanh toán và đánh giá **có** khoá ngoại tới `orders`: chúng được
TRUNCATE rồi dựng lại cùng một lượt với `orders`, đúng như `order_sellers`, nên khoá ngoại
không chặn bước dựng mà còn bắt được dòng mồ côi. `product_categories` không gắn với đơn nên
không có khoá ngoại nào. Bất kỳ thao tác nào xoá dòng khỏi `orders` phải xoá bốn bảng con
trước — `build_derived_data` gộp cả bảy vào một câu `TRUNCATE`, còn test nào thu nhỏ `orders`
thì xoá theo thứ tự con trước cha.

`order_items.product_category_name` lưu tên danh mục **gốc**, không phải nhãn tiếng Anh đã tra
sẵn: nhãn nằm ở `product_categories` và được `LEFT JOIN` lúc đọc. Nhờ vậy sửa bản dịch không
phải dựng lại 112.650 dòng, và hai danh mục chưa có bản dịch (`pc_gamer`,
`portateis_cozinha_e_preparadores_de_alimentos`) vẫn hiện tên gốc thay vì để trống.

`order_notes.order_id` thì ngược lại, cố ý không có khoá ngoại tới `orders`. `build_derived_data`
TRUNCATE rồi dựng lại `orders`, nên khoá ngoại sẽ chặn bước dựng, hoặc xóa lan mọi ghi chú
nếu thêm CASCADE. Tầng dịch vụ tự kiểm đơn tồn tại khi thêm ghi chú. Dựng lại dữ liệu dẫn
xuất không đụng tới ghi chú. Test `auth_session` TRUNCATE `order_notes` cùng `users`, vì
ghi chú có khoá ngoại tới tác giả.

`risk_assessments.order_id` cũng cố ý không có khoá ngoại tới `orders`, vì lý do mạnh hơn
`order_notes`: chính bảng này là thứ chặn `build_derived_data` (xem đoạn dưới). Có khoá
ngoại tới `users` cho `created_by` và `handled_by` — `User` không bao giờ bị xóa nên khoá
ngoại này không chặn gì. Dựng đủ ba phần (đánh giá, xử lý, đối chiếu) ngay từ migration
`0011_risk_assessments`; cột xử lý và đối chiếu để trống cho tới các ticket dùng tới chúng.

**`build_derived_data` tự dừng nếu đã có bất kỳ `Risk Assessment` nào** (ADR-0007, ADR-0010):
sự tồn tại của một dòng ở đó là dấu hiệu duy nhất có đơn tạo trong Ship Guard, và `TRUNCATE`
sẽ xoá mất đơn đó không hoàn tác được. Thông báo lỗi nêu rõ lý do, không đổi gì. Bộ test tự
dựng lại dữ liệu dẫn xuất ở vài chỗ giữa phiên (kiểm tính lặp lại, kiểm ghi chú sống sót);
những chỗ đó gọi `build_all(..., allow_existing_assessments=True)` qua hàm bọc
`rebuild_derived_data` trong `tests/conftest.py` — cờ này không tồn tại trong `main()`, nên
người vận hành không có đường nào bỏ qua chốt chặn.

Migration nào thêm cột vào bảng dẫn xuất (như `0007_order_detail` thêm thành phố và
mã bưu chính, hay `0011_risk_assessments` thêm `sellers.seller_zip_code_prefix`) thì sau
`alembic upgrade head` phải chạy lại `build_derived_data`. Chưa chạy thì cột mới để trống:
trang chi tiết đơn vẫn mở được nhưng thành phố và mã bưu chính hiện là chưa có, còn
`POST /orders` trả 503 vì thiếu mã bưu chính người bán để tính khoảng cách.
`customer_zip_code_prefix` và `seller_zip_code_prefix` đều là chuỗi được đệm lại đủ 5 chữ
số: bảng tạm nhận CSV giữ các cột này ở kiểu số nguyên nên `01310` vào thành `1310`.

Cùng luật đó áp cho migration thêm **bảng** dẫn xuất: sau `0009_derived_order_lines` phải chạy
lại `build_derived_data`, nếu không bốn bảng mới rỗng và trang chi tiết hiện mọi đơn như không
có sản phẩm, thanh toán hay đánh giá.

`orders` chứa **mọi** đơn kèm cột trạng thái. Việc chỉ lấy đơn đã giao là chuyện
của truy vấn KPI, không phải của bước dựng bảng.

Bốn cột `payment_approval`, `seller_handling`, `carrier_transit` và `is_late` là
cột sinh tự động (`GENERATED ALWAYS AS ... STORED`), không nạp vào được. Riêng
`is_late` là chỗ quan trọng nhất: `Late Order` định nghĩa bằng so sánh ở mức
**ngày lịch**, nên giao đúng ngày cam kết là đúng hạn bất kể mấy giờ. Kiểu `DATE`
của `estimated_delivery_date` một mình không đủ để chặn lỗi — so thẳng dấu thời
gian với nó, Postgres vẫn nâng `DATE` lên nửa đêm và cho ra 7.826 đơn trễ thay vì
6.534. Cột sinh đóng cứng phép so đúng vào lược đồ; truy vấn KPI đọc cờ chứ không
tự tính lại.

Vì cùng lý do đó, **không được thêm `timezone=True`** vào các cột dấu thời gian
trong `app/models/derived.py`: ép kiểu `timestamptz → date` không phải IMMUTABLE,
migration sẽ hỏng.

Lưu ý khi viết truy vấn: `is_late` là `NULL` chứ không phải `false` với đơn chưa
giao, nên cả `WHERE is_late` lẫn `WHERE NOT is_late` đều loại các đơn đó ra. Dùng
`IS TRUE` / `IS NOT TRUE` nếu cần nói rõ ý định.

`order_value` là tổng `price + freight_value` của các dòng sản phẩm, tính sẵn lúc
dựng bảng; 775 đơn không có sản phẩm nào để `NULL`. Đây không phải số tiền khách
thanh toán: 303 đơn lệch tổng thanh toán hơn 1 xu, và như vậy là đúng (so bằng
tuyệt đối ra 576, vì trả góp làm tròn từng kỳ). Bộ số vàng tính thẳng từ CSV nằm
ở `tests/test_order_value_golden.py`.

Tìm mã đơn dùng chỉ mục biểu thức `lower(order_id) text_pattern_ops`. Cơ sở dữ
liệu chạy collation `en_US.utf8`, mà btree thường theo collation đó — kể cả khoá
chính — không phục vụ được `LIKE 'abc%'`; `ILIKE` thì không đi qua chỉ mục kiểu
này. Truy vấn tiền tố mã đơn vì thế phải viết đúng dạng
`lower(order_id) LIKE '...%'`.

## Tập đơn biên dùng cho test

`tests/fixtures/edge_case_orders.json` ghim 312 mã đơn chọn có chủ đích, phủ bốn
trường hợp dễ tính sai: giao đúng ngày cam kết, thiếu mốc trung gian, nhiều người
bán, không có đánh giá. Nhóm thiếu mốc trung gian phải chọn có chủ đích vì toàn bộ
dữ liệu chỉ có 15 đơn như vậy trong 99.441 đơn.

Dựng lại tệp này bằng các truy vấn sau — `ORDER BY order_id LIMIT n` cho kết quả
cố định qua mọi lần chạy:

Chạy sau `build_derived_data` — cả bốn đọc lớp dẫn xuất, vì đó là nơi duy nhất còn dữ
liệu trong cơ sở dữ liệu:

```sql
-- delivered_on_estimated_date
SELECT order_id FROM orders
 WHERE order_status = 'delivered' AND delivered_to_customer_at IS NOT NULL
   AND delivered_to_customer_at::date = estimated_delivery_date
 ORDER BY order_id LIMIT 100;
-- missing_intermediate_milestone (lấy hết, tổng thể chỉ có 15 đơn)
SELECT order_id FROM orders
 WHERE order_status = 'delivered' AND delivered_to_customer_at IS NOT NULL
   AND (payment_approved_at IS NULL OR handed_to_carrier_at IS NULL)
 ORDER BY order_id;
-- multi_seller — order_sellers đã DISTINCT sẵn, nên count(*) ở đây chính là số người
-- bán phân biệt của đơn.
SELECT order_id FROM order_sellers GROUP BY order_id
 HAVING count(*) > 1 ORDER BY order_id LIMIT 100;
-- no_review — hỏi bảng đánh giá chứ không hỏi worst_review_score IS NULL: cột ấy rỗng
-- cả khi đơn có đánh giá mà thiếu điểm.
SELECT o.order_id FROM orders o
 WHERE NOT EXISTS (SELECT 1 FROM order_reviews r WHERE r.order_id = o.order_id)
 ORDER BY o.order_id LIMIT 100;
```

`tests/fixtures/edge_case_filters.json` là tệp anh em, ghim những thứ *không phải* danh
sách mã đơn: người bán dưới ngưỡng mẫu nhỏ, người bán nhiều đơn nhất, một kỳ báo cáo mà
cả hai kỳ đối chiếu đều rỗng, và sáu đơn mẫu mà test chi tiết đơn cần tới. Để riêng vì
`edge_case_orders.json` được đọc theo kiểu "mọi nhóm đều là danh sách mã đơn", trộn vào
sẽ làm hỏng cách đọc đó.

Sáu đơn mẫu được ghim thay vì tìm bằng truy vấn lúc chạy test: trước đây các truy vấn ấy
quét bảng thô, mà bảng thô thì không còn. Chúng ghim **mã đơn và chỉ mã đơn** — giá trị
kỳ vọng thì test luôn đọc từ CSV. Ghim cả nhãn danh mục hay điểm đánh giá vào đây là lấy
lại kết quả của chính bước dựng làm thước đo cho bước dựng, đúng cái vòng mà việc chuyển
sang CSV sinh ra để cắt.

```sql
-- small_sample_sellers (2.343 người bán như vậy; lấy 20 mã đầu cho cố định)
SELECT os.seller_id FROM order_sellers os
  JOIN orders o ON o.order_id = os.order_id
 WHERE o.order_status = 'delivered' AND o.delivered_to_customer_at IS NOT NULL
 GROUP BY os.seller_id HAVING count(*) < 30
 ORDER BY os.seller_id LIMIT 20;
-- busiest_seller
SELECT os.seller_id FROM order_sellers os
  JOIN orders o ON o.order_id = os.order_id
 WHERE o.order_status = 'delivered' AND o.delivered_to_customer_at IS NOT NULL
 GROUP BY os.seller_id ORDER BY count(*) DESC LIMIT 1;
-- empty_comparison_period: 10/2016 là tháng đầu tiên có đơn giao (205 đơn), nên kỳ
-- liền trước (9/2016) và cùng kỳ năm trước (10/2015) đều không có đơn nào.
SELECT date_trunc('month', delivered_to_customer_at) AS month, count(*)
  FROM orders WHERE order_status = 'delivered'
   AND delivered_to_customer_at IS NOT NULL
 GROUP BY 1 ORDER BY 1 LIMIT 3;
-- translated_category_order: đơn đầu tiên có dòng hàng thuộc danh mục đã dịch
SELECT i.order_id FROM order_items i
  JOIN product_categories c ON c.product_category_name = i.product_category_name
 ORDER BY i.order_id LIMIT 1;
-- untranslated_category_order: đơn đầu tiên có danh mục nhưng chưa có bản dịch
SELECT i.order_id FROM order_items i
 WHERE i.product_category_name IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM product_categories c
                    WHERE c.product_category_name = i.product_category_name)
 ORDER BY i.order_id LIMIT 1;
-- uncategorized_order: đơn đầu tiên có dòng hàng không thuộc danh mục nào
SELECT order_id FROM order_items WHERE product_category_name IS NULL
 ORDER BY order_id LIMIT 1;
-- multi_payment_order: đơn đầu tiên trả làm nhiều kỳ
SELECT order_id FROM order_payments GROUP BY order_id
 HAVING count(*) > 1 ORDER BY order_id LIMIT 1;
-- commented_review_order: đơn đầu tiên có đánh giá kèm nội dung
SELECT order_id FROM order_reviews WHERE comment_message IS NOT NULL
 ORDER BY order_id LIMIT 1;
-- leading_zero_zip_order: đơn đầu tiên có mã bưu chính bắt đầu bằng số 0
SELECT order_id FROM orders WHERE customer_zip_code_prefix LIKE '0%'
 ORDER BY order_id LIMIT 1;
```

## Ảnh chụp chi tiết đơn dùng cho test

`tests/fixtures/order_detail_snapshot.json` giữ phản hồi đầy đủ của `GET /orders/{order_id}`
cho cả 312 đơn trong `edge_case_orders.json`, một đơn một dòng. Nó được chụp **trước** khi
trang chi tiết chuyển từ bảng thô sang lớp dẫn xuất (migration `0009_derived_order_lines`), và
`test_order_detail_snapshot.py` khẳng định phản hồi sau khi chuyển giống hệt từng byte.

Kiểu lỗi mà nó sinh ra để bắt là sai lệch âm thầm: đổi nhầm một phép nối hay một tên cột thì
trang vẫn mở bình thường, chỉ khác vài trường ở vài đơn, và không bài test nào khác đỏ. Ảnh
chụp đi qua endpoint chứ không qua hàm dịch vụ, nên nó bắt được cả sai lệch ở tầng Pydantic —
số thập phân dựng thành chuỗi, định dạng dấu thời gian.

**Không chụp lại tệp này để làm một bài test đỏ thành xanh.** Đỏ nghĩa là phản hồi đã đổi, và
việc phải làm là tìm ra vì sao. Chỉ dựng lại khi phản hồi được cố ý đổi, và khi đó ảnh chụp mới
phải nằm trong cùng commit với thay đổi gây ra nó.

Dựng lại bằng kịch bản sau, chạy từ gốc repo sau khi `uv run pytest` đã tạo và nạp cơ sở dữ
liệu test:

```python
import asyncio, json
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.deps import get_db
from app.core.config import settings
from app.core.security import create_access_token
from app.main import app

FIXTURES = Path("backend/tests/fixtures")


async def main() -> None:
    edge = json.loads((FIXTURES / "edge_case_orders.json").read_text("utf-8"))
    engine = create_async_engine(settings.TEST_DATABASE_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    snapshot = {}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.headers["Authorization"] = f"Bearer {create_access_token(1, 'operations_staff', [])}"
        for order_id in sorted({o for g in edge.values() for o in g}):
            response = await client.get(f"/orders/{order_id}")
            assert response.status_code == 200, response.text
            snapshot[order_id] = response.json()
    app.dependency_overrides.clear()
    await engine.dispose()

    body = ",\n".join(
        f"  {json.dumps(k)}: {json.dumps(v, ensure_ascii=False, sort_keys=True)}"
        for k, v in snapshot.items()
    )
    (FIXTURES / "order_detail_snapshot.json").write_text("{\n" + body + "\n}\n", "utf-8")


asyncio.run(main())
```

## Kiểm thử

```bash
uv run pytest
```

Chạy từ gốc repo, không phải từ `backend/`: cấu hình pytest nằm ở
`pyproject.toml` gốc, đứng ở `backend/` thì pytest lấy nhầm tệp cấu hình và bỏ
qua `asyncio_mode`, làm mọi test bất đồng bộ hỏng.

Test dùng cơ sở dữ liệu riêng tên `shipguard_test`, được tạo tự động ở lần chạy
đầu và không chạm vào cơ sở dữ liệu phát triển. Bộ test tự khẳng định hai URL
khác nhau trước khi chạy migration.

Các bài test của mô hình rủi ro huấn luyện thật, nhưng trên một phần dữ liệu
(`RISK_SAMPLE_STEP` trong `tests/conftest.py`) để chạy trong khoảng nửa phút thay vì
năm phút. Chúng chỉ kiểm hình dạng báo cáo và tính lặp lại, **không** kiểm chất lượng
dự đoán: F1 trên một phần nhỏ dữ liệu không nói lên điều gì. Chất lượng được kiểm
bằng một lần chạy đầy đủ, xem mục dưới.

## Huấn luyện mô hình rủi ro

```bash
uv run python -m app.scripts.train_risk_model
```

Mất khoảng năm phút trên toàn bộ dữ liệu Olist. Lệnh đọc thẳng tệp CSV trong
`datasets/raw/` và không cần Postgres (ADR-0010).

Mỗi chặng trong ba chặng được dự đoán dưới dạng **phân phối** thời gian chứ không
phải một con số, rồi `Late Probability` suy ra bằng mô phỏng Monte Carlo 2.000 mẫu
(ADR-0008). Ba thuật toán ứng viên cùng được huấn luyện — XGBoost hồi quy phân vị,
XGBoost log-normal AFT, Scikit-learn HistGradientBoosting hồi quy phân vị — và bộ có
F1 cao nhất ở mốc đặt hàng trên tập kiểm tra được giữ lại.

Bốn tệp sinh ra trong `RISK_MODEL_DIR`:

| Tệp | Nội dung |
| --- | --- |
| `risk_model.joblib` | Bộ mô hình được chọn, bộ mã hoá, trung vị lịch sử ba chặng, bảng lịch sử người bán, bảng toạ độ theo mã bưu chính |
| `evaluation_report.json` | Toàn bộ báo cáo đánh giá — nguồn sự thật |
| `evaluation_metrics.csv` | Chín dòng (3 thuật toán × 3 mốc dự đoán), mở bằng Excel |
| `test_predictions.csv` | Xác suất trễ và kết quả thật trên tập kiểm tra, để notebook phân tích dùng lại |

**Sau khi huấn luyện, chép "Ngưỡng đề xuất" mà lệnh in ra vào `RISK_THRESHOLD` trong
`.env`.** Lệnh cố ý không tự ghi vào cấu hình: ngưỡng là quyết định vận hành, và đổi
nó làm mọi đơn được đánh giá từ đó trở đi đổi mức rủi ro.

Ngưỡng hợp lý nằm quanh 0,15–0,25. Nếu báo cáo đề xuất một con số xấp xỉ 0,5 thì có
gì đó sai: tỷ lệ trễ nền chỉ 6,8%, nên ở mốc đặt hàng gần như không đơn nào đạt xác
suất 0,5.

Đọc F1 trong báo cáo cần nhớ hai điều. Thứ nhất, dữ liệu chia **theo thời điểm đặt
hàng** chứ không trộn ngẫu nhiên, và tỷ lệ trễ tụt từ 7,8% ở tập huấn luyện xuống
4,3% ở tập kiểm tra — trộn ngẫu nhiên cho điểm đẹp hơn nhiều nhưng là điểm giả, vì
mô hình thật luôn dự đoán cho đơn đặt sau mọi đơn nó đã học. Thứ hai, mỗi ô có hai
con số: `best_f1` là điểm tốt nhất phép quét tìm được trên chính tập kiểm tra (tiêu
chí chọn thuật toán theo ADR-0008, nhưng lạc quan vì ngưỡng được chọn khi đã nhìn
đáp án), còn `at_selected_threshold` là điểm khi dùng ngưỡng lấy từ tập kiểm định —
đây mới là con số sẽ nhận được khi triển khai.

**Kết quả lần chạy đầy đủ gần nhất:** `sklearn_quantile` được chọn, ngưỡng đề xuất
0,18, F1 ở mốc đặt hàng **0,20 — chưa đạt** mục tiêu 0,30 của README. Mô hình vẫn
được xuất và báo cáo ghi rõ là chưa đạt, đúng như ADR-0008 đã định. F1 tăng dần theo
mốc (0,20 → 0,20 → 0,29), đúng kỳ vọng: càng về sau càng nhiều chặng đã có số thật.

Phân tích sâu hơn — đặc trưng nào dẫn dắt từng chặng, xác suất có được hiệu chỉnh
không, mô hình sai ở những đơn nào:

```bash
uv run jupyter lab backend/notebooks/risk_model_analysis.ipynb
```

Notebook chỉ đọc kết quả, không huấn luyện lại. Lưu nó với ô kết quả đã xoá sạch:
số liệu đã nằm ở JSON và CSV rồi.

### Tệp mô hình

`risk_model.joblib` là đối tượng Python tuần tự hoá bằng giao thức `pickle`; đuôi
`.joblib` chỉ là quy ước cho biết joblib đã ghi nó, không phải một định dạng mô hình
riêng. Hai hệ quả:

- **Nạp tệp là chạy mã tuỳ ý.** Chỉ nạp tệp do chính lệnh huấn luyện sinh ra; không
  bao giờ nhận tệp mô hình từ bên ngoài qua API.
- **Tệp gắn chặt với phiên bản thư viện.** Mô hình ghi bằng một bản XGBoost hay
  Scikit-learn có thể không nạp được bằng bản khác. `uv.lock` đã ghim phiên bản; khi
  lệch thì huấn luyện lại, và `model_version` trong báo cáo cho biết tệp hiện có đến
  từ lần chạy nào. Lỗi kiểu này **không** phải `FileNotFoundError`, nên
  `get_predictor` bắt lỗi rộng và trả 503 chứ không phải 500.

Tệp mô hình và báo cáo không vào git — xem `/models/` và `*.joblib` trong
`.gitignore` ở gốc repo.

## Cấu hình

Mọi giá trị đọc từ `.env` ở gốc repo — cùng chỗ với `docker-compose.yml`, và cả
hai cùng đọc một tệp. Không có giá trị mặc định trong mã: thiếu biến là hỏng
ngay lúc khởi động kèm thông báo nêu tên biến thiếu.

| Biến | Dùng ở đâu |
| --- | --- |
| `PROJECT_NAME` | Tiêu đề của API |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Docker Compose dựng container |
| `DATABASE_URL` | Ứng dụng và Alembic |
| `TEST_DATABASE_URL` | Chỉ bộ test |
| `CORS_ALLOWED_ORIGINS` | Origin của frontend, phân tách bằng dấu phẩy. Trình duyệt gọi thẳng backend nên thiếu origin đúng là màn hình trắng mà phía máy chủ không báo lỗi gì — xem `docs/adr/0006-goi-thang-backend-kem-xac-thuc-jwt.md` |
| `JWT_SECRET_KEY` | Khóa ký access token. Đổi khóa thì mọi access token đang có hết hiệu lực ngay |
| `SUPER_ADMIN_EMAIL`, `SUPER_ADMIN_PASSWORD`, `SUPER_ADMIN_NAME` | Chỉ đọc ở lần khởi động đầu, khi chưa có Super Admin — xem [Đăng nhập](#đăng-nhập) |
| `RISK_MODEL_DIR` | Nơi lệnh huấn luyện ghi tệp mô hình và báo cáo; backend đọc lại từ đây. Chưa có tệp thì backend **vẫn khởi động bình thường**, chỉ thao tác cần dự đoán mới báo lỗi |
| `RISK_THRESHOLD` | Mức `Late Probability` để một đơn là `High Risk`, lớn hơn 0 và nhỏ hơn 1. Lấy con số "Ngưỡng đề xuất" trong báo cáo đánh giá — xem [Huấn luyện mô hình rủi ro](#huấn-luyện-mô-hình-rủi-ro) |

Ghi lược đồ `postgresql://` thuần — mã tự thêm trình điều khiển `+asyncpg`.

Riêng `RISK_MODEL_DIR` là ngoại lệ có chủ đích với quy tắc khởi động ở trên. Thiếu
tài khoản quản trị thì máy chủ dừng hẳn, vì backend không có lối vào nào còn tệ hơn
backend không chạy. Thiếu tệp mô hình thì không: bảng điều khiển và tra cứu đơn phải
dùng được ngay cả khi chưa huấn luyện lần nào. Biến cấu hình vẫn bắt buộc — thiếu nó
là hỏng lúc nạp cấu hình — nhưng thư mục nó trỏ tới thì được phép rỗng.

## Migration

```bash
uv run alembic -c backend/alembic.ini revision -m "mô tả thay đổi"
uv run alembic -c backend/alembic.ini upgrade head
uv run alembic -c backend/alembic.ini downgrade -1
```
