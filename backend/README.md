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
                   /users, orders.py: /orders, /orders/export, /customer-states)
    services/      logic nghiệp vụ; route chỉ đọc tham số và gọi vào đây
      auth.py      đăng nhập, cấp và xoay vòng refresh token
      users.py     tạo User, Super Admin, quản trị User (khóa, đổi vai trò, đặt
                   lại mật khẩu), tự đổi mật khẩu
      orders.py    danh sách đơn: tìm tiền tố mã đơn, sắp xếp, phân trang
      queries.py   mảnh truy vấn dùng chung: vị ngữ DELIVERED, like_prefix
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
uv run python -m app.scripts.load_raw_data
uv run python -m app.scripts.build_derived_data
uv run fastapi dev backend/app/main.py
```

`--wait` chặn cho tới khi Postgres nhận kết nối. Thiếu nó thì lệnh migration
ngay sau đó có thể chạy trong lúc cơ sở dữ liệu còn đang khởi tạo và bị từ chối.

Lệnh `load_raw_data` nạp 9 tệp CSV Olist trong `datasets/raw/` vào các bảng
`raw_*`, nguyên trạng không lọc hay biến đổi. Chạy lại an toàn: mỗi bảng được
xoá sạch (`TRUNCATE`) rồi nạp lại trong cùng một transaction trước khi nạp,
nên không bao giờ bị nhân đôi dữ liệu.

Lệnh `build_derived_data` dựng hai bảng dẫn xuất từ các bảng thô, cũng chạy lại
an toàn theo cùng cách. Xem mục [Hai tầng bảng](#hai-tầng-bảng) bên dưới.

Kiểm tra: `curl http://localhost:8000/health` trả về
`{"status":"ok","database":"connected"}`. Nếu cơ sở dữ liệu không kết nối được,
endpoint trả mã 503 kèm `{"status":"degraded","database":"disconnected"}`.

Kiểm tra tiếp: `curl http://localhost:8000/dashboard -H 'Authorization: Bearer
<access_token>'` (lấy token ở mục [Đăng nhập](#đăng-nhập)) trả về kỳ báo cáo mặc
định kèm khối KPI; thiếu token thì 401. Truyền `?start_date=...&end_date=...` để chọn kỳ khác — hai tham
số phải đi cùng nhau, thiếu một bên thì endpoint trả mã 422.

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
| `reviews` | `review_score`, `comment_title`, `comment_message`, `created_at` |

Danh sách rỗng nghĩa là đơn không có phần đó (775 đơn không có sản phẩm, nhiều đơn
không có đánh giá), không phải lỗi. Sản phẩm, thanh toán và đánh giá tra theo chỉ mục
`order_id` trên ba bảng thô tương ứng (migration `0007_order_detail`).

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

## Hai tầng bảng

Tiền tố phân biệt hai tầng: `raw_*` là tầng thô phản chiếu nguyên trạng tệp CSV,
tên trần là tầng dẫn xuất.

| Bảng | Nội dung |
| --- | --- |
| `raw_*` | 9 bảng thô, nguyên trạng, không lọc không biến đổi |
| `orders` | Một dòng mỗi đơn — bốn mốc thời gian, ba khoảng thời gian, cờ trễ, bang, thành phố và mã bưu chính của khách, điểm đánh giá thấp nhất, trạng thái đơn, giá trị đơn |
| `order_sellers` | Bảng nối đơn với người bán, dùng khi lọc theo người bán |

Migration nào thêm cột vào bảng dẫn xuất (như `0007_order_detail` thêm thành phố và
mã bưu chính) thì sau `alembic upgrade head` phải chạy lại `build_derived_data`. Chưa
chạy thì cột mới để trống: trang chi tiết đơn vẫn mở được nhưng thành phố và mã bưu
chính hiện là chưa có. `customer_zip_code_prefix` là chuỗi được đệm lại đủ 5 chữ số:
cột thô là số nguyên nên `01310` đã nạp thành `1310`.

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

```sql
-- delivered_on_estimated_date
SELECT order_id FROM raw_orders
 WHERE order_status = 'delivered' AND order_delivered_customer_date IS NOT NULL
   AND order_delivered_customer_date::date = order_estimated_delivery_date::date
 ORDER BY order_id LIMIT 100;
-- missing_intermediate_milestone (lấy hết, tổng thể chỉ có 15 đơn)
SELECT order_id FROM raw_orders
 WHERE order_status = 'delivered' AND order_delivered_customer_date IS NOT NULL
   AND (order_approved_at IS NULL OR order_delivered_carrier_date IS NULL)
 ORDER BY order_id;
-- multi_seller
SELECT order_id FROM raw_order_items GROUP BY order_id
 HAVING count(DISTINCT seller_id) > 1 ORDER BY order_id LIMIT 100;
-- no_review
SELECT o.order_id FROM raw_orders o
 WHERE NOT EXISTS (SELECT 1 FROM raw_order_reviews r WHERE r.order_id = o.order_id)
 ORDER BY o.order_id LIMIT 100;
```

`tests/fixtures/edge_case_filters.json` là tệp anh em, ghim những thứ *không phải* mã
đơn: người bán dưới ngưỡng mẫu nhỏ, người bán nhiều đơn nhất, và một kỳ báo cáo mà cả
hai kỳ đối chiếu đều rỗng. Để riêng vì `edge_case_orders.json` được đọc theo kiểu
"mọi nhóm đều là danh sách mã đơn", trộn vào sẽ làm hỏng cách đọc đó.

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

Ghi lược đồ `postgresql://` thuần — mã tự thêm trình điều khiển `+asyncpg`.

## Migration

```bash
uv run alembic -c backend/alembic.ini revision -m "mô tả thay đổi"
uv run alembic -c backend/alembic.ini upgrade head
uv run alembic -c backend/alembic.ini downgrade -1
```
